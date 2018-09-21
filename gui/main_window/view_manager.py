from PyQt5.QtCore import Qt

from backend.barista.session.session_utils import State
from gui.main_window.docks import (
    dock_available_layers,
    dock_active_layers
)
from gui.main_window.docks.session import dock_session_list

from backend.barista.utils.settings import applicationQSetting
from gui.main_window.docks.dock_console import DockElementConsole
from gui.main_window.docks.plotter.qt5_plotter_gui import DockElementPlotter
from gui.main_window.docks.properties import dock_layer_properties, dock_solver_properties
from gui.main_window.docks.session.session_controller import SessionController
from gui.main_window.docks.weight_visualization.dock_weight_visualization import DockElementWeightPlotter


class ViewManager():

    """Management of the current view state of the main main_window"""
    def __init__(self, mainWindow, actions):
        # Store the variables for the class
        self.mainWindow = mainWindow
        self.actions = actions
        self._defaultState = None
        self._isDefaultStateSaved = False
        self.dicDockWidgets = {}
        self.dicDockActions = {}
        self.sessionController = SessionController()

    def _addDock(self, element, title):
        """Creates the Dock-Element element with title and mainwindow and add it to Menu"""
        dock = element(self.mainWindow, title)
        self.dicDockWidgets[title] = dock
        self.dicDockActions[title] = self.actions.addDockMenuEntry(dock, title)
        return dock

    def createView(self):
        """Creates the docks of the application and loads the view settings"""

        # Create the dock widgets and add the menu bar actions
        self._addDock(dock_available_layers.DockElementLayers, 'Available Layers')
        self._addDock(dock_active_layers.DockElementActivLayers, "Network Layers")
        self._addDock(dock_session_list.DockElementSessions, "Sessions")
        self._addDock(dock_layer_properties.LayerProperties, "Layer Properties")
        self._addDock(dock_solver_properties.SolverProperties, "Solver Properties")
        bottomDock=self._addDock(DockElementConsole, "Console")
        bottomDock.setMinimumHeight(100)
        plotterDock=self._addDock(DockElementPlotter, "Plotter")
        plotterDock.setMinimumHeight(100)

        weightPlotterDock=self._addDock(DockElementWeightPlotter, "Weight Visualization")
        weightPlotterDock.setMinimumHeight(100)
        self.sessionController.setWeightPlotter(weightPlotterDock)

        self.sessionController.setPlotterGui(self.dicDockWidgets['Plotter'])
        self.dicDockWidgets['Sessions'].setController(self.sessionController)

        self.loadDefaultView()

        # Try to load the view if the user has saved one
        self.loadView()

    def getLayersDock(self):
        return self.dicDockWidgets['Available Layers']

    def getActiveLayersDock(self):
        return self.dicDockWidgets['Network Layers']

    def getLayerPropertyDock(self):
        return self.dicDockWidgets['Layer Properties']

    def getSolverPropertyDock(self):
        return self.dicDockWidgets['Solver Properties']

    def getSessionsDock(self):
        return self.dicDockWidgets['Sessions']

    def dockAction(self, title):
        'Shows or hides a dock based on input from menu bar action'

        if self.dicDockWidgets[title].isHidden():
            self.dicDockWidgets[title].show()
        else:
            self.dicDockWidgets[title].hide()

        #reload the hooks in the view menu for the docks
        self.onVisibilityChange()

    def onVisibilityChange(self):
        'Shows or hides a hook for the docks in the view menu'
        # widget is only the title as string
        for widget in self.dicDockWidgets:
            if self.dicDockWidgets[widget].isVisible():
                self.dicDockActions[widget].setChecked(True)
            else:
                self.dicDockActions[widget].setChecked(False)

    def loadDefaultView(self):
        'Loads the standard view settings'

        if self._isDefaultStateSaved == False:
            # Add layers dock
            self.mainWindow.addDockWidget(Qt.LeftDockWidgetArea, self.dicDockWidgets['Available Layers'])
            self.dicDockWidgets['Available Layers'].setFloating(False)
            self.dicDockWidgets['Available Layers'].show()

            # Add network layers dock
            # self.mainWindow.addDockWidget(Qt.LeftDockWidgetArea, self.dicDockWidgets['Network Layers'])
            self.mainWindow.tabifyDockWidget(self.dicDockWidgets['Available Layers'], self.dicDockWidgets['Network Layers'])
            self.dicDockWidgets['Network Layers'].setFloating(False)
            self.dicDockWidgets['Network Layers'].show()
            self.dicDockActions['Network Layers'].setChecked(True)
            self.dicDockWidgets['Available Layers'].raise_()

            # Add running tasks dock
            self.mainWindow.addDockWidget(Qt.RightDockWidgetArea, self.dicDockWidgets['Sessions'])
            self.dicDockWidgets['Sessions'].setFloating(False)
            self.dicDockWidgets['Sessions'].show()
            self.dicDockActions['Sessions'].setChecked(True)

            # Add solver properties dock
            # self.mainWindow.addDockWidget(Qt.RightDockWidgetArea, self.dicDockWidgets['Solver Properties'])
            self.mainWindow.tabifyDockWidget(self.dicDockWidgets['Sessions'], self.dicDockWidgets['Solver Properties'])
            self.dicDockWidgets['Solver Properties'].setFloating(False)
            self.dicDockWidgets['Solver Properties'].show()
            self.dicDockActions['Solver Properties'].setChecked(True)

            # Add layer properties dock
            # self.mainWindow.addDockWidget(Qt.RightDockWidgetArea, self.dicDockWidgets['Layer Properties'])
            self.mainWindow.tabifyDockWidget(self.dicDockWidgets['Solver Properties'], self.dicDockWidgets['Layer Properties'])
            self.dicDockWidgets['Layer Properties'].setFloating(False)
            self.dicDockWidgets['Layer Properties'].show()
            self.dicDockActions['Layer Properties'].setChecked(True)
            self.dicDockWidgets['Sessions'].raise_()

            # Add Console dock
            self.mainWindow.addDockWidget(Qt.BottomDockWidgetArea, self.dicDockWidgets['Console'])
            self.dicDockWidgets['Console'].setFloating(False)
            self.dicDockWidgets['Console'].show()
            self.dicDockActions['Console'].setChecked(True)

            # Add plotter dock
            self.mainWindow.addDockWidget(Qt.BottomDockWidgetArea, self.dicDockWidgets['Plotter'])
            self.dicDockWidgets['Plotter'].setFloating(False)
            self.dicDockWidgets['Plotter'].show()
            self.dicDockActions['Plotter'].setChecked(True)

            # Add weight dock
            # self.mainWindow.addDockWidget(Qt.BottomDockWidgetArea, self.dicDockWidgets['Weight Visualization'])
            self.mainWindow.tabifyDockWidget(self.dicDockWidgets['Plotter'], self.dicDockWidgets['Weight Visualization'])
            self.dicDockWidgets['Weight Visualization'].setFloating(False)
            self.dicDockWidgets['Weight Visualization'].show()
            self.dicDockActions['Weight Visualization'].setChecked(True)
            self.dicDockWidgets['Plotter'].raise_()

            # Save this state as default so that multiple clicks on the restore default view action do not cause changes
            self._isDefaultStateSaved = True
            self._defaultState = self.mainWindow.saveState()
        else:
            self.mainWindow.restoreState(self._defaultState)

        self.onVisibilityChange()

    def loadView(self):
        'Loads the user-defined view settings from view_settings'
        settings = applicationQSetting()
        settings.beginGroup("ViewManager")
        state = settings.value("guistate", None)
        settings.endGroup()
        if state:
            self.mainWindow.restoreState(state)

        self.onVisibilityChange()

    def saveView(self):
        'Saves the current view settings to view_settings file'
        settings = applicationQSetting()
        settings.beginGroup("ViewManager")
        settings.setValue("guistate", self.mainWindow.saveState())
        settings.endGroup()

    def setProject(self, project):
        """ Set the current project of the appliction.
        """
        self.project = project
        self.sessionController.setProject(project)
        self.dicDockWidgets['Plotter'].setProject(project)

    def getProject(self):
        """ Return the current project.
        """
        return self.project

    def disableEditing(self, disable):
        """ Disable editing on all docks.
        """
        self.dicDockWidgets['Solver Properties'].disableEditing(disable)
        self.dicDockWidgets['Layer Properties'].disableEditing(disable)
        self.dicDockWidgets['Available Layers'].disableEditing(disable)
        self.dicDockWidgets['Network Layers'].disableEditing(disable)

    def getPlotter(self):
        """ Return the plotter.
        """
        return self.dicDockWidgets['Plotter']
