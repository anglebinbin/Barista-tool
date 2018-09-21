from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import pyqtSignal

from gui.main_window.docks.properties.properties_data_model import PropertiesDataModel
from gui.main_window.docks.properties.properties_widget import PropertiesWidget
from gui.main_window.docks.dock import DockElement

class SolverProperties(DockElement):
    # This signal will be emitted when any of the properties of the solver change.
    solverChanged = pyqtSignal(list, object)

    def __init__(self, mainWindow, title):
        DockElement.__init__(self, mainWindow, "Solver Properties")
        self._data = None
        self.setToolTip('This shows the Properties the loaded Solver.')
        self.setupUi()
        self._mainWindow = mainWindow
        self.disableEditing(mainWindow.getDisabled())

    def setupUi(self):
        self.tree = PropertiesWidget(self)
        self.setWidget(self.tree)

    def setSolver(self, reactiveSolver):
        """ Set the solver whose properties should be shown.
            reactiveSolver has to be an instance of PropertyData
        """
        if self._data:
            self._data.someChildPropertyChanged.disconnect(self.solverChanged)
        self._data = reactiveSolver
        self.tree.setModel(PropertiesDataModel(self._data, self.tree))
        self._data.someChildPropertyChanged.connect(self.solverChanged)

        self.disableEditing(self._mainWindow.getDisabled())

    def data(self):
        return self._data

    def disableEditing(self, disable):
        """ Disable Editing of this dock """
        self.tree.disableEditing(disable)
