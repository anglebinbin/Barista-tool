import json
import os
import socket
import sys
import logging

from PyQt5.QtNetwork import QTcpServer, QHostAddress

from backend.caffe.check_hardware import checkHardware
from backend.barista.session.session_utils import State
from backend.networking.protocol import Protocol
from backend.networking.server_session_manager import ServerSessionManager
from backend.networking.server_transaction import ServerTransaction
from backend.barista import caffe_versions


class BaristaServer():
    MIN_PORT = 0
    MAX_PORT = 65535
    DEFAULT_PORT = 4200

    def __init__(self, application, ip, port, sessionPath):
        self.application = application
        self.server = None
        self.port = int(port)
        self.ip = QHostAddress.Any
        if ip is not None:
            self.ip = QHostAddress(ip)

        self.sessionPath = sessionPath
        self.configpath = os.path.join(self.sessionPath, "barista.conf") ####
        self.hardware = []
        self.trainOnHW = 0
        self.transactionList = []
        self._loadConfig()
        self.checkHardware()
        state = self._checkConfig()
        self.start()
        self.sessionManager = ServerSessionManager(self, self.sessionPath)

    def start(self):
        self.server = QTcpServer()
        self.server.listen(self.ip, self.port)
        self.server.newConnection.connect(self._newConnection)
        if self.server.isListening():
            hostIP = str(self.server.serverAddress().toString())
            if hostIP == '0.0.0.0':
                hostIP = '<any>'
            sys.stdout.write("Hostname: " + socket.gethostname()
                             + "\tIP: " + hostIP + ":" + str(self.server.serverPort()) + "\n")

        else:
            sys.stderr.write("Something went wrong. Server is not listening.\n")
            logging.error("Something went wrong. Server is not listening.")
            exit(1)

    def getBaristaStatus(self, pid=""):
        hardware = [k["name"] for k in self.hardware]

        statusdict = {"trainOnHW": self.trainOnHW, "hardware": hardware}
        statusdict["connections"] = len(self.transactionList)
        statusdict["config"] = self._checkConfig(False)
        statusdict["training"] = len(self.sessionManager.findSessionIDsWithState(State.RUNNING)) is 0
        statusdict["sessioncount"] = len(self.sessionManager.sessions)
        statusdict["sessionpath"] = self.sessionPath
        if pid is not "":
            pidses = {}
            sessions = set(self.sessionManager.findSessionIDsByProjectId(pid))
            pidses["pid"] = pid
            pidses["count"] = len(sessions)
            pidses["running"] = len(set(self.sessionManager.findSessionIDsWithState(State.RUNNING)) & sessions)
            pidses["running"] += len(set(self.sessionManager.findSessionIDsWithState(State.PAUSED)) & sessions)
            pidses["waiting"] = len(set(self.sessionManager.findSessionIDsWithState(State.WAITING)) & sessions)
            pidses["finished"] = len(set(self.sessionManager.findSessionIDsWithState(State.FINISHED)) & sessions)

            statusdict["projectsessions"] = pidses

        return statusdict
 
    def _newConnection(self):
        transaction = ServerTransaction(self)
        self.transactionList.append(transaction)
        transaction.socketClosed.connect(lambda item=transaction: self._deleteConnection(item))
        transaction.acceptClient(self.server.nextPendingConnection())

    def _deleteConnection(self, transaction):
        index = self.transactionList.index(transaction)
        del self.transactionList[index]

    def _saveConfig(self):
        #Save train on hardware
        tosave = dict()
        tosave["trainOnHW"] = self.trainOnHW
        with open(self.configpath, "w") as file:
            json.dump(tosave, file, sort_keys=True, indent=4)

    def _loadConfig(self):
        ####
        if not os.path.exists(self.configpath):
            # TODO Default
            pass
        else:
            with open(self.configpath, "r") as file:
                res = json.load(file)
                if "trainOnHW" in res:
                    self.trainOnHW = res["trainOnHW"]
                else:
                    # TODO default
                    pass
        
    def _checkConfig(self, verbose=True):
        state = True
        caffe_versions.loadVersions(self.sessionPath)
        if caffe_versions.versionCount() == 0:    
            if verbose:
                sys.stderr.write("Warning: There is no Caffeversion set. Use the Versionmanager inside Barista to set the Path.\n")
                logging.warning("There is no Caffeversion set. Use the Versionmanager inside Barista to set the Path.")
        if self.trainOnHW >= len(self.hardware):
            self.trainOnHW = 0
            if verbose:
                sys.stderr.write("Warning: Currently selected Hardware could not be matched against detected Hardware."
                                    " Set to CPU mode!\n")
                logging.warning("Currently selected Hardware could not be matched against detected Hardware."
                                " Set to CPU mode!")

        return state

    def checkHardware(self, verbose=True, transaction=None):
        caffe_versions.loadVersions(self.sessionPath)
        if caffe_versions.versionCount() == 0:      
            if verbose:
                sys.stderr.write("Warning: Can't check hardware without Caffeversions\n")
                logging.warning("Can't check hardware without Caffeversions")
            if transaction:
                msg = {"key": Protocol.SCANHARDWARE, "status": False, "error": "Can't check hardware without Caffeversions"}
                transaction.send(msg)
            return
        try:
            binary = caffe_versions.getDefaultVersion().getBinarypath()
            self.hardware = checkHardware(binary, not verbose, transaction)
            if verbose:
                sys.stdout.write("Finished scanning Hardware. " + str(len(self.hardware)) + " devices found.\n")
                logging.info("Finished scanning Hardware. %s devices found.", str(len(self.hardware)))
            if transaction:
                msg = {"key": Protocol.SCANHARDWARE, "status": True, "finished": True, "hardware": self.hardware,
                       "current": self.trainOnHW}
                transaction.send(msg)
        except:
            if verbose:
                sys.stderr.write("Error: Failed to check hardware!\n")
                logging.error("Failed to check hardware!")
            if transaction:
                msg = {"key": Protocol.SCANHARDWARE, "status": False, "error": "Failed to check hardware!"}
                transaction.send(msg)

    def setHardware(self, hid):
        if hid >= len(self.hardware):
            return False
        self.trainOnHW = hid
        self._saveConfig()
        return True

