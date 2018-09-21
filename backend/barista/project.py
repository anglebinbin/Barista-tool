import copy
import json
import os
import re
import shutil
import uuid
from datetime import datetime

from PyQt5.Qt import QObject
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QMessageBox
from backend.barista.constraints.permanent.project import ensureProjectDataConstraints
from backend.barista.session.session import Session
from backend.barista.session.client_session import ClientSession
from backend.barista.session.session import State
from backend.barista.session.session_utils import Paths

from backend.networking.protocol import Protocol
from backend.networking.net_util import sendMsgToHost

import backend.caffe.dict_helper as helper
import backend.caffe.loader as loader
import backend.caffe.proto_info as info
import backend.caffe.saver as saver
import backend.barista.caffe_versions as caffeVersions
from backend.barista.session.session_pool import SessionPool
from backend.barista.utils.logger import Log
from backend.barista.utils.logger import LogCaller
from backend.caffe.proto_info import CaffeMetaInformation

def dirIsProject(dirname):
    """ Checks if the dir with the name dirname contains a projectfile """
    if os.path.exists(_baristaProjectFile(dirname)):
        return True
    return False

def _baristaProjectFile(directory):
    """ Returns the filename of the config-json file in the given directory """
    return os.path.join(directory,  "barista_project.json")


class Project(QObject, LogCaller):
    """ This class is a abstraction for a caffe project.

    A project has a directory which contains the following dependencies:
    - a settings file with general settings for the project, e.g. the caffe
      version
    - a layout file with information about the layout of the net in the prototxt_editor
    - a caffe solver file
    - two versions of the caffe net file
    -> original one: a copy of the net state just as it would appear by using
        the "export net" feature
    -> internal one: a slightly modified version of the original file. Relative
        paths are changed to allow executing caffe inside of a session folder,
        although the user defines paths relative to the project folder.
    - a log directory
    - a directory for training sessions containing log files and snapshots

    A project directory has the following structure:

    /project_name
     |---barista_project.json
     |---/logs
     |---/sessions
     |    |---/20161118_153000_1
     |    |    |---solver.prototxt (see FILE_NAME_SOLVER)
     |    |    |---net-original.prototxt (see FILE_NAME_NET_ORIGINAL)
     |    |    |---net-internal.prototxt (see FILE_NAME_NET_INTERNAL)
     |    |    |---/logs
     |    |    |    |---project_name_1.1.log
     |    |    |    |---project_name_1.2.log
     |    |    |---/snapshots
     |    |    |    |---project_name_iter_1000.caffemodel
     |    |    |    |---project_name_iter_1000.solverstate
     |    |---/20161118_161000_2
     |    |    |---solver-internal.prototxt (see FILE_NAME_SOLVER)
     |    |    |---net-original.prototxt (see FILE_NAME_NET_ORIGINAL)
     |    |    |---net-internal.prototxt (see FILE_NAME_NET_INTERNAL)
     |    |    |---/logs
     |    |    |    |---project_name_2.1.log
     |    |    |---/snapshots
     ...
    """



    # signals
    newSession = pyqtSignal(object)
    # The deleteSession signal is called from within backend/barista/session/session.py
    # in the Session.delete() function.
    deleteSession = pyqtSignal(object)
    resetSession = pyqtSignal(object)
    activeSessionChanged = pyqtSignal(object)

    def __init__(self, directory):
        super(Project, self).__init__()
        # Make sure needed directoies exists
        self.caffeVersion = caffeVersions.getDefaultVersion().getName()
        self.projectRootDir = directory
        self.projectId = None
        self.current_sid = None
        self.callerId = None
        self.__activeSID = None
        self.__sessions = {}
        self.__inputManagerState = dict()
        self.__transform = None

        self.sessions = os.path.join(self.projectRootDir, 'sessions')
        # self.logs = os.path.join(self.projectRootDir, 'logs')
        self.__ensureDirectory(self.sessions)
        # self.__ensureDirectory(self.logs)
        self.settings = self.__loadDefaultSettings()
        self.loadProject(True)

    def projectConfigFileName(self):
        """ Returns the filename of the config-json file """
        return _baristaProjectFile(self.projectRootDir)

    def loadProject(self, set_settings=False):
        """ Loads the settings of the project. Returns a state-dictionary for
            the NetworkManager.
            State looks like: {
                "projectid": "xyz...",
                "caffeVersion": {...},
                "inputdb": { .. },
                "network": { .. },
                "solver": {...},
                "selection": [],
                "position": {}
            }
        """
        filename = self.projectConfigFileName()
        projectData = None
        if not os.path.exists(filename):
            self.__loadDefaultSettings()
            self.projectId = str(uuid.uuid4())
            sessionID = self.createSession(state_dictionary=None)
            self.setActiveSID(sessionID)
        else:
            with open(filename, "r") as file:
                res = json.load(file)
            if set_settings and ("environment" in res):
                self.settings = res["environment"]

            if "inputdb" in res:
                self.__inputManagerState = res["inputdb"]

            if "caffeVersion" in res:
                self.caffeVersion = res["caffeVersion"]
                caffeVersions.setDefaultVersion(self.caffeVersion)

            if "projectdata" in res:  # this is for backward compatibility, only
                # Fill missing type-instances
                allLayers = info.CaffeMetaInformation().availableLayerTypes()
                layers = res["projectdata"]["network"]["layers"]
                for id in layers:
                    typename = layers[id]["parameters"]["type"]
                    layers[id]["type"] = allLayers[typename]

                projectData = res["projectdata"]

            if "transform" in res:
                self.__transform = res["transform"]

            if "projectid" in res:
                self.projectId = res["projectid"]
            else:
                self.projectId = str(uuid.uuid4())  # backwards compatibility

            self.loadSessions()

            if len(self.__sessions) == 0:
                Log.error("Could not find a valid Session, creating new empty Session. Maybe the project "
                          "contains only remote Sessions?", self.getCallerId())
                sessionID = self.createSession()

            #check which session was last active, if this is not available, take the last Session in SID order, if no
            # valid sessions are available, create a new empty session and set this active
            if "activeSession" in res:
                self.setActiveSID(res["activeSession"])
            elif len(self.getValidSIDs())>0:
                self.setActiveSID(self.getValidSIDs()[-1])
            else:  # this branch should be reached only if an old projekt format is opened, where no sessions are stored
                sessionID = self.createSession(state_dictionary=projectData)
                self.setActiveSID(sessionID)
                if projectData:
                    self.setActiveSessionStateDict(projectData)

            if self.getActiveSession().hasStateDict():
                projectData = self.getActiveSession().state_dictionary
            else:
                if projectData:
                    # this branch should be reached only if an old projekt format is opened,
                    # where sessions do not have their own state dictionary
                    self.setActiveSessionStateDict(projectData)

        return projectData, self.__inputManagerState, self.__transform

    def getInputManagerState(self):
        return self.__inputManagerState

    def getViewTransform(self):
        return self.__transform

    def saveProject(self, networkManagerState=None, inputManagerState=None, transform=None):
        """ Saves the settings of this project using the given State of the
            NetworkManager.abs
            State should looks like: {
                "projectid": "xyz...",
                "network": { .. },
                "caffeVersion": {...},
                "inputdb": { .. },
                "solver": {...},
                "selection": [],
                "position": {}
            }
        """
        if inputManagerState:
            self.__inputManagerState = copy.deepcopy(inputManagerState)
        if transform:
            self.__transform = copy.deepcopy(transform)

        for session in self.__sessions.itervalues():
            session.save()

        # Serialize
        tosave = {
            "projectid": self.projectId,
            "caffeVersion": self.caffeVersion,
            "activeSession": self.getActiveSID(),
            "inputdb": self.__inputManagerState,
            "environment": self.settings,
            "transform": [self.__transform.m11(), self.__transform.m12(),
                          self.__transform.m21(), self.__transform.m22(),
                          self.__transform.dx(), self.__transform.dy()]
        }
        with open(self.projectConfigFileName(), "w") as file:
            json.dump(tosave, file, sort_keys=True, indent=4)



    def __loadDefaultSettings(self):
        """ Load settings with sensitive defaults.
        """
        self.settings = {
            'plotter': {
                'logFiles': {},
                'checkBoxes': {}
            }
        }

    def changeProjectCaffeVersion(self, version):
        """change the project caffe version"""
        self.caffeVersion = version

    def getCaffeVersion(self):
        """returns the caffe version name, saved in the project file or, if this isn't set, from Barista default settings"""
        return self.caffeVersion

    def deletePlotterSettings(self, logId):
        """deletes the plotter settings for a given log, e.g. if a session was reset"""
        try:
            #check if settings for given logId exist:
            if "logId" in self.settings["plotter"]["checkBoxes"]:
                return
        except Exception:
            return
        res = None
        #check if a settings json exists:
        if os.path.exists(self.projectConfigFileName()):
            with open(self.projectConfigFileName(), "r") as file:
                res = json.load(file)

        #determine how much of the json is already created and write accordingly:
        if res is None:
            res ={"environment": {"plotter": {"checkBoxes": {}}}}
        elif "environment" not in res:
            res["environment"] = {"plotter": {"checkBoxes": {}}}
        elif "plotter" not in res["environment"]:
            res["environment"]["plotter"] = {"checkBoxes": {}}
        elif logId in res["environment"]["plotter"]["checkBoxes"]:
            res["environment"]["plotter"]["checkBoxes"].pop(logId)
        #save to file
        with open(self.projectConfigFileName(), "w") as file:
            json.dump(res, file, sort_keys=True, indent=4)


    def getCallerId(self):
        """ Return the unique caller id for this project
        """
        if self.callerId is None:
            self.callerId = Log.getCallerId(self.getProjectName())
        return self.callerId

    def getProjectName(self):
        """ Return the name of the project.
        """
        return os.path.basename(os.path.normpath(self.projectRootDir))

    def getProjectDirectory(self):
        """ Return the project directory.
        """
        return self.projectRootDir

    def getProjectId(self):
        """ Return the ProjectId"""
        return self.projectId

    def buildSolverPrototxt(self):
        """ Load the current solver dictionary and return the corresponding
        message object.

        :return: A solver message object.
        """
        res, inp, _ = self.loadProject()
        solver = saver.saveSolver(res["solver"])
        return solver

    def buildNetPrototxt(self, internalVersion=False):
        """ Load the current net dictionary and return the corresponding
        message object.

        :param internalVersion: Iff true, the loaded net will be modified to
        the internal version.
        :return: A net message object.
        """

        currentState = self.getActiveSession().state_dictionary
        netDictionary = None
        if currentState:
            netDictionary = currentState["network"]
        else:
            res, _, _= self.loadProject()
            netDictionary = res["network"]

        if internalVersion:
            netDictionary = self._modifyNetDictionaryToInternalVersion(copy.deepcopy(netDictionary))

        solver = saver.saveNet(netDictionary)
        return solver

    def _modifyH5TxtFile(self, dir, state=None):
        net = None
        if state:
            net = state["network"]
        else:
            session = self.getActiveSession()
            if session:
                state_dict = session.state_dictionary
                if state_dict:
                    if "network" in state_dict:
                        net = state_dict["network"]

        if net:
            h = helper.DictHelper(net)
            for layerId, layer in net.get("layers", {}).iteritems():

                paramKey = "hdf5_data_param.source"

                if h.layerParameterIsSet(layerId, paramKey):
                    paramValue = h.layerParameter(layerId, paramKey)

                    if paramValue is not None and not os.path.isabs(paramValue):
                        newFilename = str(layerId) + ".txt"
                        newFilepath = os.path.join(dir, newFilename)
                        oldPath = os.path.join(dir, os.path.join(os.pardir,
                                               os.path.join(os.pardir, paramValue)))
                        if os.path.exists(oldPath):
                            with open(newFilepath, "w") as f:
                                lines = [line.rstrip('\n') for line in open(oldPath)]
                                for line in lines:
                                    if line is not "":
                                        if line[:1] == '.':
                                            line = os.path.join(os.pardir, os.path.join(os.pardir, line))
                                        f.write("\n" + line)
                        else:
                            Log.error('Failed to copy hdf5txt file. File does not exists: ' + oldPath, self.getCallerId())

    def getActiveSession(self):
        sid = self.getActiveSID()
        if sid:
            return self.getSession(sid)
        else:
            return None

    def getActiveSID(self):
        if self.__activeSID:
            if len(self.__sessions) > 0:
                if self.__activeSID not in self.__sessions:
                    Log.log("The Active Session is no longer available. The Project seems to be broken. The active Session is set to the highest ID available.", self.callerId)
                    self.setActiveSID(self.__sessions.keys()[-1])
                    Log.log("Active Session set to " + str(self.__activeSID), self.callerId)
        return self.__activeSID

    def getSession(self, SID):
        if SID in self.getValidSIDs():
            return self.__sessions[SID]
        else:
            Log.log("Session " + str(SID) + " could not be loaded. Valid IDs are: " +
                    ", ".join([str(i) for i in self.getValidSIDs()]), self.getCallerId())
            return None

    def setActiveSessionStateDict(self, state):
        self.__sessions[self.__activeSID].setStateDict(stateDict=state)

    def setActiveSID(self, sid):
        validSIDs = self.getValidSIDs()
        if sid in validSIDs:
            self.__activeSID = sid
            self.activeSessionChanged.emit(sid)
        else:
            Log.error("Could not set active session to " + str(sid) + " valid Session-IDs are: "+
                      ", ".join([str(s) for s in validSIDs]), self.getCallerId())
            if not self.__activeSID:
                self.__activeSID = validSIDs[-1] if len(validSIDs) > 0 else None
                Log.log("Active session set to " + str(self.__activeSID), self.getCallerId())

    def getValidSIDs(self):
        validSIDs = [session.getSessionId() for session in self.__sessions.itervalues()]
        return validSIDs

    def getSettings(self):
        """ Return the settings for this project.
        """
        return self.settings

    def getSnapshots(self):
        """ Return the directory for snapshots.
        """
        return self.snapshots

    def getLogs(self):
        """ Return the directory for log files.
        """
        return self.logs

    def getSessions(self):
        """ Return a dictionary of finished and running caffe sessions, keyed
        by session id.
        """
        return self.__sessions

    def getSessionsDirectory(self):
        """ Return the directory which contains the sessions.
        """
        return self.sessions

    def createSession(self, state_dictionary=None):
        """ Return a new session instance with a new directory
        """
        sid = self.getNextSessionId()
        session = Session(self, sid=sid, parse_old=False, state_dictionary=state_dictionary)
        self.__sessions[sid] = session

        # copy HDF5TXT files
        # TODO: This should probably be moved to the Session?
        self._modifyH5TxtFile(session.getDirectory(), state=state_dictionary)

        self.newSession.emit(sid)
        return sid

    def createRemoteSession(self, remote, state_dictionary=None):
        """use this only to create entirely new sessions. to load existing use the loadRemoteSession command"""
        
        msg = {"key": Protocol.GETCAFFEVERSIONS}
        reply = sendMsgToHost(remote[0], remote[1], msg)
        if reply:
            remoteVersions = reply["versions"]
            if len(remoteVersions) <= 0:
                msgBox = QMessageBox(QMessageBox.Warning, "Error", "Cannot create remote session on a host witout a caffe-version")
                msgBox.addButton("Ok", QMessageBox.NoRole)
                msgBox.exec_()
                return None
        
        sid = self.getNextSessionId()
        msg = {"key": Protocol.CREATESESSION, "pid": self.projectId, "sid": sid}

        layers = []
        for layer in state_dictionary["network"]["layers"]:
            layers.append(state_dictionary["network"]["layers"][layer]["parameters"]["type"])

        msg["layers"] = layers

        ret = sendMsgToHost(remote[0], remote[1], msg)
        if ret:
            if ret["status"]:
                uid = ret["uid"]
            else:
                for e in ret["error"]:
                    Log.error(e, self.getCallerId())
                return None
        else:
            Log.error('Failed to create remote session! No connection to Host', self.getCallerId())
            return None

        session = ClientSession(self, remote, uid, sid)
        if state_dictionary is not None:
            session.state_dictionary = state_dictionary
        self.__sessions[sid] = session
        self.newSession.emit(sid)
        return sid

    def loadRemoteSession(self, remote, uid):
        sid = self.getNextSessionId()
        session = ClientSession(self, remote, uid, sid)

        availableTypes = info.CaffeMetaInformation().availableLayerTypes()
        unknownLayerTypes = []
        for layerID in session.state_dictionary["network"]["layers"]:
            type = session.state_dictionary["network"]["layers"][layerID]["parameters"]["type"]
            if not type in availableTypes and not type in unknownLayerTypes:
                unknownLayerTypes.append(type)

        if len(unknownLayerTypes) > 0:
            msg = "Cannot load session. The selected session contains layers unknown to the current caffe-version.\n\nUnknown layers:"
            for type in unknownLayerTypes:
                msg += "\n" + type
            msgBox = QMessageBox(QMessageBox.Warning, "Warning", msg)
            msgBox.addButton("Ok", QMessageBox.NoRole)
            msgBox.exec_()
            session._disconnect()
            return None

        self.__sessions[sid] = session
        self.newSession.emit(sid)
        return sid

    def cloneRemoteSession(self, oldSolverstate, oldSession):
        """
         Starts the cloning process for a remote session and creates the corr. local session upon success

         oldSolverstate: solverstate produced by the snapshot from which the clone should be created
         oldSession: session from which a clone should be created (type ClientSession)
        """
        # validate the given session and solverstate
        if oldSolverstate is None:
            Log.error('Could not find solver',
                      self.getCallerId())
            return None
        if oldSession is None:
            Log.error('Failed to create session!', self.getCallerId())
            return None

        sid = self.getNextSessionId()
        # call the remote host to invoke cloning; @see cloneSession in server_session_manager.py
        msg = {"key": Protocol.CLONESESSION, "pid": self.projectId,
               "sid": sid, "old_uid": oldSession.uid, "old_solverstate": oldSolverstate}
        ret = sendMsgToHost(oldSession.remote[0], oldSession.remote[1], msg)
        # receive and validate answer
        if ret:
            if ret["status"]:
                uid = ret["uid"]
            else:
                for e in ret["error"]:
                    Log.error(e, self.getCallerId())
                return None
        else:
            Log.error('Failed to clone remote session! No connection to Host', self.getCallerId())
            return None
        # Create a corr. local session and copy (if available) the state-dictionary to maintain
        # solver/net etc.
        session = ClientSession(self, oldSession.remote, uid, sid)
        if hasattr(oldSession, 'state_dictionary'):
            session.state_dictionary = oldSession.state_dictionary
        self.__sessions[sid] = session
        self.newSession.emit(sid)
        return sid


    def cloneSession(self, oldSolverstate, oldSession):
        """
         Creates a new session with the same net/solver etc. and a additional .caffemodel file with pretrained weights

         oldSolverstate: solverstate produced by the snapshot from which the clone should be created
         oldSession: session from which a clone should be created (type ClientSession)
        """
        if type(oldSolverstate) is not str and type(oldSolverstate) is not unicode:
            # if no valid solverstate is given, take the last model created for this session
            oldCaffemodel = oldSession.getLastModel()
        else:
            snapshotDir = os.path.join(oldSession.getSnapshotDirectory(), oldSolverstate)
            oldCaffemodel = loader.getCaffemodelFromSolverstate(snapshotDir)
        if oldCaffemodel is None:
            Log.error('Could not find model',
                      self.getCallerId())
            return None
        if oldSession:
            oldSnapshotDir = oldSession.getSnapshotDirectory()
            if os.path.isabs(oldSnapshotDir):
                # locate caffemodel
                oldModelPath = os.path.join(oldSnapshotDir, oldCaffemodel)
            else:
                oldSessionDir = oldSession.getDirectory()
                oldModelPath = os.path.join(oldSessionDir, oldSnapshotDir, oldCaffemodel)
        else:
            Log.error('Failed to create session!', self.getCallerId())
            return None

        # create new session
        sessionID = self.createSession()
        if sessionID is None:
            Log.error('Failed to create session!', self.getCallerId())
            return None
        self.__sessions[sessionID].setParserInitialized()

        # create directories for the new session
        newSnapshotDir = self.__sessions[sessionID].getSnapshotDirectory()
        self.__ensureDirectory(self.__sessions[sessionID].getDirectory())
        self.__ensureDirectory(newSnapshotDir)
        if os.path.isdir(newSnapshotDir):
            newCaffemodel = 'pretrained.caffemodel'
            newModelPath = os.path.join(newSnapshotDir, newCaffemodel)
            try:
                # copy the old caffemodel to the new location
                shutil.copy2(oldModelPath, newModelPath)
                # initialize new session
                self.__sessions[sessionID].setPretrainedWeights(newCaffemodel)
                self.__sessions[sessionID].iteration = 0
                self.__sessions[sessionID].max_iter = oldSession.max_iter
            except Exception as e:
                Log.error('Failed to copy caffemodel to new session: '+str(e),
                          self.getCallerId())

            # copy the old state-dict into the new session
            self.__sessions[sessionID].setStateDict(oldSession.state_dictionary)
            self.__sessions[sessionID].setState(State.WAITING)
            self.__sessions[sessionID].save(includeProtoTxt=True)
            return sessionID
        else:
            self.__sessions[sessionID].delete()
            Log.error('Snapshot directory '+newSnapshotDir+' does not exist!',
                      self.getCallerId())
            return None

    def rebuildSession(self, directory):
        """ Rebuild the session from the given directory.

        Return: The session if the directory is a valid session directory.
        """
        session = Session(self, directory=directory, parse_old=False)
        return session

    def loadSessions(self):
        """ Load sessions which are found in the sessions directory.

        Create a session object for every session and key it by the session id.
        """
        pool = SessionPool()
        sdir = self.getSessionsDirectory()
        count = 0
        for entry in os.listdir(sdir):
            sess_dir = os.path.join(sdir, entry)
            if self.isSession(sess_dir):
                session = self.rebuildSession(sess_dir)
                if session:
                    self.__sessions[session.getSessionId()] = session
                    pool.addSession(session)
                    self.newSession.emit(session.getSessionId())
                    count += 1

        return count

    def removeSessions(self, sessions):
        """ Remove the sessions from the project.
        """
        for session in sessions:
            sid = session.getSessionId()
            session.delete()
            self.__sessions.pop(sid)
            del session

    def closeSession(self, remoteSession):
        """ Close a remote session and remove it from the available sessions"""
        sid = remoteSession.getSessionId()
        remoteSession.close()
        self.__sessions.pop(sid)
        del remoteSession

    def isSession(self, directory):
        """ Checks if the directory contains a valid session."""
        if not os.path.exists(directory):
            Log.error('Session directory '+directory+' does not exist', self.getCallerId())
            return False

        session_file = os.path.join(directory, Paths.FILE_NAME_SESSION_JSON)
        if not os.path.exists(session_file):
            Log.error('Session directory '+directory+' does not contain a session file.', self.getCallerId())
            return False

        with open(session_file, 'r') as file:
            d = json.load(file)

        jsonKeys = ("Iteration", "MaxIter", "NetworkState", "ProjectID", "SessionState")

        keyNotFound=False
        for key in jsonKeys:
            if key not in d:
                Log.error("Session directory "
                                 + os.path.basename(os.path.normpath(dir)) + " is invalid! Key '"
                                 + key + "' is missing in sessionstate!", self.getCallerId())
                keyNotFound = True
        if keyNotFound:
            Log.error("Session at %s is invalid. Key %s in 'sessionstate.json' is missing", self.getCallerId())
            return False

        return True

    def hasRunningSessions(self):
        """ Return True if there are running sessions in this project.
        """
        for sid, session in self.__sessions.iteritems():
            if session.getState() is State.RUNNING:
                return True
        return False

    def pauseRunningSessions(self):
        """ Pause all running sessions.
        """
        for sid, session in self.__sessions.iteritems():
            if session.getState() is State.RUNNING:
                session.pause()

    def getNextSessionId(self):
        """ Return the next session id from the sequence of ids.
        """
        sIDs = [s for s in self.__sessions.iterkeys()]
        if len(sIDs) > 0:
            return max(max(sIDs)+1, 1)
        else:
            return 1

    def __ensureDirectory(self, directory):
        """ Creates a directory if it does not exist.
        """
        if directory == '':
            return
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
                Log.log('Created directory: '+directory, self.getCallerId())
            except Exception as e:
                Log.error('Failed to create directory '+directory+')'+str(e),
                          self.getCallerId())

    def parseSnapshotPrefixFromFile(self, filename):
        """ Return the snapshot prefix of the solver.
        """
        with open(filename) as f:
            regex_prefix = re.compile(
                'snapshot_prefix:[\s]+"(.+)"')
            for line in f:
                prefix_match = regex_prefix.search(line)
                if prefix_match:
                    return prefix_match.group(1)