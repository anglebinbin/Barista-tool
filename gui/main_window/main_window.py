# To change this license header, choose License Headers in Project Properties.
# To change this template file, choose Tools | Templates
# and open the template in the prototxt_editor.

from PyQt5 import QtWidgets, QtCore

from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSignal

import gui.main_window.default_actions
import gui.main_window.status_bar
from backend.barista.session.session_utils import State
from backend.caffe import dict_helper
from gui.caffe_version_manager import caffe_version_manager
from gui.input_manager import input_manager
from gui.host_manager import host_manager
from gui.main_window import view_manager
from gui.main_window.node_editor.node_editor import NodeEditor
from gui.network_manager import network_manager
from gui.prototxt_editor import editor_widget

class UiMainWindow(QtWidgets.QMainWindow):

    sessionSelectionChanged = pyqtSignal(object)

    def __init__(self, actions=None, desktop = None):
        QtWidgets.QMainWindow.__init__(self)
        self.setUnifiedTitleAndToolBarOnMac(True)

        self.disabled = False

        #self.setGeometry(desktop.screenGeometry())   #fullscreen
        self.setWindowTitle("Barista")
        self.setWindowIcon(QIcon('./resources/icon.png'))

        # Initialize menu and status bar
        if actions:
            self.actions = actions
            self.actions.setParent(self)

        else:
            self.actions = gui.main_window.default_actions.DefaultActions(self)
        self.editor = editor_widget.EditorWidget(parent=self)
        self.editor.setWindowTitle("Barista Network Editor")
        self.actions.setEditor(self.editor)
        self.inManager = input_manager.InputManager(self)
        self.actions.setInputManager(self.inManager)
        self.hostManager = host_manager.HostManager(self)
        self.actions.setHostManager(self.hostManager)
        caffeVersionManager = caffe_version_manager.CaffeVersionManager(self.hostManager, self.actions)
        caffeVersionManager.setWindowTitle("Caffe Version Manager")
        self.actions.setVersionManager(caffeVersionManager)
        self.setMenuBar(self.actions.buildMenuBar())
        filetoolbar = self.actions.buildFileToolbar()
        self.addToolBar(filetoolbar)
        self.actions.addToolBarEntry(filetoolbar)
        edittoolbar=self.actions.buildEditToolbar()
        self.addToolBar(edittoolbar)
        self.actions.addToolBarEntry(edittoolbar)
        #runtoolbar=self.actions.buildRunToolbar()
        #self.addToolBar(runtoolbar)
        #self.actions.addToolBarEntry(runtoolbar)
        # Create the view manager
        self.viewManager = view_manager.ViewManager(self, self.actions)
        self.actions.setViewManager(self.viewManager)
        self.setStatusBar(gui.main_window.status_bar.UiStatusBar(self))
        # Create the view
        self.viewManager.createView()
        # Create the node prototxt_editor as the central widget
        self.nodeEditor = NodeEditor(self)
        self.setCentralWidget(self.nodeEditor.getView())
        self.actions.setScene(self.nodeEditor.getView().scene())
        # Connect the node editor context menu.
        self.nodeEditor.getView().arrangeVerticallyClicked.connect(self.actions.sortSceneActionVertical.trigger)
        self.nodeEditor.getView().arrangeHorizontallyClicked.connect(self.actions.sortSceneAction.trigger)
        # Create the network manager to save all layers and handle layer-related events
        self.networkManager = network_manager.NetworkManager(self.viewManager.getActiveLayersDock(),
                                                             self.viewManager.getLayerPropertyDock(),
                                                             self.viewManager.getSolverPropertyDock,
                                                             self.nodeEditor)


        # Link networkManager to menuBar
        self.actions.setNetworkManager(self.networkManager)
        # As a test, open the dummy network file
        self.networkManager.setNetwork(dict_helper.bareNet("default"))

        #connect all signals
        self.actions.quitTriggered.connect(self.close)
        self.actions.projectChanged.connect(self._onProjectChanged)
        self.networkManager.modifiedChanged.connect(self._onNetworkChanged)
        self.viewManager.sessionController.sessionSelectionChanged.connect(self._onSessionChanged)
        self.networkManager.newStateData.connect(self._onStateDictChanged)
        self.viewManager.sessionController.sessionStateRefreshed.connect(self.disableEditing)
        
        self.rec_installEventfilter()

    def eventFilter(self, source, event):
        if event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton:
            self.viewManager.onVisibilityChange()
        return super(UiMainWindow, self).eventFilter(source, event)


    def rec_installEventfilter(self):
        def recursive_set(parent):
            for child in parent.findChildren(QtCore.QObject):
                try:
                    child.installEventFilter(self)
                except:
                    pass
                recursive_set(child)

        self.installEventFilter(self)
        recursive_set(self)

    def availableActions(self):
        return self.actions

    def showPathWarning(self):
        self.warningBox = QtWidgets.QMessageBox()
        self.warningBox.setText("caffe-path does not exists on your PC, please edit caffe-path in settings and restart the program")
        self.warningBox.setIcon(2)
        self.warningBox.show()

    def closeEvent(self, event):
        # check if there are running sessions and ask the user to pause them
        if self.actions.checkRunningSessions() is False:
            event.ignore()
            return
        # Save the current view
        self.viewManager.saveView()
        # Ask the user if he wants to save project changes if necessary.
        if self.actions.askUserAndSave(self):
            # We need to process events here, because when the project is saved
            # an event is emitted. If this doesn't get processed, the main window
            # will not be closed.
            QtWidgets.QApplication.processEvents()
            event.accept()
        else:
            # The user decided to abort the close event.
            event.ignore()

    def _onProjectChanged(self, project):
        from backend.caffe.path_loader import PathLoader

        self.setWindowTitle("Barista - {}".format(project.getProjectName()))
        #reload the caffe information
        self.actions._versionManager.updateProject(project)

        # TODO: Those lines should not be commented, right?
        # self.editor = editor_widget.EditorWidget(self)
        # self.editor.setWindowTitle("Barista Network Editor")
        # network_manager.helper.bareNet(project.getProjectName())
        # self.viewManager.loadView()

    def _onStateDictChanged(self, stateDict):
        self.viewManager.project.getActiveSession().state_dictionary = stateDict

    def _onSessionChanged(self):
        activeSession = self.viewManager.project.getActiveSession()
        self.networkManager.setState(activeSession.state_dictionary if activeSession is not None else None)

    def _onNetworkChanged(self, changeSinceLastSave):
        #update the status bar
        self.statusBar().showModifiedFlag(changeSinceLastSave)
        #update the current session
        self.viewManager.project.setActiveSessionStateDict(self.networkManager.getStateDictionary())

    def _onSolverChanged(self, changedItems, changedObject):
        if "max_iter" in changedItems:
            activeSession = self.viewManager.project.getActiveSession()
            if not activeSession.isRemote():
                activeSession.setMaxIteration(0)
                self.viewManager.sessionController.sessionIterationChanged(activeSession)

    def disableEditing(self, state):
        """ Handle event on state change of a session and disable/enable editing.
        """
        disable = False
        if state in [State.RUNNING, State.PAUSED, State.FINISHED, State.NOTCONNECTED, State.FAILED]:
            disable = True
        self.actions.disableEditing(disable)
        self.viewManager.disableEditing(disable)
        self.nodeEditor.disableEditing(disable)
        self.inManager.disableEditing(disable)
        self.editor.disableEditing(disable)
        self.show()
        self.disabled = disable

    def getDisabled(self):
        return self.disabled
