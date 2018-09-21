from PyQt5 import QtWidgets

from gui.main_window.docks.dock import DockElement
from gui.network_manager.network_manager import NetworkManager

from gui.main_window.docks.properties.properties_data_model import PropertiesDataModel
from gui.main_window.docks.properties.properties_widget import PropertiesWidget

class LayerProperties(DockElement):

    def __init__(self, mainWindow, title):
        DockElement.__init__(self, mainWindow, "Layer Properties")
        self.tab = QtWidgets.QTabWidget()
        self.tab.setDocumentMode(True)
        self.setWidget(self.tab)
        self.ids = []
        self.datadict = {}
        self._mainWindow = mainWindow
        self.disableEditing(mainWindow.getDisabled())

    def setTab(self, id):
        """ Set the layer whose properties should be shown by its id """
        self.tab.clear()
        self.addTab(id)

    def addTab(self, id):
        """ Add a new property editor for the layer with the given id """
        network = self._networkmanager.network
        falloutlen = len(network.uri())
        layer = network["layers"][id]
        data = layer["parameters"]
        widget = PropertiesWidget(self)
        widget.setModel(PropertiesDataModel(data))
        self.tab.addTab(widget, data["name"])
        self.ids.append(id)
        self.datadict[id] = data
        self.disableEditing(self._mainWindow.getDisabled())

    def setNetworkManager(self, networkManager):
        self._networkmanager = networkManager # type: NetworkManager

    def setTabs(self, ids):
        """ Set the layers whose properties should be shown by its id.
            ids is a list of string.
        """
        self.clearProperties()
        for id in ids:
            self.addTab(id)

    def clearProperties(self):
        """ Let the dock show no properties for any layer """
        self.ids = []
        self.datadict = {}
        self.tab.clear()

    def updateDock(self):
        """ Rebuild all property editors in this dock """
        ids = self.ids
        self.clearProperties()
        self.setTabs(ids)

    def removeTab(self, id):
        """ Remove the property editor for the layer with the given id """
        idx = self.ids.index(id)
        self.tab.removeTab(idx)
        self.ids.remove(id)
        del self.datadict[id]

    def disableEditing(self, disable):
        """ Disable Editing of each widget in this dock """
        for i in range(0, self.tab.count()):
            tab = self.tab.widget(i)
            tab.disableEditing(disable)
