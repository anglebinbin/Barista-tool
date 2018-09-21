import os
import sys
import logging

from PyQt5.QtCore import QFileInfo, QDirIterator, QDateTime, QRegExp, pyqtSignal
from PyQt5.QtCore import QTimer

from backend.networking.transaction import Transaction
from gui.input_manager.database_object import DatabaseObject
from backend.networking.protocol import Protocol
import backend.barista.caffe_versions as caffeVersions
import backend.barista.hash as Hash
import backend.barista.utils.db_util as db_util

class ServerTransaction(Transaction):
    def __init__(self, parent):
        self.options = {
            Protocol.ECHO: self.msgEcho,
            Protocol.RESTART: self.restart,

            Protocol.GETDIR: self.getDir,
            Protocol.GETSTATUS: self._getBaristaStatus,
            Protocol.GETDBSTATUS: self._getDBStatus,

            Protocol.MAKEPATHRELATIVE: self._makeRelative,
            Protocol.MAKEHDF5TXT: self._makeHDF5Txt,
            Protocol.ADDHDF5: self._addHdf5,
            Protocol.GETFILECONTENT: self._getFileContent,
            Protocol.WRITEFILECONTENT: self._writeFileContent,
            Protocol.GETHASH: self._getHash,

            Protocol.GETHARDWARE: self._getHardware,
            Protocol.SCANHARDWARE: self._scanHardware,
            Protocol.SETHARDWARE: self._setHardware,
            Protocol.GETPLATFORM: self._getPlatform,

            Protocol.CREATESESSION: self._createSession,
            Protocol.CONNECTTOSESSION: self._connectToSession,
            Protocol.GETSESSIONS: self._getSessions,
            Protocol.DELETESESSION: self._deleteSession,
            Protocol.SESSION: self._doNothing,
            Protocol.CLONESESSION: self._cloneSession,
            Protocol.DISCONNECTSESSION: self._disconnectSession,
            Protocol.SESSION: self._doNothing,

            Protocol.GETCAFFEVERSIONS: self._getCaffeVersions,
            Protocol.ADDCAFFEVERSION: self._addCaffeVersion,
            Protocol.SETCURRENTCAFFEVERSION: self._setCurrentCaffeVersion,
            Protocol.REMOVECAFFEVERSION: self._removeCaffeVersion,
            Protocol.GETDEFAULTCAFFEVERSION: self._getDefaultCaffeVersion,
            Protocol.GETCAFFERESTART: self._getCaffeRestart,
            Protocol.GETFILEHASH: self._getFileHash,
            Protocol.GETDIRHASH: self._getDirHash

        }
        Transaction.__init__(self)
        self.parent = parent

    def processMessage(self):
        """process the received message and call further processing"""
        # key = self.messageOutput[0]["key"]
        key = self.getAttrOfFirst(["key"])[0] # Threadsafe
        if key in self.options:
            self.options[key]()
        else:
            sys.stderr.write("Wrong Key: " + str(key) + "\n")

    def msgEcho(self):
        """return the message back to client. this is for testing."""
        msg = self.asyncRead()
        self.send(msg)

    def restart(self):
        """Saves all server-sessions of the current project and restarts the host afterwards."""
        msg = self.asyncRead()
        if msg and "pid" in msg:
            path = msg["pid"]
            sessionsUIDs = self.parent.sessionManager.findSessionIDsByProjectId(msg["pid"])
            success = True
            for uid in sessionsUIDs:
                session = self.parent.sessionManager.findSessionBySessionUid(uid)
                if session.isConnected:
                    if not session.save():
                        success = False
            if success is False:
                msg["error"] = ["Could not save a session because it contains layer of another caffe-version."]
                msg["status"] = False
                self.send(msg) 
            else:
                os.execl(sys.executable, sys.executable, *sys.argv)

    def getDir(self):
        """list all files and subdirectories for a given dir with regex."""
        msg = self.asyncRead()
        if msg:
            path = msg["path"]

            dirselect = False
            if "dirSelect" in msg:
                dirselect = msg["dirSelect"]

            if path == "":
                path = "/home"
            path = os.path.normpath(path)

            filters = ["*"]
            if "filter" in msg:
                filters = msg["filter"]
            dirIter = QDirIterator(path)
            data = list()
            while dirIter.hasNext():
                dirIter.next()
                if dirIter.fileName() in [".", ".."]:
                    continue

                if not dirIter.fileInfo().isDir():
                    if dirselect:
                        continue
                    match = False
                    for fi in filters:
                        reg = QRegExp(fi)
                        reg.setPatternSyntax(QRegExp.Wildcard)
                        if reg.exactMatch(dirIter.fileName()):
                            match = True
                            break
                    if not match:
                        continue

                elem = dict()
                elem["name"] = dirIter.fileName()
                elem["path"] = dirIter.filePath()

                inf = dirIter.fileInfo()  # type: QFileInfo
                elem["isDir"] = inf.isDir()

                last = inf.lastModified()  # type: QDateTime
                elem["lastChange"] = last.toString("yyyy.MM.dd - HH:MM")

                if inf.isDir():
                    elem["fileSize"] = ""
                else:
                    elem["fileSize"] = self._sizeHumanReadableStr(inf.size())

                data.append(elem)

            data = sorted(data, key=lambda di: (not di["isDir"], di["name"].lower()))

            msg["data"] = data
            logging.debug("There is/are %i element/s in %s", len(data), path)
            self.send(msg)

    def _sizeHumanReadableStr(self, size):
        """convert integer to human readable size"""
        sizes = ["B", "kB", "MB", "GB", "TB"]
        curSize = 0
        unit = sizes[curSize]

        while (size > 1000 and curSize < len(sizes) - 1):
            curSize = curSize + 1
            unit = sizes[curSize]
            size = round(size / 1000.0, 1)
        return str(size) + " " + unit

    def _getBaristaStatus(self):
        """start the Timer for Heartbeat"""
        msg = self.asyncRead()
        if "projectid" in msg.keys():
            self.projectID = msg["projectid"]
        if not hasattr(self, "timer"):
            self.timer = QTimer()
            self.timer.setInterval(5000)
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(self._sendBaristaStatus)
            self.socketClosed.connect(lambda : self.timer.stop())
            logging.debug("start heartbeat timer")
        self._sendBaristaStatus()


    def _sendBaristaStatus(self):
        """return the server status"""
        if hasattr(self, "timer"):
            self.timer.stop()
            if self.isConnected():
                self.timer.start()
        msg = {"key": Protocol.GETSTATUS}
        if hasattr(self, "projectID"):
            state = self.parent.getBaristaStatus(self.projectID)
        else:
            state = self.parent.getBaristaStatus()
        msg["data"] = state
        logging.debug("got state")
        self.send(msg)

    def _getDBStatus(self):
        """open a database, check for status and get properties"""
        msg = self.asyncRead()
        dbo = DatabaseObject()
        path = msg["path"]
        if "absolute" not in msg:
            path = os.path.join(self.parent.sessionPath, path)
        dbo.setDB(path, msg["type"])
        if msg["type"] == "HDF5TXT":
            dbo.setProjectPath(self.parent.sessionPath)
        dbo.open()
        status = dbo.isOpen()
        msg["status"] = status
        if status:
            msg["dataCount"] = dbo.getDataCount()
            msg["dimensions"] = dbo.getDimensions()
        dbo.close()
        logging.debug("Database: %s, Status: %s", path, str(status))
        self.send(msg)

    def _makeRelative(self):
        """make a given path relative to sessionpath"""
        msg = self.asyncRead()
        path = msg["path"]
        sesPath = self.parent.sessionPath
        msg["path"] = os.path.relpath(path, sesPath)
        logging.debug("old: '%s', new: '%s'", path, msg["path"])
        self.send(msg)

    def _makeHDF5Txt(self):
        """create the hdf5txt file"""
        msg = self.asyncRead()
        msg["status"] = False
        path = msg["path"]
        if not os.path.exists(path):
            with open(path, 'w') as file:
                file.write(msg["hdf5"])
                msg["status"] = True
        logging.debug("File created: %s", str(msg["status"]))
        self.send(msg)

    def _addHdf5(self):
        """add a line to HDF5txt"""
        msg = self.asyncRead()
        msg["status"] = False
        path = os.path.join(self.parent.sessionPath, msg["path"])
        if os.path.exists(path):
            with open(path, 'a') as file:
                file.write("\n" + msg["hdf5"])
                msg["status"] = True
        logging.debug("Line written: %s", str(msg["status"]))
        self.send(msg)

    def _getFileContent(self):
        """read a file and return contents"""
        # TODO this can be a security flaw since it allows to read arbitrary files.
        msg = self.asyncRead()
        msg["status"] = False
        path = os.path.join(self.parent.sessionPath, msg["path"])
        if os.path.exists(path):
            with open(path, 'r') as file:
                msg["file"] = file.read()
                msg["status"] = True
        else:
            logging.warning("File does not exist: %s", path)
        self.send(msg)

    def _writeFileContent(self):
        """write a file"""
        # TODO this can be a security flaw since it allows to write arbitrary files.
        msg = self.asyncRead()
        msg["status"] = False
        path = os.path.join(self.parent.sessionPath, msg["path"])
        if os.path.exists(path):
            with open(path, 'w') as file:
                file.write(msg["file"])
                msg["status"] = True
        else:
            logging.warning("File does not exist: %s", path)
        self.send(msg)

    """
    Computes and sends the hashValue of a db file, if this file exists.

    @author : j_stru18
    """
    def _getHash(self):
        msg = self.asyncRead()
        msg["status"] = False
        if "path" in msg and "type" in msg:
            path = msg["path"]
            type = msg["type"]
            hashValue = 0
            if path is not None and type is not None:
                if os.path.exists(path):
                    dbPaths = db_util.getDBPathsByType(path, type)
                    hashValue = db_util.getMultipleHash(dbPaths)
                    msg["status"] = True
                else:
                    logging.warning("File does not exist: %s", path)
            else:
                logging.warning("Internal error: Remote message gave no path and type.")
            msg["hashValue"] = hashValue
        else:
            logging.warning("Internal error: Remote message was faulty.")
        self.send(msg)

    def _getHardware(self):
        """get the hardware specs"""
        msg = self.asyncRead()
        msg["hardware"] = self.parent.hardware
        msg["current"] = self.parent.trainOnHW
        self.send(msg)

    def _scanHardware(self):
        """launch a hardware scan"""
        self.parent.checkHardware(True, self)

    def _setHardware(self):
        msg = self.asyncRead()
        status = self.parent.setHardware(msg["hid"])
        msg["status"] = status
        logging.info("Set current hardware to HID %i: %s", msg["hid"], str(status))
        self.send(msg)

    def _getPlatform(self):
        msg = self.asyncRead()
        msg["platform"] = sys.platform
        self.send(msg)

    def _createSession(self):
        self.parent.sessionManager.createNewSession(self)

    def _cloneSession(self):
        self.parent.sessionManager.cloneSession(self)

    def _disconnectSession(self):
        self.parent.sessionManager.disconnectSession(self)

    def _deleteSession(self):
        self.parent.sessionManager.deleteSession(self)

    def _connectToSession(self):
        self.parent.sessionManager.connectToSession(self)

    def _getSessions(self):
        self.parent.sessionManager.getSessions(self)

    def _doNothing(self):
        pass

    def _getCaffeVersions(self):
        versions = caffeVersions.getAvailableVersions()
        msg = self.asyncRead()
        versionsToSend = {}
        for version in versions:
            versionsToSend[version.getName()] = {"root": version.getRootpath(),
                                        "binary": version.getBinarypath(),
                                        "python": version.getPythonpath(),
                                        "proto": version.getProtopath()}
        msg["versions"] = versionsToSend
        msg["status"] = True
        self.send(msg)

    def _addCaffeVersion(self):
        msg = self.asyncRead()
        versionReceived = msg["version"]
        version = caffeVersions.caffeVersion(versionReceived["name"], versionReceived["root"], versionReceived["binary"], versionReceived["python"], versionReceived["proto"])
        caffeVersions.addVersion(version, self.parent.sessionPath)
        msg["status"] = True
        self.send(msg)

    def _setCurrentCaffeVersion(self):
        msg = self.asyncRead()
        versionNameReceived = msg["versionname"]
        caffeVersions.setDefaultVersion(versionNameReceived, self.parent.sessionPath)
        caffeVersions.restart = True
        msg["status"] = True
        self.send(msg)

    def _removeCaffeVersion(self):
        msg = self.asyncRead()
        versionNameReceived = msg["versionname"]
        version = caffeVersions.getVersionByName(versionNameReceived)
        caffeVersions.removeVersion(version, self.parent.sessionPath)
        msg["status"] = True
        self.send(msg)

    def _getDefaultCaffeVersion(self):
        msg = self.asyncRead()
        if caffeVersions.getDefaultVersion():
            msg["defaultVersionName"] = caffeVersions.getDefaultVersion().getName()
            msg["status"] = True
        else:
            msg["status"] = False
        self.send(msg)

    def _getCaffeRestart(self):
        msg = self.asyncRead()
        msg["cafferestart"] = caffeVersions.restart
        msg["status"] = True
        self.send(msg)

    def _getFileHash(self):
        msg = self.asyncRead()
        path = msg["path"]
        hash = Hash.hashFile(path)
        msg["status"] = True
        msg["hash"] = hash
        self.send(msg)

    def _getDirHash(self):
        msg = self.asyncRead()
        path = msg["path"]
        hash = Hash.hashDir(path)
        msg["status"] = True
        msg["hash"] = hash
        self.send(msg)