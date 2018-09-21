import os
import re
import shutil
import signal
import time
import json
import copy
from subprocess import Popen, PIPE, STDOUT
from threading import Lock
from datetime import datetime

from PyQt5.Qt import QObject
from PyQt5.QtCore import pyqtSignal

from backend.parser.concatenator import Concatenator
from backend.parser.parser_listener import ParserListener
from backend.parser.parser import Parser

from backend.barista.constraints.session_run.training import checkMinimumTrainingRequirements
from backend.barista.session.session_pool import SessionPool
from backend.barista.session.session_utils import *
from backend.barista.utils.logger import Log
from backend.barista.utils.logger import LogCaller
from backend.barista.deployed_net import DeployedNet

from backend.barista.session.session_common import SessionCommon

import backend.caffe.saver as saver
import backend.caffe.proto_info as info
import backend.caffe.dict_helper as helper

import backend.barista.caffe_versions as caffeVersions


class Session(QObject, LogCaller, ParserListener, SessionCommon):
    """ A session is a caffe training process.

    Objects of this class encapsulate the state of a process, control the
    process (starting, pausing etc.), handle events and provide the session
    output stream.
    """

    # event signals
    stateChanged = pyqtSignal(object)
    stateDictChanged = pyqtSignal(object, bool)
    iterationChanged = pyqtSignal()
    snapshotAdded = pyqtSignal(object)

    def __init__(self, project, directory=None, sid=None, parse_old=False, caffe_bin=None,
                 last_solverstate=None, last_caffemodel=None, state_dictionary=None):
        super(Session, self).__init__()
        self.caller_id = None
        self.state = State.UNDEFINED
        self.invalidErrorsList = []
        self.sid = sid
        self.directory = directory
        self.rid = 0
        self.project = project
        self.logs = None
        if self.directory is None:
            if self.sid is None:
                raise ValueError('Either directory or sid must be provided to create a session.')
            self.directory = self.__createSessionDirectoryName()
            self.logs = os.path.join(self.directory, 'logs')
        else:
            self.logs = os.path.join(directory, 'logs')
            dir_sid, self.rid = self.__parseSessionId()
            if self.sid is None:
                self.sid = dir_sid
            else:
                Log.log('Provided sid and directory do not match ('+str(self.sid) + ' vs. ' + str(dir_sid) + '), ' +
                        'provided sid is used.', self.getCallerId())

        self.parse_old = parse_old
        self.caffe_bin = caffe_bin  # overrides project caffe_root if necessary, i.e. if deployed to another system
        self.pretrainedWeights = None
        
        self.last_solverstate = last_solverstate
        self.last_caffemodel = last_caffemodel
        self.state_dictionary = state_dictionary  # state as saved from the network manager, such it can be restored

        self.start_time = self.__parseStartTime()

        self.snapshot_dir = None
        self.snapshot_prefix = None
        self.proc = None
        self.tee = None
        self.parser = None
        self.iteration = 0
        self.max_iter = 1
        self.parser_initialized = False

        self.__getSettingsFromSessionFile()

        if self.state_dictionary is not None:
            self.__parseSettings(self.state_dictionary)

        self.__solverFile = os.path.join(self.directory, Paths.FILE_NAME_SOLVER)
        self.__netInternalFile = os.path.join(self.directory, Paths.FILE_NAME_NET_INTERNAL)
        self.__netOriginalFile = os.path.join(self.directory, Paths.FILE_NAME_NET_ORIGINAL)

        self.lock = Lock()
        self.getSnapshotDirectory()

    # comparison methods for the priorization of sessions in the thread pool

    def __lt__(self, other):
        if type(other) is not Session:
            return True
        return other.sid - self.sid < 0

    def __gt__(self, other):
        if type(other) is not Session:
            return False
        return other.sid - self.sid > 0

    def __eq__(self, other):
        if type(other) is not Session:
            return False
        return other.sid - self.sid == 0

    def __le__(self, other):
        if type(other) is not Session:
            return True
        return other.sid - self.sid <= 0

    def __ge__(self, other):
        if type(other) is not Session:
            return False
        return other.sid - self.sid >= 0

    def __ne__(self, other):
        if type(other) is not Session:
            return True
        return other.sid - self.sid != 0

    def __createSessionDirectoryName(self):
        """ Return a new session directory with the format YYYYMMDD_hh24mmss_SID
        """
        directory = self.__getDateTimeString()
        directory += '_'+str(self.sid)
        return os.path.join(self.project.getSessionsDirectory(), directory)

    def __ensureDirectory(self, directory):
        """ Creates a directory if it does not exist.
        """
        if directory == '':
            return
        if os.path.exists(directory) is False:
            try:
                os.makedirs(directory)
                Log.log('Created directory: ' + directory, self.getCallerId())
            except Exception as e:
                Log.error('Failed to create directory '+directory+')'+str(e),
                          self.getCallerId())

    def __getSettingsFromSessionFile(self):
        filename = os.path.join(self.directory, baristaSessionFile(self.directory))
        if os.path.isfile(filename):
            with open(filename, 'r') as f:
                res = json.load(f)
                self.__parseSettings(res)

    def checkFiles(self):
        """ Check for the existence of the session directories and files.
        """
        if os.path.exists(self.directory) is False:
            Log.error('Session directory does not exists: '+self.directory,
                      self.getCallerId())
        if os.path.exists(self.logs) is False:
            Log.error('Log directory does not exists: '+self.logs,
                      self.getCallerId())
        if os.path.exists(self.snapshot_dir) is False:
            Log.error('Snapshot directory does not exists: '+self.snapshot_dir,
                      self.getCallerId())
        if os.file.exists(caffeVersions.getVersionByName(self.project.getCaffeVersion())) is False:
            Log.error('Caffe binary does not exists: ' +
                      self.project.getCaffeVersion(),
                      self.getCallerId())


    def __parseSnapshotPrefix(self):
        """ Parse the snapshot prefix from the solver file.
        """
        if self.snapshot_prefix is None:
            sf = os.path.join(self.getDirectory(), self.getSolver())
            if os.path.isfile(sf):
                self.snapshot_prefix = self.project.parseSnapshotPrefixFromFile(sf)
        return

    def getSnapshotPrefix(self):
        """ Return the snapshot prefix which is used for snapshots of this
        session.
        """
        if not self.snapshot_prefix:
            self.__parseSnapshotPrefix()
        if not self.snapshot_prefix:
            self.snapshot_prefix = ''

        return self.snapshot_prefix

    def getSnapshotExtension(self):
        """ Return the file name extension for snapshot files.
        The extensions differ between binaryproto and hdf5 formats.
        """
        extension = None
        if self.last_caffemodel:
            # try to parse the extension from the last_caffemodel
            regex_snapshot = re.compile('(\.caffemodel[\.\w-]*)')
            snapshot_match = regex_snapshot.search(self.last_caffemodel)
            if snapshot_match:
                return snapshot_match.group(1)
        else:
            # try to parse the suffix from the last_solverstate
            extension = self.getLastSnapshot()
            if extension:
                regex_snapshot = re.compile('\.solverstate([\.\w-]*)')
                snapshot_match = regex_snapshot.search(extension)
                if snapshot_match:
                    ext = snapshot_match.group(1)
                    if ext:
                        # append suffix
                        return '.caffemodel' + ext
        return '.caffemodel'

    def getSolverstateExtension(self):
        """ Return the file name extension for solverstate files.
        The extensions differ between binaryproto and hdf5 formats.
        """
        extension = self.getLastSnapshot()
        if extension:
            regex_snapshot = re.compile('(\.solverstate[\.\w-]*)')
            snapshot_match = regex_snapshot.search(extension)
            if snapshot_match:
                return snapshot_match.group(1)
        return '.solverstate'

    def getState(self):
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
            elif len(self.getSnapshots()) > 0:
                self.state = State.PAUSED
            else:
                self.state = State.WAITING
        return self.state

    def getErrorList(self):
        return self.invalidErrorsList

    def setState(self, state):
        """ Set the state of the session and emit a stateChanged signal.
        """
        self.state = state
        self.stateChanged.emit(self.state)


    def setErrorList(self, errorList):
        self.invalidErrorsList = errorList

    def setStateDict(self, stateDict):
        self.state_dictionary = stateDict
        self.stateDictChanged.emit(self, False)

        return


    def getSessionId(self):
        """ Return the id of the session.
        """
        return self.sid

    def getRunId(self):
        """ Return the run id of the session.

        This id increases every time the process is started/proceeded.
        It enables the user to distinguish between different runs of the
        session.
        """
        return self.rid

    def start(self, solverstate=None, caffemodel=None):
        """ Start the process.

        Return
            True if the process was started
            False if the start failed
        """
        if self.getState() is State.WAITING:
            self.rid += 1
            # (re-)write all session files
            self.save(includeProtoTxt=True)
            # check if the session has its own caffeRoot
            caffeBin = self.caffe_bin
            if not caffeBin:
                # else take the project's caffeRoot path
                caffeBin = caffeVersions.getVersionByName(self.project.getCaffeVersion()).getBinarypath()

            try:
                self.getParser().setLogging(True)

                cmd = [caffeBin,
                    'train',
                    '-solver', self.getSolver()]
                if solverstate:
                    cmd.append('-snapshot')
                    cmd.append(str(solverstate))
                elif caffemodel:
                    cmd.append('-weights')
                    cmd.append(str(caffemodel))
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
                    # continue without tee
                    Log.error('Failed to start tee: '+str(e),
                              self.getCallerId())
                self.setState(State.RUNNING)
                Log.log('Session '+self.getRunLogFileName(True) +
                        ' was started', self.getCallerId())
                self.__startParsing()
                return True
            except Exception as e:
                # check if caffe root exists
                Log.error('Failed to start session: '+str(e),
                          self.getCallerId())
                if os.file.exists(caffeVersions.getVersionByName(self.project.getCaffeVersion()).getBinarypath()) is False:
                    Log.error('CAFFE_BINARY directory does not exists: ' +
                              caffe_bin +
                              '! Please set CAFFE_BINARY to run a session.',
                              self.getCallerId())
        else:
            Log.error(
                'Could not start a session in state '+str(self.getState()),
                self.getCallerId())
            # self.setState(State.UNDEFINED)
        return False

    def pause(self):
        """ Pause the process.

        Return
            True if the process was paused
            False if the pause failed
        """
        if self.getState() is State.RUNNING:
            if self.proc:
                self.snapshot()
                # give the caffe process a second to save the state
                time.sleep(1)
                try:
                    if self.proc:
                        self.proc.kill()
                except Exception as e:
                    Log.error('Pausing session failed: '+str(e))
                try:
                    if self.tee:
                        self.tee.kill()
                except Exception:
                    pass
                self.proc = None
                self.tee = None
                self.last_solverstate = None
                snap = self._getLastSnapshotFromSnapshotDirectory()
                if snap is not None:
                    self.last_solverstate = os.path.basename(self._getLastSnapshotFromSnapshotDirectory())
                    regex_iter = re.compile('iter_([\d]+)\.solverstate[\.\w-]*$')
                    iter_match = regex_iter.search(self.last_solverstate)
                    if iter_match:
                        self.iteration = int(iter_match.group(1))
                    self.iterationChanged.emit()
                    self.setState(State.PAUSED)
                    Log.log('Session ' + self.getRunLogFileName(True) +
                            ' was paused', self.getCallerId())
                else:
                    self.setState(State.WAITING)
                    Log.log('Session ' + self.getRunLogFileName(True) +
                            ' was halted', self.getCallerId())
                self.save()
                return True
            else:
                Log.error(
                    'Could not pause a session in state '+str(self.getState()),
                    self.getCallerId())
                self.setState(State.UNDEFINED)
        return False

    def proceed(self, snapshot=None):
        """ Continue training from the (last) snapshot.

        Return
            True if the process was continued
            False if the continuation failed
        """
        if self.getState() is State.PAUSED:
            self.__ensureDirectory(self.getSnapshotDirectory())
            self.__ensureDirectory(self.logs)

            if snapshot is None:
                snapshot = self.getLastSnapshot()
            self.rid += 1
            try:
                self.getParser().setLogging(True)
                self.proc = Popen([
                        caffeVersions.getVersionByName(self.project.getCaffeVersion()).getBinarypath(),
                        'train',
                        '-solver', self.getSolver(),
                        '-snapshot', snapshot],
                    stdout=PIPE,
                    stderr=STDOUT,
                    cwd=self.getDirectory())
                try:
                    self.tee = Popen(
                        ['tee', '-a', self.getRunLogFileName()],
                        stdin=self.proc.stdout,
                        stdout=PIPE)
                except Exception as e:
                    # continue without tee
                    Log.error('Failed to start tee: '+str(e),
                              self.getCallerId())
                self.setState(State.RUNNING)
                Log.log('Session '+self.getRunLogFileName(True) +
                        ' was proceeded', self.getCallerId())
                self.__startParsing()
                return True
            except Exception as e:
                # check if caffe root exists
                Log.error('Failed to continue session: '+str(e),
                          self.getCallerId())
                if os.file.exists(caffeVersions.getVersionByName(self.project.getCaffeVersion()).getBinarypath()) is False:
                    Log.error('CAFFE_BINARY directory does not exists: ' +
                        caffe_bin +
                        '! Please set CAFFE_BINARY to run a session.',
                        self.getCallerId())
        elif self.getState() in (State.FAILED, State.FINISHED):
            Log.error('Could not continue a session in state ' +
                      str(self.getState()), self.getCallerId())
        return False

    def snapshot(self):
        """ Create a snapshot from the training state.

        Return
            True if the snapshot was created
            False if the snapshot could not be created
        """
        if self.getState() is State.RUNNING:
            if self.proc:
                self.last_solverstate = None
                try:
                    self.proc.send_signal(signal.SIGHUP)
                except Exception as e:
                    Log.error('Failed to take snapshot: '+str(e),
                              self.getCallerId())
                    return False
                Log.log('Snapshot was saved for session ' +
                        self.getRunLogFileName(True)+'', self.getCallerId())
                return True
            else:
                Log.error(
                    'Could not take a session snapshot in state ' +
                    str(self.getState()),
                    self.getCallerId())
        return False

    def setFinished(self):
        """ Mark this session as finished.
        """
        self.save()
        self.setState(State.FINISHED)
        self.proc = None

    def getStream(self):
        """ Return the log stream of this session.
        This is an iterator over stdout of the subprocess.
        """
        if self.tee:
            return iter(self.tee.stdout.readline, '')
        if self.proc:
            return iter(self.proc.stdout.readline, '')
        return iter([])

    def getDirectory(self):
        """ Return the session directory, usually a directory of the form
        YYYYMMDD_hh24mmss_SID.
        """
        return self.directory

    def getLogs(self):
        """ Return the log directory.
        """
        if os.path.exists(self.logs) is False:
            os.makedirs(self.logs)
        return self.logs

    def isRemote(self):
        return False

    def getSnapshotDirectory(self):
        """ Return the snapshot directory.
        """
        if self.snapshot_dir:
            return self.snapshot_dir
        snapshot_prefix = self.getSnapshotPrefix()
        sdir = os.path.dirname(snapshot_prefix)
        self.snapshot_dir = os.path.join(self.getDirectory(), sdir)
        return self.snapshot_dir

    def getSnapshots(self):
        """ Return all snapshot files, keyed by iteration number.
        """
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

    def getLastModel(self):
        """ Return the name of the last saved caffe model.
        """
        return self.last_caffemodel

    def setLastModel(self, lcm):
        self.last_caffemodel = lcm

    def getPretrainedWeights(self):
        return self.pretrainedWeights

    def setPretrainedWeights(self, weights):
        self.pretrainedWeights = weights

    def setLastSnapshot(self, lss):
        self.last_solverstate = lss

    def getSolver(self, log=False):
        """ Returns the solver prototxt file name.
        When the log flag is set, a message will be sent to the logger console if the file does not exist.
        """
        if log:
            if not os.path.isfile(self.__solverFile):
                Log.log("This sessions Solverfile: " + self.__solverFile + " does not exist.", self.caller_id)
        return self.__solverFile

    def getOriginalNetFile(self, log=False):
        """ Returns the original net prototxt file name.
        When the log flag is set, a message will be sent to the logger console if the file does not exist.
        """
        if log:
            if not os.path.isfile(self.__netOriginalFile):
                Log.log("This sessions net file: " + self.__netOriginalFile + " does not exist.", self.caller_id)
        return self.__netOriginalFile

    def getInternalNetFile(self, log=False):
        """ Returns the original net prototxt file name.
        When the log flag is set, a message will be sent to the logger console if the file does not exist.
        """
        if log:
            if not os.path.isfile(self.__netInternalFile):
                Log.log("This sessions net file: " + self.__netInternalFile + " does not exist.", self.caller_id)
        return self.__netInternalFile

    def readInternalNetFile(self):
        """ Returns the contents of the internal net prototxt file. """
        path = self.getInternalNetFile()
        with open(path, 'r') as f:
            contents = f.read()
        return contents

    def readDeployedNetAsString(self):
        """ Returns the contents of the deployable net prototxt file. """
        path = self.getInternalNetFile()
        dn = DeployedNet(open(path).read())
        return dn.getProtoTxt()

    def readCaffemodelFile(self, snapshot):
        """ Returns the contents of the .caffemodel file that belongs to snapshot.

        snapshot: string
            Filename without path of the snapshot file.
        """
        path = os.path.join(self.getSnapshotDirectory(), snapshot)
        with open(path, 'r') as f:
            contents = f.read()
        return contents

    def getRunLogFileName(self, basename=False):
        """ Return the name of the logfile with session and run id.
        """
        log_file = self.project.getProjectName()+'_'+str(self.getSessionId())+'.'+str(self.getRunId())+'.log'
        if basename is True:
            return log_file
        log_file = os.path.join(self.getLogs(), log_file)
        return log_file

    def getLogFileName(self, basename=False):
        """ Return the name of the logfile with session id.
        """
        log_file = self.project.getProjectName()+'_'+str(self.getSessionId())+'.log'
        if basename is True:
            return log_file
        log_file = os.path.join(self.getLogs(), log_file)
        return log_file

    def getLogId(self):
        """ Return the id of the logfile. For local sessions same as the name of the logfile.
        """
        return self.getLogFileName(True)

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
                        Log.error('Failed to parse log file '+self.getLogFileName(True)+": "+str(e), self.getCallerId())
        except Exception as e:
            Log.error('Failed to parse old log '+str(e), self.getCallerId())
        finally:
            if locked:
                self.lock.release()

    def __startParsing(self):
        """ Create a parser and run it in a newly dispatched thread.
        """
        self.parseOldLogs()
        logs = self.getStream()
        self.getParser().addLogStream(logs)
        pool = SessionPool()
        pool.addSession(self)

    def getParser(self):
        """ Return the log parser of this session.
        """
        if self.parser is None:
            self.parser = Parser(None, Events.events, self.getCallerId())
            self.parser.addListener(self)
        return self.parser

    def getIteration(self):
        """ Return the current training iteration of this session.
        """
        return self.iteration

    def getMaxIteration(self):
        """ Return the maximum training iteration of this session.
        """
        return self.max_iter

    def setMaxIteration(self, maxIteration):
        """ Set the maximum training iteration of this session.
        """
        if maxIteration > 0:
            self.max_iter = maxIteration
        self.stateChanged.emit(self.getState())

    def setParserInitialized(self):
        """ Should be called after the parser finished the inital parsing of
        log files.
        """
        #if self.parser_initialized is False:
        #    self.snapshotAdded.emit(self.last_solverstate)
        self.parser_initialized = True

    def isParserInitialized(self):
        return self.parser_initialized

    def delete(self):
        """ Delete the session directory and disconnect signals.
        """
        self.pause()
        try:
            shutil.rmtree(self.getDirectory())
        except Exception as e:
            Log.error('Could not remove session directory: '+str(e),
                      self.getCallerId())
        try:
            self.stateChanged.disconnect()
            self.iterationChanged.disconnect()
            self.snapshotAdded.disconnect()
            self.project.deleteSession.emit(self.sid)
        except Exception as e:
            pass
        Log.removeCallerId(self.caller_id, False)

    # LogCaller

    def getCallerId(self):
        """ Return the unique caller id for this session
        """
        if self.caller_id is None:
            self.caller_id = Log.getCallerId(self.getLogFileName(True))
        return self.caller_id

    # ParserListener

    def update(self, phase, row):
        """ Called when the parser has parsed a new record.
        """
        self.iteration = row['NumIters']
        self.iterationChanged.emit()

    def handle(self, event, message, groups):
        """ Called when the parser has parsed a registered event.
        """
        if event == 'OptimizationDone':
            self.setFinished()
        elif event == 'max_iter':
            self.max_iter = int(groups[0])
        elif event == 'state_snapshot':
            self.last_solverstate = groups[0]
            #if self.parser_initialized:
            self.snapshotAdded.emit(self.last_solverstate)
        elif event == 'model_snapshot':
            self.last_caffemodel = groups[0]

    def parsingFinished(self):
        """ Called when the parser has processed all available streams.
        """

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
                Log.error('Session failed with return code '+str(rcode),
                          self.getCallerId())


        self.setParserInitialized()

    def hasStateDict(self):
        return self.state_dictionary is not None

    def save(self, includeProtoTxt = False):
        """Saves the current session to a json file. If includeProtoTxt is True, prototxt files are saved as well."""
        toSave = {"SessionState": self.state, "Iteration": self.iteration, "MaxIter": self.max_iter}
        toSave["ProjectID"] = self.project.projectId

        self.__ensureDirectory(self.directory)
        Log.log("Saving current Session status to disk.", self.getCallerId())
        if self.last_solverstate:
            toSave["LastSnapshot"] = self.last_solverstate
        if self.getPretrainedWeights():
            toSave["PretrainedWeights"] = self.getPretrainedWeights()
        if self.state_dictionary:
            serializedDict = copy.deepcopy(self.state_dictionary)
            if includeProtoTxt:
                if "solver" in self.state_dictionary:
                    solver = self.buildSolverPrototxt()
                    with open(self.getSolver(log=False), 'w') as f:
                        f.write(solver)
                else:
                    Log.error("Could not save a solver prototxt file, because no solver settings are defined.", self.getCallerId())

            if "network" in serializedDict:
                if includeProtoTxt:
                    net = self.buildNetPrototxt(internalVersion=False)
                    with open(self.getOriginalNetFile(log=False), 'w') as f:
                        f.write(net)
                    net = self.buildNetPrototxt(internalVersion=True)
                    with open(self.getInternalNetFile(log=False), 'w') as f:
                        f.write(net)
                if "layers" in serializedDict["network"]:
                    layers = serializedDict["network"]["layers"]
                    for id in layers:
                        del layers[id]["type"]
            else:
                Log.error("Could not save the network state because no state was defined.", self.getCallerId())

            toSave["NetworkState"] = serializedDict

        with open(baristaSessionFile(self.directory), "w") as f:
            json.dump(toSave, f, sort_keys=True, indent=4)

    def _modifyNetDictionaryToInternalVersion(self, net):
        """ Take an original net dictionary and apply all changes necessary for
        the internal version.

        Mainly, this will change all relative paths to be relative to a session
        folder.
        Hint: This will change net itself. You might want to create a (deep)
        copy of the dictionary before calling this method.
        """
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
                            newPath = os.path.join(
                                os.pardir,
                                os.path.join(os.pardir, paramValue)
                            )
                        else:
                            newFilename = str(layerId) + ".txt"
                            newPath = os.path.join(os.curdir, newFilename)

                        h.setLayerParameter(layerId, paramKey, newPath)

        return net

    def buildSolverPrototxt(self):
        """ Load the current solver dictionary and return the corresponding
        message object.

        :return: A solver message object.
        """

        if not self.state_dictionary:
            return None
        elif "solver" not in self.state_dictionary:
            return None
        else:
            solver = saver.saveSolver(self.state_dictionary["solver"])
            return solver

    def buildNetPrototxt(self, internalVersion=False):
        """ Load the current net dictionary and return the corresponding
        message object.

        :param internalVersion: Iff true, the loaded net will be modified to
        the internal version.
        :return: A net message object.
        """

        currentState = self.state_dictionary
        netDictionary = None
        if currentState:
            netDictionary = currentState["network"]

        if internalVersion:
            netDictionary = self._modifyNetDictionaryToInternalVersion(copy.deepcopy(netDictionary))

        solver = saver.saveNet(netDictionary)
        return solver

    def __parseSettings(self, settings):
        if settings:
            if "SessionState" in settings:
                self.state = settings["SessionState"]
                self.__previousState = self.state

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
                self.setPretrainedWeights(settings["PretrainedWeights"])

            if "NetworkState" in settings:
                self.state_dictionary = settings["NetworkState"]
                layers = self.state_dictionary["network"]["layers"]
                for id in layers:
                    if "parameters" in layers[id]:
                        if "type" in layers[id]["parameters"]:
                            typename = layers[id]["parameters"]["type"]
                            layers[id]["type"] = info.CaffeMetaInformation().getLayerType(typename)
                            # layers[id]["type"] = info.CaffeMetaInformation().availableLayerTypes()[typename]
                solver = self.state_dictionary["solver"]
                if solver:
                    if "snapshot_prefix" in solver:
                        self.snapshot_prefix = solver["snapshot_prefix"]

    def updateMaxIterFromStateDict(self):
        if self.state_dictionary:
            if "solver" in self.state_dictionary:
                if "max_iter" in self.state_dictionary["solver"]:
                    self.max_iter = self.state_dictionary["solver"]["max_iter"]
            elif "MaxIter" in self.state_dictionary:
                self.max_iter = self.state_dictionary["MaxIter"]

    def __parseSessionId(self):
        """ Return a tuple (session_id, run_id). The ids are parsed from the
        directory. session_id is the id of the session and run_id the highest
        found run id.
        """
        regex_sid = re.compile('[\d]{8}_[\d]{6}_([\d]+)')
        sid_match = regex_sid.search(self.directory)
        session_id = None
        if sid_match:
            try:
                session_id = int(sid_match.group(1))
            except:
                pass
        run_id = 0
        regex_rid = re.compile('([\d]+)\.([\d]+)\.log')
        if os.path.exists(self.logs):
            for entry in os.listdir(self.logs):
                rid_match = regex_rid.search(entry)
                if rid_match:
                    try:
                        _run_id = int(rid_match.group(2))
                        if run_id:
                            if _run_id > run_id:
                                run_id = _run_id
                        else:
                            run_id = _run_id
                        if session_id is None:
                            session_id = int(rid_match.group(1))
                    except:
                        pass
        return session_id, run_id

    def __parseStartTime(self):
        """ Parse the start time with second precision from the directory name.

        Return the parsed datetime.
        """
        regex_time = re.compile(
            '([\d]{4})([\d]{2})([\d]{2})_([\d]{2})([\d]{2})([\d]{2})')
        time_match = regex_time.search(self.directory)
        time = datetime.now()
        if time_match:
            try:
                year = int(time_match.group(1))
                month = int(time_match.group(2))
                day = int(time_match.group(3))
                hour = int(time_match.group(4))
                minute = int(time_match.group(5))
                second = int(time_match.group(6))
                time = time.replace(year=year, month=month, day=day, hour=hour,
                                    minute=minute, second=second)
            except Exception:
                pass
        return time

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

    def reset(self):
        self.pause()
        for dirpath, dirnames, filenames in os.walk(self.directory, topdown=True):
            for dirname in dirnames:
                if os.path.join(dirpath, dirname) == self.logs:
                    try:
                        shutil.rmtree(self.logs)
                    except shutil.Error as e:
                        Log.error('Failed to delete logs folder: ' + str(e), self.getCallerId())
            for filename in filenames:
                if filename.endswith(".solverstate") or filename.endswith(".caffemodel"):
                    if not filename == self.getPretrainedWeights():
                        try:
                            os.remove(os.path.join(dirpath, filename))
                        except OSError as e:
                            Log.error('Failed to delete ' + str(filename) + ': ' + str(e), self.getCallerId())
                if filename in ["net-internal.prototxt", "net-original.prototxt", "solver.prototxt"]:
                    try:
                        os.remove(os.path.join(dirpath, filename))
                    except OSError as e:
                        Log.error('Failed to delete ' + str(filename) + ': ' + str(e), self.getCallerId())
            break
        self.iteration = 0
        self.iterationChanged.emit()
        self.state = State.UNDEFINED
        self.setState(self.getState())
        self.setLastModel(None)
        self.setLastSnapshot(None)
        self.project.resetSession.emit(self.getSessionId())
        self.save()