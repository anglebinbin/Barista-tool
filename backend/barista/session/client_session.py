from PyQt5.QtCore import QTimer

from backend.barista.session.session import *
from backend.barista.session.session_utils import State
from backend.barista.utils.logger import Log
from backend.parser.parser_dummy import ParserDummy
from backend.networking.net_util import buildTransaction
from backend.networking.protocol import Protocol, SessionProtocol
from gui.main_window.docks.weight_visualization.weights import loadNetParamFromString

class ClientSession(QObject):
    # event signals
    stateChanged = pyqtSignal(object)
    stateDictChanged = pyqtSignal(object, bool)
    iterationChanged = pyqtSignal()
    snapshotAdded = pyqtSignal(object)

    def __init__(self, project, remote, uid, sid):
        super(self.__class__, self).__init__()

        self.options = {
            SessionProtocol.UPDATESTATE: self._updateState,
            SessionProtocol.PRINTLOG: self._printLog,
            SessionProtocol.UPDATEPARSER: self._updateParser,
            SessionProtocol.UPDATEKEYS: self._updateParserKeys,
            SessionProtocol.ADDSNAPSHOT: self._addSnapshot,
            SessionProtocol.PARSEHANDLE: self._parseHandle
        }

        self.firstConnect = True
        self.remote = remote
        self.isConnected = False
        self.transaction = None
        self.caller_id = None
        self.project = project
        self.parser = ParserDummy()
        # One ID for client, on ID for server
        self.sid = sid
        self.uid = uid
        self.lastStateDict = None
        self.state = State.NOTCONNECTED
        self.invalidErrorsList = []
        # setup timer
        # see details in setStateDict()
        self.timer = QTimer()
        self.timer.timeout.connect(self.transmit)
        self.timer.setSingleShot(True)
        self.timer.setInterval(10)
        self.getStateFirstTime = True

        self.lastIter = 0
        self.lastMaxIter = 0

        # maybe get log

    def processMessage(self):
        # key = self.transaction.messageOutput[0]["key"]

        for subkey in self.options.keys():
            if self.transaction.containsAttr(["subkey", subkey]):
                self.options[subkey]()
                return
        self.transaction.stage()

    def _assertConnection(self):
        if self.isConnected:
            return True
        return self._connect()

    def _connect(self):
        if not self.isConnected:
            trans = buildTransaction(self.remote[0], self.remote[1])
            if trans:
                trans.send({"key": Protocol.CONNECTTOSESSION, "uid": self.uid})
                ret = trans.asyncRead(attr=("key", Protocol.CONNECTTOSESSION))
                if ret:
                    if ret["status"]:
                        self.transaction = trans
                        self.isConnected = True
                        self.transaction.socketClosed.connect(self._disconnect)
                        self.transaction.bufferReady.connect(self.processMessage)
                        self.firstConnect = False
                        if not self.firstConnect:
                            self.setState(self.getState(False))
                        return True
                    else:
                        # connected but session not found
                        self._handleErrors(ret["error"])
                        trans.close()
                        return False
                else:
                    # connected but no answer
                    self._handleErrors(["Communication error on connecting to session."])  # TODO better error msg
                    trans.close()
                    return False
            else:
                # can't connect to host
                self._handleErrors(["Host not found"])  # TODO add more info
                return False
        return True

    def _disconnect(self):
        if self.isConnected:
            self.transaction.socketClosed.disconnect()
            self.transaction.bufferReady.disconnect()
            self.transaction.close()
            self.isConnected = False
            self.transaction = None
            self.setState(State.NOTCONNECTED)
            self.getStateFirstTime = True
            self._handleErrors(["Session: Connection to host lost!"])

    def _handleErrors(self, errors):
        for error in errors:
            Log.error(error, self.getCallerId())

    def _printLog(self):
        msg = self.transaction.asyncRead(attr=("subkey", SessionProtocol.PRINTLOG))
        logs = msg["log"]
        for log, error in logs:
            if not isinstance(log, list):
                log = [log]
            # if msg["isError"]:
            if error:
                self._handleErrors(log)
            else:
                for l in log:
                    Log.log(l, self.getCallerId())

    def _updateIter(self):
        msg = self.transaction.asyncRead(attr=("subkey", SessionProtocol.UPDATEITER))
        self.lastIter = msg["iteration"]
        self.iterationChanged.emit()

    def _updateParser(self):
        msg = self.transaction.asyncRead(attr=("subkey", SessionProtocol.UPDATEPARSER))
        phase = msg["phase"]
        row = msg["row"]
        self.lastIter = row["NumIters"]
        self.iterationChanged.emit()
        self.parser.sendParserUpdate(phase, row)
        #TODO plotter

    def _updateParserKeys(self):
        msg = self.transaction.asyncRead(attr=("subkey", SessionProtocol.UPDATEKEYS))
        phase = msg["phase"]
        key = msg["parserkey"]
        self.parser.sendParserRegisterKeys(phase, key)
        # Log.log("Found key: " + key, self.getCallerId())

    def _addSnapshot(self):
        msg = self.transaction.asyncRead(attr=("subkey", SessionProtocol.ADDSNAPSHOT))
        snapshot = msg["snapshot"]
        self.snapshotAdded.emit(snapshot)

    def _parseHandle(self):
        msg = self.transaction.asyncRead(attr=("subkey", SessionProtocol.PARSEHANDLE))
        event = msg["event"]
        message = msg["message"]
        groups = msg["groups"]
        self.parser.sendParserHandle(event, message, groups)

    def getCallerId(self):
        """ Return the unique caller id for this session
        """
        if self.caller_id is None:
            self.caller_id = Log.getCallerId(self._getLogFileName())
        return self.caller_id

    def _getLogFileName(self):
        """ Return the name of the logfile with session id.
        """
        log_file = self.project.getProjectName() + '_' + str(self.getSessionId()) + '.log'
        return log_file

    def getSessionId(self):
        return self.sid

    def checkFiles(self):
        if self._assertConnection():
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.CHECKFILES}
            self.transaction.send(msg)
            ret = self.transaction.asyncRead(staging=True, attr=("subkey", SessionProtocol.CHECKFILES))
            if ret:
                self._handleErrors(ret["error"])
                return
        self._handleErrors(["Failed to connect to remote session to check files."])

    def getSnapshots(self):
        """ Return all snapshot files, keyed by iteration number.
        """
        if self._assertConnection():
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.GETSNAPSHOTS}
            self.transaction.send(msg)
            ret = self.transaction.asyncRead(staging=True, attr=("subkey", SessionProtocol.GETSNAPSHOTS))
            if ret:
                return ret["snapshots"]
        self._handleErrors(["Failed to connect to remote session to acquire Snapshots."])
        return {}

    def getIteration(self):
        # Maybe let this be local + signal
        if self._assertConnection():
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.GETITERATION}
            self.transaction.send(msg)
            ret = self.transaction.asyncRead(staging=True, attr=("subkey", SessionProtocol.GETITERATION))
            if ret:
                self.lastIter = ret["iteration"]
                return self.lastIter
        self._handleErrors(["Failed to connect to remote session to acquire current iteration."])
        return 0

    def getMaxIteration(self):
        if self.lastMaxIter > 0 \
                and self.getState() in [State.RUNNING, State.FAILED, State.FINISHED, State.NOTCONNECTED]:
            return self.lastMaxIter
        elif self._assertConnection():
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.GETMAXITERATION}
            self.transaction.send(msg)
            ret = self.transaction.asyncRead(staging=True, attr=("subkey", SessionProtocol.GETMAXITERATION))
            if ret:
                self.lastMaxIter = ret["iteration"]
                return self.lastMaxIter
        self._handleErrors(["Failed to connect to remote session to acquire max iteration."])
        return 1

    def getPretrainedWeights(self):
        if self._assertConnection():
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.GETPRETRAINED}
            self.transaction.send(msg)
            ret = self.transaction.asyncRead(staging=True, attr=("subkey", SessionProtocol.GETPRETRAINED))
            if ret:
                return ret.get("pretrained", None)
        self._handleErrors(["Failed to connect to remote session to acquire pre-trained weights."])
        return None

    def setMaxIteration(self, maxIteration):
        if maxIteration <= 0:
            return
        if self._assertConnection():
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.SETMAXITERATION, "iteration": maxIteration}
            self.transaction.send(msg)
            self.lastMaxIter = maxIteration
        else:
            self._handleErrors(["Failed to connect to remote session to update max iteration."])
            self.setState(State.NOTCONNECTED, True)

    def delete(self):
        if self._assertConnection():
            msg = {"key": Protocol.DELETESESSION, "uid": self.uid}
            self.transaction.send(msg)
            ret = self.transaction.asyncRead(staging=True, attr=("key", Protocol.DELETESESSION))
            if ret:
                if ret["status"]:
                    self.project.deleteSession.emit(self.getSessionId())
        else:
            self._handleErrors(["Failed to connect to remote session to acquire current state."])
            self.setState(State.NOTCONNECTED, True)

    def close(self):
        if self._assertConnection():
            msg = {"key": Protocol.DISCONNECTSESSION, "uid": self.uid}
            self.transaction.send(msg)

    def reset(self):
        if self._assertConnection():
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.RESET}
            self.transaction.send(msg)
            ret = self.transaction.asyncRead(staging=True, attr=("subkey", SessionProtocol.RESET))
            if ret:
                if ret["status"]:
                    self.iterationChanged.emit()
                    self.project.resetSession.emit(self.getSessionId())
                    return True
                else:
                    self._handleErrors(ret["error"])
        self._handleErrors(["Could not reset session in state " + str(self.getState())])
        return False

    def getState(self, local=True):
        if local and not self.getStateFirstTime:
            return self.state 
        self.getStateFirstTime = False
        if self._assertConnection(): 
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.GETSTATE}
            self.transaction.send(msg)
            ret = self.transaction.asyncRead(staging=True, attr=("subkey", SessionProtocol.GETSTATE))
            if ret:
                if ret["status"]:
                    self.setState(ret["state"], True)
                    return ret["state"]
                    
                else:
                    self._handleErrors(ret["error"])
                    self.setState(State.UNDEFINED, True)
                    return State.UNDEFINED  
        self._handleErrors(["Failed to connect to remote session to acquire current state."])
        self.setState(State.NOTCONNECTED, True)
        return State.NOTCONNECTED

    def setState(self, state, silent=False):
        self.state = state
        if not silent:
            self.stateChanged.emit(self.state)

    def setErrorList(self, errorList):
        self.invalidErrorsList = errorList

    def _updateState(self):
        msg = self.transaction.asyncRead(attr=("subkey", SessionProtocol.UPDATESTATE))
        self.setState(msg["state"])

    def getErrorList(self):
        return self.invalidErrorsList

    def save(self):
        Log.log("Saving current Session status to disk.", self.getCallerId())
        if self._assertConnection():
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.SAVE}
            self.transaction.send(msg)
            ret = self.transaction.asyncRead(attr=("subkey", SessionProtocol.SAVE))
            if ret:
                if ret["status"]:
                    return True
                else:
                    self._handleErrors(ret["error"])
        self._handleErrors(["Could not save session."])
        return False


    def setStateDict(self, stateDict):
        self.lastStateDict = stateDict

        # to prevent subsequent writes, wait until some time passed before sending the statedict
        self.timer.stop()
        self.timer.start()

    def transmit(self):
        if self._assertConnection():
            if not self._validateLayerOrder(self.lastStateDict):
                self._handleErrors(["Warning: layerorder does not match layers"])
                return
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.SETSTATEDICT}
            # remove types for transfer
            transferDict = copy.deepcopy(self.lastStateDict)
            layers = transferDict["network"]["layers"]
            for id in layers:
                del layers[id]["type"]

            msg["statedict"] = transferDict
            self.transaction.send(msg)
            ret = self.transaction.asyncRead(attr=("subkey", SessionProtocol.SETSTATEDICT))
            if ret:
                if not ret["status"]:
                    self._handleErrors(ret["error"])
        else:
            self._handleErrors(["SetStateDict: Failed to send StateDict"])  # TODO improve warnings

        self.stateDictChanged.emit(self, False)

    def _validateLayerOrder(self, dict):
        """There is a fundamental problem in how the setStateDict function is designed.
        In theory there should by only one write one write access.
        But in reality layerorder and the layer itself are writen in subsequent operations.
        this leads to a statedict with a layer in the layerorder, but no corresponding layer in the net.
        thus the save function produces a key error since they iterate over the layerorder.
        simply waiting until the layer is in layerorder and layer solves this problem.
        this function verifies this for all IDs.
        """

        for id in dict["network"]["layerOrder"]:
            if id not in dict["network"]["layers"]:
                return False
        return True

    @property
    def state_dictionary(self):
        if self.lastStateDict is None:
            if self._assertConnection():
                msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.GETSTATEDICT}
                self.transaction.send(msg)
                ret = self.transaction.asyncRead(staging=True, attr=("subkey", SessionProtocol.GETSTATEDICT))
                if ret:
                    if ret["status"]:
                        self.lastStateDict = ret["statedict"]
                        try:
                            layers = self.lastStateDict["network"]["layers"]
                            for id in layers:
                                if "parameters" in layers[id]:
                                    if "type" in layers[id]["parameters"]:
                                        typename = layers[id]["parameters"]["type"]
                                        layers[id]["type"] = info.CaffeMetaInformation().availableLayerTypes()[typename]
                        except KeyError:
                            pass
                        return self.lastStateDict
                    else:
                        self._handleErrors(ret["error"])

        if self.lastStateDict is None:
            return {u'position': {}, u'selection': [], u'hidden_connections': {},
                    u'network': {u'layers': {}, u'name': u'default', u'layerOrder': []},
                    u'solver': {u'net': u'net-internal.prototxt'}}
        return self.lastStateDict

    @state_dictionary.setter
    def state_dictionary(self, value):
        self.setStateDict(value)

    def hasStateDict(self):
        return True

    def checkTraining(self):
        if self._assertConnection():
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.CHECKTRAINING}
            self.transaction.send(msg)
            ret = self.transaction.asyncRead(staging=True, attr=("subkey", SessionProtocol.CHECKTRAINING))
            if ret:
                if ret["status"]:
                    return ret["check"]
                else:
                    self._handleErrors(msg["error"])
                    return [(msg["error"], "")]
            else:
                self._handleErrors(["CheckTraining: Did not receive a reply from host."])
                return [("CheckTraining: Did not receive a reply from host.", "No reply from host")]
        else:
            self._handleErrors(["CheckTraining: Failed to connect to host to check session validity!"])
            return [("CheckTraining: Failed to connect to host to check session validity!", "Failed to connect")]

    def start(self, solverstate=None, caffemodel=None):
        if self._assertConnection():
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.START}
            if solverstate is not None:
                msg["solverstate"] = solverstate
            if caffemodel is not None:
                msg["caffemodel"] = caffemodel
            self.transaction.send(msg)
            ret = self.transaction.asyncRead(staging=True, attr=("subkey", SessionProtocol.START))
            if ret:
                if ret["status"]:
                    return True
                else:
                    self._handleErrors(ret["error"])
        self._handleErrors(["Could not start session in state " + str(self.getState())])
        return False

    def pause(self):
        if self._assertConnection():
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.PAUSE}
            self.transaction.send(msg)
            ret = self.transaction.asyncRead(staging=True, attr=("subkey", SessionProtocol.PAUSE))
            if ret:
                if ret["status"]:
                    self.iterationChanged.emit()
                    return True
                else:
                    self._handleErrors(ret["error"])
        self._handleErrors(["Could not pause session in state " + str(self.getState())])
        return False

    def snapshot(self):
        if self._assertConnection():
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.TAKESNAPSHOT}
            self.transaction.send(msg)
            ret = self.transaction.asyncRead(staging=True, attr=("subkey", SessionProtocol.TAKESNAPSHOT))
            if ret:
                if ret["status"]:
                    return True
                else:
                    self._handleErrors(ret["error"])
        self._handleErrors(["Could not take snapshot of session in state " + str(self.getState())])
        return False

    def proceed(self, snapshot=None):
        # TODO snapshot
        if self._assertConnection():
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.PROCEED}
            if snapshot is not None:
                msg["snapshot"] = snapshot
                print "proceed with snapshot", msg
            self.transaction.send(msg)
            ret = self.transaction.asyncRead(staging=True, attr=("subkey", SessionProtocol.PROCEED))
            if ret:
                if ret["status"]:
                    return True
                else:
                    self._handleErrors(ret["error"])
        self._handleErrors(["Could not proceed session in state " + str(self.getState())])
        return False

    def getParser(self):
        return self.parser

    def getLogFileName(self, basename=False):
        if basename:
            return self.project.getProjectName() + "_" + str(self.sid) + ".log"
        else:
            print "There is no 'getLogFileName' for clientsessions!"
            return None

    def getLogId(self):
        return self.uid

    def isRemote(self):
        return True

    def fetchParserData(self):
        if self._assertConnection() and self.transaction is not None:
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.FETCHPARSERDATA}
            self.transaction.send(msg)
            ret = self.transaction.asyncRead(staging=True, attr=("subkey", SessionProtocol.FETCHPARSERDATA))
            if ret:
                if ret["status"]:
                    parserRows = ret["ParserRows"]
                    parserKeys = ret["ParserKeys"]
                    parserHandle = ret["ParserHandle"]
                    parserLog = ret["ParserLogs"]

                    for phase, key in parserKeys:
                        self.parser.sendParserRegisterKeys(phase, key)

                    for phase, row in parserRows:
                        self.parser.sendParserUpdate(phase, row)

                    for event, line, groups in parserHandle:
                        self.parser.sendParserHandle(event, line, groups)

                    for log, error in parserLog:
                        if error:
                            Log.error(log, self.getCallerId())
                        else:
                            Log.log(log, self.getCallerId())


                    return
                else:
                    self._handleErrors(ret["error"])
        self._handleErrors(["Failed to fetch parser data from host."])

    def readInternalNetFile(self):
        """ Returns the contents of the internal net prototxt file.

        Wrapper around loadInternalNetFile, to provide a coherent interface
        together with the Session class.
        """
        return self.loadInternalNetFile()

    def readDeployedNetAsString(self):
        """ Returns the contents of the deployable net prototxt file.

        Wrapper around loadDeployedNetFile, to provide a coherent interface
        together with the Session class.
        """
        return self.loadDeployedNetAsString()

    def readCaffemodelFile(self, snapshot):
        """ Returns the contents of the .caffemodel file that belongs to snapshot.

        snapshot: string
            Filename without path of the snapshot file.
        """
        return self.loadCaffemodel(snapshot)

    def loadInternalNetFile(self):
        if self._assertConnection():
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.LOADINTERNALNET}
            self.transaction.send(msg)
            ret = self.transaction.asyncRead(staging=True, attr=("subkey", SessionProtocol.LOADINTERNALNET))
            if ret:
                if ret["status"]:
                    return ret["NetInternal"]
                else:
                    self._handleErrors(ret["error"])
        self._handleErrors(["Failed to load InternalNet Prototxt"])
        return ""

    def loadDeployedNetAsString(self):
        if self._assertConnection():
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.LOADDEPLOYEDNET}
            self.transaction.send(msg)
            ret = self.transaction.asyncRead(staging=True, attr=("subkey", SessionProtocol.LOADDEPLOYEDNET))
            if ret:
                if ret["status"]:
                    return ret["Net"]
                else:
                    self._handleErrors(ret["error"])
        self._handleErrors(["Failed to load Deployed Net"])
        return ""

    def loadNetParameter(self, snapshot):
        if self._assertConnection():
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.LOADNETPARAMETER}
            msg["snapshot"] = snapshot
            self.transaction.send(msg)
            ret = self.transaction.asyncRead(staging=True, attr=("subkey", SessionProtocol.LOADNETPARAMETER))
            if ret:
                if ret["status"]:
                    net = ret["NetParams"]
                    net = loadNetParamFromString(net)
                    if net is not None:
                        return net
                    else:
                        self._handleErrors(["Failed to load " + str(snapshot),
                                    "HDF5 snapshot format is not supported for weight "
                                    "visualization. This can be changed by setting the "
                                    "snapshot_format in the solver properties."])

                else:
                    self._handleErrors(ret["error"])
        self._handleErrors(["Failed to load NetParameter for snapshot '" + snapshot + "'"])
        return None

    def getCaffemodelContents(self, snapshot):
        """ Wrapper around the loadCaffemodel function to provide a coherent interface
        between local and remote sessions. """
        return self.loadCaffemodel(snapshot)

    def loadCaffemodel(self, snapshot):
        """ Loads the contents of the caffemodel file belonging to the given snapshot
        from the server. """
        if self._assertConnection():
            msg = {"key": Protocol.SESSION, "subkey": SessionProtocol.LOADCAFFEMODEL}
            msg["snapshot"] = snapshot
            self.transaction.send(msg)
            ret = self.transaction.asyncRead(staging=True, attr=("subkey", SessionProtocol.LOADCAFFEMODEL))
            if ret:
                if ret["status"]:
                    return ret["caffemodel"]
                else:
                    self._handleErrors(ret["error"])
        self._handleErrors(["Failed to load caffemodel contents for snapshot '" + snapshot + "'"])
        return None
