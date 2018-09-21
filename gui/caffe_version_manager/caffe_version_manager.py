from PyQt5.QtCore import pyqtSlot as Slot, QMetaObject,Qt
from PyQt5.QtGui import QIcon, QFont, QColor
from PyQt5.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QListWidget,
    QMessageBox,
    QListWidgetItem,
    QGridLayout,
    QStyle,
    qApp,
    QAbstractItemView
)

from backend.barista.utils.logger import Log
from gui.caffepath_dialog import CaffepathDialog
import backend.barista.caffe_versions as caffeVersions
from gui.caffe_version_manager.caffe_version_widget import CaffeVersionWidget
from backend.networking.net_util import sendMsgToHost
from backend.networking.protocol import Protocol
from gui.gui_util import askFromList


class CaffeVersionManager(QDialog):
    """This Editor enables management of different caffe versions."""

    def __init__(self, hostManager, default_actions, parent = None):
        QDialog.__init__(self, parent)

        self.project = None
        self.setModal(True)
        self.hostManager = hostManager
        self.actions = default_actions
        self.resize(600, 300)
        self.layout = QGridLayout(self)
        self.selectedVersion = None
        self.boldFont = QFont()
        self.boldFont.setBold(True)

        """Layout"""
        self.pbAddVersion = QPushButton("Add new version")
        self.layout.addWidget(self.pbAddVersion, 0, 0, 1, -1)

        """Version widgets"""
        self.lstVersions = QListWidget(self)
        self.lstVersions.setSelectionMode(QAbstractItemView.SingleSelection)
        #self.lstVersions.setStyleSheet(self.lstVersions.styleSheet() + "QListWidget::item { border-bottom: 1px solid lightgray; }" )
        self.layout.addWidget(self.lstVersions, 1, 0, -1, -1)

        self.pbAddVersion.clicked.connect(self._onAddVersion)
        self.lstVersions.itemSelectionChanged.connect(self._onSelectionChanged)

        self.updateList()
        
    def _onAddVersion(self):
        """Opens the dialog to add new caffe versions"""
        hosts = self.hostManager.getActiveHostList()[:]
        ret = None
        if len(hosts) == 0:
            caffedlg = CaffepathDialog("Add a new caffe version to Barista", "Add version")
            caffedlg.exec_()
        else:
            hosts.insert(0, ["local", "Local host"])
            ret = askFromList(self, hosts, "Select host on which to add version",
                          "You have configured remote Hosts.\nPlease select where to add the version.")
        if ret:
            if ret == "local":
                caffedlg = CaffepathDialog("Add a new caffe version to Barista", "Add version")
                caffedlg.exec_()
            else:
                host = self.hostManager.getHostById(ret)
                caffedlg = CaffepathDialog("Add a new caffe version to the Host", "Add version", remote=True, host=host)
                caffedlg.exec_()
        self.updateList()

    def _onRemoveVersion(self, name, host):
        """Removes the selected caffe version"""
        if host == None:
            if caffeVersions.getAvailableVersions() > 1:
                caffeVersions.removeVersion(caffeVersions.getVersionByName(name))
                if(self.project.getCaffeVersion() == name):
                    self.project.changeProjectCaffeVersion(caffeVersions.getDefaultVersion().getName())
            else:
                QMessageBox.warning(self, self.tr("Warning"), self.tr("Cannot delete version. At least one caffe-version must be available at all times in barista."))
        else:
            msg = {"key": Protocol.REMOVECAFFEVERSION, "versionname": name}
            sendMsgToHost(host.host, host.port, msg)
        self.updateList()

    def _onSelectionChanged(self):
        """Displays more information about the selected caffe version if it is selected"""
        if len(self.lstVersions.selectedItems()) >= 1 and self.lstVersions.currentItem() is not None:
            widget = self.lstVersions.itemWidget(self.lstVersions.currentItem())
            if not isinstance(widget, QLabel):
                selected = {}
                selected["host"] = widget.host
                selected["versionname"] = widget.caffe_version.getName()
                if self.versionsEqual(selected, self.selectedVersion):
                    self.selectedVersion = None
                else:
                    self.selectedVersion = selected
                self.updateList()

    def versionsEqual(self, version1, version2):
        try:
            return version1["host"] == version2["host"] and version1["versionname"] == version2["versionname"]
        except:
            return False

    def updateList(self):
        """updates the list containing all available caffe versions"""
        self.lstVersions.clear()

        lblLocalVersion = QLabel("Local versions:")
        lblLocalVersion.setFont(self.boldFont)
        self.addListWidget(lblLocalVersion, False, False)

        localCurrent = ""
        if self.project != None:
            localCurrent = self.project.getCaffeVersion()

        for version in caffeVersions.getAvailableVersions():
            name = version.getName()
            selected = self.versionsEqual(self.selectedVersion, {"host": None, "versionname": version.getName()})
            widget = CaffeVersionWidget(caffeVersions.getVersionByName(name), self.lstVersions, self, isSelected = selected, current = name == localCurrent, restart = caffeVersions.restart, host = None)
            self.addListWidget(widget, True, selected)

        for host in self.hostManager.getActiveHostList():
            host = self.hostManager.getHostById(host[0])
            lblRemoteVersion = QLabel("Versions on " + host.host + ":"+ str(host.port) +":")
            lblRemoteVersion.setFont(self.boldFont)
            lblRemoteVersion.setStyleSheet(lblRemoteVersion.styleSheet() + "QLabel{ border-top: 1px solid black; }")
            self.addListWidget(lblRemoteVersion, False, False)

            remoteCurrent = ""
            msg = {"key": Protocol.GETDEFAULTCAFFEVERSION}
            reply = sendMsgToHost(host.host, host.port, msg)
            if reply:
                if reply["status"]:
                    remoteCurrent = reply["defaultVersionName"]

            remoteRestart = False
            msg = {"key": Protocol.GETCAFFERESTART}
            reply = sendMsgToHost(host.host, host.port, msg)
            if reply:
                if reply["status"]:
                    remoteRestart = reply["cafferestart"]

            msg = {"key": Protocol.GETCAFFEVERSIONS}
            reply = sendMsgToHost(host.host, host.port, msg)
            if reply:
                remoteVersions = reply["versions"]
                for version in remoteVersions:
                    version = caffeVersions.caffeVersion(version, remoteVersions[version]["root"], remoteVersions[version]["binary"], remoteVersions[version]["python"], remoteVersions[version]["proto"])
                    selected = self.versionsEqual(self.selectedVersion, {"host": host, "versionname": version.getName()})
                    widget = CaffeVersionWidget(version, self.lstVersions, self, isSelected = selected, current = remoteCurrent == version.getName(), restart = remoteRestart, host = host)
                    self.addListWidget(widget, True, selected)

    def addListWidget(self, widget, selectable, selected):
        item = QListWidgetItem()
        item.setSizeHint(widget.sizeHint())
        if not selectable:
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        if selected:
            item.setBackground(QColor(233, 119, 72))
        self.lstVersions.addItem(item)
        self.lstVersions.setItemWidget(item, widget)

    def updateProject(self, project):
        """Updates the caffe version of the project"""
        self.project = project
        self.updateList()

    def showEvent(self, event):
        self.updateList()
        QDialog.showEvent(self, event)
