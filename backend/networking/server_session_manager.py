import os
import re
import shutil
import sys
import json
from datetime import datetime
import logging

from backend.barista.session.server_session import ServerSession
from backend.barista.session.session_pool import SessionPool
from backend.barista.session.session_utils import Paths, State
from backend.caffe import loader

from backend.caffe.proto_info import resetCaffeProtoModulesvar
from PyQt5.QtCore import pyqtSignal
from PyQt5.Qt import QObject
from backend.caffe.proto_info import UnknownLayerTypeException
import backend.caffe.proto_info as info


class ServerSessionManager(QObject):

    poolEmptyJob = pyqtSignal(str)
    jsonKeys = ("Iteration", "MaxIter", "NetworkState", "ProjectID", "SID", "SessionState", "UID")

    def __init__(self, parent, sessionPath):
        super(ServerSessionManager, self).__init__()
        resetCaffeProtoModulesvar()
        self.parent = parent
        self.sessionPath = sessionPath
        # TODO CaffeMetaInfo (use caffe/protopath)
        self.sessions = []
        self.loadSessions()

    def connectToSession(self, transaction):
        """connect to an existing session with UID"""
        msg = transaction.asyncRead()
        msg["error"] = []
        msg["status"] = False
        if "uid" in msg:
            session = self.findSessionBySessionUid(msg["uid"])
            if session:
                if session.connect(transaction):
                    msg["status"] = True
                    logging.info("Session connected.")
                else:
                    msg["error"].append("ConnectToSession: Failed to connect. Session is already connected!")
                    logging.error("Failed to connect. Session is already connected")
            else:
                msg["error"].append("ConnectToSession: No session with UID '" + msg["uid"] + "' found.")
                logging.error("No session with UID '%s' found.", msg["uid"])
        else:
            msg["error"].append("ConnectToSession: No UID provided.")
            logging.error("No UID provided.")
        transaction.send(msg)

    def createNewSession(self, transaction):
        """create a new session with SID and PID"""
        msg = transaction.asyncRead()
        if "pid" in msg and "sid" in msg and "layers" in msg:
            layers = msg["layers"]
            try:
                for layer in layers:
                    typename = info.CaffeMetaInformation().getLayerType(layer)
            except UnknownLayerTypeException as e:
                msg["status"] = False
                msg["error"] = [e._msg]
                logging.error("Could not create session. Unknown layer")
                transaction.send(msg)
                return
            dirp = self._createDirName(msg["sid"])
            uid = self._createSession(msg["pid"], dirp)
            self.findSessionBySessionUid(uid).setInitialSid(msg["sid"])
            msg["status"] = True
            msg["uid"] = uid
            logging.info("Session created with UID '%s'", uid)
        else:
            msg["status"] = False
            msg["error"] = ["CreateNewSession: No PID or SID provided."]
            logging.error("Could not create session. No PID or SID provided.")
        transaction.send(msg)

    def cloneSession(self, transaction):
        """
         Creates a new session with the same net/solver etc. and a additional .caffemodel file with pretrained weights
        """
        msg = transaction.asyncRead()
        if "pid" in msg and "sid" in msg:
            # create new session
            dirp = self._createDirName(msg["sid"])
            uid = self._createSession(msg["pid"], dirp) # note: this session is empty for now, net/solver will be loaded later
            newSession = self.findSessionBySessionUid(uid)
            newSession.setInitialSid(msg["sid"])
            msg["uid"] = uid
            if "old_uid" in msg and "old_solverstate" in msg:
                # find the old session (where the caffemodel is extracted from) with help of its uid
                oldSession = self.findSessionBySessionUid(msg["old_uid"])
                # given solverstate, is used to locate and identify the caffemodel
                oldSolverstate = msg["old_solverstate"]
                del msg["old_uid"]
                del msg["old_solverstate"]

                if type(oldSolverstate) is not str and type(oldSolverstate) is not unicode:
                    # if no valid solverstate is given, take the last model created for this session
                    oldCaffemodel = oldSession.getLastModel()
                else:
                    snapshotDir = os.path.join(oldSession.getSnapshotDirectory(), oldSolverstate)
                    oldCaffemodel = loader.getCaffemodelFromSolverstate(snapshotDir)

                if oldSession and oldCaffemodel:
                    # locate caffemodel
                    oldSnapshotDir = oldSession.getSnapshotDirectory()
                    oldModelPath = os.path.join(oldSnapshotDir, oldCaffemodel)
                else:
                    logging.error('Failed to create session!')
                    msg["error"] = ["No valid Session to clone from"]
                    msg["status"] = False
                    transaction.send(msg)
                    return

                # create directories for the new session
                newSnapshotDir = newSession.getSnapshotDirectory()
                self.__ensureDirectory(newSession.getDirectory())
                self.__ensureDirectory(newSnapshotDir)
                if os.path.isdir(newSnapshotDir):
                    newCaffemodel = 'pretrained.caffemodel'
                    newModelPath = os.path.join(newSnapshotDir, newCaffemodel)
                    try:
                        # copy the old caffemodel to the new location
                        shutil.copy2(oldModelPath, newModelPath)
                        # initialize new session
                        newSession.setPretrainedWeights(newCaffemodel)
                        newSession.iteration = 0
                        newSession.max_iter = oldSession.max_iter
                    except Exception as e:
                        logging.error('Failed to copy caffemodel to new session: ' + str(e))
                    # copy the old state-dict into the new session
                    newSession.setStateDict(oldSession.state_dictionary)
                    newSession.setState(State.WAITING)
                    newSession.save(includeProtoTxt=True)
                    msg["status"] = True
                    logging.info("Session cloned with UID '%s'", uid)
                else:
                    # cloning failed; clean up by deleting the new session
                    newSession.delete()
                    logging.error('Snapshot directory ' + newSnapshotDir + ' does not exist!')
                    msg["error"] = ["Snapshot directory does not exist!"]
                    msg["status"] = False
        else:
            msg["status"] = False
            msg["error"] = ["CreateNewSession: No PID or SID provided."]
            logging.error("Could not create session. No PID or SID provided.")
        transaction.send(msg)


    def __ensureDirectory(self, directory):
        """ Creates a directory if it does not exist.
        """
        if directory == '':
            return
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
                logging.info('Created directory: '+directory)
            except Exception as e:
                logging.error('Failed to create directory '+directory+')'+str(e))

    def deleteSession(self, transaction):
        """delete an existing session with UID"""
        msg = transaction.asyncRead()
        msg["error"] = []
        msg["status"] = False
        if "uid" in msg:
            session = self.findSessionBySessionUid(msg["uid"])
            if session:
                for sess in self.sessions:
                    if sess["uid"] == msg["uid"]:
                        self.sessions.remove(sess)
                session.delete()
                del session
                msg["status"] = True
                logging.info("Session deleted.")
            else:
                msg["error"].append("DeleteSession: No session with UID '" + msg["uid"] + "' found.")
                logging.error("No session with UID '%s' found.", msg["uid"])
        else:
            msg["error"].append("DeleteSession: No UID provided.")
            logging.error("No UID provided.")
        transaction.send(msg)

    def disconnectSession(self, transaction):
        msg = transaction.asyncRead()
        if "uid" in msg:
            session = self.findSessionBySessionUid(msg["uid"])
            if session:
                session.disconnect()

    def getSessions(self, transaction):
        """Get all session for a project with PID"""
        msg = transaction.asyncRead()
        if "pid" in msg:
            ret = []
            uids = self.findSessionIDsByProjectId(msg["pid"])
            for uid in uids:
                session = self.findSessionBySessionUid(uid)
                name = session.directory
                name = os.path.basename(name)
                if session.isConnected:
                    name = "(connected) " + name
                state = session.state
                if state is State.FINISHED:
                    name += " [FINISHED]"
                if state is State.WAITING:
                    name += " [READY]"
                if state is State.RUNNING:
                    name += " [RUNNING]"
                if state is State.PAUSED:
                    name += " [PAUSED]"
                if state is State.FAILED:
                    name += " [FAILED]"
                ret.append((uid, name))
            ret.sort(key=lambda s: s[1], reverse=True)
            msg["sessions"] = ret
            msg["status"] = True
            logging.debug("Found %s Session/s", str(len(ret)))
        else:
            msg["status"] = False
            msg["error"] = ["GetSessions: No PID provided"]
            logging.error("Sessions not found. No PID provided.")
        transaction.send(msg)

    def findSessionBySessionUid(self, uid):
        """find a single session with UID"""
        for sessiondict in self.sessions:
            if sessiondict["uid"] == uid:
                logging.debug("Found session for UID '%s'", uid)
                return sessiondict["session"]
        logging.debug("No sessions found for UID '%s'", uid)
        return None

    def findSessionIDsByProjectId(self, pid):
        """list all sessionids with PID"""
        uids = []
        for sessiondict in self.sessions:
            if sessiondict["pid"] == pid:
                uids.append(sessiondict["uid"])
        logging.info("Found %s session/s for PID '%s'", str(len(uids)), pid)
        return uids

    def findSessionIDsWithState(self, state):
        """find all session UIDs with state"""
        sessions = []
        for sessiondict in self.sessions:
            if sessiondict["session"].state == state:
                sessions.append(sessiondict["uid"])
        logging.debug("There are %i session/s with state %i", len(sessions), state)
        return sessions

    def _createSession(self, pid, dir):
        """Create a new session with PID in directory"""
        # TODO
        session = ServerSession(self, dir, pid=pid)
        uid = session.uid
        self.sessions.append({"pid": pid, "uid": uid, "session": session})
        return uid

    def _loadSession(self, dir):
        """load a session from directory"""
        session = ServerSession(self, dir, parse_old=True)
        return {"pid": session.pid, "uid": session.uid, "session": session}

    def _createDirName(self, sid):
        """create a directory for session with SID"""
        directory = self.__getDateTimeString()
        directory += "_" + str(sid)
        sdir = os.path.join(self.sessionPath, directory)
        return sdir

    def __getDateTimeString(self):
        """ Return the current datetime in the format YYYYMMDD_hh24mmss
        """
        now = datetime.now()
        date_string = ''
        date_string += str(now.year)
        date_string += str(now.month).zfill(2)
        date_string += str(now.day).zfill(2)
        date_string += '_'
        date_string += str(now.hour).zfill(2)
        date_string += str(now.minute).zfill(2)
        date_string += str(now.second).zfill(2)
        return date_string

    def loadSessions(self):
        """load all session from sessionpath and add them to the pool"""
        pool = SessionPool()
        count = 0
        for entry in os.listdir(self.sessionPath):
            if entry == "barista.conf" or entry == "caffeVersions":
                continue
            sdir = os.path.join(self.sessionPath, entry)
            if self._isSession(sdir):
                sessiondict = self._loadSession(sdir)
                if sessiondict is not None:
                    self.sessions.append(sessiondict)
                    pool.addSession(sessiondict["session"])
                    count += 1
        self.poolEmptyJob.connect(self.emptyJob)
        pool.activate(lambda: self.poolEmptyJob.emit("All jobs finished. SessionPool Queue empty."))
        logging.info("Loaded %s session/s", str(count))
        return count

    def emptyJob(self, msg):
        logging.info("All jobs finished. SessionPool Queue empty.")
        print msg

    def _isSession(self, dir):
        """Check if directory contains a valid session."""
        session_json = os.path.join(dir,Paths.FILE_NAME_SESSION_JSON)
        if os.path.isdir(dir) is False:
            sys.stderr.write("Session directory " + dir + " is invalid! No directory!\n")
            logging.error("Session directory %s is invalid. No directory", dir)
            return False
        if not os.path.exists(session_json):
            sys.stderr.write("Session directory " + os.path.basename(os.path.normpath(dir)) + " is invalid!\n    File 'sessionstate.json' does not exist!\n")
            logging.error("Session directory %s is invalid. 'sessionstate.json' does not exist!", dir)
            return False
        with open(session_json,"r") as file:
            try:
                dict = json.load(file)
            except ValueError:
                sys.stderr.write("Session file " + session_json + " is invalid!\n    File 'sessionstate.json' could not be parsed!\n")
                logging.error("Session file %s is invalid. 'sessionstate.json' could not be parsed!", session_json)
                return False
            
        for key in self.jsonKeys:
            if key not in dict:
                sys.stderr.write("Session directory "
                                 + os.path.basename(os.path.normpath(dir))+" is invalid!\n    Key '"
                                 +key +"' is missing in sessionstate!\n")
                logging.error("Session at %s is invalid. Key %s in 'sessionstate.json' is missing.",dir,key)
                return False
        if "LastSnapshot" in dict:
            if dict["LastSnapshot"]:
                if not os.path.exists(os.path.join(dir,dict["LastSnapshot"])):
                    sys.stderr.write("Session directory "
                                     + os.path.basename(os.path.normpath(dir)) + " is invalid!\n    Snapshot "
                                                                                 "was set but not found in directory\n")
                    logging.error("Session at %s is invalid. Snapshot was set but not found.", dir)
                    return False
        logging.debug("Session directory %s is valid!", dir)
        return True

    def _parseSnapshotPrefixFromFile(self, filename):
        """ Return the snapshot prefix of the solver.
        """
        with open(filename) as f:
            regex_prefix = re.compile(
                'snapshot_prefix:[\s]+"(.+)"')
            for line in f:
                prefix_match = regex_prefix.search(line)
                if prefix_match:
                    return prefix_match.group(1)

    def isTraining(self):
        """check if there is already a session running on this server"""
        return len(self.findSessionIDsWithState(State.RUNNING)) > 0
