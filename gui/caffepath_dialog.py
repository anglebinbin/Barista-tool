# -*- coding: utf-8 -*-
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtGui import QIcon
from backend.barista import caffe_versions
from gui.host_manager.remote_file_dialog import RemoteFileDialog
from backend.networking.net_util import sendMsgToHost
from backend.networking.protocol import Protocol
from enum import Enum
import sys
import signal
import os.path

class Platform(Enum):
    LINUX = 1
    WINDOWS = 2
    CYGWIN = 3
    MACOSX = 4
    OS2 = 5
    OS2EMX = 6
    RISCOS = 7
    ATHEOS = 8


class CaffepathDialog(QtWidgets.QDialog):

    def __init__(self, reason, buttontext, quitonclose = False, parent = None, remote = False, host = None):
        super(CaffepathDialog, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setWindowTitle("Caffepath")
        self.changes = False
        self.quitonclose = quitonclose
        self.startPath = "/home"
        self.remote = remote
        self.host = host
        caffepathttext = reason

        if remote:
            msg = {"key": Protocol.GETPLATFORM}
            reply = sendMsgToHost(self.host.host, self.host.port, msg)
            platform = reply["platform"]
        else:
            platform = sys.platform

        if platform == "win32": self.platform = Platform.WINDOWS
        elif platform == "cygwin": self.platform = Platform.CYGWIN
        elif platform == "darwin": self.platform = Platform.MACOSX
        elif platform == "os2": self.platform = Platform.OS2
        elif platform == "os2emx": self.platform = Platform.OS2EMX
        elif platform == "riscos": self.platform = Platform.RISCOS
        elif platform == "atheos": self.platform = Platform.ATHEOS
        else: self.platform = Platform.LINUX

        if remote==True and self.host==None:
            print("Error: CaffepathDialog needs a host if remote is True")
            exit(-1)

        lay = QtWidgets.QGridLayout(self)
        lay.addWidget(QtWidgets.QLabel(caffepathttext, self),0,0,1,1)

        self.pbSaveStart = QtWidgets.QPushButton(buttontext)
        lay.addWidget(self.pbSaveStart, 1, 0, 1, 2)
        
        self.labelName = QtWidgets.QLabel("Unique name:")
        lay.addWidget(self.labelName, 3, 0, 1, 4)

        self.LineEditName = QtWidgets.QLineEdit()
        lay.addWidget(self.LineEditName, 4, 0, 1, 2)

        self.labelPathtoCaffe = QtWidgets.QLabel("Path to caffe root:")
        lay.addWidget(self.labelPathtoCaffe, 5, 0, 1, 4)

        self.LineEditPathtoCaffe = QtWidgets.QLineEdit()
        lay.addWidget(self.LineEditPathtoCaffe, 6, 0, 1, 2)

        self.labelPathtoPython = QtWidgets.QLabel("Path to python packages of caffe:")
        lay.addWidget(self.labelPathtoPython, 7, 0, 1, 4)

        self.LineEditPathtoPython = QtWidgets.QLineEdit()
        lay.addWidget(self.LineEditPathtoPython, 8, 0, 1, 2)

        if self.platform == Platform.WINDOWS:
            self.labelPathtoBinaries = QtWidgets.QLabel("Caffe executable:")
        else:
            self.labelPathtoBinaries = QtWidgets.QLabel("Caffe binary file:")
        lay.addWidget(self.labelPathtoBinaries, 9, 0, 1, 4)

        self.LineEditPathtoBinaries = QtWidgets.QLineEdit()
        lay.addWidget(self.LineEditPathtoBinaries, 10, 0, 1, 2)

        self.labelPathtoProto = QtWidgets.QLabel("Caffe proto file:")
        lay.addWidget(self.labelPathtoProto, 11, 0, 1, 4)

        self.LineEditPathtoProto = QtWidgets.QLineEdit()
        lay.addWidget(self.LineEditPathtoProto, 12, 0, 1, 2)

        pix = QtWidgets.qApp.style().standardPixmap(QtWidgets.QStyle.SP_DialogOpenButton)
        ico = QIcon(pix)
        self.pbCaffePath = QtWidgets.QPushButton(ico, "")
        lay.addWidget(self.pbCaffePath, 6, 3, 1, 1)

        pix = QtWidgets.qApp.style().standardPixmap(QtWidgets.QStyle.SP_DialogOpenButton)
        ico = QIcon(pix)
        self.pbPythonFile = QtWidgets.QPushButton(ico, "")
        lay.addWidget(self.pbPythonFile, 8, 3, 1, 1)

        pix = QtWidgets.qApp.style().standardPixmap(QtWidgets.QStyle.SP_DialogOpenButton)
        ico = QIcon(pix)
        self.pbBinaryFiles = QtWidgets.QPushButton(ico, "")
        lay.addWidget(self.pbBinaryFiles, 10, 3, 1, 1)

        pix = QtWidgets.qApp.style().standardPixmap(QtWidgets.QStyle.SP_DialogOpenButton)
        ico = QIcon(pix)
        self.pbProtoFile = QtWidgets.QPushButton(ico, "")
        lay.addWidget(self.pbProtoFile, 12, 3, 1, 1)

        self.pbCaffePath.clicked.connect(self._onCaffePath)
        self.pbPythonFile.clicked.connect(self._onPythonFile)
        self.pbBinaryFiles.clicked.connect(self._onBinaryFile)
        self.pbProtoFile.clicked.connect(self._onProtoFile)
        self.pbSaveStart.clicked.connect(self._onSave)

    def _onCaffePath(self):
        """if default path should be changed, show file dialog to chose a path """

        ret = ""

        if self.remote:
            rfd = RemoteFileDialog(self.host.host, self.host.port, "Select rootpath of caffe", dirSelect=True)
            rfd.exec_()
            ret = rfd.returnvalue

        else:
            ret = QtWidgets.QFileDialog.getExistingDirectory(self, "Select rootpath of caffe",
                                                    self.startPath,
                                                    QtWidgets.QFileDialog.ShowDirsOnly)

        if len(ret) != 0:
            self.LineEditPathtoCaffe.setText(ret)
            self.startPath = ret
            if len(str(self.LineEditPathtoPython.text())) == 0:
                pythonpath = os.path.join(ret, "python")
                if os.path.exists(pythonpath):
                    self.LineEditPathtoPython.setText(pythonpath)
            if len(str(self.LineEditPathtoBinaries.text())) == 0:
                # There are differnt variations on the name of the caffe binary, so we look for and accept any one of them
                for binaryName in ["caffe.exe", "caffe", "caffe.bin"]:
                    binarypath = os.path.join(ret, "build", "tools", binaryName)
                    if os.path.isfile(binarypath):
                        self.LineEditPathtoBinaries.setText(binarypath)
                        break
            if len(str(self.LineEditPathtoProto.text())) == 0:
                protopath = os.path.join(ret, "src", "caffe", "proto", "caffe.proto")
                if os.path.exists(protopath):
                    self.LineEditPathtoProto.setText(protopath)

    def _onPythonFile(self):
        """if default path should be changed, show file dialog to chose a path """

        ret = ""

        if self.remote:
            rfd = RemoteFileDialog(self.host.host, self.host.port, "Select path to the python packages of caffe", dirSelect=True)
            rfd.exec_()
            ret = rfd.returnvalue
        else:
            ret = QtWidgets.QFileDialog.getExistingDirectory(self, "Select path to the python packages of caffe",
                                                    self.startPath,
                                                    QtWidgets.QFileDialog.ShowDirsOnly)
        if len(ret) != 0:
            self.LineEditPathtoPython.setText(ret)

    def _onBinaryFile(self):
        """if default path should be changed, show file dialog to chose a path """

        ret = ""

        if self.remote:
            if self.platform == Platform.WINDOWS:
                rfd = RemoteFileDialog(self.host.host, self.host.port, "Select caffe executable", "ALL (*.exe)", dirSelect=False)
            else:
                rfd = RemoteFileDialog(self.host.host, self.host.port, "Select caffe binary file", "ALL (*.bin)", dirSelect=False)
            rfd.exec_()
            ret = rfd.returnvalue

        else:
            if self.platform == Platform.WINDOWS:
                ret = QtWidgets.QFileDialog.getOpenFileName(self, "Select caffe executable", self.startPath, "Executables (*.exe)")                
            else:
                ret = QtWidgets.QFileDialog.getOpenFileName(self, "Select caffe binary file", self.startPath, "Binary Files (*.bin)")

        if len(ret) != 0:
            self.LineEditPathtoBinaries.setText(ret[0])

    def _onProtoFile(self):
        """if default path should be changed, show file dialog to chose a path """

        ret = ""

        if self.remote:
            rfd = RemoteFileDialog(self.host.host, self.host.port, "Select caffe proto file", "ALL (*.proto)", dirSelect=False)
            rfd.exec_()
            ret = rfd.returnvalue

        else:
            ret = QtWidgets.QFileDialog.getOpenFileName(self, "Select caffe proto file", self.startPath, "Proto Files (*.proto)");
            
        if len(ret) != 0:
            self.LineEditPathtoProto.setText(ret[0])

    def _onSave(self):
        """if path in LineEditPathtoPython is correct caffepath, change caffepath and close window,
        otherwise show warning """
        caffename = str(self.LineEditName.text())
        caffepath = str(self.LineEditPathtoCaffe.text())
        pythonpath = str(self.LineEditPathtoPython.text())
        binarypath = str(self.LineEditPathtoBinaries.text())
        protopath = str(self.LineEditPathtoProto.text())

        versions = []

        if self.remote:
            msg = {"key": Protocol.GETCAFFEVERSIONS}
            reply = sendMsgToHost(self.host.host, self.host.port, msg)
            if reply:
                remoteVersions = reply["versions"]
                for version in remoteVersions:
                    versions.append(caffe_versions.caffeVersion(version, remoteVersions[version]["root"], remoteVersions[version]["binary"], remoteVersions[version]["python"], remoteVersions[version]["proto"]))
        else:
            versions = caffe_versions.getAvailableVersions()

        existing = False
        for version in versions:
            if version.getName() == caffename:
                existing = True

        if existing:
                QtWidgets.QMessageBox.warning(self, "Error", "An version with the given name already exists. Please choose a unique name.")
        else:
            try:
                if len(caffepath) == 0: raise Exception("Please select the caffe root path")

                try:
                    import importlib
                    import sys

                    sys.path.insert(0, pythonpath)
                    caffe = importlib.import_module("caffe")
                    sys.path.pop(0)
                except ImportError as e:
                    raise Exception("Please select the path to the python package of caffe")
                
                if len(binarypath) == 0:
                    if self.platform == Platform.WINDOWS:
                        raise Exception("Plese select the caffe executable")
                    else:
                        raise Exception("Please select the caffe binary file")
                if len(protopath) == 0: raise Exception("Please select the proto file")
                #if os.path.isfile(binarypath)
                version = caffe_versions.caffeVersion(caffename, caffepath, binarypath, pythonpath, protopath)

                if self.remote:
                    msg = {"key": Protocol.ADDCAFFEVERSION, "version": {"name": version.getName(),
                                                                "root": version.getRootpath(),
                                                                "binary": version.getBinarypath(),
                                                                "python": version.getPythonpath(),
                                                                "proto": version.getProtopath()}}
                    sendMsgToHost(self.host.host, self.host.port, msg)
                else:
                    caffe_versions.addVersion(version)

                self.changes = True
                self.close()
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Error", self.tr(repr(e)))

    def closeEvent(self, event):
        if(self.quitonclose):
            #if nothing has changed(no new Caffepath) just exit complete programm
            if not self.changes:
                exit(1)
