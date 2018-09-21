import json
import sys
import os
import re
import tempfile
import traceback
import backend.barista.caffe_versions as caffeVersions

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QPixmap, QIcon, QTransform
from PyQt5.QtWidgets import QStyle, QMessageBox

from backend.barista.constraints.session_run.training import checkMinimumTrainingRequirements
from backend.barista.project import Project, dirIsProject
from backend.barista.session.client_session import ClientSession
from backend.barista.session.session_utils import State
from backend.barista.utils.logger import Log
from backend.barista.utils.settings import applicationQSetting
from backend.caffe.proto_info import UnknownLayerTypeException
from backend.caffe import loader
from backend.caffe import saver
from gui.deployment_dialog import DeploymentDialog
from gui.export_solver_dialog import ExportSolverDialog
from gui.gui_util import getNewProjectDir, getOpenProjectDir
from gui.change_caffe_version_dialog import CaffeVersionDialog


class RecentlyData(QtCore.QObject):
    """ Model for Recently-Menu """
    recentlyChanged = pyqtSignal()

    def __init__(self, parent=None, maxHistory=5):
        super(RecentlyData, self).__init__(parent)
        self._recently = []
        self._maxHistory = maxHistory

    def addRecently(self, text, data):
        """ Add an entry.
            It will contains the given data but show the given text.
        """
        # Remove if already exists (because of order)
        if [text, data] in self._recently:
            self._recently.remove([text, data])
        self._recently.append([text, data])
        # Delete oldest if needed
        if len(self._recently) >= self._maxHistory:
            self._recently = self._recently[-self._maxHistory:]
        self.recentlyChanged.emit()

    def setRecently(self, recentlylist):
        """ Set entries from a list.
            recentlylist should look like [[text1,data1],[text2,data2],...]
        """
        if type(recentlylist) != list:
            return
        self._recently = recentlylist
        if len(self._recently) >= self._maxHistory:
            self._recently = self._recently[-self._maxHistory:]
        self.recentlyChanged.emit()

    def getRecently(self):
        """ Returns the list of recent entries in form of
            [[text1, data1],[text2,data2],...]
        """
        return self._recently

    def getMostRecent(self):
        """ returns: Most recent [text, data] tuple or None (if there are no recent elements)
        """
        try:
            return self._recently[-1]
        except IndexError:
            return None

    def recentlyFromSerialization(self, string):
        """ Deserialize recent entries from a json-string """
        self.setRecently(json.loads(string))

    def serializeRecently(self):
        """ Serialize recent entries into a json-string and return it"""
        return json.dumps(self._recently)


class RecentMenu(QtWidgets.QMenu):
    """ QMenu showing recent files with a clear entry """
    recentlySelected = pyqtSignal(object)

    def __init__(self, name, recentlydata, parent=None):
        super(RecentMenu, self).__init__(name, parent)
        self._data = recentlydata  # type: RecentlyData
        self._data.recentlyChanged.connect(self.__rebuildMenu)
        self.__rebuildMenu()

    def __rebuildMenu(self):
        self.clear()
        recently = self._data.getRecently()
        for i in range(0, len(recently)):
            # Build Recently-Menu Reverse
            (text, data) = recently[-i - 1]
            validPath = os.path.exists(text)
            if not validPath:
                text = '(?) ' + text
            try:
                action = self.addAction("{}. {}".format(i, text))
            except UnicodeEncodeError:
                action = self.addAction("{}. (?)".format(i))
                action.setEnabled(False)
            else:
                if not validPath:
                    action.setEnabled(False)
            action.setData(data)
            action.triggered.connect(self.__recentlyFound)

        self.addSeparator()
        clearAction = self.addAction(self.tr("Clear"))
        clearAction.triggered.connect(lambda: self._data.setRecently([]))

    def __recentlyFound(self):
        sender = self.sender()
        data = sender.data()
        self.recentlySelected.emit(data)


class DefaultActions(QtCore.QObject):
    """ DefaultActions implements function which are used by the user.
        It can expose this function by building menus and toolbars.
    """

    projectChanged = pyqtSignal(object)
    parentChanged = pyqtSignal(object)
    netManagerChanged = pyqtSignal(object)
    viewManagerChanged = pyqtSignal(object)

    quitTriggered = pyqtSignal()

    def __init__(self, parentWdg=None):
        """ Initialize DefaultActions.
            parentWdg will be used for dialogs to block interaction to it if wanted.
        """
        super(DefaultActions, self).__init__()
        self._parent = parentWdg
        self._netManager = None
        self._viewManager = None
        self._scene = None
        self._editor = None
        self._editMode = None
        self._project = None
        self._versionManager = None
        self._inputManager = None
        self._hostManager = None
        self._solverDialog = None
        self._deploymentDialog = None

        # Build all actions
        self.openNetAction = self._buildAction(self.tr("&Import Network"), None, lambda: self.openNetDialog())
        self.openSolverAction = self._buildAction(self.tr("Import Solver"), None, lambda: self.openSolverDialog())
        self.saveNetAction = self._buildAction(self.tr("&Export Network"), None, lambda: self.saveNetDialog())
        self.saveSolverAction = self._buildAction("&Export Solver", None, lambda: self.saveSolverDialog())
        self.exitAction = self._buildAction(self.tr("&Exit"), "Ctrl+Q", self.quitTriggered, None,
                                            self.tr("Close Application"))

        self.undoAction = self._buildAction(self.tr("Undo"), "Ctrl+Z", lambda: self._netManager.undo(),
                                            icon="resources/leftArrow.png")
        self.redoAction = self._buildAction(self.tr("Redo"), "Shift+Ctrl+Z", lambda: self._netManager.redo(),
                                            icon="resources/rightArrow.png")

        self.editNetAction = self._buildAction(self.tr("Edit &Network as Prototxt"), "Ctrl+E", self.openNetEditor)
        self.editSolverAction = self._buildAction(self.tr("Edit &Solver as Prototxt"), "Shift+Ctrl+E",
                                                  self.openSolverEditor)
        self.viewInputManager = self._buildAction(self.tr("&Input Manager"), "Ctrl+I", self.openInputManager, icon="resources/input_manager.png")
        self.viewHostManager = self._buildAction(self.tr("&Host Manager"), "Ctrl+H", self.openHostManager, icon="resources/host_manager.png")
        self.viewCaffeVersionManager = self._buildAction(self.tr("&Caffe Version Manager"), "Ctrl+M", self.changeCaffeVersion, icon="resources/CVM.png")

        self.loadDefaultViewAction = self._buildAction(self.tr("&Load Default View"), None, self._loadDefaultView)

        self.sortSceneAction = self._buildAction(self.tr("Arrange Layers Horizontally"), None, self._sortScene)
        self.sortSceneActionVertical = self._buildAction(self.tr("Arrange Layers Vertically"), None, self._sortSceneVertical)

        self.newProjectAction = self._buildAction(self.tr("New Project"), "Ctrl+N", lambda: self.newProjectDialog(),
                                                  icon="resources/newDocument.png")
        self.loadProjectAction = self._buildAction(self.tr("Load Project"), "Ctrl+O", lambda: self.openProjectDialog(),
                                                   icon="resources/openDocument.png")
        self.saveProjectAction = self._buildAction(self.tr("Save Project"), "Ctrl+S", lambda: self.saveProject(),
                                                   icon="resources/saveProject.png")

        self.deployAction = self._buildAction(self.tr("Deploy and export"), None,
                                              lambda: self.openDeploymentDialog())

        # Build menus
        self.dockMenu = QtWidgets.QMenu("Docks", self._parent)
        self.toolBarMenu = QtWidgets.QMenu("Toolbars", self._parent)

        # Recently-Menu
        self.recentNetData = RecentlyData()
        self.recentSolverData = RecentlyData()
        self.recentProjectsData = RecentlyData()
        self._loadActionSettings()

        self.recentNetData.recentlyChanged.connect(self._saveActionSettings)
        self.recentSolverData.recentlyChanged.connect(self._saveActionSettings)
        self.recentProjectsData.recentlyChanged.connect(self._saveActionSettings)

        self.recentNetMenu = None
        self.recentSolverMenu = None

        # Actions for the active session
        self.startSessionAction = self._buildAction("Start Session", "F5",
                                                    lambda: self._viewManager.getSessionsDock().onStart(),
                                                    icon=QIcon(QPixmap('resources/start.png')))
        self.pauseSessionAction = self._buildAction("Pause Session", "F6",
                                                    lambda: self._viewManager.getSessionsDock().onPause(),
                                                    icon=QIcon(QPixmap('resources/pause.png')))
        self.snapshotAction = self._buildAction("Create Snapshot", "F8",
                                                lambda: self._viewManager.getSessionsDock().onSnap(),
                                                icon=QIcon(QPixmap('resources/snap.png')))

        def projectHelper(p):
            if self._versionManager and p:
                self._versionManager.updateProject(p)

        self.projectChanged.connect(projectHelper)

    def setParent(self, parent):
        """ Sets the parent widget.
            It is primary used to block interaction when opening a dialog
        """
        if parent == self._parent: return
        # oldp = self._parent
        self._parent = parent
        self.parentChanged.emit(parent)

    # Recent-Data

    def _loadActionSettings(self):
        settings = applicationQSetting()
        settings.beginGroup("Actions")
        self.recentNetData.recentlyFromSerialization(settings.value("recent_nets", "[]"))
        self.recentSolverData.recentlyFromSerialization(settings.value("recent_solvers", "[]"))
        self.recentProjectsData.recentlyFromSerialization(settings.value("recent_projects", "[]"))
        settings.endGroup()

    def _saveActionSettings(self):
        settings = applicationQSetting()
        settings.beginGroup("Actions")
        settings.setValue("recent_nets", self.recentNetData.serializeRecently())
        settings.setValue("recent_solvers", self.recentSolverData.serializeRecently())
        settings.setValue("recent_projects", self.recentProjectsData.serializeRecently())
        settings.endGroup()

    # Recent-Gui-Menu

    def buildRecentNetMenu(self, name="Recent Nets", parent=None):
        return self.__buildRecentMenu(name, self.recentNetData, parent, self.openNet)

    def buildRecentSolverMenu(self, name="Recent Solvers", parent=None):
        return self.__buildRecentMenu(name, self.recentSolverData, parent, self.openSolver)

    def buildRecentProjectMenu(self, name="Recent Projects", parent=None, callback=None):
        if callback is None:
            callback = lambda directory: self.setProjectAskUserForSave(directory, parent)
        return self.__buildRecentMenu(name, self.recentProjectsData, parent, callback)

    def __buildRecentMenu(self, name, data, parent, action):
        if parent is None:
            parent = self._parent
        res = RecentMenu(name, data, parent)
        res.recentlySelected.connect(action)
        return res

    # Update Action-State
    def updateActionState(self):
        """ Update Actions (setup enabled e.g.)"""
        self._updateUndoRedoState()
        self.saveProjectAction.setEnabled(not self._project is None)

    def _updateUndoRedoState(self):
        if self._netManager:
            self.undoAction.setEnabled(self._netManager.canUndo())
            self.redoAction.setEnabled(self._netManager.canRedo())

    # Build-Gui-Elements

    def buildMenuBar(self, parent=None):
        """ Build a menubar with all available actions. Set its parent to the given one. """
        if parent is None:
            parent = self._parent
        bar = QtWidgets.QMenuBar(self._parent)

        fileMenu = bar.addMenu(self.tr("&File"))  # type: QtWidgets.QMenu
        fileMenu.addAction(self.newProjectAction)
        fileMenu.addAction(self.loadProjectAction)
        fileMenu.addMenu(self.buildRecentProjectMenu(parent=parent))
        fileMenu.addAction(self.saveProjectAction)
        fileMenu.addSeparator()
        fileMenu.addAction(self.openNetAction)
        fileMenu.addAction(self.openSolverAction)
        fileMenu.addAction(self.saveNetAction)
        fileMenu.addAction(self.saveSolverAction)
        fileMenu.addSeparator()
        self.recentNetMenu = self.buildRecentNetMenu(parent=parent)
        fileMenu.addMenu(self.recentNetMenu)
        self.recentSolverMenu = self.buildRecentSolverMenu(parent=parent)
        fileMenu.addMenu(self.recentSolverMenu)
        fileMenu.addSeparator()
        fileMenu.addAction(self.exitAction)

        editMenu = bar.addMenu(self.tr("&Edit"))
        editMenu.addAction(self.undoAction)
        editMenu.addAction(self.redoAction)
        editMenu.addSeparator()
        editMenu.addAction(self.sortSceneAction)
        editMenu.addAction(self.sortSceneActionVertical)
        editMenu.addSeparator()
        editMenu.addAction(self.editNetAction)
        editMenu.addAction(self.editSolverAction)

        toolsMenu = bar.addMenu(self.tr("&Tools"))
        toolsMenu.addAction(self.viewCaffeVersionManager)
        toolsMenu.addAction(self.viewInputManager)
        toolsMenu.addAction(self.viewHostManager)

        viewMenu = bar.addMenu(self.tr("&View"))
        viewMenu.addMenu(self.dockMenu)
        viewMenu.addMenu(self.toolBarMenu)
        viewMenu.addSeparator()
        viewMenu.addAction(self.loadDefaultViewAction)

        deployMenu = bar.addMenu(self.tr("&Deployment"))
        deployMenu.addAction(self.deployAction)

        viewMenu.aboutToShow.connect(lambda: self.triggerViewMenu())
        return bar

    def triggerViewMenu(self):
        """ Update dock visibility when ViewMenu was clicked """
        self._viewManager.onVisibilityChange()

    def addDockMenuEntry(self, dockwdg, title=None):
        """ Add a new menu entry for the dockwidget dockwdg """
        if title is None:
            title = dockwdg.windowTitle()
        action = self.dockMenu.addAction(title)
        action.setCheckable(True)
        action.setChecked(dockwdg.isVisible())
        action.triggered.connect(lambda: self._viewManager.dockAction(title))
        dockwdg.visibilityChanged.connect(lambda vis: action.setChecked(vis))
        return action

    def addToolBarEntry(self, toolbar):
        """ Add a new menu entry for the visibility of the given toolbar """
        action = self.toolBarMenu.addAction(toolbar.windowTitle())
        action.setCheckable(True)
        action.setChecked(toolbar.isVisible())
        action.triggered.connect(toolbar.setVisible)
        toolbar.visibilityChanged.connect(action.setChecked)
        return toolbar

    def buildFileToolbar(self, title="File"):
        """ Build toolbar with default actions for file"""
        toolbar = QtWidgets.QToolBar(title)
        toolbar.setObjectName("FileToolbar")
        toolbar.addAction(self.newProjectAction)
        toolbar.addAction(self.loadProjectAction)
        toolbar.addAction(self.saveProjectAction)
        toolbar.addAction(self.viewInputManager)
        toolbar.addAction(self.viewHostManager)
        toolbar.addAction(self.viewCaffeVersionManager)
        return toolbar

    def buildEditToolbar(self, title="Edit"):
        """ Build toolbar with default actions for edit"""
        toolbar = QtWidgets.QToolBar(title)
        toolbar.setObjectName("EditToolbar")
        toolbar.addAction(self.undoAction)
        toolbar.addAction(self.redoAction)
        return toolbar

    def buildRunToolbar(self, title="Active Job"):
        """ Build toolbar with default actions for edit"""
        toolbar = QtWidgets.QToolBar(title)
        toolbar.setObjectName("RunToolbar")
        toolbar.addAction(self.startSessionAction)
        toolbar.addAction(self.pauseSessionAction)
        toolbar.addAction(self.snapshotAction)
        return toolbar

    def _buildAction(self, text, shortcut, fun, icon=None, statustip=None, standardPixmap=None):
        """ Build QAction with given parameter """
        res = QtWidgets.QAction(text, self._parent)
        if standardPixmap:
            icon = QtWidgets.qApp.style().standardIcon(standardPixmap)
        if icon:
            if type(icon) == str:
                icon = QtGui.QIcon(icon)
            res.setIcon(icon)
        if statustip:
            res.setStatusTip(statustip)
        if shortcut:
            res.setShortcut(shortcut)
        if fun:
            res.triggered.connect(fun)
        return res

    # Project

    def checkRunningSessions(self):
        """ Check if there are running sessions and if thats the case ask the
            user to pause them.
        """
        if self._project:
            if self._project.hasRunningSessions():
                QM = QtWidgets.QMessageBox
                answer = QM.question(self._parent, self.tr("Pause sessions?"), self.tr(
                    "There are running sessions. To proceed all sessions must be paused. Do you want to pause them?"),
                                     QM.Yes | QM.Cancel, QM.Cancel)
                if answer == QM.Yes:
                    self._project.pauseRunningSessions()
                    return True
                if answer == QM.Cancel:
                    return False

    def checkSessionState(self, session, showWarnings):
        valid = checkMinimumTrainingRequirements(session=session, parentGui=self._viewManager.sessionController.sessionGui, reportToUser=showWarnings)
        if valid:
            session.setState(session.getState())
        else:
            if not session.getState() == State.NOTCONNECTED:
                session.setState(State.INVALID)

    def setProjectAskUserForSave(self, project_dir, parent=None):
        """ Load the project from the given dir.
            The user will be asked for saving the current project if
            there are some unsaved changes.
        """
        try:
            if self.checkRunningSessions() is False:
                return
            if os.path.exists(project_dir) is False:
                if self.askRecreateProject(parent):
                    os.makedirs(project_dir)
                else:
                    return
            self.recentProjectsData.addRecently(project_dir, project_dir)
            project = Project(project_dir)
            if parent is None:
                parent = self._parent
            if self.askUserAndSave(parent):
                self.setProject(project)
        except:
            self.errorMsg("Error while trying to use an existing project.", "set_project")
            return False

    def setProject(self, project):
        """ Set the project.
            It will be loaded automatically in gui if networkmanager is set.
        """
        try:
            if self._project == project: return

            # Register project as (most) recently used
            self.recentProjectsData.addRecently(project.projectRootDir, project.projectRootDir)

            self.removeProjectFromPlotter(self._project)
            self._project = project
            self._inputManager.clearInputManager()
            self._viewManager.setProject(self._project)
            self.updateActionState()
            self.__propagateProjectToNetworkManager()
            self._project.newSession.connect(self.registerNewSession)
            self._project.deleteSession.connect(self.disconnectSession)
            activeSID = self._project.getActiveSID()
            if activeSID:
                self.registerNewSession(activeSID)
                self.selectSessionInList(activeSID)
            self.projectChanged.emit(project)

        except:
            self.errorMsg("Error while trying to use an existing project.", "set_project")
            return False

    def removeProjectFromPlotter(self, project):
        """ Removes the given project from the plotter.
        """
        if project:
            for session in project.getSessions().values():
                self._viewManager.getPlotter().removeLog(str(session.getLogId()), str(session.getLogFileName(True)))

    def selectSessionInList(self, SID):
        self._viewManager.getSessionsDock().setSelectedSID(SID)

    def registerNewSession(self, SID):
        self._project.getSession(SID).stateDictChanged.connect(self.checkSessionState)

    def disconnectSession(self, SID):
        try:
            self._project.getSession(SID).stateDictChanged.disconnect()
        except TypeError:
            # will be raised if disconnect failed
            # TODO: Not sure if this is the right way to do it. This happens if a non-active session is deleted.
            pass

    def changeSession(self, newSID, oldSID=None):
        """Changes the active session within one project.
        The current State of the netManager is saved to the old session. The state of the new session is loaded to the netManager."""
        self.storeSessionState(SID=oldSID, stateDict=None)
        self._project.setActiveSID(newSID)
        if self._project.getActiveSID() == newSID:
            self.loadSessionState(SID=newSID)
        else:
            Log.log("New Session " + str(newSID) + " could not be set. Valid SIDs are: " +
                    ", ".join([str(id) for id in self._project.getValidSIDs()]),
                    self._viewManager.sessionController.getCallerId())
        return

    def storeSessionState(self, SID=None, stateDict=None):
        """Stores the stateDict to a session.
        If no SID is provided, the currently active session is used.
        If no dictionary is provided, the current netManager state is used."""
        dict = stateDict
        if not dict:
            dict = self._netManager.getStateDictionary()
        _SID = SID
        if not _SID:
            _SID = self._project.getActiveSID()
        elif _SID not in self._project.getValidSIDs():
            Log.log("Could not store state to SID ", _SID, ". Valid SIDs are:" +
                    ", ".join([str(id) for id in self._project.getValidSIDs()]),
                    self._viewManager.sessionController.getCallerId())

        self._project.getSession(_SID).setStateDict(dict)

        return

    def loadSessionState(self, SID=None):
        """Loades the state from a session to the netManager.
        If no Session is provided, the currently active session is used."""
        _SID = SID
        if not _SID:
            _SID = self._project.getActiveSID()

        if _SID in self._project.getValidSIDs():
            if self._project.getSession(_SID).hasStateDict():
                dict = self._project.getSession(_SID).state_dictionary
                net = None
                pos = None
                sel = None
                if "network" in dict:
                    net = dict["network"]
                elif ("layerOrder" in dict) and ("layers" in dict):
                    net = dict

                if "position" in dict:
                    pos = dict["position"]

                if "selection" in dict:
                    sel = dict["selection"]

                if net:
                    self._netManager.setStateDictionary(dictionary=dict, clearHistory=True)
            else:
                Log.log("Could not load state from Session," + str(_SID) + " is this an old Project?",
                        self._viewManager.sessionController.getCallerId())

        else:
            # TODO: write proper Error to log
            print("Could not load state from session", _SID)
            Log.log("Could not load state from session " + str(_SID),
                    self._viewManager.sessionController.getCallerId())

        return

    def __propagateProjectToNetworkManager(self):
        """ Setup the current Project in NetworkManager """
        if self._project is None:
            return
        if self._netManager is None:
            return
        state = self._project.getActiveSession().state_dictionary
        inputdb = self._project.getInputManagerState()
        transform = self._project.getViewTransform()
        self._inputManager.importdb(inputdb)
        self._netManager.setStateDictionary(state, clearHistory=True)
        self._netManager.resetModifiedFlag()

        if transform is None:
            return

        self._netManager.nodeEditor.getView().setTransform(
            QTransform(transform[0], transform[1], transform[2], transform[3], transform[4], transform[5]))

    # method called when creating a new project, either from start window
    # or from project menu bar
    def newProjectDialog(self, dir="", parent=None):
        """ Open a new dialog for selecting a new project.
            Parent is the parent for the dialogs. If None the set parent in this instance is used.
            Returns true if successfully selecting a project dir, false otherwise.
        """
        try:
            if parent is None: parent = self._parent
            if not self.askUserAndSave(parent):
                return
            # directory alreay selected?
            if dir == "":
                dir = getNewProjectDir(self, parent)
            # directory valid? if not abort
            if len(dir) == 0:
                return

            if self.checkRunningSessions() is False:
                return False
            # Create project
            os.mkdir(dir)
            self.setProject(Project(dir))
            self.recentProjectsData.addRecently(dir, dir)
            self.saveProject()
            return True
        except:
            self.errorMsg("Error while trying to create a new project.", "create_project")
            return False

    def openProjectDialog(self, parent=None):
        """ Open a new dialog for selecting an existing project.
            Parent is the parent for the dialog. If None the set parent in this instance is used.
            Returns true if successfully selecting a project, false otherwise.
        """
        try:
            if parent is None: parent = self._parent
            if not self.askUserAndSave(parent):
                return False
            dir = getOpenProjectDir(self, parent)
            if len(dir) == 0:
                return False

            if self.checkRunningSessions() is False:
                return False
            self.recentProjectsData.addRecently(dir, dir)
            proj = Project(dir)
            proj_old = self._project
            self.setProject(proj)
            if(proj.getCaffeVersion() != proj_old.getCaffeVersion()):
                msgBox = QMessageBox(QMessageBox.Warning, "Warning", "Please restart Barista client for changes to apply, otherwise Barista may be unstable!")
                msgBox.addButton("Ok", QMessageBox.NoRole)
                msgBox.addButton("Restart now", QMessageBox.YesRole)
                if msgBox.exec_() == 1:
                    self.restart()
            return True
        except UnknownLayerTypeException as e:
            caffeVersionDialog = CaffeVersionDialog(e, dir, self)
            caffeVersionDialog.exec_()
            return False
        except:
            self.errorMsg("Error while trying to open an existing project.", "open_project")
            return False

    def restart(self, projDir=""):
        """Save the actual project and restart barista"""
        if not projDir:
            self.saveProject()
        """Determine arguments for the restart. 
        Catch the old -o/--open with regex1 and allow every other old arguments with regex2"""
        parameter = []
        regex1=re.compile("(-o)|(--open).*")
        regex2=re.compile("([-.]).*")
        for argument in sys.argv:
            if not regex1.match(argument) and regex2.match(argument):
                parameter.append(argument)
        if not projDir:
            parameter.append(str("-o"+self.getProjectPath()))
        else:
            parameter.append(str("-o"+projDir))

        os.execl(sys.executable, sys.executable, *parameter)

    def saveProject(self):
        """ Save the project in the directory it lives """
        try:
            if self._project is None or self._netManager is None:
                return False
            dict = self._netManager.getStateDictionary()
            inputs = self._inputManager.getDBDict()
            transform = self._netManager.nodeEditor.getView().transform()
            self._project.saveProject(dict, inputs, transform)
            self._netManager.resetModifiedFlag()
            return True
        except:
            self.errorMsg("Error while trying to save the project.", "save_project")
            return False

    def getProjectPath(self):
        """returns the project path for external classes"""
        if self._project:
            return self._project.projectRootDir
        return None

    # Network Manager

    def saveNetDialog(self, parent=None):
        """ Open a save dialog and saves the network.
            Parent is the parent for the dialog. If None the set parent in this instance is used.
            Returns True if successfully  selecting an place to save, False otherwise.
        """
        try:
            if parent is None: parent = self._parent
            if self._netManager is None:
                return False
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(parent, self.tr("Export Network"))
            if len(filename) == 0:
                return False
            self._netManager.saveNetworkToFile(filename)
            self.recentNetData.addRecently(filename, filename)
            return True
        except:
            self.errorMsg("Error while trying to export the network.", "network_export")
            return False

    def saveSolverDialog(self, parent=None):
        """ Open a save dialog and saves the solver.
            Parent is the parent for the dialog. If None the set parent in this instance is used.
            Returns True if successfully  selecting an place to save, False otherwise.
        """

        try:
            if parent is None:
                parent = self._parent

            if self._netManager is None:
                return False

            self._solverDialog = ExportSolverDialog(self._netManager.solver, self._netManager.network, parent, self)
            self._solverDialog.show()
            return True
        except:
            self.errorMsg("Error while trying to export the solver.", "solver_export")
            return False

    def openSolverDialog(self, parent=None):
        """ Open a open dialog and load the solver.
            Parent is the parent for the dialog. If None the set parent in this instance is used.
            Returns True if successfully  selecting a file to load, False otherwise.
        """
        if parent is None: parent = self._parent
        if self._netManager is None:
            return False
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(parent, self.tr("Import Solver File"), "",
                                                            "Prototxt (*.prototxt) ;; All Files (*)")
        if len(filename) == 0:
            return False
        try:
            self.openSolver(filename)
            return True
        except loader.ParseException as ex:
            QtWidgets.QMessageBox.critical(parent, self.tr("Error parsing prototxt"), str(ex))
            return False

    def openSolver(self, filename):
        if not os.path.exists(filename):
            QtWidgets.QMessageBox.critical(None, self.tr("File does not exists"),
                                           self.tr("Cannot load {}. File does not exists.").format(filename))
            return
            # open solver
        self._netManager.openSolverFromFile(filename)
        self.recentSolverData.addRecently(filename, filename)

        # check whether the loaded solver does contain a network specification, too
        # (we need to load the solver once again, as the redundant network specification has been removed automatically)
        with open(filename, 'r') as file:
            solverOriginalString = file.read()
        solverOriginalDictionary = loader.loadSolver(solverOriginalString)
        solverRefersToNetFile = "net" in solverOriginalDictionary
        solverIncludesNet = "net_param" in solverOriginalDictionary

        # Theoretically, the solver definition might contain both: a file reference and an inline definition
        # We do support this case, but as it will be very seldom, we do not create a new main_window handling both options.
        # Instead we just show two separate windows after each other
        if solverRefersToNetFile:

            netPath = solverOriginalDictionary["net"]
            # if the given path is not an absolute one..
            if not os.path.isabs(netPath):
                # it's either relative to the caffe root directory
                netPathAlternative1 = os.path.join(caffeVersions.getVersionByName(self._project.getCaffeVersion()).getRootpath(), netPath)
                # or relative to the solver file (e.g. for Barista sessions)
                netPathAlternative2 = os.path.join(os.path.dirname(filename), netPath)

                if netPathAlternative1 and os.path.isfile(netPathAlternative1):
                    netPath = netPathAlternative1
                else:
                    netPath = netPathAlternative2

            self._promptForAutoNetImport(netPath)

        if solverIncludesNet:
            # get the network definition as a string
            netString = loader.extractNetFromSolver(solverOriginalString)

            # save inline definition to temporary file, so we can use the same algorithm as above
            tempFilePath = tempfile.NamedTemporaryFile(delete=False)
            tempFilePath.write(netString)
            tempFilePath.close()
            self._promptForAutoNetImport(tempFilePath.name)
            os.remove(tempFilePath.name)

    def _promptForAutoNetImport(self, netPath):
        """Open a message box and ask the user if he/she wants to import the net definition given in netPath.

        netPath contains a net definition that has been extracted from a loaded solver definition.
        """

        # check whether the specified file does exist
        if os.path.isfile(netPath):

            # get the file content
            with open(netPath, 'r') as file:
                netPrototxt = file.read()

            msgBox = QMessageBox()
            msgBox.setWindowTitle("Barista")
            msgBox.setText(self.tr("Solver definition contains a network reference."))
            msgBox.setInformativeText(self.tr("Do you want to import the network, too?"))
            msgBox.setDetailedText("File:\n{}\n\nNet definition:\n{}".format(netPath, netPrototxt))
            msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msgBox.setDefaultButton(QMessageBox.Yes)
            ret = msgBox.exec_()
            if ret == QMessageBox.Yes:
                self.openNet(netPath)
        else:
            callerId = Log.getCallerId('file_loader')
            Log.log("Found network reference in loaded solver definition, but the file {} does not exist.".format(
                netPath
            ), callerId)

    def openNet(self, filename):
        if not os.path.exists(filename):
            QtWidgets.QMessageBox.critical(None, self.tr("File does not exists"),
                                           self.tr("Cannot load {}. File does not exists.").format(filename))
            return
        self._netManager.openNetworkFromFile(filename)
        self.recentNetData.addRecently(filename, filename)

    def openNetDialog(self, parent=None):
        """ Open a open dialog and load the network.
            Parent is the parent for the dialog. If None the set parent in this instance is used.
            Returns True if successfully selecting a file to load, False otherwise.
        """
        if parent is None: parent = self._parent
        if self._netManager is None:
            return False
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(parent, self.tr("Import Network File"), "",
                                                            "Prototxt (*.prototxt) ;; All Files (*)")
        if len(filename) == 0:
            return False
        try:
            self.openNet(filename)
            return True
        except loader.ParseException as ex:
            QtWidgets.QMessageBox.critical(parent, self.tr("Error parsing prototxt"), str(ex))
            return False

    def setNetworkManager(self, networkManager):
        """ Set the Networkmanager the actions should work with"""
        if networkManager == self._netManager: return
        if self._netManager:
            self._netManager.stateChanged.disconnect(self.updateActionState)
        self._netManager = networkManager
        if self._netManager:
            self._netManager.stateChanged.connect(self.updateActionState)
        self.updateActionState()
        self.netManagerChanged.emit(networkManager)

    # View Manager
    def setViewManager(self, viewManager):
        """Set the ViewManager the actions should work with"""
        if viewManager == self._viewManager: return
        self._viewManager = viewManager
        self.updateActionState()
        self.viewManagerChanged.emit(viewManager)

    def _loadDefaultView(self):
        if self._viewManager is None:
            return
        self._viewManager.loadDefaultView()

    def _sortScene(self):
        self._netManager.nodeEditor.rearrangeNodes()

    def _sortSceneVertical(self):
        self._netManager.nodeEditor.rearrangeNodesVertical()

    # SCENE
    def setScene(self, scene):
        self._scene = scene
        self.updateActionState()

    # EDITOR

    def openNetEditor(self):
        """ Open a Editor for editing the prototxt of the network """
        if self._editor is None:
            return False
        self._editMode = "Network"
        self._editor.setText(saver.saveNet(self._netManager.network))
        self._editor.show()
        return True

    def openSolverEditor(self):
        """ Open a Editor for editing the prototxt of the solver """
        if self._editor is None:
            return False
        self._editMode = "Solver"
        self._editor.setText(saver.saveSolver(self._netManager.solver))
        self._editor.show()
        return True

    def openInputManager(self):
        if self._inputManager is None:
            return False
        self._inputManager.updateListWidget()
        self._inputManager.show()
        return True

    def openHostManager(self):
        if self._hostManager is None:
            return False
        self._hostManager.show()
        return True

    def _editorChangedText(self, netproto):
        try:
            netproto = netproto.encode("utf-8")
            if self._netManager:
                if self._editMode == "Network":
                    self._netManager.openNetworkFromString(netproto, False)
                    self._netManager.checkForDuplicateNames()
                if self._editMode == "Solver":
                    self._netManager.openSolverFromString(netproto)
                    self._project.getActiveSession().setMaxIteration(int(loader.loadSolver(netproto).get("max_iter", 1)))
        except loader.ParseException as ex:
            QtWidgets.QMessageBox.critical(self._parent, "Error parsing prototxt", str(ex))

    def setEditor(self, editor):
        """Set the Editor the actions should work with"""
        if self._editor:
            self._editor.sgSave.disconnect(self._editorChangedText)
        self._editor = editor
        if self._editor:
            self._editor.sgSave.connect(self._editorChangedText)
        self.updateActionState()

    def setInputManager(self, manager):
        """sets the input Manager"""
        self._inputManager = manager
        self.updateActionState()

    def setHostManager(self, manager):
        """sets the host Manager"""
        self._hostManager = manager
        self.updateActionState()

    def changeCaffeVersion(self):
        if self._versionManager is None:
            return False
        self._versionManager.show()

    def openDeploymentDialog(self):
        """Show a file selection main_window and export a deployment network to the selected location."""

        self._deploymentDialog = DeploymentDialog(self._project.getSessions(), self._parent)
        self._deploymentDialog.show()

        return True

    def setVersionManager(self, manager):
        self._versionManager = manager
        self.updateActionState()

    def askUserAndSave(self, parent=None):
        """ Ask the user for saving if something changes since last save.
            If the user want to save, the project get saved.
            If the user want to abort, return False else return True
        """
        if parent is None:
            parent = self._parent
        if not self._netManager or not self._netManager.isModified():
            return True

        QM = QtWidgets.QMessageBox
        answer = QM.question(parent, self.tr("Are you sure?"), self.tr("Do you want to save the changes you made?"),
                             QM.Yes | QM.No | QM.Abort, QM.Abort)
        if answer == QM.Abort:
            return False
        if answer == QM.Yes:
            self.saveProject()
        return True

    def askRecreateProject(self, parent=None):
        """ Ask the user if he wants to create a new project in the directory.
        """
        QM = QtWidgets.QMessageBox
        answer = QM.question(parent, self.tr("Are you sure?"), self.tr(
            "The directory does not exists. Do you want to create a new project in this directory?"), QM.Yes | QM.Abort,
                             QM.Abort)
        if answer == QM.Yes:
            self.saveProject()
            return True
        if answer == QM.Abort:
            return False
        return False

    def errorMsg(self, errorMsg, loggerIdString=None, addStacktrace=True):
        """Show an error message in the Logger as well as in an additional GUI popup."""
        # use the logger
        if loggerIdString is not None:
            callerId = Log.getCallerId(loggerIdString)
        else:
            callerId = None
        Log.log(errorMsg, callerId)

        # show message in the GUI
        msgBox = QMessageBox()
        msgBox.setWindowTitle("Barista - Error")
        msgBox.setText(self.tr(errorMsg))
        if addStacktrace:
            stacktrace = traceback.format_exc()
            msgBox.setDetailedText(stacktrace)
        msgBox.setStandardButtons(QMessageBox.Ok)
        _ = msgBox.exec_()

    def disableEditing(self, disable):
        """ Disable actions for loading a new net or solver. """
        self.openNetAction.setDisabled(disable)
        self.openSolverAction.setDisabled(disable)
        if self.recentNetMenu:
            self.recentNetMenu.setDisabled(disable)
        if self.recentSolverMenu:
            self.recentSolverMenu.setDisabled(disable)
