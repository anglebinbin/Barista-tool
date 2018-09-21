import uuid

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import Qt, pyqtSlot as Slot, QMetaObject, QTimer, QObject
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import *

from backend.barista.utils.settings import applicationQSetting
from backend.networking.net_util import sendMsgToHost, buildTransaction
from backend.networking.protocol import Protocol
from gui.gui_util import askFromList
from gui.host_manager.remote_file_dialog import RemoteFileDialog
from gui.host_manager.hardware_selector import HardwareSelector
from gui.manager_dialog import ManagerDialog
from backend.networking.barista_server import BaristaServer


class HostManager(ManagerDialog):
    DEFAULT_HOSTNAME = 'Default'

    def __init__(self, parent=None):
        ManagerDialog.__init__(self, parent)

        # main_window title
        self.setWindowTitle("Host Manager")

        # add "new host" button
        self._pb_add = QPushButton("Add new Host")
        self._buttonlayout.addWidget(self._pb_add)

        self._buttonlayout.addStretch()

        # combobox for filters
        self._filterCombo = QtWidgets.QComboBox()
        types = ["ALL", "ALIVE", "DEAD"]
        self._filterCombo.addItems(types)
        self._filterCombo.currentIndexChanged.connect(self._onFilter)
        self._buttonlayout.addWidget(self._filterCombo)

        # listwidget with all hosts
        self._itemscroll.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._itemscroll.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._layout.addWidget(self._itemscroll)

        self.dict = {"hostorder": [], "hostlist": {}}

        self._pb_add.clicked.connect(self._addNewHost)

        self._loadFromSettings()
        self._addDefaultServer()
        self._updateListWidget()

    def _addDefaultServer(self):
        """ Add a localhost server with name 'Default', if it's not already in the
        list. """
        for id, item in self.dict['hostlist'].iteritems():
            if item.host == 'localhost' and item.port == BaristaServer.DEFAULT_PORT:
                return False
        host = Host(self, 'localhost', BaristaServer.DEFAULT_PORT, self.DEFAULT_HOSTNAME)
        id = str(uuid.uuid4())
        host.setID(id)
        self.dict["hostorder"].append(id)
        self.dict["hostlist"][id] = host
        return True

    def _loadFromSettings(self):
        settings = applicationQSetting()
        settings.beginGroup("Host")
        val = settings.value("dict", "")
        settings.endGroup()
        if val != "":
            self.dict = self._fromDict(val)

    def _saveToSettings(self):
        settings = applicationQSetting()
        settings.beginGroup("Host")
        settings.setValue("dict", self._toDict())
        settings.endGroup()

    def _toDict(self):
        """ Converts the dict of Hosts into a serializable dictionary
        """
        serialdict = {}
        serialdict["hostlist"] = {}
        for id in self.dict["hostorder"]:
            host = self.dict["hostlist"][id]
            serialdict["hostlist"][id] = {"host": host.host, "port": host.port, "name": host.name}
        serialdict["hostorder"] = self.dict["hostorder"]
        return serialdict

    def _fromDict(self, dict):
        """ Converts the serializable dictionary into the dict of Hosts
        """
        hostdict = {}
        hostdict["hostlist"] ={}
        if "hostorder" in dict.keys():
            hostdict["hostorder"] = dict["hostorder"]
        for id in dict["hostorder"]:
            host = Host(self, dict["hostlist"][id]["host"],
                        dict["hostlist"][id]["port"],
                        dict["hostlist"][id]["name"])
            host.setID(id)
            hostdict["hostlist"][id] = host
        return hostdict

    def _selectedHost(self):
        if len(self._hostscroll.selectedItems()) < 1:
            return None
        id = self._hostscroll.selectedItems()[0].data(Qt.UserRole)
        host = self.dict["hostlist"][id]
        return host

    def _selectionChange(self):
        """disable and enable the delete button on selection"""
        num_selected = len(self._itemscroll.selectedItems())
        self._pb_remove.setEnabled(num_selected > 0 and self._selectedHost().name != self.DEFAULT_HOSTNAME)

    def getActiveHostList(self):
        ret = []
        for id in self.dict["hostorder"]:
            if self.dict["hostlist"][id].connect():
                host = [id, "Remote Host: '" + self.dict["hostlist"][id].name + "'"]
                ret.append(host)
        return ret

    def getHostDataById(self, id):
        if id in self.dict["hostorder"]:
            return [self.dict["hostlist"][id].host, self.dict["hostlist"][id].port, self.dict["hostlist"][id].name]

    def getHostById(self, id):
        if id in self.dict["hostorder"]:
            return self.dict["hostlist"][id]

    def makePathRelative(self, id, path):
        if id in self.dict["hostorder"]:
            return self.makePathRealtiveDirect(self.dict["hostlist"][id].host,
                                               self.dict["hostlist"][id].port, path)

    def makePathRealtiveDirect(self, host, port, path):
        msg = {"key": Protocol.MAKEPATHRELATIVE, "path": path}
        ret = sendMsgToHost(host, port, msg)
        if ret:
            return ret["path"]

    def _onFilter(self):
        '''apply the filter to all items by hiding and unhiding'''
        type = self._filterCombo.currentText()
        activeHostIds = []
        for host in self.getActiveHostList():
            activeHostIds.append(host[0])
        for index in range(0, self._itemscroll.count()):
            item = self._itemscroll.item(index)
            if (type == "DEAD" and item.data(Qt.UserRole) not in activeHostIds) \
                    or (type == "ALIVE" and item.data(Qt.UserRole) in activeHostIds) \
                    or type == "ALL":
                item.setHidden(False)
            else:
                item.setHidden(True)

    def onDelete(self):
        """remove selected hosts"""
        ic = len(self._itemscroll.selectedItems())
        if ic > 0:
            # Prevent DEFAULT HOST from being deleted.
            if self._selectedHost().name == self.DEFAULT_HOSTNAME:
                return
            gramNum = ""
            if ic > 1:
                gramNum = "s"
            # confirm delete
            ret = QMessageBox.question(self, "Remove {0} selected Host{1}".format(str(ic), gramNum),
                                       "Do you really want to delete the selected host{}?".format(gramNum),
                                       QMessageBox.Ok, QMessageBox.No)
            if ret == QMessageBox.Ok:
                for item in self._itemscroll.selectedItems():
                    self.deletebyID(item.data(Qt.UserRole))
                # instead of using the _updateListWidget function it is more efficient to remove the widgets by hand
                rows = []
                # get all the rows
                for item in self._itemscroll.selectedItems():
                    rows.append(self._itemscroll.row(item))
                # remove in reverse order to conserve the row-number
                for row in reversed(sorted(rows)):
                    item = self._itemscroll.takeItem(row)
                    item = None
                self._saveToSettings()
                self._updateSizeHint()


    def onKeyDelete(self):
        self.onDelete()


    def keyReleaseEvent(self, QKeyEvent):
        if QKeyEvent.key() == QtCore.Qt.Key_Delete:
            self.onKeyDelete()
        super(HostManager, self).keyReleaseEvent(QKeyEvent)


    def deletebyID(self, id):
        """given an ID remove the entry from the host dict"""
        if id:
            if id in self.dict["hostorder"]:
                self.dict["hostorder"].remove(id)  # this removes it from the order list
                self.dict["hostlist"][id].onDelete()
                del self.dict["hostlist"][id]# this removes it from the dict

    def removeFromListByID(self, id):
        """remove a HostWidget from the _itemscroll list"""
        row = self._getIndexinList(id)
        item = self._itemscroll.takeItem(row)
        item = None
        self._saveToSettings()
        self._updateSizeHint()

    def setName(self, id, name):
        self.dict["hostlist"][id].name = name
        self._saveToSettings()
        self._updateSizeHint()

    def _addNewHost(self):
        mask = HostSelect(self)
        mask.exec_()
        ret = mask.returnvalue
        if ret["valid"]:
            host = Host(self, ret["host"], ret["port"], ret["host"])
            id = str(uuid.uuid4())
            host.setID(id)
            self.dict["hostorder"].append(id)
            self.dict["hostlist"][id] = host
            self._saveToSettings()
            self._updateListWidget()

    def _updateListWidget(self):
        self._itemscroll.clear()
        for id in self.dict["hostorder"]:
            host = self.dict["hostlist"][id]

            widget = HostWidget(self)
            widget.setHost(host)
            host.widget = widget
            widget.updateState()

            item = QListWidgetItem()
            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.UserRole, id)
            item.setHidden(True)

            self._itemscroll.addItem(item)
            self._itemscroll.setItemWidget(item, widget)
            self._updateSizeHint()
        self._onFilter()

    @Slot()
    def _updateSizeHint(self):
        """update the size of a widget inside the listwidget"""
        for index in range(0, self._itemscroll.count()):
            item = self._itemscroll.item(index)
            widget = self._itemscroll.itemWidget(item)
            item.setSizeHint(widget.sizeHint())
        self._itemscroll.update()

    def createWidget(self, id):
        # ... but you can't move the widget. you need to create the widget anew
        host = self.dict["hostlist"][id]
        widget = HostWidget(self)
        host.widget = widget
        widget.setHost(host)
        widget.updateState()
        return widget

    def updateAfterMovement(self):
        pass

    def _getIndexinList(self, id):
        """given an id what is the index of the item in the listwidget"""
        for index in range(0, self._itemscroll.count()):
            item = self._itemscroll.item(index)
            if item.data(Qt.UserRole) == id:
                return index
        return -1

    def _showLineDialog(self, title, text, default=""):
        """display a simple dialog asking for a line input"""
        # create a dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        # layouts and widgets
        layout = QVBoxLayout(dialog)
        label = QLabel(text)
        layout.addWidget(label)
        line = QLineEdit(default)
        layout.addWidget(line)
        button = QPushButton("Ok")
        layout.addWidget(button)
        button.clicked.connect(lambda: dialog.close())
        # exec and get the line content
        dialog.exec_()
        return line.text()

class HostSelect(QDialog):
    def __init__(self, parent):

        self.hostlist = parent.dict["hostlist"]

        QDialog.__init__(self, parent)
        self.setWindowTitle("Add new Host")
        self.layout = QVBoxLayout(self)

        self.lbl_host = QLabel("Specifiy IP address or public hostname:")
        self.layout.addWidget(self.lbl_host)

        self.le_host = QLineEdit()
        self.layout.addWidget(self.le_host)

        self.lbl_port = QLabel("Specify port:")
        self.layout.addWidget(self.lbl_port)

        self.sb_port = QSpinBox()
        self.sb_port.setMinimum(1)
        self.sb_port.setSingleStep(1)
        self.sb_port.setMaximum(65535)
        self.sb_port.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.layout.addWidget(self.sb_port)

        self.sublayout = QHBoxLayout()
        self.layout.addLayout(self.sublayout)

        self.pb_confirm = QPushButton("OK")
        self.sublayout.addWidget(self.pb_confirm)

        self.pb_cancel = QPushButton("Cancel")
        self.sublayout.addWidget(self.pb_cancel)

        self.returnvalue = {"host": "", "port": 0, "valid": False}

        self.pb_confirm.clicked.connect(self.checkInput)
        self.pb_cancel.clicked.connect(self.close)

    def checkInput(self):
        if self.le_host.text() == "":
            QMessageBox.critical(self, "Invalid", "Host can not be empty!")
            return
        for id in self.hostlist.keys():
            if self.hostlist[id].host == self.le_host.text() and \
                            self.hostlist[id].port == self.sb_port.value():
                QMessageBox.critical(self, "Already existing", "This host has already been added.")
                return
        self.returnvalue["host"] = self.le_host.text()
        self.returnvalue["port"] = self.sb_port.value()
        self.returnvalue["valid"] = True
        self.close()

class HostWidget(QWidget):

    def __init__(self, manager):
        super(self.__class__, self).__init__()

        self.manager = manager
        self.host = None
        # self.port = None
        # self.name = ""
        # self.id = None

        # add layouts
        self.layout = QVBoxLayout(self)
        self.hbox0 = QHBoxLayout()
        self.hbox0.setAlignment(Qt.AlignLeft)
        self.hbox1 = QHBoxLayout()
        self.hbox1.setAlignment(Qt.AlignLeft)
        self.hbox2 = QHBoxLayout()
        self.hbox2.setAlignment(Qt.AlignLeft)
        self.hbox3 = QHBoxLayout()
        self.hbox3.setAlignment(Qt.AlignLeft)
        self.layout.addLayout(self.hbox0)
        self.layout.addLayout(self.hbox1)

        # add labels
        self.lbl_status = QLabel("state")
        self.lbl_status.setFixedWidth(45)
        self.hbox0.addWidget(self.lbl_status)

        # create all resources
        ico_rename = QIcon("resources/pencil.png")

        ico_remove = QIcon("resources/trash.png")

        pix_reload = qApp.style().standardPixmap(QStyle.SP_BrowserReload)
        ico_reload = QIcon(pix_reload)

        pix_up = qApp.style().standardPixmap(QStyle.SP_ArrowUp)
        ico_up = QIcon(pix_up)

        pix_down = qApp.style().standardPixmap(QStyle.SP_ArrowDown)
        ico_down = QIcon(pix_down)

        #pix_path = qApp.style().standardPixmap(QStyle.SP_CommandLink)
        #ico_path = QIcon(pix_path)
        ico_path = QIcon("resources/gear.png")

        pix_hw = qApp.style().standardPixmap(QStyle.SP_ComputerIcon)
        ico_hw = QIcon(pix_hw)

        pix_add = qApp.style().standardPixmap(QStyle.SP_FileIcon)
        ico_add = QIcon(pix_add)

        # make all buttons
        self.pb_rename = QPushButton(ico_rename, "")
        self.pb_rename.setFixedSize(30, 30)
        self.pb_rename.setToolTip("Rename")
        self.hbox1.addWidget(self.pb_rename)

        # delete button
        self.pb_remove = QPushButton(ico_remove, "")
        self.pb_remove.setFixedSize(30, 30)
        self.pb_remove.setToolTip("Remove")
        self.hbox1.addWidget(self.pb_remove)

        self.pb_reload = QPushButton(ico_reload, "")
        self.pb_reload.setFixedSize(30, 30)
        self.pb_reload.setToolTip("Reload")
        self.hbox1.addWidget(self.pb_reload)

        self.pb_up = QPushButton(ico_up, "")
        self.pb_up.setFixedSize(30, 30)
        self.pb_up.setToolTip("Move Up")
        self.hbox1.addWidget(self.pb_up)

        self.pb_down = QPushButton(ico_down, "")
        self.pb_down.setFixedSize(30, 30)
        self.pb_down.setToolTip("Move Down")
        self.hbox1.addWidget(self.pb_down)
       
        #self.pb_path = QPushButton(ico_path, "")
        #self.pb_path.setFixedSize(30, 30)
        #self.pb_path.setToolTip("Set Caffe Path")
        #self.hbox1.addWidget(self.pb_path)
          
        self.pb_hw = QPushButton(ico_hw, "")
        self.pb_hw.setFixedSize(30, 30)
        self.pb_hw.setToolTip("Manage server hardware")
        self.hbox1.addWidget(self.pb_hw)

        self.pb_add = QPushButton(ico_add, "")
        self.pb_add.setFixedSize(30, 30)
        self.pb_add.setToolTip("Add Session from Host")
        self.hbox1.addWidget(self.pb_add)

        # rest of labels

        self.lbl_name = QLabel()
        font = self.lbl_name.font()
        font.setBold(True)
        self.lbl_name.setFont(font)
        self.hbox0.addWidget(self.lbl_name)

        self.lbl_addr = QLabel()
        font = self.lbl_addr.font()
        font.setItalic(True)
        self.lbl_addr.setFont(font)
        self.hbox0.addWidget(self.lbl_addr)

        self.lbl_hostconfig = QLabel()
        self.hbox2.addWidget(self.lbl_hostconfig)

        self.lbl_hosttraining = QLabel()
        self.hbox2.addWidget(self.lbl_hosttraining)

        self.layout.addLayout(self.hbox2)

        self.lbl_hardwaremode = QLabel()
        self.hbox3.addWidget(self.lbl_hardwaremode)

        self.lbl_hardwarename = QLabel()
        self.hbox3.addWidget(self.lbl_hardwarename)

        self.layout.addLayout(self.hbox3)



        #self.lbl_caffepath = QLabel()
        #self.layout.addWidget(self.lbl_caffepath)

        self.lbl_sessionpath = QLabel()
        self.layout.addWidget(self.lbl_sessionpath)

        self.lbl_sessioncount = QLabel()
        self.layout.addWidget(self.lbl_sessioncount)

        self.lbl_projectsession = QLabel()
        self.layout.addWidget(self.lbl_projectsession)

        self.lbl_projectsession_running = QLabel()
        self.layout.addWidget(self.lbl_projectsession_running)

        self.lbl_projectsession_finished = QLabel()
        self.layout.addWidget(self.lbl_projectsession_finished)

        self.lbl_projectsession_waiting = QLabel()
        self.layout.addWidget(self.lbl_projectsession_waiting)

        self.lbl_projectsession_other = QLabel()
        self.layout.addWidget(self.lbl_projectsession_other)

        self.lbl_connectioncount = QLabel()
        self.layout.addWidget(self.lbl_connectioncount)

        self.collapseGui()

        # Number of sessions all together
        # caffepath
        # button: select caffe path

        self.pb_rename.clicked.connect(self._rename, Qt.QueuedConnection)
        self.pb_remove.clicked.connect(self._remove, Qt.QueuedConnection)
        self.pb_reload.clicked.connect(self._onReload, Qt.QueuedConnection)
        self.pb_up.clicked.connect(lambda: self.manager.moveUp("hostorder", self.host.id), Qt.QueuedConnection)
        self.pb_down.clicked.connect(lambda: self.manager.moveDown("hostorder", self.host.id), Qt.QueuedConnection)
        self.pb_hw.clicked.connect(self.showHardwareSelect)
        self.pb_add.clicked.connect(self.addSessionFromHost)

        # self.transaction = None
        # self.timer = QTimer()
        # self.timer.setSingleShot(True)
        # self.timer.setInterval(15000)
        # self.timer.timeout.connect(self._disconnected, Qt.QueuedConnection)

    def showHardwareSelect(self):
        self.hw = HardwareSelector(self.host.host, self.host.port, self)
        self.hw.exec_()
        if self.hw.selectedHW is not None:
            ret = self.host.setHardware(self.hw.selectedHW)
            if ret:
                self.updateState()
                if ret["status"]:
                    return
            QMessageBox.critical(self, "Set Hardware", "Failed to set Hardware")

    def addSessionFromHost(self):
        if not hasattr(self.manager.parent.viewManager, "project"):
            return
        pid = self.manager.parent.viewManager.project.projectId
        ret = self.host.getSessionsOfProject(pid)
        seslist = None
        if ret:
            if ret["status"]:
                if len(ret["sessions"]) > 0:
                    seslist = ret["sessions"]
                else:
                    QMessageBox.information(self, "Sessions on '" + self.host.name + "'",
                                            "No sessions for this project were found.")
            else:
                QMessageBox.critical(self, "Sessions on '" + self.host.name + "'",
                                     "No connection could be established to this host!")

        if seslist is None:
            return

        ses = askFromList(self, seslist, "Sessions on '" + self.host.name + "'",
                          "Please select a session to add.")

        if ses is None:
            return

        self.manager.parent.viewManager.sessionController.loadRemoteSession((self.host.host, self.host.port, self.host.name), ses)

    def setHost(self, host):
        self.host = host

    def _onReload(self):
        self.manager.parent.viewManager.sessionController.filterState()
        self.updateState()


    def updateState(self):
       # self._setState()
        self.lbl_name.setText(self.host.name)
        self.lbl_addr.setText("@ " + self.host.host + ":" + str(self.host.port))
        self.host.updateNetwork()

    def _rename(self):
        '''ask for a new name an set it'''
        name = self.manager._showLineDialog("Rename", "Enter a new name:", self.lbl_name.text())
        self.lbl_name.setText(name)
        self.manager.setName(self.host.id, name)

    def _remove(self):
        ret = QMessageBox.question(self.manager, "Remove this Host",
                                   "Do you really want to delete this host?",
                                   QMessageBox.Ok, QMessageBox.No)
        if ret == QMessageBox.Ok:
            self.manager.deletebyID(self.host.id)
            self.manager.removeFromListByID(self.host.id)

    def setState(self, alive=False):
        if alive:
            self.lbl_status.setText("alive")
        else:
            self.lbl_status.setText("dead")

        # set the stylesheet
        self.lbl_status.setStyleSheet("""
            QLabel{
                """ + self._statusColor(alive) + """
                border-style: solid;
                border-width: 1px;
                border-color: #555555;
                border-radius: 5px;
                text-align: center;
            }
        """)

    def _statusColor(self, status):
        '''set the color for the status'''
        if status:
            return """background-color: #00EE00;color:#000000;"""
        return """background-color:#EE0000;color:#EEEEEE;"""

    def _setHardware(self, id, name):
        color = """background-color: #00EECC;color:#000000;"""
        if id is 0:
            self.lbl_hardwaremode.setText("CPU")
            color = """background-color: #FFEE00;color:#000000;"""
        else:
            self.lbl_hardwaremode.setText("GPU " + str(id-1))
        self.lbl_hardwaremode.setStyleSheet("""
                        QLabel{
                            """ + color + """
                            border-style: solid;
                            border-width: 1px;
                            border-color: #555555;
                            border-radius: 5px;
                            text-align: center;
                        }
                    """)
        self.lbl_hardwarename.setText(name)

    def _setConfig(self, valid):
        if valid:
            self.lbl_hostconfig.setText("Valid config")
        else:
            self.lbl_hostconfig.setText("Invalid config")
        self.lbl_hostconfig.setStyleSheet("""
                        QLabel{
                            """ + self._statusColor(valid) + """
                            border-style: solid;
                            border-width: 1px;
                            border-color: #555555;
                            border-radius: 5px;
                            text-align: center;
                        }
                    """)

    def _setTraining(self, valid):
        if valid:
            self.lbl_hosttraining.setText("Host is free for training")
        else:
            self.lbl_hosttraining.setText("Training in progress")
        self.lbl_hosttraining.setStyleSheet("""
                        QLabel{
                            """ + self._statusColor(valid) + """
                            border-style: solid;
                            border-width: 1px;
                            border-color: #555555;
                            border-radius: 5px;
                            text-align: center;
                        }
                    """)

    def collapseGui(self):
        obj = [self.lbl_sessionpath, self.lbl_hostconfig, self.lbl_hostconfig,
               self.lbl_hosttraining, self.lbl_hardwaremode, self.lbl_hardwarename, self.lbl_sessioncount,
               self.lbl_connectioncount]
        obj = obj + [self.lbl_projectsession, self.lbl_projectsession_running, self.lbl_projectsession_waiting,
                     self.lbl_projectsession_finished, self.lbl_projectsession_other]
        #obj = obj + [self.pb_path, self.pb_hw, self.pb_add]
        for o in obj:
            o.setHidden(True)

    def _expandGui(self, projectsessions=False):
        obj = [self.lbl_sessionpath, self.lbl_hostconfig, self.lbl_hostconfig,
               self.lbl_hosttraining, self.lbl_hardwaremode, self.lbl_hardwarename, self.lbl_sessioncount,
               self.lbl_connectioncount, self.lbl_projectsession]
        if projectsessions:
            obj = obj + [self.lbl_projectsession_running, self.lbl_projectsession_waiting,
                         self.lbl_projectsession_finished, self.lbl_projectsession_other]
        #obj = obj + [self.pb_path, self.pb_hw, self.pb_add]
        for o in obj:
                o.setHidden(False)


    # @Slot()
    # def _updateNetwork(self):
    #     if self._connect():
    #         msg = {"key": Protocol.GETSTATUS}
    #         if hasattr(self.manager.parent, "viewManager"):
    #             if hasattr(self.manager.parent.viewManager, "project"):
    #                 msg["projectid"] = self.manager.parent.viewManager.project.projectId
    #         self.transaction.send(msg)
    #         return
    #     self.collapseGui()
    #     self.setState()

        # self.timer.stop()
        # if self.host and self.port:
        #     msg = {"key": Protocol.GETSTATUS}
        #     if hasattr(self.manager.parent, "viewManager"):
        #         if hasattr(self.manager.parent.viewManager, "project"):
        #             msg["projectid"] = self.manager.parent.viewManager.project.projectId
        #
        #
        #     ret = sendMsgToHost(self.host, self.port, msg)
        #     if ret:
        #         if "data" in ret.keys():
        #             self._parseData(ret["data"])
        #
        #             self.timer.start()
        #             return
        #

    def parseData(self, data):
        self._expandGui("projectsessions" in data.keys())
        self.setState(True)

        if "sessionpath" in data.keys():
            self.lbl_sessionpath.setText("Sessionpath: \t" + data["sessionpath"])
        if "trainOnHW" in data.keys():
            name = ""
            if "hardware" in data.keys():
                if len(data["hardware"]) >= data["trainOnHW"] and len(data["hardware"]) is not 0:
                    name = data["hardware"][data["trainOnHW"]]
            self._setHardware(data["trainOnHW"], name)
        if "sessioncount" in data.keys():
            self.lbl_sessioncount.setText("Sessions on server: \t" + str(data["sessioncount"]))
        if "connections" in data.keys():
            self.lbl_connectioncount.setText("Connections open: \t" + str(data["connections"]))
        if "config" in data.keys():
            self._setConfig(data["config"])
        if "training" in data.keys():
            self._setTraining(data["training"])
        if "projectsessions" in data.keys():
            pdat = data["projectsessions"]
            self.lbl_projectsession.setText("Sessions of this project: \t" + str(pdat["count"]))
            self.lbl_projectsession_running.setText("    running/paused: \t" + str(pdat["running"]))
            self.lbl_projectsession_finished.setText("    finished: \t\t" + str(pdat["finished"]))
            self.lbl_projectsession_waiting.setText("    waiting: \t\t" + str(pdat["waiting"]))
            other = pdat["count"] - pdat["finished"] - pdat["waiting"] - pdat["running"]
            self.lbl_projectsession_other.setText("    other: \t\t" + str(other))
        else:
            self.lbl_projectsession.setText("Sessions of this project: \t0")
        QMetaObject.invokeMethod(self.manager, "_updateSizeHint", Qt.QueuedConnection)

    # def _connect(self):
    #     if self.transaction is None:
    #         ct = buildTransaction(self.host, self.port)
    #         if ct is not None:
    #             self.transaction = ct
    #             self.transaction.socketClosed.connect(self._disconnected)
    #             self.transaction.bufferReady.connect(self._heartbeat)
    #             self.timer.start()
    #             return True
    #     return self.transaction is not None

    # def _disconnected(self):
    #     self.timer.stop()
    #     # self.transaction.socketClosed.disconnect()
    #     # self.transaction.bufferReady.disconnect()
    #     if self.transaction.isConnected():
    #         self.transaction.close()
    #     del self.transaction
    #     self.transaction = None
    #     self.collapseGui()
    #     self.setState()
    #     QMetaObject.invokeMethod(self.manager, "_updateSizeHint", Qt.QueuedConnection)

    # def _heartbeat(self):
    #     ret = self.transaction.asyncRead()
    #     if ret is not None:
    #         if ret["key"] is Protocol.GETSTATUS:
    #             if "data" in ret.keys():
    #                 self.timer.stop()
    #                 self.timer.start()
    #                 self.parseData(ret["data"])
    #
    #                 if hasattr(self.manager.parent, "viewManager"):
    #                     if hasattr(self.manager.parent.viewManager, "project"):
    #                         pid = self.manager.parent.viewManager.project.projectId
    #                         if "projectsessions" in ret["data"].keys():
    #                             if "pid" in ret["data"]["projectsessions"].keys():
    #                                 if not ret["data"]["projectsessions"]["pid"] == pid:
    #                                     self._updateNetwork()
    #                             else:
    #                                 # broken protocol
    #                                 self._disconnected()
    #                         else:
    #                             self._updateNetwork()



class Host(QObject):
    """ This class encapsulates a host known by Barista(GUI). All communication with
        the actual server and corresponding data is managed here.
    """
    def __init__(self, parent, host, port, name):
        super(self.__class__, self).__init__()
        self.manager = parent
        self.widget = None #type: HostWidget

        self.host = host
        self.port = port
        self.name = name
        self.id = None

        self.transaction = None
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(15000)
        self.timer.timeout.connect(self.disconnected, Qt.QueuedConnection)

    def setID(self, id):
        self.id = id

    def setHardware(self, hid):
        msg = {"key": Protocol.SETHARDWARE, "hid": hid}
        return sendMsgToHost(self.host, self.port, msg)

    def getSessionsOfProject(self, pid):
        msg = {"key": Protocol.GETSESSIONS, "pid": pid}
        return sendMsgToHost(self.host, self.port, msg)

    #def setCaffePath(self, path):
    #    msg = {"key": Protocol.SETCAFFEPATH, "path": path}
    #    return sendMsgToHost(self.host, self.port, msg)

    def connect(self):
        if self.transaction is None:
            ct = buildTransaction(self.host, self.port)
            if ct is not None:
                self.transaction = ct
                self.transaction.socketClosed.connect(self.disconnected)
                self.transaction.bufferReady.connect(self.heartbeat)
                self.timer.start()
                return True
        return self.transaction is not None

    def disconnected(self):
        self.timer.stop()
        # self.transaction.socketClosed.disconnect()
        # self.transaction.bufferReady.disconnect()
        if self.transaction.isConnected():
            self.transaction.close()
        del self.transaction
        self.transaction = None

        self.widget.collapseGui()
        self.widget.setState()
        QMetaObject.invokeMethod(self.manager, "_updateSizeHint", Qt.QueuedConnection)

    def heartbeat(self):
        ret = self.transaction.asyncRead()
        if ret is not None:
            if ret["key"] is Protocol.GETSTATUS:
                if "data" in ret.keys():
                    self.timer.stop()
                    self.timer.start()
                    self.widget.parseData(ret["data"])

                    if hasattr(self.manager.parent, "viewManager"):
                        if hasattr(self.manager.parent.viewManager, "project"):
                            pid = self.manager.parent.viewManager.project.projectId
                            if "projectsessions" in ret["data"].keys():
                                if "pid" in ret["data"]["projectsessions"].keys():
                                    if not ret["data"]["projectsessions"]["pid"] == pid:
                                        self.updateNetwork()
                                else:
                                    # broken protocol
                                    self.disconnected()
                            else:
                                self.updateNetwork()

    @Slot()
    def updateNetwork(self):
        if self.connect():
            msg = {"key": Protocol.GETSTATUS}
            if hasattr(self.manager.parent, "viewManager"):
                if hasattr(self.manager.parent.viewManager, "project"):
                    msg["projectid"] = self.manager.parent.viewManager.project.projectId
            self.transaction.send(msg)
            return
        self.widget.collapseGui()
        self.widget.setState()

    def onDelete(self):
        if self.transaction:
            self.transaction.close()
            self.transaction = None
