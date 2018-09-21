import copy
import re
import sys
import uuid

from PyQt5.QtCore import QObject, pyqtSignal, Qt
from PyQt5.QtWidgets import QMessageBox
from gui.main_window.docks.properties.property_widgets.network_dict_info import NetworkDictInfoBuilder
from gui.main_window.docks.properties.property_widgets.program_state_info import ProgramStateInfoBuilder, defaultState
from gui.network_manager.history_manager import HistoryManager

import gui.main_window.docks.properties.property_widgets.data as PropData
from backend.barista.constraints.permanent.solver import ensureSolverConstraints
from backend.barista.utils.logger import Log
from backend.caffe import loader, saver, proto_info, dict_helper as helper
from gui.main_window.docks.properties.property_widgets.data import ReasonUpdated, ReasonKeyDeleted, ReasonKeyAdded, ReasonRemoved
from gui.network_manager.layer_helper import LayerHelper

def buildNetData(network):
    """ Build PropertyData for the network-dictionary network """
    netinfo = NetworkDictInfoBuilder(network)
    return PropData.PropertyData(network, netinfo.buildRootInfo().subparameter(), netinfo)

def buildStateData(stateDict):
    """ Build PropertyData for the state-dictionary stateDict """
    if stateDict == None:
        stateDict = defaultState()
    info = ProgramStateInfoBuilder(stateDict)
    return PropData.PropertyData(stateDict, info.buildRoot().subparameter(), info, signalcontroller=PropData.SignalController())

class HistoryWriting(object):
    """ Class which should give methods to avoid recursive history writings """

    def __init__(self, state, callback):
        """ Creates this object.
        state is the state-object which can be changed
              through the makeEntry-call
        callback is a function which will be called
                 if an entry in history should be make
        """
        self.__state = state
        self.__callback = callback
        self.__lock = False

    def valueOf(self,uri):
        return self.__state.valueOf(uri)

    def makeEntry(self, func):
        """ Make an entry in history.
        func is a function which will be called
             with the state object
             (e.g. historywriter.makeEntry(lambda state: state["name"] = 2)
        as long as func is called, no other function can make an entry in history,
        but they still can change the state through this function
        """
        prevLocked = self.__lock
        self.__lock = True
        res = None
        if func:
            res = func(self.__state)
        if not prevLocked:
            self.__lock = False
            self.__callback()
        return res


    def entryWithoutHistory(self,func):
        """ Change state without touching the history. See makeEntry for the argument """
        prevLocked = self.__lock
        self.__lock = True
        res = None
        if func:
            res = func(self.__state)
        if not prevLocked:
            self.__lock = False
        return res

class NetworkManager(QObject):
    """ stateChanged is triggered if the state of the network or solver has changed.
     modifiedChanged is used to indicate a change of the network to other components.
     The boolean value indicates whether the current state differs from the last saved one.
    """
    stateChanged = pyqtSignal()
    modifiedChanged = pyqtSignal(bool)
    newStateData = pyqtSignal(object)

    'The network manager stores the information for all layers currently in ui and handles all layer-related events'
    def __init__(self, dockElementActiveLayers,  dockLayerProperties, dockSolverProperties, nodeEditor):
        'Creates a new network manager'
        super(NetworkManager, self).__init__()
        self.callerId = Log.getCallerId('networkmanager')


        # Set the reference to the active layers dock, as well as reference to network manager in active layers dock
        self.dockElementActiveLayers = dockElementActiveLayers.getLayersListWidget()
        self.dockElementActiveLayers.setNetworkManager(self)

        # Set the reference to property dock, as well as reference to network manager in property dock
        self.dockLayerProperties = dockLayerProperties
        self.dockLayerProperties.setNetworkManager(self)

        # Set the reference to the solver property dock
        self.dockSolverProperties = dockSolverProperties
        #self.dockSolverProperties().solverChanged.connect(self.makeHistory)
        self.dockSolverProperties().solverChanged.connect(self.validateChangedSolver, Qt.QueuedConnection)

        # Set the reference to the node edtior scene, as well as reference to network manager in node prototxt_editor
        self.nodeEditor = nodeEditor
        self.nodeEditor.setNetworkManager(self)

        # Get the caffe metainformation
        self.caffeInfo = proto_info.CaffeMetaInformation()

        # Set up a counter for overall number of layers in the application, to use as id for each layer
        self.layerCount = 0

        # Create an empty network, to be filled by both opening a file and user actions
        self.stateData = None
        self.historyWriter = None  # type: HistoryWriting
        self.setState(None)

        # self.setNetwork(helper.bareNet("Unnamed"))
        # Set up a list that contains all currently selected layer ids

        # Setup historyManager
        self.__historyDepth = 0
        self._historymanager = HistoryManager()
        self.makeHistory()

        self.__lastModified = 0
        self.stateChanged.connect(lambda: self.modifiedChanged.emit(self.isModified()))

        self.networkHelper = None # type: helper.DictHelper


    def validateChangedSolver(self):
        """This method is triggered automatically whenever the solver has been changed (in the GUI)."""

        # prevent manipulation of solver constraints (changes self.solver)
        data = self.dockSolverProperties().data()
        if data is None:
            data = self.solver
        ensureSolverConstraints(data)
        # ensureSolverConstraints(self.solver)

        # backpropagate changed changes to the GUI by replacing the complete solver object
        # (it's already up to date inside of this class, but not in the GUI)
        # self.dockSolverProperties().setSolver(self.solver)

    @property
    def network(self):
        return self.stateData["network"]

    @property
    def solver(self):
        return self.stateData["solver"]

    """Method that adds a Layer in to the scene, called when drag and dropping a layer from
    layer selection"""
    def addLayer(self, type, scenePosX, scenePosY):
        # Check if a layer have been moved
        self.checkLayersForMovement(self.nodeEditor.getNodeIds())
        """ Add a layer from the type (a string) at the given position """
        def intern(stateData):
            # generate new Layer Name
            state = self.stateData.getBoringDict()
            boringNetwork = state["network"]
            nethelper = helper.DictHelper(boringNetwork)
            # get all present Layer Names in a list
            allLayerNames = nethelper.nameOfLayers()

            # set new Name as Typename and layercount = 0
            newName = type
            count = 0

            for name in allLayerNames:
                if newName == re.sub(' #[0-9]+$', '', name):
                    try:
                        number = int(re.sub(newName + ' #', '', name))
                        count = number if number > count else count
                    except ValueError:
                        count = 0
            # increment layertype count
            count += 1
            # append layertypecount to new Layername
            newName = newName + " #" + str(count)

            network = stateData["network"]
            networkHelper = helper.DictHelper(network)

            # Add a layer to the network
            #self.stateData.signalController().lock()
            newlayer, id = networkHelper.addLayer(self.caffeInfo.availableLayerTypes()[type], newName, 0)
            #self.stateData.signalController().unlock()

            # Add the node item to the graphics scene
            stateData["position"][id] = [scenePosX, scenePosY]
            #self.nodeEditor.addLayer(id, network['layers'][id], scenePosX, scenePosY)

            # Get the order and add the layer to the dock of active layers
            order = network["layerOrder"].index(id)
            #self.dockElementActiveLayers.addItem(id, name, order, type)
            self.updateOrder()

            # Set the selection to the new element
            self.setSelection(id)

            # Set the new overall layer count
            self.layerCount += 1

        self.historyWriter.makeEntry(intern)

    def focusLayer(self, id):
        self.checkLayersForMovement(id)
        self.nodeEditor.focusLayer(id)

    def deleteLayer(self, id):
        # Check if a layer have been moved
        self.checkLayersForMovement(self.nodeEditor.getNodeIds())
        """ Removes the layer with the given id """
        def intern(stateDict):
            self.setSelection(id)
            self.deleteSelectedLayers()
        self.historyWriter.makeEntry(intern)

    def deleteSelectedLayers(self):
        # Check if a layer have been moved
        self.checkLayersForMovement(self.nodeEditor.getNodeIds())
        'Deletes all Layers currently selected'
        def intern(stateData):
            stateData.signalController().lock()
            self.nodeEditor.disconnectConnectionsOfSelection()

            network = stateData["network"]
            networkHelper = helper.DictHelper(network)

            selected = list(stateData["selection"])
            stateData["selection"].setValue([])

            for id in selected:
                self.__checkLayerForMovement(id)
                if networkHelper.hasLayerWithId(id):
                    networkHelper.removeLayer(id)
                del stateData["position"][id]

            stateData.signalController().unlock()


            self.updateOrder()


        self.historyWriter.makeEntry(intern)

    def onStateUpdate(self, uri, reason):
        """ Get called if something is changed in stateData """
        def intern(stateData):
            # # Debugging output:
            # stateData.signalController().enableLoging()
            # print("Updating {} because {}".format(uri, reason))

            # If something in selection changed
            if uri[0] == "selection":
                # If we have an complete new list of selected docks
                if isinstance(reason, ReasonUpdated):
                    ids = reason.oldValue
                    # Trigger if layers moved
                    self.__checkLayerForMovement(ids)
                # If a node get deselected
                if isinstance(reason, ReasonRemoved):
                    ids = [id for id in stateData["selection"]]
                    ids.append(reason.value)
                    # Trigger if layers moved
                    self.__checkLayerForMovement(ids)
                # Set the selection in prototxt_editor and the propertywdg
                ids = [id for id in stateData["selection"]]
                self.nodeEditor.setSelectedLayers(ids)
                self.dockLayerProperties.setTabs(ids)
            # The whole network changed
            elif uri == ["network"]:
                # Refresh node-items and connections
                self.refreshItems()
                self.refreshConnections()
            elif uri == ["hidden_connections"]:
                self.updateHiddenConnectionsInNodeEditor()

            # Some layer information changed
            elif uri[:2] == ["network","layers"] and len(uri) > 2:
                id = uri[2]
                # Some parameter changed
                if len(uri) > 4 and uri[3] == "parameters":
                    self.updateToolTip(id)
                    reluri = uri[4:]
                    # The top blobs changed -> tell the node prototxt_editor
                    if reluri == ["top"]:
                        # Some blob added
                        if isinstance(reason, PropData.ReasonAdded):
                            idx = reason.idx
                            content = self.historyWriter.valueOf(uri+[idx])
                            self.nodeEditor.addTopBlob(id, content)
                        # Some blob removed
                        elif isinstance(reason, PropData.ReasonRemoved):
                            idx = reason.idx
                            self.nodeEditor.disconnectTopBlob(id, idx)
                            self.nodeEditor.removeTopBlob(id, idx)
                            self.updateOrder()
                    # The bottom blobs changed -> tell the node prototxt_editor
                    elif reluri == ["bottom"]:
                        # Some blob added
                        if isinstance(reason, PropData.ReasonAdded):
                            idx = reason.idx
                            content = self.historyWriter.valueOf(uri+[idx])
                            self.nodeEditor.addBottomBlob(id, idx)
                        # Some blob removed
                        elif isinstance(reason, PropData.ReasonRemoved):
                            idx = reason.idx
                            self.nodeEditor.disconnectBottomBlob(id, idx)
                            self.nodeEditor.removeBottomBlob(id, idx)
                            self.updateOrder()
                    # One top blobs changed -> tell the node prototxt_editor
                    elif reluri[0] == "top" and isinstance(reason, PropData.ReasonUpdated):
                        newVal = reason.newValue
                        self.nodeEditor.renameTopBlob(id, reluri[1], newVal)
                    # One bottom blobs changed -> tell the node prototxt_editor
                    elif reluri[0] == "bottom" and isinstance(reason, PropData.ReasonUpdated):
                        newVal = reason.newValue
                        self.nodeEditor.renameBottomBlob(id, reluri[1], newVal)
                    elif reluri[0] == "name" and isinstance(reason, PropData.ReasonUpdated):
                        if reason.oldValue != reason.newValue:
                            self.nodeEditor.updateLayerData(id)
                            layerNames = [self.nodeEditor.getNodes()[currentId].getName() for currentId in self.nodeEditor.getNodes().keys()]
                            layerNames.remove(reason.newValue)
                            if reason.newValue in layerNames:
                                buttonReply = QMessageBox.question(None, "Warning!",
                                                                   "A layer with that name already exists. "
                                                                   "During training, caffe will assume shared weights among equally named layers. "
                                                                   "Training will fail if dimensions don't match.\n\n"
                                                                   "Do you still want to change the name?",
                                                                   QMessageBox.Yes | QMessageBox.No)
                                if buttonReply == QMessageBox.No:
                                    self.undo()
                                else:
                                    pass
                    # The include phase changed -> tell the node prototxt_editor
                    else:
                        self.nodeEditor.updateLayerData(id)
            # Layers are changed
            elif uri == ["network", "layers"]:
                # If a layer is removed -> tell the node prototxt_editor
                if isinstance(reason, ReasonKeyDeleted):
                    # Check if some node has moved
                    id = reason.key
                    layerstocheck = list(stateData["selection"])
                    if id in layerstocheck:
                        layerstocheck.remove(id)
                    self.__checkLayerForMovement(layerstocheck)
                    self.nodeEditor.deleteItemsByID([id])
                    self.updateOrder()
                # If a layer is added -> tell the node prototxt_editor
                if isinstance(reason,ReasonKeyAdded):
                    # Check if some node has moved
                    self.__checkLayerForMovement(list(stateData["selection"]))
                    id = reason.key
                    self.nodeEditor.addLayer(id, stateData["network"]["layers"][id], 0.0,0.0)

            # Positions get updated -> tell the node prototxt_editor
            elif uri[0] == "position" and (isinstance(reason, ReasonUpdated) or isinstance(reason,ReasonKeyAdded)):

                self.nodeEditor.applyLayerPositionDict(stateData["position"])
            # We've got a new solver -> set solver to the propertywdg
            elif uri == ["solver"]:
                self.setSolver(stateData["solver"])

            #stateData.signalController().disableLoging()

        self.historyWriter.entryWithoutHistory(intern)
        self.newStateData.emit(self.getStateDictionary())


    def setSelection(self, id):
        """ Select the layer with the given id.
            Note: you can also manipulate stateData["selection"] instead.
        """
        self.setSelectionList([id])

    def setSelectionList(self, ids):
        """ Select all layers in ids
            Note: you can also manipulate stateData["selection"] instead.
        """
        def intern(stateData):
            stateData["selection"].setValue(ids)
        self.historyWriter.makeEntry(intern)

    def addLayerToSelection(self, id):
        """ Add the layer with the given id to the selection.
            Note: you can also manipulate stateData["selection"] instead.
        """
        self.historyWriter.makeEntry(lambda stateData: stateData["selection"].pushBack(id))

        # Notify all elements
        #self.dockElementActiveLayers.addItemToSelection(id)
        #self.nodeEditor.addLayerToSelection(id)
        #self.dockLayerProperties.addTab(id)

        # Save the history to include this step in undo and redo
        #self.__historyDepth -= 1
        #self.makeHistory()

    def __checkLayerForMovement(self,ids):
        """ Checks if the layer with ids (a list of string or a string)
            has a different position in prototxt_editor than in stateData.
            If so the stateData will be updated.
        """
        if type(ids) != list:
            ids = [ids]
        def intern(stateData):
            # mayUpdate contains ids which are valid
            #           because some if ids could already be deleted
            mayUpdate = set(ids).intersection(stateData["position"].keys())
            oldValues = dict([(id, stateData["position"][id]) for id in mayUpdate])
            newValue = dict([(id,self.nodeEditor.getPositionOfLayer(id)) for id in mayUpdate])
            for id in mayUpdate:
                oldx, oldy = oldValues[id]
                newx, newy = newValue[id]
                if oldx != newx or oldy != newy:
                    stateData["position"][id].setValue([newx,newy])
        self.historyWriter.makeEntry(intern)

    def checkLayersForMovement(self,ids):
        self.__checkLayerForMovement(ids)

    def removeLayerFromSelection(self, id):
        """ Deselect the layer with the given id.
            Note: you can also manipulate stateData["selection"] instead.
        """
        def intern(stateData):
            stateData["selection"].remove(id)
        self.historyWriter.makeEntry(intern)


    def clearSelection(self):
        """ Deselect all layers.
            Note: you can also manipulate stateData["selection"] instead.
        """
        if len(self.stateData["selection"]) == 0: return
        def intern(stateData):
                stateData["selection"].setValue([])
        self.historyWriter.makeEntry(intern)


    def clearSelectionWithoutSavingHistory(self):
        """ Deselect all layers without an entry in history.
            Note: you can also manipulate stateData["selection"]
                  through historyWriter.entryWithoutHistory instead.
        """
        self.historyWriter.entryWithoutHistory(lambda state: self.clearSelection())

    def updateNet(self):
        """ Force an entry in history """
        self._historymanager.insertFunc(None)
        # todo: this should really do something


    def updateName(self, id, name):
        """ Sets the name of the layer with the given id
            to the given name.
            Note: you can also manipulate
                  stateData["network"]["layers"][id]["parameters"]["name"]
                  instead
        """
        def intern(stateDict):
            network = stateDict["network"]
            networkHelper = helper.DictHelper(network)
            networkHelper.layerParams(id)["name"] = name
            print("updateName: ", id, name)

        self.historyWriter.makeEntry(intern)


    def updateLayerInNodeEditor(self, layerID):
        """ Tell nodeEditor to update the layerdata of the given layer """
        self.nodeEditor.updateLayerData(layerID)

    def updateOrder(self):
        """ Recalculate the order of the layer """
        if set(self.nodeEditor.getNodeIds()) == set(self.network["layers"].keys()):
            self.network["layerOrder"].setValue(self.nodeEditor.calculateLayerOrder())

    def refreshConnections(self):
        """ Refresh the connections of all layers """
        # Connect layers
        connections = LayerHelper.buildConnectionList(self.network.getBoringDict())
        #connections = LayerHelper.buildConnectionList(self.network)
        for connection in connections:
            self.nodeEditor.createConnection(connection[0], connection[1], connection[2], connection[3])

    def updateHiddenConnectionsInNodeEditor(self):
        """ Update the NodeEditor to hide connections which
            should be hidden in the current state
        """
        # There are no hidden_connections
        if not "hidden_connections" in self.stateData:
            self.nodeEditor.setHiddenConnectionsFromList([])
            return
        connectionList = []
        for el in self.stateData["hidden_connections"]:
            topId = el["topLayerId"]
            topIdx = el["topBlobIdx"]
            bottomId = el["bottomLayerId"]
            bottomIdx = el["bottomBlobIdx"]
            connectionList.append(( topId, topIdx, bottomId, bottomIdx ))
        self.nodeEditor.setHiddenConnectionsFromList(connectionList)

    def connectionsHiddenStateChanged(self, listOfConnections):
        """ Gets called when a connection gets hidden/shown. listOfConnections is a list of tupels (topLayerID, topBlobIndex, bottomLayerID, bottomBlobIndex) """
        hidden_connections = []
        for (topid, topidx, bottomid, bottomidx) in listOfConnections:
            hidden_connections.append({
                "topLayerId": topid,
                "topBlobIdx": topidx,
                "bottomLayerId": bottomid,
                "bottomBlobIdx": bottomidx
            })
        self.historyWriter.makeEntry(lambda stateData: stateData.giveProperty("hidden_connections", hidden_connections))

    def refreshItems(self):
        # Clear everything, if a previous network has been opened
        self.nodeEditor.clearAll()

        self.dockLayerProperties.clearProperties()
        self.dockElementActiveLayers.clearTable()
        for id, layer in self.getLayerDict().iteritems():
            # todo: Set an ID for each layer in input dictionary
            # Create a new node item in the view and set focus to it
            self.nodeEditor.addLayer(id, layer)

            # Create a new entry in the active layers list
            self.dockElementActiveLayers.addItem(id,
                                                 layer["parameters"]["name"],
                                                 self.network["layerOrder"].index(id),
                                                 layer["parameters"]["type"])

            # Add one to the count of all layers in the application
            self.layerCount += 1

    def addBottomBlob(self, layerID, blobName=""):
        'Adds a bottom entry to the layer with the given id'
        def intern(stateDict):
            network = stateDict["network"]
            networkHelper = helper.DictHelper(network)
            layerParams = networkHelper.layerParams(layerID)
            if "bottom" not in layerParams:
                layerParams.giveProperty("bottom",[])
            layerParams["bottom"].pushBack(blobName)

            # TODO: Instead update in onStateUpdate
            #self.nodeEditor.addBottomBlob(layerID, "")

            # update property dock
            self.dockLayerProperties.updateDock()

        self.historyWriter.makeEntry(intern)




    def removeBottomBlob(self, layerID, blobIndex):
        def intern(stateDict):
            network = stateDict["network"]
            networkHelper = helper.DictHelper(network)

            self.nodeEditor.disconnectBottomBlob(layerID, blobIndex)
            del networkHelper.layerParameter(layerID, "bottom")[blobIndex]

            # TODO: Instead update in onStateUpdate
            # self.nodeEditor.removeBottomBlob(layerID, blobIndex)
            self.updateOrder()

            # update property dock
            self.dockLayerProperties.updateDock()

        self.historyWriter.makeEntry(intern)


    def addTopBlob(self, layerID, blobName):
        'Adds a top entry to the layer with the given id'
        def intern(stateDict):
            network = stateDict["network"]
            networkHelper = helper.DictHelper(network)
            layerParams = networkHelper.layerParams(layerID)
            if "top" not in layerParams:
                layerParams.giveProperty("top", [])
            layerParams["top"].pushBack(blobName)

            # TODO: Instead update in onStateUpdate
            #self.nodeEditor.addTopBlob(layerID, blobName)

            # update property dock
            self.dockLayerProperties.updateDock()

        self.historyWriter.makeEntry(intern)



    def renameTopBlob(self, layerID, blobIndex, newName):

        def intern(stateDict):
            network = stateDict["network"]
            networkHelper = helper.DictHelper(network)
            networkHelper.layerParams(layerID)["top"][blobIndex] = newName

            # TODO: Instead update in onStateUpdate

            #self.nodeEditor.renameTopBlob(layerID, blobIndex, newName)

            # update property dock
            self.dockLayerProperties.updateDock()

        self.historyWriter.makeEntry(intern)



    def renameBottomBlob(self, layerID, blobIndex, newName):
        def intern(stateDict):
            network = stateDict["network"]
            networkHelper = helper.DictHelper(network)
            networkHelper.layerParams(layerID)["bottom"][blobIndex] = newName

            # TODO: Instead update in onStateUpdate
            #self.nodeEditor.renameBottomBlob(layerID, blobIndex, newName)

            # update property dock
            self.dockLayerProperties.updateDock()

        self.historyWriter.makeEntry(intern)

    def removeTopBlob(self, layerID, blobIndex):
        def intern(stateDict):
            network = stateDict["network"]
            networkHelper = helper.DictHelper(network)
            self.nodeEditor.disconnectTopBlob(layerID, blobIndex)

            del networkHelper.layerParams(layerID)["top"][blobIndex]

            # TODO: Instead update in onStateUpdate
            #self.nodeEditor.removeTopBlob(layerID, blobIndex)

            self.updateOrder()

            # update property dock
            self.dockLayerProperties.updateDock()
        self.historyWriter.makeEntry(intern)


    def connectLayers(self, topLayerID, topBlobIndex, bottomLayerID, bottomBlobIndex):

        def intern(stateDict):
            network = stateDict["network"]
            networkHelper = helper.DictHelper(network)

            blobName = networkHelper.layerParams(topLayerID)["top"][topBlobIndex]

            networkHelper.layerParams(bottomLayerID)["bottom"][bottomBlobIndex] = blobName

            # TODO: Instead update in onStateUpdate
            self.nodeEditor.updateLayerData(bottomLayerID)
            self.nodeEditor.createConnection(topLayerID, topBlobIndex, bottomLayerID, bottomBlobIndex)
            # self.updateNet()
            self.updateOrder()

            # update property dock
            self.dockLayerProperties.updateDock()

        self.historyWriter.makeEntry(intern)

    def disconnectLayer(self, bottomLayerID, bottomBlobIndex):

        def intern(stateDict):
            network = stateDict["network"]
            networkHelper = helper.DictHelper(network)

            networkHelper.layerParams(bottomLayerID)["bottom"][bottomBlobIndex] = unicode("")
            # TODO: Instead update in onStateUpdate
            self.nodeEditor.updateLayerData(bottomLayerID)
            #self.updateNet()
            self.updateOrder()
            # update property dock
            self.dockLayerProperties.updateDock()

        self.historyWriter.makeEntry(intern)

    def isValidLayerType(self, type):
        if type in self.caffeInfo.availableLayerTypes():
            return True
        return False


    def __historyEntry(self, uri, reason):
        self.historyWriter.makeEntry(None)

    def setState(self, statedict):
        """ Sets a new stateData and refresh the gui.
            statedict has to be from type dict and
            will be wrapped with PropertyData through this function.
        """
        # Disconnect old signals
        if self.stateData:
            self.stateData.someChildPropertyChanged.disconnect(self.onStateUpdate)
            self.stateData.someChildPropertyChanged.disconnect(self.__historyEntry)

        # Build PropertyData
        self.stateData = buildStateData(statedict)
        # Refresh everynthing
        self.__connectReactiveThings()
        self.refreshItems()
        self.refreshConnections()
        self.nodeEditor.applyLayerPositionDict(self.stateData["position"])
        self.nodeEditor.setSelectedLayers(self.stateData["selection"])
        self.updateHiddenConnectionsInNodeEditor()

        if self.stateData:
            self.historyWriter = HistoryWriting(self.stateData, self.makeHistory)
            def intern(stateData):
                self.networkHelper = helper.DictHelper(stateData["network"])
                self.dockLayerProperties.setTabs(stateData["selection"])
                # Reconnect
                self.stateData.someChildPropertyChanged.connect(self.__historyEntry)
                self.stateData.someChildPropertyChanged.connect(self.onStateUpdate)
                if "solver" in self.stateData:
                    self.setSolver(stateData["solver"])
                else:
                    self.setSolver(None)
            self.historyWriter.entryWithoutHistory(intern)

    def makeHistory(self):
        """ Make an entry in history.
            Note: If possible use historyWriter.makeEntry instead
                  as it avoid making unnecessary entries.
        """
        #if self.__historyDepth > 0:
        #    return

        boring = self.stateData.getBoringDict()
        network = self.stateData["network"].getBoringDict()
        valid, msg = helper.isNetDictValid(network)
        if not valid:
           Log.error(
                 "WARNING!!!! Network-Dictionary is not valid:"
                +"            " + msg
                +"\nInfo: Current Dictionary looks like this:\n"
                + str(self.network.getBoringDict()),
                self.callerId
            )
        self._historymanager.insertFunc(lambda insert: insert(copy.deepcopy(self.stateData.getBoringDict())))

        netids = set(network["layerOrder"])
        posids = set(self.stateData["position"].getBoringDict())
        if netids != posids:
            Log.error("WARNING!!! NetworkManager has invalid History-State",self.callerId)
            for id in netids.difference(posids):
                Log.error("Id {} is in net, but has no position".format(id),self.callerId)
            for id in posids.difference(netids):
                Log.error("Id {} has position, but is not in net".format(id),self.callerId)
            Log.log("Info: Current State-Dictionary looks like this:",self.callerId)
            Log.log(str(self._historymanager.currentState()),self.callerId)
        self.stateChanged.emit()

    def _refreshStateFromHistory(self):
        """ Rebuild State of network, selection, position from latest point in history """
        state = copy.deepcopy(self._historymanager.currentState())
        def updateFun():
            self.setState(state)
            #self.setNetwork(state["network"])
            #self.refreshItems()
            #self.refreshConnections()
            #self.setSelectionList(state["selection"])
            #self.setLayerPositionDictionary(state["position"])
            #self.setSolver(state["solver"])
        #if not state is None:
        self._historymanager.lockHistory(updateFun)
        self.stateChanged.emit()

    def canUndo(self):
        return self._historymanager.canUndo()

    def undo(self):
        self._historymanager.undo()
        self._refreshStateFromHistory()

    def canRedo(self):
        return self._historymanager.canRedo()

    def redo(self):
        self._historymanager.redo()
        self._refreshStateFromHistory()

    def isModified(self):
        """ Return True iff anything changes since last reset of changes """
        return self.__lastModified != self._historymanager.position

    def resetModifiedFlag(self):
        """ Reset the change flag, so the program things nothing has changes
            since last save.
            Then there is no need to ask the user for example.
        """
        self.__lastModified = self._historymanager.position
        self.modifiedChanged.emit(self.isModified())

    def setModifiedFlag(self):
        """ Set the change flag, so the program things something has changes
            since last save.
            So there is need to ask the user for example.
        """
        self.__lastModified = -1
        self.modifiedChanged.emit(self.isModified())

    def openNetworkFromFile(self, filePath):
        with open(filePath, 'r') as file:
            inputString = file.read()

        self.openNetworkFromString(inputString)

    def saveNetworkToFile(self, filePath):
        with open(filePath, 'w') as file:
            file.write(saver.saveNet(self.network))

    def openNetworkFromString(self, inputString, clearHistory = True):
        if clearHistory:
            self._historymanager.clear()

        def intern(stateData):
            self.setNetwork(loader.loadNet(inputString))
            #self.refreshItems()
            #self.refreshConnections()

            # Rearrange the layers
            self.nodeEditor.rearrangeNodes()
            self.updateOrder()

        self.historyWriter.makeEntry(intern)

    def checkForDuplicateNames(self):
        """
        Check for duplicate layer names and send a warning but not if they have different phases.
        """
        state = self.stateData.getBoringDict()
        network = state["network"]
        nethelper = helper.DictHelper(network)

        if nethelper:
            layerNames = nethelper.nameOfLayers()
            layerNamesSet = set(layerNames)
            if not len(layerNames) == len(layerNamesSet):
                # Extract only duplicate layer names
                duplicateNames = set([name for name in layerNames if not name in layerNamesSet or layerNamesSet.remove(name)])
                for name in duplicateNames:
                    phases = []
                    noPhase = False
                    for id in nethelper.layerIdsForName(name):
                        params = nethelper.layerParams(id)
                        if params and "include" in params and len(params["include"]) > 0 and "phase" in params["include"][0]:
                            phases.append(params["include"][0]["phase"])
                        else:
                            noPhase = True
                            break
                    if noPhase or not len(phases) == len(set(phases)):
                        QMessageBox.about(None, "Warning!", "A layer with that name already exists. "
                                                            "During training, caffe will assume shared weights among equally named layers. "
                                                            "Training will fail if dimensions don't match.")
                        return

    def setNetwork(self, network):
        def intern(stateData):
            stateData.signalController().lock()
            stateData.giveProperty("network", network)
            stateData["position"].setValue(dict([(id, [0.0,0.0]) for id in network["layerOrder"]]))
            stateData["selection"].setValue([])
            stateData.signalController().unlock()

        self.historyWriter.entryWithoutHistory(intern)

        self.networkHelper = helper.DictHelper(self.stateData["network"])
    def __connectReactiveThings(self):
        if self.dockElementActiveLayers:
            self.dockElementActiveLayers.setReactiveState(self.stateData)

    def openSolverFromFile(self, filePath):
        with open(filePath, 'r') as file:
            inputString = file.read()

        self.openSolverFromString(inputString)

    def openSolverFromString(self,inputString, clearHistory=False):
        if clearHistory:
            self._historymanager.clear()

        def intern(stateDict):
            stateDict.giveProperty("solver",loader.loadSolver(inputString))
        self.historyWriter.makeEntry(intern)

    def setSolver(self, solver):
        # prevent manipulation of solver constraints
        if solver:
            solver = ensureSolverConstraints(solver)

        # save data
        self.dockSolverProperties().setSolver(solver)
        self.historyWriter.makeEntry(None)

    def setLayerPositionDictionary(self, posDict):
        self.nodeEditor.applyLayerPositionDict(posDict)

    def getLayerPositionDictionary(self):
        return self.nodeEditor.createLayerPositionDict()

    def getLayerDict(self):
        return self.network["layers"]

    def getLayer(self, layerId):
        return self.networkHelper.layerPerId(layerId)

    def getLayerCount(self):
        return self.layerCount

    def getLayerTypeCount(self, type):
        return self.dicLayerTypeCounter[type]

    def setStateDictionary(self, dictionary, clearHistory = False):
        """ Sets the dictionary of docks state and update gui """
        if clearHistory:
            self._historymanager.clear()

        self._historymanager.insertFunc(lambda inserter: inserter(dictionary))
        self._refreshStateFromHistory()

    def getStateDictionary(self):
        """ Returns a dictionary which represents the current state of the project """
        #return self._historymanager.currentState()
        return self.stateData.getBoringDict()

    def getToolTip(self, id):
        'Returns the standard tooltip for an item representing the layer given by id'
        # Check if name exists, since it is optional
        network = self.stateData["network"].getBoringDict()
        if "name" in network["layers"][id]["parameters"]:
            tooltip = network["layers"][id]["parameters"]["name"] + "\n"

        # Add type and other parameters
        tooltip += "Type: " + network["layers"][id]["parameters"]["type"] + "\n"
        tooltip += "\n"
        tooltip += "Parameters: " + "\n"

        # Add all other parameters to the tooltip
        for key in network["layers"][id]["parameters"]:
            if not key in ["name", "type", "top", "bottom"]:
                tooltip += self._getToolTipHelper(0, key, network["layers"][id]["parameters"][key])

        tooltip += "\n"

        # Add Top and Bottom to the bottom of the tooltip
        if "top" in network["layers"][id]["parameters"]:
            tooltip += self._getToolTipHelper(0, "top", network["layers"][id]["parameters"]["top"])
        if "bottom" in network["layers"][id]["parameters"]:
            tooltip += self._getToolTipHelper(0, "bottom", network["layers"][id]["parameters"]["bottom"])

        return tooltip

    def _getToolTipHelper(self, tabs, key, data):
        # Initialize the partial tooltip as a string containing the given key
        toolTipPart = tabs * "    "
        toolTipPart += key

        # Use recursion if the data is a dict
        if isinstance(data, dict):
            toolTipPart += " { \n"

            for innerKey in data:
                # Add a tabulator as starter string for inner parts of the dict
                toolTipPart += self._getToolTipHelper(tabs + 1, innerKey, data[innerKey])

            toolTipPart += tabs * "    " + "} \n"
        elif isinstance(data, list):
            # Set up a special case for the representation of top and bottom lists
            if (key == "top") | (key == "bottom"):
                toolTipPart += ": "

                for i in range(0, len(data)):
                    # The string may contain some spacial characters which can not be displayed in unicode.
                    # The encode method returns a bytes representation of the unicode string and ignores errors.
                    # Then the decode method convertes the string using the utf-8 codec.
                    # This string can be displayed even if it is containing special characters.
                    toolTipPart += "\t" + data[i].encode('utf-8', 'ignore').decode('utf-8') + "\n"
            else:
                # Proceed based on the type of the list elements, catch empty lists
                if len(data) > 0:
                    # Assumption: All elements of the parameter list are of the same type
                    # always true in current network definitions. If that is changed, this code must be revised
                    if isinstance(data[0], int) | isinstance(data[0], float):
                        # In case of simple int or float values, just concatenate the elements into one line of string
                        toolTipPart += ": "

                        for i in range(0, len(data)):
                            toolTipPart += str(data[i]) + " "
                        toolTipPart += "\n"
                    elif isinstance(data[0], dict):
                        # In case of more complex element types, create a new subset of values containing the elements
                        toolTipPart += " [ \n"

                        # Type is dictionary, use recursion to get all values from that dicationary
                        for i in range(0, len(data)):
                            for key in data[i]:
                                toolTipPart += self._getToolTipHelper(tabs + 1, key, data[i][key])
                        toolTipPart += tabs * "    " + "] \n"
                    elif isinstance(data[0], list):
                        # In case of more complex element types, create a new subset of values containing the elements
                        toolTipPart += " [ \n"

                        # Type is list, user recursion to get all values from that list
                        for i in range(0, len(data)):
                            toolTipPart += self._getToolTipHelper(tabs, "", data[i])

                        toolTipPart += tabs * "    " + "] \n"

        elif isinstance(data, str) or isinstance(data, unicode):
            # Add string by simple concatenation
            toolTipPart += ": " + "\"" + data + "\"" + "\n"
        elif isinstance(data, int) or isinstance(data, float):
            # Add int by simple concatenation
            toolTipPart += ": " + str(data) + "\n"

        return toolTipPart

    def updateToolTip(self, layerID):
        self.nodeEditor.updateTooltip(layerID)

    def duplicateLayers(self, layerIDs, point=None):
        """ Duplicates the layer referenced by layerIDs. If these are interconnected, then the connection is duplicated
            as well.
        """
        # Get the current data
        state = self.stateData.getBoringDict()
        network = state["network"]
        nethelper = helper.DictHelper(network)

        # Check if a layer have been moved
        self.checkLayersForMovement(self.nodeEditor.getNodeIds())

        layerIDs = self._checkValidIDs(layerIDs, nethelper)
        newLayerNames = self._generateNewLayerNames(layerIDs, nethelper)
        newIDs = self._generateNewLayers(layerIDs, newLayerNames, nethelper, state)
        self._addBlobs(layerIDs, newIDs, newLayerNames,  nethelper)
        self._addConnections(layerIDs, newIDs)
        self._translateLayers(layerIDs, newIDs, point)

    def _checkValidIDs(self, layerIDs, nethelper):
        """ check if every id is valid, returns a list of all valid IDs in layerIDs. """
        tempLayerIds = []
        for index, id in enumerate(layerIDs):
            # encapsulate getting the layer per id in a try block
            try:
                nethelper.layerPerId(id)
                tempLayerIds.append(id)
            except KeyError:
                Log.error(
                    "Could not copy element with id " + str(id),
                    self.callerId
                )
        return tempLayerIds


    def _generateNewLayerNames(self, layerIDs, nethelper):
        """ This function generates new Layer names based on a list of layerIds to be duplicated and the already given
            names in the network, to prevent duplicate names or unreasonable enumeration.
            The names are generated as followed:
            1. Check if the layer to be copied ends in a number.
                If it does:
                    add 1 to this number
                If it does not:
                    append #1 at the end
            2. Increase the last number until the string does not match any given layer name in the network or of the
                new names already generated in the loop.
        """
        # get all already distributed names, including the new generated names in the following loop
        allLayerNames = nethelper.nameOfLayers()
        # list to save the new generated Names
        newNames = []
        for id in layerIDs:
            # Get the old layer and its name
            oldLayer = nethelper.layerPerId(id)
            oldName = oldLayer["parameters"]["name"]
            # Check if oldName  ends with a number, then strips the number
            # baseName  stored the name without the number at the end
            baseName = re.sub('[0-9]+$', '', oldName)
            # check if there was a number attached at the end, store it in counter
            try:
                counter = int(oldName[len(baseName):])
                counter += 1
            except ValueError:
                # Set up new counter, add a '#' at the basename to indicate a new enumeration
                counter = 1
                baseName = baseName + "#"
            newName = "{}{}".format(baseName, counter)
            # Check if there already is a name with that number, if yes, add one to counter for new name
            while newName in allLayerNames:
                counter += 1
                newName = "{}{}".format(baseName, counter)
            # Append the chosen Name
            allLayerNames.append(newName)
            newNames.append(newName)
        return newNames

    def _generateNewLayers(self, layerIDs, newLayerNames, nethelper, state):
        """ Given a list of given layerIDs, and a list of new layer names, duplicate the layers in the first list by
            using the names of the latter. The i-th elements of the two lists correspond to one another.
            Returns a list of the IDs of the new layers.
        """
        # Get the current data
        positions = state["position"]
        network = state["network"]
        newIDs = []
        for index in range(len(layerIDs)):
            id = layerIDs[index]
            newName = newLayerNames[index]
            # Get the old layer and its name
            oldLayer = nethelper.layerPerId(id)
            # Create a new layer with the type and parameters of the old layer
            newLayer = {
                "type": oldLayer["type"],
                "parameters": copy.deepcopy(oldLayer["parameters"])
            }

            # Overwrite the values for name, top and bottom
            newLayer["parameters"]["name"] = newName
            newLayer["parameters"]["top"] = []
            newLayer["parameters"]["bottom"] = []

            # Generate random new ID and set the new idx
            newId = str(uuid.uuid4())
            idx = network["layerOrder"].index(id) + 1

            # Add the new layer to the network
            network["layers"][newId] = newLayer
            network["layerOrder"].insert(idx, newId)
            newIDs.append(newId)

        # Set the new position for each copied element, also replace selection with duplicates
        newPositions = positions.copy()
        for i in range(0, len(layerIDs)):
            (x, y) = positions[layerIDs[i]]
            newPositions[newIDs[i]] = (x + 20, y + 20)

        # Update the network manager
        self.setStateDictionary({
            "position": newPositions,
            "selection": newIDs,
            "network": network,
            "solver": state["solver"]
        })
        return newIDs

    def _addBlobs(self, layerIDs, newIDs, newLayerNames, nethelper):
        """ Add bottom and uniquely named top blobs to the layers referenced by newIDs, by using the blobs in the layers
            referenced by layerIDs as a template.
            The naming of the top blobs goes as follows:
            1.  If the name of the blob in the old layer matches the name of the layer:
                    The new blob gets the name of the new layer (which always ends in a number).
                Else:
                    If the old blob end with a number:
                        Add one to that number
                    Else:
                        Append "#1" to the name

            2. Increase the last number until the string does not match any given layer name in the network or of the
                new names already generated in the loop.

        """
        allTopNames = nethelper.nameOfTopBlobs()
        # Add the right top and bottom blobs to all new layers
        for index in range(0, len(layerIDs)):
            newLayerName = newLayerNames[index]
            oldLayer = nethelper.layerPerId(layerIDs[index])
            oldLayerName = oldLayer["parameters"]["name"]
            newID = newIDs[index]
            oldID = layerIDs[index]
            # Create the right amount of bottom blobs for the new layer
            if "bottom" in nethelper.layerPerId(oldID)["parameters"]:
                for j in range(0, len(nethelper.layerPerId(oldID)["parameters"]["bottom"])):
                    self.addBottomBlob(newID)

            # Create the right amount of top blobs for the new layer, using the names from the old one
            if "top" in nethelper.layerPerId(oldID)["parameters"]:
                for j in range(0, len(nethelper.layerPerId(oldID)["parameters"]["top"])):
                    topBlobName = nethelper.layerPerId(oldID)["parameters"]["top"][j]
                    # Check if top blob name matches the layername
                    if topBlobName == oldLayerName:
                        # check if newLayerName is candidate for top blob name
                        candidateName = newLayerName
                        if candidateName in allTopNames:
                            candidateName += "#1"
                        # Since newName ends with a number (either as an iteration based on a previous name or by adding
                        #  #1), we can assert here that candidateName ends with a number
                    else:
                        candidateName = topBlobName
                        # Check if there is no number at the end of the  top blob name
                        baseName = re.sub('[0-9]+$', '', candidateName)
                        if baseName >= candidateName:
                            candidateName += '#1'
                    # Set up the current counter, either by setting it to 1 or by getting the suffix, if it is a number
                    baseName = re.sub('[0-9]+$', '', candidateName)
                    try:
                        counter = int(candidateName[len(baseName):])
                    except ValueError:
                        # Set up new counter, add a '#' at the basename to indicate a new enumeration
                        counter = 1
                        baseName = baseName + "#"
                    newTopName = "{}{}".format(baseName, counter)
                    # increase pending number of candidateName, until it is unique.
                    while newTopName in allTopNames:
                        baseName = re.sub('[0-9]+$', '', newTopName)
                        counter += 1
                        newTopName = "{}{}".format(baseName, counter)
                    self.addTopBlob(newIDs[index], newTopName)
                    # Add new name to the list to prevent duplicates
                    allTopNames.append(newTopName)

    def _addConnections(self, layerIDs, newIDs):
        """ Check if copied layers were interconnected, if yes, add these connections to the new layers. """
        for i in range(0, len(layerIDs)):
            # Get the corresponding layer item
            nodeItem = self.nodeEditor.getNodes()[layerIDs[i]]
            for j in range(0, len(nodeItem.getBottomConnectors())):
                for k in range(0, len(nodeItem.getBottomConnectors()[j].getConnections())):
                    for n in range(0, len(layerIDs)):
                        if nodeItem.getBottomConnectors()[j].getConnections()[k].getTopConnector() in \
                                self.nodeEditor.getNodes()[layerIDs[n]].getTopConnectors():
                            self.connectLayers(newIDs[n], nodeItem.getBottomConnectors()[j].getConnections()[
                                k].getTopConnector().getIndex(),
                                               newIDs[i], nodeItem.getBottomConnectors()[j].getIndex())

    def _translateLayers(self, layerIDs, newIDs, point):
        """ If a position has been given by user, translate the new layers. """
        if point != None:
            # Find the smallest x coordinate from the old layers
            minX = sys.maxint
            nodes = self.nodeEditor.getNodes()
            for id in layerIDs:
                if nodes[id].x() < minX:
                    minX = nodes[id].x()
                    correspondingY = nodes[id].y()

            # Translate all new elements accordingly
            for i in range(0, len(newIDs)):
                nodes[newIDs[i]].setPos(nodes[layerIDs[i]].x() - minX + point.x(),
                                        nodes[layerIDs[i]].y() - correspondingY + point.y())
        # todo: IMPORTANT how do i save these positions so that they won't get reversed?
