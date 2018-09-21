import os

from PyQt5.QtCore import QPoint, Qt, pyqtSignal
from PyQt5.QtGui import QCursor
from PyQt5.QtGui import QStandardItem
from PyQt5.QtWidgets import (
    QWidget,
    QPushButton,
    QMessageBox,
    QComboBox,
    QListWidget,
    QToolButton,
    QMenu,
    QAction,
    QVBoxLayout,
    QHBoxLayout,
    QListWidgetItem,
    QAbstractItemView,
    QFileDialog
)

import backend.caffe.loader as loader
from gui.main_window.docks.dock import DockElement
from gui.main_window.docks.session.session_item import SessionWidget
from gui.gui_util import askFromList
from backend.barista import caffe_versions
from backend.barista import project


class DockElementSessions(DockElement):

    def __init__(self, mainWindow, title):
        DockElement.__init__(self, mainWindow, title)
        self.mainWindow = mainWindow
        self.default_actions = mainWindow.actions
        self.name = title
        self.resize(300, 500)
        self.__setupGui()
        self.controller = None
        self.displayed_sessions = None

    def showDialog(self, text, info, title, buttons, location=None):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)

        msg.setText(text)
        msg.setInformativeText(info)
        msg.setWindowTitle(title)
        msg.setStandardButtons(buttons)
        if location is None:
            location = QCursor.pos()
        msg.move(location - QPoint(msg.sizeHint().width() / 2,
                                   msg.sizeHint().height() / 2))

        return msg.exec_()

    def __setupGui(self):
        """ Create the widgets for this view.
        """
        self.widget = QWidget()
        vbox = QVBoxLayout()
        hbox = QHBoxLayout()
        #
        #
        # Create buttons
        # create a new Session
        self.new = QPushButton()
        self.new.setToolTip('Create Session')
        self.new.setText('New')
        self.new.setEnabled(True)
        self.new.clicked.connect(self._onCreate)
        hbox.addWidget(self.new)


        self.status_combo_box = QComboBox()
        self.status_combo_box.clear()
        self.status_combo_box.move(120, 30)
        model = self.status_combo_box.model()
        states = [
            'ALL',
            'RUNNING',
            'PAUSED',
            'WAITING',
            'FAILED',
            'FINISHED',
            'INVALID'
        ]
        for state in states:
            item = QStandardItem(state)
            model.appendRow(item)
        hbox.addWidget(self.status_combo_box)


        vbox.addLayout(hbox)

        self.session_list = QListWidget()
        self.session_list.setSelectionMode(QAbstractItemView.SingleSelection)
        vbox.addWidget(self.session_list)

        self.widget.setLayout(vbox)
        self.setWidget(self.widget)

    def showSessions(self, sessions):
        """ Show the session widgets in the list.
        """
        self.session_list.clear()
        for sid in reversed(sorted(sessions.keys())):
            session = sessions[sid]
            item = QListWidgetItem(self.session_list)
            item.setData(Qt.UserRole, sid)
            widget = SessionWidget(session, self.controller, self.session_list)
            item.setSizeHint(widget.sizeHint())
            self.session_list.addItem(item)
            self.session_list.setItemWidget(item, widget)
        self.displayed_sessions = sessions

    def sessionStateChanged(self, session, state):
        """ Notify the widget of the given session about changed state.
        """
        for item in self.session_list.findItems('', Qt.MatchRegExp):
            widget = self.session_list.itemWidget(item)
            if widget:
                if widget.getSession() is session:
                    widget.sessionStateChanged(state)

    def sessionIterationChanged(self, session):
        """ Notify the widget of the given session about iteration-change.
        """
        for item in self.session_list.findItems('', Qt.MatchRegExp):
            widget = self.session_list.itemWidget(item)
            if widget:
                if widget.getSession() is session:
                    widget.sessionIterationChanged()

    def sessionSnapshotAdded(self, session):
        """ Notify the widget of the given session about an added snapshot.
        """
        for item in self.session_list.findItems('', Qt.MatchRegExp):
            widget = self.session_list.itemWidget(item)
            if widget:
                if widget.getSession() is session:
                    widget.addAllSnapshots()

    def setSelectedSID(self, SID):
        """ Sets the list widgets selection to the session with SID.
        """
        numItems = self.session_list.count()
        for idx in range(numItems):
            buff = self.session_list.model().index(idx, 0)
            _sid = buff.data(Qt.UserRole)
            if _sid == SID:
                self.session_list.setCurrentIndex(buff)

    def getSelectedSessions(self):
        """ Return the currently selected sessions as a list.
        """
        ret = []
        for item in self.session_list.selectedItems():
            sid = item.data(Qt.UserRole)
            sess = self.displayed_sessions[sid]
            if sess:
                ret.append(sess)
        return ret

    def _onCreate(self):
        list = self.mainWindow.hostManager.getActiveHostList()  # type: list
        if len(list) == 0:
            self.controller.justCreateNewSession()
            return
        list.insert(0, ["local", "Local Host"])
        ret = askFromList(self, list, "Select Host for new Session",
                          "You have configured remote Hosts.\nPlease select where to create the Session.")
        if ret:
            if ret == "local":
                self.controller.justCreateNewSession()
            else:
                remote = self.mainWindow.hostManager.getHostDataById(ret)
                self.controller.justCreateNewSession(remote)
        return

    def onSelectionChanged(self):
        """ Called when the list selection changed.
        """
        if len(self.session_list.selectedItems()) == 1:
            sid = self.getSelectedSessions()[0].getSessionId()
            self.default_actions.changeSession(newSID=sid)

    def getFilterState(self):
        """ Return the text of the currently filtered state.
        """
        return str(self.status_combo_box.currentText())

    def setController(self, controller):
        """ Set the controller and connect actions to contoller.
        """
        self.controller = controller
        self.controller.setSessionGui(self)
        self.status_combo_box.currentIndexChanged.connect(
            self.controller.filterState)
        self.session_list.itemSelectionChanged.connect(
            self.onSelectionChanged)
