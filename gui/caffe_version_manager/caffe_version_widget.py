from PyQt5.QtGui import QIcon
from PyQt5 import QtCore
from backend.barista.session.session import State
import backend.barista.caffe_versions as caffeVersions
from backend.networking.net_util import sendMsgToHost
from backend.networking.protocol import Protocol
from PyQt5.QtWidgets import (
    QWidget,
    QGridLayout,
    QLabel,
    QPushButton,
    qApp,
    QStyle,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QMessageBox
)

class CaffeVersionWidget(QWidget):
    """This widget class represents a caffe version as it is displayed in the caffe_version_manager"""

    def __init__(self, version, parent, versionManager, isSelected, current, restart, host):
        super(CaffeVersionWidget, self).__init__(parent)
        self.caffe_version = version
        self.versionManager = versionManager
        self.host = host

        """Icons"""
        self.ico_delete = QIcon('resources/trash.png')
        self.ico_edit = QIcon('resources/pencil')
        self.ico_remove = QIcon('resources/remove.png')

        """Layout"""
        self.layout = QGridLayout(self)

        """Name label"""
        self.lblName = QLabel(self.caffe_version.getName())
        self.layout.addWidget(self.lblName, 0, 0, 1, 1)

        """General buttons"""
        self.btnDelete = QPushButton(self.ico_delete, "")
        self.btnDelete.setToolTip("Delete Version")
        self.btnDelete.setFixedSize(30,30)
        self.layout.addWidget(self.btnDelete, 0, 1, 1, 1)

        if current:
            """Indicators if version is current project version or not"""
            if restart:
                self.lblCurrent = QLabel("Restart!")
                self.lblCurrent.setFixedSize(0, 0)
                self.lblCurrent.setStyleSheet(self.lblCurrent.styleSheet() + "QLabel{background-color: #F4EE42; border: 1px solid black; border-radius: 5px}")
            else:
                self.lblCurrent = QLabel("Current")
                self.lblCurrent.setFixedSize(0, 0)
                self.lblCurrent.setStyleSheet(self.lblCurrent.styleSheet() + "QLabel{background-color: #00EE00; border: 1px solid black; border-radius: 5px}")

            self.lblCurrent.setAlignment(QtCore.Qt.AlignCenter)
            self.lblCurrent.setFixedSize(150, 30)
            self.layout.addWidget(self.lblCurrent, 0, 2, 1, 1)
        else:
            self.btnSetCurrent= QPushButton("Set as current")
            self.btnSetCurrent.setFixedSize(150, 30)
            self.layout.addWidget(self.btnSetCurrent, 0, 2, 1, 1)
            self.btnSetCurrent.clicked.connect(self._onSetCurrent)

        if isSelected:
            """show details of the current version if it is selected"""
            self.layout2 = QGridLayout()
            #btnEdit = QPushButton(self.ico_edit, "")
            #btnEdit.setFixedSize(30,30)
            #self.layout2.addWidget(btnEdit, 0, 0, 1, 1)
            self.layout2.addWidget(QLabel("Root:\t"+self.caffe_version.getRootpath()), 0, 1, 1, -1)
            #btnEdit = QPushButton(self.ico_edit, "")
            #btnEdit.setFixedSize(30,30)
            #self.layout2.addWidget(btnEdit, 1, 0, 1, 1)
            self.layout2.addWidget(QLabel("Binary:\t"+self.caffe_version.getBinarypath()), 1, 1, 1, -1)
            #btnEdit = QPushButton(self.ico_edit, "")
            #btnEdit.setFixedSize(30,30)
            #self.layout2.addWidget(btnEdit, 2, 0, 1, 1)
            self.layout2.addWidget(QLabel("Python:\t"+self.caffe_version.getPythonpath()), 2, 1, 1, -1)
            #btnEdit = QPushButton(self.ico_edit, "")
            #btnEdit.setFixedSize(30,30)
            #self.layout2.addWidget(btnEdit, 3, 0, 1, 1)
            self.layout2.addWidget(QLabel("Proto:\t"+self.caffe_version.getProtopath()), 3, 1, 1, -1)

            self.layout.addLayout(self.layout2, 1, 0, 1, -1)

        self.btnDelete.clicked.connect(self._onRemoveVersion)

    def _onRemoveVersion(self):
        """Remove this version from the caffe_version_manager"""
        self.versionManager._onRemoveVersion(self.caffe_version.getName(), self.host)
        if self.host == None:
            self.restartWarning()
        else:
            msgBox = QMessageBox(QMessageBox.Warning, "Warning", "Please restart Barista host for changes to apply, otherwise Barista may be unstable!")
            msgBox.addButton("Ok", QMessageBox.NoRole)
            msgBox.addButton("Restart now", QMessageBox.YesRole)
            if msgBox.exec_() == 1:
                msg = {"key": Protocol.RESTART, "pid": self.versionManager.project.getProjectId()}
                sendMsgToHost(self.host.host, self.host.port, msg)
    
    def _onSetCurrent(self):
        """Sets this version as the current projects/remote hosts caffe version"""
        if self.host == None:
            self.versionManager.project.changeProjectCaffeVersion(self.caffe_version.getName())
            self.restartWarning()
            caffeVersions.restart = True
        else:
            msg = {"key": Protocol.SETCURRENTCAFFEVERSION, "versionname": self.caffe_version.getName()}
            sendMsgToHost(self.host.host, self.host.port, msg)
            
            msgBox = QMessageBox(QMessageBox.Warning, "Warning", "Please restart Barista host for changes to apply, otherwise Barista may be unstable!")
            msgBox.addButton("Ok", QMessageBox.NoRole)
            msgBox.addButton("Restart now", QMessageBox.YesRole)
            
            if msgBox.exec_() == 1:
                msg = {"key": Protocol.RESTART, "pid": self.versionManager.project.getProjectId()}
                ret = sendMsgToHost(self.host.host, self.host.port, msg)
                if ret and not ret["status"]:
                    msgBox = QMessageBox(QMessageBox.Warning, "Warning", ret["error"][0])
                    msgBox.addButton("Ok", QMessageBox.NoRole)
                    msgBox.exec_()
        self.versionManager.updateList()

    def restartWarning(self):
            msgBox = QMessageBox(QMessageBox.Warning, "Warning", "Please restart Barista client for changes to apply, otherwise Barista may be unstable!")
            msgBox.addButton("Ok", QMessageBox.NoRole)
            msgBox.addButton("Restart now", QMessageBox.YesRole)
            if msgBox.exec_() == 1:
                self.versionManager.actions.restart()