import copy
import json
import os
import re
import signal
import sys
import time
import uuid
import shutil

from collections import OrderedDict
from subprocess import Popen, PIPE, STDOUT


from PyQt5.Qt import QObject
from PyQt5.QtCore import Qt, pyqtSignal

import backend.caffe.dict_helper as helper
import backend.caffe.proto_info as info
import backend.caffe.saver as saver
from backend.barista.constraints.session_run.training import checkMinimumTrainingRequirements
from backend.barista.session.session import State
from backend.barista.session.session_common import SessionCommon
from backend.barista.session.session_pool import SessionPool
from backend.barista.session.session_utils import Paths, Events
from backend.networking.protocol import Protocol, SessionProtocol
from backend.parser.concatenator import Concatenator
from backend.parser.parser import Parser
from backend.parser.parser_listener import ParserListener
import backend.barista.caffe_versions as caffeVersions
from backend.barista.deployed_net import DeployedNet
from backend.caffe.proto_info import UnknownLayerTypeException

from PyQt5.QtCore import QTimer
from threading import Lock

class ServerSession(QObject, ParserListener, SessionCommon):
    logsig = pyqtSignal(str, bool)  # This is the way to do threadsafe logging while the session is running
    parssig = pyqtSignal(str, OrderedDict)
    keysig = pyqtSignal(str, str)
    statesig = pyqtSignal(int)
    snapshotsig = pyqtSignal(str)
    handlesig = pyqtSignal(str, str, list)

    # a runnning session is moved to another thread (which is not a QThread and has no main-loop)
    # using the network feature causes warnings unless every operation is connected with a signal to the
    # original network method with Qt.Autoconnect (theoretically Qt.QueuedConnection should work as well)


    def __init__(self, manager, directory, parse_old=False, pid=""):
        super(self.__class__, self).__init__()
        self.options = {SessionProtocol.CHECKFILES: self._msgCheckFiles,
                        SessionProtocol.CHECKTRAINING: self._msgCheckTraining,
                        SessionProtocol.GETSNAPSHOTS: self._msgGetSnapshots,
                        SessionProtocol.GETITERATION: self._msgGetIteration,
                        SessionProtocol.GETMAXITERATION: self._msgGetMaxIteration,
                        SessionProtocol.SETMAXITERATION: self._msgSetMaxIteration,
                        SessionProtocol.GETSTATE: self._msgGetState,
                        SessionProtocol.GETPRETRAINED: self._msgGetPretrainedWeights,
                        SessionProtocol.SETSTATEDICT: self._msgSetStateDict,
                        SessionProtocol.GETSTATEDICT: self._msgGetStateDict,
                        SessionProtocol.SAVE: self._msgSave,
                        SessionProtocol.START: self._start,
                        SessionProtocol.PAUSE: self._pause,
                        SessionProtocol.PROCEED: self._proceed,
                        SessionProtocol.TAKESNAPSHOT: self._takeSnapshot,
                        SessionProtocol.FETCHPARSERDATA: self._msgFetchParserData,
                        SessionProtocol.LOADINTERNALNET: self._msgLoadInternalNet,
                        SessionProtocol.LOADDEPLOYEDNET: self._msgLoadDeployedNet,
                        SessionProtocol.LOADNETPARAMETER: self._msgLoadNetParameter,
                        SessionProtocol.LOADCAFFEMODEL: self._msgLoadCaffemodel,
                        SessionProtocol.RESET: self._reset,
                        SessionProtocol.DELETE: self.delete}

        self.logsig.connect(self.Log, Qt.AutoConnection)
        self.parssig.connect(self.addParserRow, Qt.AutoConnection)
        self.keysig.connect(self.addParserKey, Qt.AutoConnection)
        self.statesig.connect(self.setState, Qt.AutoConnection)
        self.snapshotsig.connect(self.addSnapshot, Qt.AutoConnection)
        self.handlesig.connect(self.addHandle, Qt.AutoConnection)

        self.transaction = None
        self.isConnected = False
        self.manager = manager
        self.directory = directory
        self.pid = None
        self.sid = None
        self.uid = str(uuid.uuid4())
        self.snapshot_dir = None
        self.snapshot_prefix = None
        self.iteration = 0
        self.max_iter = 1
        self.state_dictionary = {}
        self.state = State.WAITING
        self.invalidErrorsList = []
        self.last_solverstate = None
        self.pretrainedWeights = None
        self.logs = os.path.join(directory, 'logs')

        # run stuff
        self.rid = 0
        self.tee = None
        self.proc = None
        self.parser = None
        self.lock = Lock()
        self.parse_old = False
        self.parser_initialized = False

        self.parserRows = []
        self.parserKeys = []
        self.parserHandle = []
        self.parserLogs = []

        self.timer = QTimer()
        self.timer.timeout.connect(self.transmitLog)
        self.timer.setSingleShot(True)
        self.timer.setInterval(10)
        self.logBuffer = []
        self.logLock = Lock()

        if not parse_old:
            self.pid = pid
        else:
            self.rebuild()
            self._parseSessionAndRunID()
            self.parse_old = True

    def __lt__(self, other):
        if type(other) is not ServerSession:
            return True
        return other.sid - self.sid < 0

    def __gt__(self, other):
        if type(other) is not ServerSession:
            return False
        return other.sid - self.sid > 0

    def __eq__(self, other):
        if type(other) is not ServerSession:
            return False
        return other.sid - self.sid == 0

    def __le__(self, other):
        if type(other) is not ServerSession:
            return True
        return other.sid - self.sid <= 0

    def __ge__(self, other):
        if type(other) is not ServerSession:
            return False
        return other.sid - self.sid >= 0

    def __ne__(self, other):
        if type(other) is not ServerSession:
            return True
        return other.sid - self.sid != 0

    def rebuild(self):
        filename = os.path.join(self.directory, Paths.FILE_NAME_SESSION_JSON)
        if os.path.isfile(filename):
            with open(filename, 'r') as f:
                try:
                    res = json.load(f)
                    self._parseSetting(res)
                except Exception:
                    sys.stderr.write("ERROR on reading json data from: " + filename + "\n")

    def connect(self, transaction):
        if not self.isConnected:
            self.isConnected = True
            self.transaction = transaction
            self.transaction.bufferReady.connect(self.processMessage)
            self.transaction.socketClosed.connect(self.disconnect)
            return True
        return False

    def disconnect(self):
        self.isConnected = False
        if self.transaction is not None:
            self.transaction.bufferReady.disconnect()
            self.transaction.socketClosed.disconnect()
            self.transaction = None

    def processMessage(self):
        # key = self.transaction.messageOutput[0]["key"]
        key, subkey = self.transaction.getAttrOfFirst(["key", "subkey"])
        if key is Protocol.SESSION:
            # if "subkey" in self.transaction.messageOutput[0]:
            #     subkey = self.transaction.messageOutput[0]["subkey"]
            if subkey is not None:
                if subkey in self.options:
                    self.options[subkey]()
                else:
                    sys.stderr.write("Wrong subkey for session: " + str(subkey) + "\n")
                    msg = self.transaction.asyncRead()
                    msg["status"] = False
                    msg["error"] = ["Wrong subkey for session: " + str(subkey)]
                    self.transaction.send(msg)
                    return
            else:
                sys.stderr.write("Missing subkey for session\n")
                msg = self.transaction.asyncRead()
                msg["status"] = False
                msg["error"] = ["Missing subkey for session"]
                self.transaction.send(msg)
                return

    def setErrorList(self, errorList):
        self.invalidErrorsList = errorList

    def setState(self, state):
        self.state = state
        if (self.isConnected):
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.UPDATESTATE}
            msg["state"] = state
            self.transaction.send(msg)



    def Log(self, log, error=False):
        self.logLock.acquire()
        self.logBuffer.append((log, error))
        self.logLock.release()
        self.parserLogs.append((log, error))
        self.timer.stop()
        self.timer.start()
        # if self.isConnected:
        #     msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.PRINTLOG}
        #     msg["log"] = log
        #     msg["isError"] = error
        #     self.transaction.send(msg)

    def transmitLog(self):
        self.logLock.acquire()
        log = self.logBuffer
        self.logBuffer = []
        self.logLock.release()
        if self.isConnected:
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.PRINTLOG}
            msg["log"] = log
            self.transaction.send(msg)

    def addParserRow(self, phase, row):
        self.parserRows.append((phase, row))
        if self.isConnected:
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.UPDATEPARSER, "phase": phase, "row": row}
            self.transaction.send(msg)

    def addParserKey(self, phase, key):
        self.parserKeys.append((phase, key))
        if self.isConnected:
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.UPDATEKEYS, "phase": phase, "parserkey": key}
            self.transaction.send(msg)

    def addSnapshot(self, snapshot):
        if self.isConnected:
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.ADDSNAPSHOT, "snapshot": snapshot}
            self.transaction.send(msg)

    def addHandle(self, event, message, groups):
        self.parserHandle.append([event, message, groups])
        if self.isConnected:
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.PARSEHANDLE,
                   "event": event, "message": message, "groups": groups}
            self.transaction.send(msg)

    def getDirectory(self):
        return self.directory

    def getErrorList(self):
        return self.invalidErrorsList

    def setInitialSid(self, sid):
        self.sid = sid

    def _msgCheckFiles(self):
        """ Check for the existence of the session directories and files.
                """
        msg = self.transaction.asyncRead()
        errors = []
        if os.path.exists(self.getDirectory()) is False:
            errors.append('Session directory does not exists: ' + self.directory)
        if os.path.exists(self.logs) is False:
            errors.append('Log directory does not exists: ' + self.logs)
        if os.path.exists(self.snapshot_dir) is False:
            errors.append('Snapshot directory does not exists: ' + self.snapshot_dir)
        if os.path.exists(caffeVersions.getDefaultVersion().getBinaryPath()) is False:
            errors.append('CAFFE_BINARY does not exists: ' + caffeVersions.getDefaultVersion().getBinaryPath())
        msg["error"] = errors
        self.transaction.send(msg)

    def _msgCheckTraining(self):
        msg = self.transaction.asyncRead()
        req = checkMinimumTrainingRequirements(self)
        self.setState(self._getState())
        msg["status"] = True
        msg["check"] = req
        self.transaction.send(msg)

    def delete(self):
        self.pause()  # make sure the session is not running
        try:
            shutil.rmtree(self.getDirectory())
        except OSError as e:
            sys.stderr.write(str(e)+'\n')  # python docs say, that rmtree should raise an OSError code 66 if dir is not empty. However, this does not seem to happen.

        self.disconnect()
        return

    def _msgGetSnapshots(self):
        """ Return all snapshot files, keyed by iteration number.
        """
        msg = self.transaction.asyncRead()
        msg["snapshots"] = self._getSnapshots()
        self.transaction.send(msg)

    def _getSnapshots(self):
        regex_snapshot = re.compile('iter_([\d]+)\.solverstate')
        snaps = {}
        if os.path.exists(self.getSnapshotDirectory()):
            for entry in os.listdir(self.getSnapshotDirectory()):
                snap_match = regex_snapshot.search(entry)
                if snap_match:
                    try:
                        iter_num = int(snap_match.group(1))
                        snaps[iter_num] = entry
                    except Exception:
                        pass

        return snaps

    def _msgGetIteration(self):
        msg = self.transaction.asyncRead()
        msg["iteration"] = self.getIteration()
        self.transaction.send(msg)

    def _msgGetMaxIteration(self):
        msg = self.transaction.asyncRead()
        msg["iteration"] = self.getMaxIteration()
        self.transaction.send(msg)

    def _msgSetMaxIteration(self):
        msg = self.transaction.asyncRead()
        self.max_iter = msg["iteration"]

    def _msgGetState(self):
        msg = self.transaction.asyncRead()
        msg["state"] = self._getState()
        msg["status"] = True
        self.transaction.send(msg)

    def _msgGetPretrainedWeights(self):
        msg = self.transaction.asyncRead()
        msg["pretrained"] = self.getPretrainedWeights()
        self.transaction.send(msg)

    def getLastModel(self):
        return self.last_caffemodel

    def getIteration(self):
        return self.iteration

    def getMaxIteration(self):
        return self.max_iter

    def getPretrainedWeights(self):
        return self.pretrainedWeights

    def setPretrainedWeights(self, weights):
        self.pretrainedWeights = weights

    def _getState(self):
        """ Return the state of the session.
        """
        if self.state == State.FAILED:
            return self.state

        if self.proc is not None:
            if self.iteration == self.max_iter:
                self.state = State.FINISHED
            else:
                self.state = State.RUNNING
        else:
            if len(checkMinimumTrainingRequirements(self)) > 0:
                self.state = State.INVALID
            elif self.iteration == self.max_iter:
                self.state = State.FINISHED
            elif len(self._getSnapshots()) > 0:
                self.state = State.PAUSED
            else:
                self.state = State.WAITING
        return self.state

    def _msgSetStateDict(self):
        msg = self.transaction.asyncRead()
        try:
            self.setStateDict(msg["statedict"])
            msg["status"] = True
        except UnknownLayerTypeException as e:
            msg["status"] = False
            msg["error"] = [e._msg]
        del msg["statedict"]
        self.transaction.send(msg)

    def setStateDict(self, statedict):
        self.state_dictionary = statedict
        self._parseSetting(self.state_dictionary)
        # restore lost types
        if hasattr(self.state_dictionary, '__getitem__'):
            if "network" in self.state_dictionary:
                if "layers" in self.state_dictionary["network"]:
                    layers = self.state_dictionary["network"]["layers"]
                    for id in layers:
                        if "parameters" in layers[id]:
                            if "type" in layers[id]["parameters"]:
                                typename = layers[id]["parameters"]["type"]
                                layers[id]["type"] = info.CaffeMetaInformation().getLayerType(typename)

    def _msgGetStateDict(self):
        msg = self.transaction.asyncRead()

        transferDict = copy.deepcopy(self.state_dictionary)
        try:
            layers = transferDict["network"]["layers"]
            for id in layers:
                del layers[id]["type"]
            msg["statedict"] = transferDict
            msg["status"] = True
        except KeyError as e:
            msg["statedict"] = transferDict
            msg["status"] = True
        self.transaction.send(msg)

    def save(self, includeProtoTxt = False, errors = []):
        """Saves the current session to prototxt files and session_settings json file."""
        res = self.__ensureDirectory()
        if len(res) > 0:
            return res

        availableTypes = info.CaffeMetaInformation().availableLayerTypes()
        unknownLayerTypes = []
        for layerID in self.state_dictionary["network"]["layers"]:
            type = self.state_dictionary["network"]["layers"][layerID]["parameters"]["type"]
            if not type in availableTypes and not type in unknownLayerTypes:
                unknownLayerTypes.append(type)
        if len(unknownLayerTypes) > 0:
            errors.extend(unknownLayerTypes)
            return False
        else:
            toSave = {"SessionState": self.state, "Iteration": self.iteration, "MaxIter": self.max_iter}
            toSave["UID"] = self.uid
            toSave["SID"] = self.sid
            toSave["ProjectID"] = self.pid
            if self.last_solverstate:
                toSave["LastSnapshot"] = self.last_solverstate
            if self.pretrainedWeights:
                toSave["PretrainedWeights"] = self.pretrainedWeights
            if self.state_dictionary:
                serializedDict = copy.deepcopy(self.state_dictionary)
                if "network" in serializedDict:
                    if includeProtoTxt:
                        netDict = copy.deepcopy(self.state_dictionary["network"])
                        net = saver.saveNet(netdict=netDict)
                        with open(os.path.join(self.directory, Paths.FILE_NAME_NET_ORIGINAL), 'w') as f:
                            f.write(net)

                    if "layers" in serializedDict["network"]:
                        layers = serializedDict["network"]["layers"]
                        for id in layers:
                            del layers[id]["type"]

                toSave["NetworkState"] = serializedDict

            filename = os.path.join(self.directory, Paths.FILE_NAME_SESSION_JSON)

            # clear the file. sometimes json.dump does not exitclean and causes valuerrors on load
            open(filename, 'w').close()

            with open(filename, "w") as f:
                json.dump(toSave, f, sort_keys=True, indent=4)
            return True
            

    def prepairInternalPrototxt(self):
        error = []
        serializedDict = copy.deepcopy(self.state_dictionary)
        if "solver" in self.state_dictionary:
            solverDict = self.state_dictionary["solver"]
            if self.manager.parent.trainOnHW == 0:
                solverDict["solver_mode"] = 'CPU'
            else:
                solverDict["solver_mode"] = 'GPU'
            solver = saver.saveSolver(solverdict=solverDict)
            with open(os.path.join(self.directory, Paths.FILE_NAME_SOLVER), 'w') as f:
                f.write(solver)
        else:
            error.append("There is no solver")
        if "network" in serializedDict:
            net, error = self._modifyNetDictionaryToInternalVersion(serializedDict["network"])
            net = saver.saveNet(net)
            with open(os.path.join(self.directory, Paths.FILE_NAME_NET_INTERNAL), 'w') as f:
                f.write(net)
        else:
            error.append("There is no network")
        return error

    def _modifyNetDictionaryToInternalVersion(self, net):
        # define all layer parameters that can contain (relative) paths
        # (use a dot to separate nested parameters)
        layerParamsContainingPaths = [
            "data_param.source",
            "hdf5_data_param.source",
            "image_data_param.source",
            "window_data_param.source",
            "data_param.mean_file",
            "hdf5_output_param.file_name",
            "image_data_param.mean_file",
            "window_data_param.mean_file",
            "transform_param.mean_file"]

        error = []

        # evaluate layer after layer
        h = helper.DictHelper(net)
        for layerId, layer in net.get("layers", {}).iteritems():

            # evaluate parameter after parameter
            for paramKey in layerParamsContainingPaths:
                # if the current layer does have the current parameter..
                if h.layerParameterIsSet(layerId, paramKey):
                    paramValue = h.layerParameter(layerId, paramKey)

                    # ..and its value is a relative path: modify it
                    if paramValue is not None and not os.path.isabs(paramValue):
                        if paramKey != "hdf5_data_param.source":
                            newPath = os.path.join(os.pardir, paramValue)
                        else:
                            newFilename = str(layerId) + ".txt"
                            newPath = os.path.join(os.curdir, newFilename)
                            parentPath = self.manager.parent.sessionPath
                            oldPath = os.path.join(parentPath, paramValue)

                            # this builds the new hdf5 files
                            if os.path.exists(oldPath):
                                with open(os.path.join(self.directory, newPath), 'w') as f:
                                    lines = [line.rstrip('\n') for line in open(oldPath)]
                                    for line in lines:
                                        if line is not "":
                                            if line[:1] == '.':
                                                line = os.path.join(os.pardir, line)
                                            f.write("\n" + line)
                            else:
                                self.Log("Failed to copy hdf5txt file. File does not exists: " + oldPath, True)
                                error.append("Failed to copy hdf5txt file. File does not exists: " + oldPath)

                        h.setLayerParameter(layerId, paramKey, newPath)
        return net, error

    def _parseSetting(self, settings):
        if not hasattr(settings, '__getitem__'):
            return
        else:
            if "UID" in settings:
                self.uid = settings["UID"]
            if "SID" in settings:
                self.sid = settings["SID"]
            if "ProjectID" in settings:
                self.pid = settings["ProjectID"]
            if "SessionState" in settings:
                self.state = settings["SessionState"]
                if self.state == State.RUNNING:
                    self.state = State.PAUSED
                self.previousState = self.state

            if "Iteration" in settings:
                self.iteration = settings["Iteration"]

            if "solver" in settings:
                if "max_iter" in settings["solver"]:
                    self.max_iter = settings["solver"]["max_iter"]
            elif "MaxIter" in settings:
                self.max_iter = settings["MaxIter"]

            if "LastSnapshot" in settings:
                self.last_solverstate = settings["LastSnapshot"]

            if "PretrainedWeights" in settings:
                self.pretrainedWeights = settings["PretrainedWeights"]
            if "NetworkState" in settings:
                self.state_dictionary = settings["NetworkState"]
                layers = self.state_dictionary["network"]["layers"]
                for id in layers:
                    if "parameters" in layers[id]:
                        if "type" in layers[id]["parameters"]:
                            typename = layers[id]["parameters"]["type"]
                            layers[id]["type"] = info.CaffeMetaInformation().getLayerType(typename)
                solver = self.state_dictionary["solver"]
                if solver:
                    if "snapshot_prefix" in solver:
                        self.snapshot_prefix = solver["snapshot_prefix"]

    def _parseSessionAndRunID(self):

        if self.sid is None:
            regex_sid = re.compile('[\d]{8}_[\d]{6}_([\d]+)')

            sid_match = regex_sid.search(self.directory)
            session_id = None
            if sid_match:
                try:
                    self.sid = int(sid_match.group(1))
                except:
                    pass
            if self.sid is None:
                self.sid = 0

        regex_rid = re.compile('([\d]+)\.([\d]+)\.log')
        run_id = 0
        if os.path.exists(self.logs):
            for entry in os.listdir(self.logs):
                rid_match = regex_rid.search(entry)
                if rid_match:
                    try:
                        _run_id = int(rid_match.group(2))
                        if _run_id > run_id:
                            run_id = _run_id
                    except:
                        pass
        self.rid = run_id

    def getSnapshotDirectory(self):
        """ Return the snapshot directory.
        """
        return self.getDirectory()
        # if self.snapshot_dir:
        #     return self.snapshot_dir
        # snapshot_prefix = self._getSnapshotPrefix()
        # sdir = os.path.dirname(snapshot_prefix)
        # self.snapshot_dir = os.path.join(self.directory, sdir)
        # return self.snapshot_dir

    def _getSnapshotPrefix(self):
        """ Return the snapshot prefix which is used for snapshots of this
        session.
        """
        if not self.snapshot_prefix:
            pass
            # self.__parseSnapshotPrefix() # TODO
        if not self.snapshot_prefix:
            self.snapshot_prefix = ''

        return self.snapshot_prefix

    def _start(self):
        msg = self.transaction.asyncRead()
        if self.manager.isTraining():
            msg["error"] = ["Could not start Session. There is already one running Session on this Server."]
            msg["status"] = False
            self.transaction.send(msg)
            return
        
        solverstate = None
        if "solverstate" in msg:
            solverstate = msg["solverstate"]
        caffemodel = None
        if "caffemodel" in msg:
            caffemodel = msg["caffemodel"]

        msg["error"] = self.start(solverstate, caffemodel)
        msg["status"] = len(msg["error"]) == 0
        self.transaction.send(msg)

    def _pause(self):
        msg = self.transaction.asyncRead()
        msg["status"] = self.pause()
        msg["iteration"] = self.iteration
        if not msg["status"]:
            msg["error"] = ["Could not pause a session in state " + str(self.state)]
        self.transaction.send(msg)
        self.save()

    def _reset(self):
        msg = self.transaction.asyncRead()
        msg["status"] = self.reset()
        msg["iteration"] = 0
        if not msg["status"]:
            msg["error"] = ["Could not reset a session in state " + str(self.state)]
        self.transaction.send(msg)
        self.save()

    def _proceed(self):
        msg = self.transaction.asyncRead()
        if self.manager.isTraining():
            msg["error"] = ["Could not proceed Session. There is already one running Session on this Server."]
            msg["status"] = False
            self.transaction.send(msg)
            return
        snapshot = None
        if "snapshot" in msg:
            snapshot = msg["snapshot"]
        msg["error"] = self.proceed(snapshot)
        msg["status"] = len(msg["error"]) == 0
        self.transaction.send(msg)

    def _msgSave(self):
        msg = self.transaction.asyncRead()
        error = []
        ret = self.save(errors = error)
        msg["status"] = ret
        msg["error"] = error
        self.transaction.send(msg)

    def _takeSnapshot(self):
        msg = self.transaction.asyncRead()
        msg["status"] = self.snapshot()
        if not msg["status"]:
            msg["error"] = ["Could not take snapshot of session."]
        self.transaction.send(msg)

    def getRunLogFileName(self, basename=False):
        """ Return the name of the logfile with session and run id.
        """
        log_file = 'server_' + str(self.sid) + '.' + str(self.rid) + '.log'
        if basename is True:
            return log_file
        log_file = os.path.join(self.getLogs(), log_file)
        return log_file

    def getParser(self):
        """ Return the log parser of this session.
        """
        if self.parser is None:
            self.parser = Parser(None, Events.events)
            self.parser.setLogging(True)
            self.parser.printLogSignl.connect(self.Log, Qt.AutoConnection)
            self.parser.addListener(self)
        return self.parser

    def getLogs(self):
        """ Return the log directory.
        """
        logs = os.path.join(self.directory, "logs")
        if os.path.exists(logs) is False:
            os.makedirs(logs)
        return logs

    def startParsing(self):
        """ Create a parser and run it in a newly dispatched thread.
        """
        self.parseOldLogs()
        logs = self.getStream()
        self.getParser().addLogStream(logs)
        pool = SessionPool()
        pool.addSession(self)

    def parseOldLogs(self):
        """ Parse all log files in the log directory.
        """
        locked = self.lock.acquire()
        if locked is False:
            return
        try:
            if self.parse_old:
                self.parse_old = False
                log_files = {}
                regex_filename = re.compile('[\d]+\.([\d]+)\.log$')
                for entry in os.listdir(self.getLogs()):
                    filename_match = regex_filename.search(entry)
                    if filename_match:
                        # key files by run id
                        try:
                            run_id = int(filename_match.group(1))
                            log_files[run_id] = entry
                        except:
                            pass
                log_list = []
                for run_id in sorted(log_files.keys()):
                    log_file = os.path.join(self.getLogs(), log_files[run_id])
                    log_list.append(log_file)
                con = Concatenator(log_list)
                logs = con.concate()
                for log in logs:
                    try:
                        self.getParser().addLogStream(log)
                    except Exception as e:
                        self.Log('Failed to parse log file ' + self.getLogFileName(True) + ": " + str(e), True)
        except Exception as e:
            self.Log('Failed to parse old log ' + str(e), True)
        finally:
            if locked:
                self.lock.release()

    def getLogFileName(self, basename=False):
        """ Return the name of the logfile with session id.
        """
        log_file = 'server_' + str(self.getSessionId()) + '.log'
        if basename is True:
            return log_file
        log_file = os.path.join(self.getLogs(), log_file)
        return log_file

    def getStream(self):
        """ Return the log stream of this session.
        This is an iterator over stdout of the subprocess.
        """
        if self.tee is not None:
            return iter(self.tee.stdout.readline, '')
        if self.proc is not None:
            return iter(self.proc.stdout.readline, '')
        return iter([])

    def update(self, phase, row):
        self.iteration = row['NumIters']
        self.parssig.emit(phase, row)

    def parsingFinished(self):
        """ Called when the parser has processed all available streams.
        """
        if self.parser_initialized:
            self.logsig.emit("Parsing Finished", False)


        if self.proc is not None:
            # Wait for caffe process, kill tee and respond to return code
            assert self.state is State.RUNNING
            rcode = self.proc.wait()
            self.proc = None
            try:
                self.tee.kill()
            except Exception:
                pass
            self.tee = None
            if rcode is 0:
                self.setFinished()
            else:
                self.setState(State.FAILED)
                self.Log('Session failed with return code ' + str(rcode), True)

        self.parser_initialized = True

    def registerKey(self, phase, key):
        # TODO save the keys and send them on connection
        self.keysig.emit(phase, key)

    def handle(self, event, message, groups):
        self.handlesig.emit(event, message, groups)
        if event == 'OptimizationDone':
            self.save()
            self.setState(State.FINISHED)
            self.proc = None
        elif event == 'max_iter':
            self.max_iter = int(groups[0])
            # todo update max_iter
        elif event == 'state_snapshot':
            self.last_solverstate = groups[0]
            #if self.parser_initialized:
            self.snapshotsig.emit(self.last_solverstate)
        elif event == 'model_snapshot':
            self.last_caffemodel = groups[0]


    def setFinished(self):
        self.iteration = self.max_iter
        self.setState(State.FINISHED)

    def start(self, solverstate=None, caffemodel=None):
        # TODO only one training per server
        error = []
        # (re-)write all session files
        self.save(includeProtoTxt=True, errors=error)
        if not os.path.exists(self.logs):
            try:
                os.makedirs(self.logs)
            except OSError as e:
                error.extend(['Failed to create Folder: ' + str(e)])

        if self.rid is None:
            self._parseSessionAndRunID()
        if self.state is State.WAITING:
            self.rid += 1
            error.extend(self.prepairInternalPrototxt())
            if len(error) > 0:
                return error
            caffe_bin = caffeVersions.getDefaultVersion().getBinarypath()
            try:
                self.getParser().setLogging(True)
                # TODO set hardware trainOnHW
                cmd = [
                    caffe_bin, 'train', '-solver',
                    os.path.join(self.directory, Paths.FILE_NAME_SOLVER)]
                if solverstate is not None:
                    cmd.append('-snapshot')
                    cmd.append(str(solverstate))
                if caffemodel is not None:
                    cmd.append('-weights')
                    cmd.append(str(caffemodel))
                if self.manager.parent.trainOnHW > 0:
                    cmd.append('-gpu')
                    cmd.append(str(self.manager.parent.trainOnHW-1))
                self.proc = Popen(
                    cmd,
                    stdout=PIPE,
                    stderr=STDOUT,
                    cwd=self.getSnapshotDirectory())
                try:
                    self.tee = Popen(
                        ['tee', '-a', self.getRunLogFileName()],
                        stdin=self.proc.stdout,
                        stdout=PIPE)
                except Exception as e:
                    self.Log("Failed to start tee: " + str(e), error=True)
                self.setState(State.RUNNING)
                self.Log('Session ' + self.getRunLogFileName(True) + " was started.")
                self.startParsing()
                return []
            except Exception as e:
                return ["Failed to start session: " + str(e)]
        else:
            self.statesig.emit(self.state)
            error.append("Failed to start session in state " + str(self.state))
            return error

    def pause(self):
        if self.state is State.RUNNING:
            if self.proc:
                self.snapshot()
                time.sleep(1)
                try:
                    if self.proc:
                        self.proc.kill()
                except Exception as e:
                    self.logsig.emit('Pausing session failed: ' + str(e), True)
                try:
                    if self.tee:
                        self.tee.kill()
                except Exception:
                    pass
                self.proc = None
                self.tee = None
                self.last_solverstate = None
                self.last_solverstate = self._getLastSnapshotFromSnapshotDirectory(True)
                regex_iter = re.compile('iter_([\d]+)\.solverstate[\.\w-]*$')
                iter_match = None
                if self.last_solverstate is not None:
                    iter_match = regex_iter.search(self.last_solverstate)
                if iter_match is not None:
                    self.iteration = int(iter_match.group(1))
                # self.iterationChanged.emit() # implicit in _pause
                self.setState(State.PAUSED)
                self.logsig.emit("Session " + self.getRunLogFileName(True) + " was paused", False)
                return True
        return False

    def snapshot(self):
        if self.proc:
            self.last_solverstate = None
            try:
                self.proc.send_signal(signal.SIGHUP)
            except Exception as e:
                self.Log('Failed to take snapshot: ' + str(e), True)
                return False
            self.Log('Snapshot was saved for session ' + self.getRunLogFileName(True))
            return True
        else:
            self.statesig.emit(self.state)
            self.Log('Could not take a snapshot in state ' + str(self.state))
        return False

    def proceed(self, snapshot=None):
        if self.state is State.PAUSED:
            if snapshot is None:
                snapshot = self.getLastSnapshot()
            caffe_bin = caffeVersions.getDefaultVersion().getBinarypath()
            self.rid += 1
            try:
                self.getParser().setLogging(True)
                cmd = [
                    caffe_bin, 'train', '-solver',
                    os.path.join(self.directory, Paths.FILE_NAME_SOLVER)]
                cmd.append('-snapshot')
                cmd.append(snapshot)
                if self.manager.parent.trainOnHW > 0:
                    cmd.append('-gpu')
                    cmd.append(str(self.manager.parent.trainOnHW-1))
                self.proc = Popen(
                    cmd,
                    stdout=PIPE,
                    stderr=STDOUT,
                    cwd=self.getDirectory())
                try:
                    self.tee = Popen(
                        ['tee', '-a', self.getRunLogFileName()],
                        stdin=self.proc.stdout,
                        stdout=PIPE)
                except Exception as e:
                    self.Log("Failed to start tee: " + str(e), True)
                self.setState(State.RUNNING)
                self.Log('Session ' + self.getRunLogFileName(True) + " was proceeded.")
                self.startParsing()
                return []
            except Exception as e:
                return ["Failed to proceed session: " + str(e)]
        else:
            self.statesig.emit(self.state)
            return ["Can't proceed a session in state " + str(self.state)]

    def __ensureDirectory(self):
        if os.path.exists(self.directory) is False:
            try:
                os.makedirs(self.directory)
                return []
            except Exception as e:
                return ["Can't create Session Directory '" + self.directory + "': "+str(e)]
        return []

    def _msgFetchParserData(self):
        msg = self.transaction.asyncRead()
        msg["ParserRows"] = self.parserRows
        msg["ParserKeys"] = self.parserKeys
        msg["ParserHandle"] = self.parserHandle
        msg["ParserLogs"] = self.parserLogs
        self.transaction.send(msg)

    def _msgLoadInternalNet(self):
        msg = self.transaction.asyncRead()
        try:
            path = os.path.join(self.directory, Paths.FILE_NAME_NET_ORIGINAL)
            file = open(path, 'r')
            msg["NetInternal"] = file.read()
        except IOError:
            msg["status"] = False
            msg["error"] = ["Failed to read " + path]
        self.transaction.send(msg)

    def _msgLoadDeployedNet(self):
        msg = self.transaction.asyncRead()
        try:
            path = os.path.join(self.directory, Paths.FILE_NAME_NET_ORIGINAL)
            file = open(path, 'r')
            dn = DeployedNet(file.read())
            msg["Net"] = dn.getProtoTxt()
        except IOError:
            msg["status"] = False
            msg["error"] = ["Failed to read " + path]
        self.transaction.send(msg)

    def _msgLoadNetParameter(self):
        msg = self.transaction.asyncRead()
        msg["status"] = False
        if "snapshot" in msg.keys():
            path = msg["snapshot"]
            path = os.path.join(self.directory, path)
            if os.path.exists(path):
                try:
                    with open(path, 'rb') as f:
                        msg["NetParams"] = f.read()
                        msg["status"] = True
                except:
                    msg["error"] = ["Failed to load " + str(path)]
            else:
                msg["error"] = ["File not found " + str(path)]

        else:
            msg["error"] = ["No Snapshot provided"]
        self.transaction.send(msg)

    def _msgLoadCaffemodel(self):
        msg = self.transaction.asyncRead()
        msg["status"] = False
        print("Load caffe model received.")
        if "snapshot" in msg.keys():
            path = msg["snapshot"]
            print(path)
            path = os.path.join(self.directory, path)
            if os.path.exists(path):
                try:
                    with open(path, 'rb') as f:
                        msg["caffemodel"] = f.read()
                        msg["status"] = True
                except:
                    msg["error"] = ["Failed to load " + str(path)]
            else:
                msg["error"] = ["File not found " + str(path)]

        else:
            msg["error"] = ["No Snapshot provided"]
        self.transaction.send(msg)

    def reset(self):
        self.pause()
        for dirpath, dirnames, filenames in os.walk(self.directory, topdown=True):
            for dirname in dirnames:
                if os.path.join(dirpath, dirname) == self.logs:
                    try:
                        shutil.rmtree(self.logs)
                    except shutil.Error as e:
                        self.logsig.emit('Failed to delete logs folder: ' + str(e), self.getCallerId(), True)
            for filename in filenames:
                if filename.endswith(".solverstate") or filename.endswith(".caffemodel"):
                    if not filename == self.getPretrainedWeights():
                        try:
                            os.remove(os.path.join(dirpath, filename))
                        except OSError as e:
                            self.logsig.emit('Failed to delete ' + str(filename) + ': ' + str(e), self.getCallerId(), True)
                if filename in ["net-internal.prototxt", "net-original.prototxt", "solver.prototxt"]:
                    try:
                        os.remove(os.path.join(dirpath, filename))
                    except OSError as e:
                        self.logsig.emit('Failed to delete ' + str(filename) + ': ' + str(e), self.getCallerId(), True)
            break
        self.iteration = 0
        self.state = State.UNDEFINED
        self._getState()
        self.last_caffemodel = None
        self.last_solverstate = None
        self.save()
        self.statesig.emit(self.state)
        return True
