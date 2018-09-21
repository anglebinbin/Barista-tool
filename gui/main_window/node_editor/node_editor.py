from PyQt5.QtCore import QPointF
from PyQt5.QtWidgets import QInputDialog, QMessageBox
from gui.main_window.node_editor.items.connection_item import ConnectionItem

from gui.main_window.node_editor.items.node_item import NodeItem
from gui.main_window.node_editor.node_editor_event_handler import NodeEditorEventHandler
from gui.main_window.node_editor.node_editor_view import NodeEditorView
from gui.main_window.node_editor.node_sort import NodeSort


class NodeEditor:
    def __init__(self, parent=None):
        self.__view = NodeEditorView(self, parent)
        self.__scene = self.__view.scene()
        self.__networkManager = None
        self.__currentPhase = ""

        self.__nodes = dict()
        self.__hiddenConnections = list()

        self.__eventHandler = NodeEditorEventHandler(self, self.__view, self.__scene)
        self.__view.setEventHandler(self.__eventHandler)
        self.__scene.setEventHandler(self.__eventHandler)

        self.disable = False

    def getNodes(self):
        """ Returns the dict of all node items, the layer ID is the key """

        return self.__nodes

    def setNetworkManager(self, networkManager):
        """ Sets the NetworkManager """
        self.__networkManager = networkManager
        self.__eventHandler.setNetworkManager(networkManager)

    def getNetworkManager(self):
        """ Returns the NetworkManager """

        return self.__networkManager

    def setCopySelection(self):
        self.__eventHandler.setCopySelection()

    def clearAll(self):
        """ Removes all items from the scene and clears the internal dicts """
        self.__nodes.clear()
        self.__scene.clear()

    def createLayerPositionDict(self):
        """ Creates and returns a dict with the layer ID as key and the layers position in the scene as value """

        # create a new dict
        positions = dict()

        # fill dict
        for layerID, nodeItem in self.__nodes.iteritems():
            pos = nodeItem.scenePos()
            positions[layerID] = (pos.x(), pos.y())
        return positions

    def getPositionOfLayer(self, id):
        """ Returns the position of a node item with a given layer ID """

        pos = self.__nodes[id].scenePos()
        return pos.x(), pos.y()

    def setPositionOfLayer(self, id, pos):
        """ Sets the position of a node item with the given layer ID """

        self.__nodes[id].setPos(pos[0],pos[1])

    def applyLayerPositionDict(self, positionsDict):
        """ Sets the positions of all node items to the positions defined in positionsDict, layerID is the key """

        for layerID, pos in positionsDict.iteritems():
            self.__nodes[layerID].setPos(pos[0], pos[1])


    def addLayer(self, layerID, layerData, scenePosX = 0.0, scenePosY = 0.0):
        """ Creates a new NodeItem to represent the layer """

        # create the new node Item
        nodeItem = NodeItem(layerID, layerData, self)

        # set the tooltip containing the parameters to the node item
        parameters = self.__networkManager.getToolTip(layerID)
        nodeItem.setToolTip(parameters)

        # add top connectors to the node item
        if "top" in layerData["parameters"]:
            for top in layerData["parameters"]["top"]:
                nodeItem.addTopConnector(top)

        # add bottom connectors to the node item
        if "bottom" in layerData["parameters"]:
            for bottom in layerData["parameters"]["bottom"]:
                nodeItem.addBottomConnector(bottom)

        # add the node item to the scene and the internal dict
        self.__scene.addItem(nodeItem)
        self.__nodes[layerID] = nodeItem

        nodeItem.setPos(QPointF(scenePosX, scenePosY))


    def setKeyboardFocus(self):
        self.__view.setFocus()

    def focusLayer(self, layerID):
        """ Focuses the viewport to the node item with the given layer ID """

        position = self.__nodes[layerID].pos()
        self.__view.centerOn(position)

    def addBottomBlob(self, layerID, blobName):
        """ Adds a bottom connector to the node item with the given layer ID """

        nodeItem = self.__nodes[layerID]
        nodeItem.addBottomConnector(blobName)

    def removeBottomBlob(self, layerID, blobIndex):
        """ Removes a bottom connector from the node item with the given layer ID """
        self.__nodes[layerID].removeBottomConnector(blobIndex)

        # Update the tooltip as well
        self.updateTooltip(layerID)

    def addTopBlob(self, layerID, blobName):
        """ Adds a top connector to the node item with the given layer ID """

        nodeItem = self.__nodes[layerID]
        nodeItem.addTopConnector(blobName)

        bottomConnectors = self.__nodes[layerID].getBottomConnectors()
        for bottomConnector in bottomConnectors:
            connections = bottomConnector.getConnections()
            for connection in connections:
                connection.updateData()

        # Update the tooltip as well
        self.updateTooltip(layerID)

    def renameTopBlob(self, layerID, blobIndex, newName):
        """ Renames a top connector and changes the name of all connected bottom connectors """

        # update the top connectors name
        connector = self.__nodes[layerID].getTopConnectors()[blobIndex]
        connector.setBlobName(newName)
        self.__nodes[layerID].updateLayerData()

        # get all connected connectors and change their name
        connections = connector.getConnections()
        for connection in connections:
            bottomConnector = connection.getBottomConnector()
            self.__networkManager.renameBottomBlob(bottomConnector.getNodeItem().getLayerID(),
                                                   bottomConnector.getIndex(),
                                                   newName)
            connection.updateData()

        # update all connections
        bottomConnectors = self.__nodes[layerID].getBottomConnectors()
        for bottomConnector in bottomConnectors:
            connections = bottomConnector.getConnections()
            for connection in connections:
                connection.updateData()

        # Update the tooltip as well
        self.updateTooltip(layerID)

    def renameBottomBlob(self, layerID, blobIndex, newName):
        """ Renames a bottom connector and removes all connections getting invalid by this operation """
        # rename the bottom connector
        bottomConnector = self.__nodes[layerID].getBottomConnectors()[blobIndex]
        bottomConnector.setBlobName(newName)
        self.__nodes[layerID].updateLayerData()

        # get all top connectors and check if they have the same name. If not -> remove connection
        connections = list(bottomConnector.getConnections())
        for connection in connections:
            topConnector = connection.getTopConnector()
            if topConnector.getBlobName() != newName:
                self.removeConnection(connection)

        # Update the tooltip as well
        self.updateTooltip(layerID)

    def removeTopBlob(self, layerID, blobIndex):
        """ Removes a top connector from the node item with the given layer ID """

        self.__nodes[layerID].removeTopConnector(blobIndex)

        # Update the tooltip as well
        self.updateTooltip(layerID)

    def disconnectBottomBlob(self, layerID, blobIndex):
        """ Removes all connections connected to the bottom connector with the given index
            of the node item with the given layer ID """

        connector = self.__nodes[layerID].getBottomConnectors()[blobIndex]
        self.__disconnectAllConnectorConnections(connector)

        # Update the tooltip as well
        self.updateTooltip(layerID)

    def disconnectTopBlob(self, layerID, blobIndex):
        """ Removes all connections connected to the top connector with the given index
            of the node item with the given layer ID """

        connector = self.__nodes[layerID].getTopConnectors()[blobIndex]
        self.__disconnectAllConnectorConnections(connector)

        # Update the tooltip as well
        self.updateTooltip(layerID)

    def createConnection(self, topLayerID, topBlobIndex, bottomLayerID, bottomBlobIndex):
        """ Creates a new connection between the top connector at topBlobIndex of the node item with the topLayerID
            and the bottom connector at bottomBlobIndex of the node item with the bottomLayerID """

        # get the connectors
        topConnector = self.__nodes[topLayerID].getTopConnectors()[topBlobIndex]
        bottomConnector = self.__nodes[bottomLayerID].getBottomConnectors()[bottomBlobIndex]

        # create a new connection item and add it to the scene
        connection = ConnectionItem(self)
        self.__scene.addItem(connection)

        # set the connection/connectors in the connection/connectors
        connection.setTopConnector(topConnector)
        connection.setBottomConnector(bottomConnector)
        bottomConnector.addConnection(connection)
        topConnector.addConnection(connection)

    def rearrangeNodes(self):
        """ Automatically sorts the node items """
        nodesort = NodeSort(self.getNodes(), self.__view)
        self.__networkManager.checkLayersForMovement(self.getNodeIds())

    def rearrangeNodesVertical(self):
        """ Automatically sorts the node items Vertical """
        nodesort = NodeSort(self.getNodes(), self.__view, True)
        self.__networkManager.checkLayersForMovement(self.getNodeIds())

    def clearSelection(self):
        """ Clears the selection """

        self.__scene.clearSelection()

    def setSelectedLayer(self, layerID):
        """ Sets a single layer as selected. Already selected layers get deselected. """

        # remove all node items from the selection
        self.clearSelection()

        # get the node item with layer ID and set it as selected
        for item in self.__scene.items():
            if isinstance(item, NodeItem):
                if item.getLayerID() == layerID:
                    item.setSelected(True)
                    break

    def setSelectedLayers(self, layerIDs):
        """ Sets a list of layers as selected. Alread selected layers get deselected. """

        # remove all node items from the selection
        self.clearSelection()

        # get all items in the scene
        layerList = list(layerIDs)
        items = self.__scene.items()

        # check all items and set the as selected if they are in the given list
        while(len(layerList) > 0):
            for item in items:
                if isinstance(item, NodeItem):
                    if item.getLayerID() == layerList[0]:
                        item.setSelected(True)
                        break

            del layerList[0]

    def addLayerToSelection(self, layerID):
        """ Selects a node item without clearing other layers selection """

        items = self.__scene.items()
        for item in items:
            if isinstance(item, NodeItem):
                if item.getLayerID() == layerID:
                    item.setSelected(True)
                    break

    def removeLayerFromSelection(self, layerID):
        """ Deselects a node item without clearing other layers selection """

        selectedItems = self.__scene.selectedItems()
        for item in selectedItems:
            if isinstance(item, NodeItem):
                if item.getLayerID() == layerID:
                    item.setSelected(False)
                    break

    def updateLayerData(self, layerID):
        """ Notifies a node item to update the layer data to render correctly after change """

        self.__nodes[layerID].updateLayerData()

        # Update the tooltip as well
        self.updateTooltip(layerID)

    def disconnectConnectionsOfSelection(self):
        """ Removes all connections from the selection and all connections connecting any selected node item """

        # get all selected items
        selectedItems = self.__scene.selectedItems()

        # remove all selected connections
        for item in selectedItems:
            if isinstance(item, ConnectionItem):
                self.removeConnection(item)

        # remove all connections connected to selected layers
        for item in selectedItems:
            if isinstance(item, NodeItem):
                self.__disconnectAllLayerConnections(item)

    def __disconnectAllLayerConnections(self, nodeItem):
        """ Removes all connections connected to any top or bottom connector of a given node item """

        # remove connections of top connectors
        for topConnector in nodeItem.getTopConnectors():
            self.__disconnectAllConnectorConnections(topConnector)

        # remove connections of bottom connectors
        for bottomConnector in nodeItem.getBottomConnectors():
            self.__disconnectAllConnectorConnections(bottomConnector)

    def __disconnectAllConnectorConnections(self, connector):
        """ Removes all connections connected to a connector """

        connections = list(connector.getConnections())
        for connection in connections:
            self.removeConnection(connection)

    def removeConnection(self, connection):
        """ Removes a connection """

        # get all selected items
        selectedItems = self.__scene.selectedItems()

        # remove connection from connectors
        topConnector = connection.getTopConnector()
        bottomConnector = connection.getBottomConnector()
        topConnector.removeConnection(connection)
        bottomConnector.removeConnection(connection)

        # get layer ID and connector index to notify data change
        bottomLayerID = bottomConnector.getNodeItem().getLayerID()
        bottomBlobIndex = bottomConnector.getIndex()

        # if the bottom connector has no connections left and is not in the selection,
        # remove the underling data relation of top-bottom blob
        if bottomConnector.getConnectionCount() == 0 and bottomConnector.getNodeItem() not in selectedItems:
            self.__networkManager.disconnectLayer(bottomLayerID, bottomBlobIndex)

        # remove the connection item from the scene
        self.__scene.removeItem(connection)

    def deleteItemsByID(self, list):
        """ Removes node items from the scene based on the list of layer IDs """

        for layerID in list:
            items = self.__scene.items()
            for item in items:
                if isinstance(item, NodeItem):
                    if item.getLayerID() == layerID:
                        self.__scene.removeItem(item)
                        index = self.__nodes.values().index(item)
                        key = self.__nodes.keys()[index]
                        del self.__nodes[key]

    def updateLayerName(self, layerID, name):
        """ Notify the node item to update the rendering. """

        self.__nodes[layerID].updateLayerData()

        # Update the tooltip as well
        self.updateTooltip(layerID)

    def updateTooltip(self, layerID):
        """ Updates the tooltip of the node item with the given layer ID """

        parameters = self.__networkManager.getToolTip(layerID)
        self.__nodes[layerID].setToolTip(parameters)

    def createListFromHiddenConnections(self):
        """ Creates a list of tuples containing the hidden connections, the tuples have the form
            (topLayerID, topBlobIndex, bottomLayerID, bottomBlobIndex) """

        outList = list()
        for connection in self.__hiddenConnections:
            topConnector = connection.getTopConnector()
            bottomConnector = connection.getBottomConnector()
            outList.append((topConnector.getNodeItem().getLayerID(), topConnector.getIndex(),
                            bottomConnector.getNodeItem().getLayerID(), bottomConnector.getIndex()))
        return outList

    def setHiddenConnectionsFromList(self, hiddenList):
        """ Sets all connections to show and then hides the connections specified in hiddenList,
            hiddenList contains tuples (topLayerID, topBlobIndex, bottomLayerID, bottomBlobIndex) """

        self.__hiddenConnections = []

        for data in hiddenList:
            connection = self.__getConnection(data[0], data[1], data[2], data[3])
            if connection is not None:
                connection.setHidden(True)
                self.__hiddenConnections.append(connection)

    def tryToAddHiddenConnection(self, connection):
        """ Called by connections to notify a hidden state change. """

        if connection not in self.__hiddenConnections:
            self.__hiddenConnections.append(connection)
        self.__networkManager.connectionsHiddenStateChanged(self.createListFromHiddenConnections())

    def tryToRemoveHiddenConnection(self, connection):
        """ Called by connections to notify a hidden state change. """

        if connection in self.__hiddenConnections:
            self.__hiddenConnections.remove(connection)
        self.__networkManager.connectionsHiddenStateChanged(self.createListFromHiddenConnections())

    def tryToCreateLayer(self, type, scenePosX, scenePosY):
        """ Notifies the NetworkManager to create a new Layer. """

        self.__networkManager.addLayer(type, scenePosX, scenePosY)

    def tryToAddBottomBlob(self, layerID, blobName):
        """ Notifies the NetworkManager to create a new bottom connector for the given layer. """

        self.__networkManager.addBottomBlob(layerID, blobName)

    def tryToRemoveBottomBlob(self, layerID, blobIndex):
        """ Notifies the NetworkManager to try to remove the bottom connector
            with the given index in the given layer. """
        self.__networkManager.removeBottomBlob(layerID, blobIndex)

    def getNode(self, layerID):
        return self.__nodes[layerID]

    def tryToAddTopBlob(self, layerID, blobName):
        """ Notifies the NetworkManager to add a top connector to the layer with the given name. """

        self.__networkManager.addTopBlob(layerID, blobName)

    def tryToRenameTopBlob(self, connector):
        """ Shows a input dialog to ask for a new blob name
            and notifies the NetworkManager to change the blobs name. """

        # show input dialog
        name, ok = QInputDialog.getText(self.__view, "Change name of top blob", "Top blob name:")
        name = name.strip()

        # if the name is invalid ask again
        duplicateFound = True
        while ok:
            if len(name) == 0:
                QMessageBox.warning(self.__view, "Top blob name is empty",
                                        "The name for the top blob can't be empty or all whitespace characters.")
                name, ok = QInputDialog.getText(self.__view, "Change name of top blob", "Top blob name:")
                name = name.strip()
                continue
            elif duplicateFound:
                for blob in connector.getNodeItem().getTopConnectors():
                    if name == blob.getBlobName() and blob != connector:
                        QMessageBox.warning(self.__view, "Top blob name already exists",
                                            "The name you chose already exists on this Layer, please choose another name.")
                        name, ok = QInputDialog.getText(self.__view, "Change name of top blob", "Top blob name:")
                        name = name.strip()
                        duplicateFound = True
                        break # stop for loop, continue while loop
                    else:
                        duplicateFound = False
            else:
                break # if string is valid

        # the user provided a valid name
        if ok:
            # check if any bottom connector has multiple connections as a bottom connector can only have one name
            bottomConnectorWithMultipleConnectionsFound = False
            connections = connector.getConnections()
            for connection in connections:
                bottomConnector = connection.getBottomConnector()
                if bottomConnector.getConnectionCount() > 1:
                    bottomConnectorWithMultipleConnectionsFound = True

            # ask the user whether they want to continue (break invalid connections) ore cancel
            shouldRename = True
            if bottomConnectorWithMultipleConnectionsFound:
                reply = QMessageBox.question(self.__view, "Removing connections",
                                             "A bottom blob, connected to the top blob, has multiple connections. "
                                             "By renaming the top blob, the other connections will get removed. "
                                             "Continue?", QMessageBox.Yes, QMessageBox.No)
                if reply != QMessageBox.Yes:
                    shouldRename = False

            # if the user did not cancel -> notify the Networkmanager
            if shouldRename:
                self.__networkManager.renameTopBlob(connector.getNodeItem().getLayerID(), connector.getIndex(), name)

    def tryToRemoveTopBlob(self, layerID, blobIndex):
        """ Notifies the NetworkManager to remove the bottom connector with the given index of the given layer """

        self.__networkManager.removeTopBlob(layerID, blobIndex)

    def tryToClearSelection(self):
        """ Notifies the NetworkManager to clear the selection """

        self.__networkManager.clearSelectionWithoutSavingHistory()

    def tryToSetSelectionList(self, layerIDs):
        """ Notifies the NetworkManager to update the selected layer list """

        self.__networkManager.setSelectionList(layerIDs)

    def tryToDeleteSelection(self):
        """ Notifies the NetworkManager to remove all selected layers """

        self.__networkManager.deleteSelectedLayers()

    def tryToConnect(self, topLayerID, topBlobIndex, bottomLayerID, bottomBlobIndex):
        """ Checks wheter the new connection would be valid and
            notifies the NetworkManager to create the new connection """

        topConnector = self.__nodes[topLayerID].getTopConnectors()[topBlobIndex]
        bottomConnector = self.__nodes[bottomLayerID].getBottomConnectors()[bottomBlobIndex]
        alreadyConnectedBottomLayers = topConnector.getConnectedLayers()

        # check id the new connections is between two connectors of the same layer7
        if topConnector.getNodeItem() == bottomConnector.getNodeItem():
            return False

        # check if connection between both connectors exists
        if bottomLayerID in alreadyConnectedBottomLayers:
            return False

        # check if both layers have the same phase (if both are not in all phases)
        if topConnector.getPhase() != "" and bottomConnector.getPhase() != "":
            if topConnector.getPhase() != bottomConnector.getPhase():
                return False

        # if the top layer is in all phases, the bottom layer is not allowed to have any connection at the connector
        if topConnector.getPhase() == "":
            if bottomConnector.getConnectionCount() > 0:
                return False
        # if the top layer is not in all phases, check if the
        # bottom layer connector has another connection in the same phase
        else:
            if bottomConnector.hasPhaseConnection(topConnector.getPhase()):
                return False
            elif bottomConnector.getBlobName() != "":
                if topConnector.getBlobName() != bottomConnector.getBlobName():
                    return False

        if topConnector.isInPlace():
            if topConnector.hasPhaseConnection(bottomConnector.getPhase()):
                return False

        # layers can get connected
        self.__networkManager.connectLayers(topLayerID, topBlobIndex, bottomLayerID, bottomBlobIndex)
        return True

    def isCurrentPhase(self, phase):
        """ Returns whether the phase is equals the current displayed phase. """

        if len(phase) == 0 or self.__currentPhase == phase:
            return True
        else:
            return False

    def __getConnection(self, topID, topIndex, bottomID, bottomIndex):
        """ Returns the connection between the layers with the IDs topID and bottomID,
            connected at the connectors with the indices topIndex and bottomIndex """

        topConnector = self.__nodes[topID].getTopConnectors()[topIndex]
        connections = topConnector.getConnections()
        for connection in connections:
            bottomConnector = connection.getBottomConnector()
            if bottomConnector.getNodeItem().getLayerID() == bottomID and bottomConnector.getIndex() == bottomIndex:
                return connection
        return None

    def calculateLayerOrder(self):
        """ Returns a list of layer ID representing the order of connection """

        order = list()

        # get a list of all node items with no bottom connectors
        # or with no connections connected to any bottom connector
        currentNodes = self.__getStartNodes()
        waitingNodes = dict()

        # unused
        touched = {}

        # repeat until all nodes have been processed
        while len(currentNodes) > 0:
            currentNode = currentNodes[0]

            touched[currentNode.getLayerID()] = currentNode.getName()

            # add the current node to the order list
            order.append(currentNode.getLayerID())

            # get a list of all nodes connected to any top connector of the current node
            followingNodes = currentNode.getNodesConnectedToTops()
            for node in followingNodes:
                touched[node.getLayerID()] = node.getName()

            # for all following nodes, check if they are waiting (not all node items connected to bottoms
            # have been processed) and decrees the waiting count. If all needed nodes have benn processed,
            # add the node to the processable nodes
            for following in followingNodes:
                # the layer has already been processed
                if following.getLayerID() in order:
                    continue

                # layer has other unprocessed pre nodes
                if following in waitingNodes:
                    if waitingNodes[following] > 1:
                        waitingNodes[following] -= 1
                    else:
                        currentNodes.append(following)
                        del waitingNodes[following]
                else:
                    inputNodeCount = len(following.getNodesConnectedToBottoms())

                    if inputNodeCount > 1:
                        waitingNodes[following] = inputNodeCount - 1
                    else:
                        currentNodes.append(following)

            currentNodes.remove(currentNode)
        return order

    def getView(self):
        return self.__view

    def getScene(self):
        return self.__view.scene()

    def __getStartNodes(self):
        """ Returns a list of all node items with no bottom connectors
            or no connections connected to bottom connectors. """

        startNodes = list()
        for layerID, item in self.__nodes.iteritems():
            if item.getBottomConnectorCount() == 0:
                startNodes.append(item)
            else:
                connected = False
                for connector in item.getBottomConnectors():
                    if connector.getConnectionCount() > 0:
                        connected = True
                        break
                if not connected:
                    startNodes.append(item)
        return startNodes

    def getNodeIds(self):
        """ Returns a list of all layer IDs of nodes currently in the scene. """
        return self.__nodes.keys()

    def disableEditing(self, disable):
        """ Disable relevant changes of the net. """
        self.disable = disable
        self.__eventHandler.setDisabled(disable)
        self.__view.scene().disableEditing(disable)
        for _, node in self.getNodes().iteritems():
            node.disableBlobs(disable)
