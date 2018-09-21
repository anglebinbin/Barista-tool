from PyQt5.QtCore import QRectF
from PyQt5.QtWidgets import QGraphicsItem

from gui.main_window.node_editor.items.connector_bottom_item import ConnectorBottomItem
from gui.main_window.node_editor.items.connector_top_item import ConnectorTopItem
from gui.network_manager.layer_helper import LayerHelper
from gui.main_window.node_editor.items.renderer.node_item_renderer import NodeItemRenderer


class NodeItem(QGraphicsItem):

    def __init__(self, layerID, layerData, nodeEditor, parent=None):
        super(NodeItem, self).__init__(parent)

        # Tell Qt to send change events
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsScenePositionChanges, True)

        self.setZValue(1.0)

        self.__nodeEditor = nodeEditor
        self.__layerID = layerID
        self.__layerData = layerData
        self.__phase = ""
        self.__isInPlace = False

        self.__bottomConnectors = list()
        self.__topConnectors = list()

        # create a renderer to split logic from rendering
        self.__renderer = NodeItemRenderer(self)

        self.updateLayerData()

    def updateLayerData(self):
        """ Updates the layers internal variables to represent changes made to the layer and updates the rendering """

        self.__phase = LayerHelper.getLayerPhase(self.__layerData)
        for topConnector in self.getTopConnectors():
            for connection in topConnector.getConnections():
                for linkedConnection in connection.getBottomConnector().getConnections():
                    if self.__phase == "":
                        if linkedConnection is not connection:
                            self.__nodeEditor.removeConnection(linkedConnection)
                    if linkedConnection.getPhase() == self.__phase and linkedConnection is not connection:
                        self.__nodeEditor.removeConnection(linkedConnection)
        self.__updateConnectorNames()
        self.__isInPlace = LayerHelper.isLayerInPlace(self.__layerData)
        self.__renderer.update()
        self.__renderer.updateConnectorPositions(self.__bottomConnectors, True)
        self.__renderer.updateConnectorPositions(self.__topConnectors, False)
        self.update()

    def __updateConnectorNames(self):
        """ Sets the internal connector names to correspond to the blob names in the underling data structure """
        if "top" in self.__layerData["parameters"]:
            for index in range(0, len(self.__topConnectors)):
                blobName = self.__layerData["parameters"]["top"][index]
                self.__topConnectors[index].setBlobName(blobName)

        if "bottom" in self.__layerData["parameters"]:
            for index in range(0, len(self.__bottomConnectors)):
                blobName = self.__layerData["parameters"]["bottom"][index]
                self.__bottomConnectors[index].setBlobName(blobName)

    def addTopConnector(self, blobName):
        """ Adds a top connector with the given name to the node item """

        connector = ConnectorTopItem(len(self.__topConnectors), self, self.__nodeEditor, self)
        connector.setBlobName(blobName)
        self.__topConnectors.append(connector)
        self.updateLayerData()

    def addBottomConnector(self, blobName):
        """ Adds a bottom connector with the given name to the node item """

        connector = ConnectorBottomItem(len(self.__bottomConnectors), self, self.__nodeEditor, self)
        connector.setBlobName(blobName)
        self.__bottomConnectors.append(connector)
        self.updateLayerData()

    def removeBottomConnector(self, blobIndex):
        """ Removes the bottom connector with the given index """

        self.__removeConnector(self.__bottomConnectors, blobIndex)

    def removeTopConnector(self, blobIndex):
        """ Removes the top connector with the given index """

        self.__removeConnector(self.__topConnectors, blobIndex)

    def boundingRect(self):
        return self.__renderer.boundingRect()

    def paint(self, painter, option, widget):
        self.__renderer.paint(painter)

    def getTopConnectorCount(self):
        """ Returns the number of top connectors """

        return len(self.__topConnectors)

    def getBottomConnectorCount(self):
        """ Returns the number of bottom connectors """

        return len(self.__bottomConnectors)

    def getTopConnectors(self):
        """ Returns a list of all top connector items """

        return self.__topConnectors

    def getBottomConnectors(self):
        """ Returns a list of all bottom connector items """

        return self.__bottomConnectors

    def getNodeEditor(self):
        return self.__nodeEditor

    def getLayerID(self):
        """ Returns the internal layer ID of the layer represented by this node item """

        return self.__layerID

    def getName(self):
        """ Returns the name of the layer, represented by this node item """

        return self.__layerData["parameters"]["name"]

    def getTypeString(self):
        """ Returns the type name as a string """
        return self.__layerData["type"].name()

    def getType(self):
        """ Returns the internal type object """
        return self.__layerData["type"]

    def getPhase(self):
        """ Returns this node items phase """

        return self.__phase

    def getIsInPlace(self):
        """ Returns, whether the layer, represented by this node item, works in-place """
        return self.__isInPlace

    def getNodesConnectedToTops(self):
        """ Returns a list of node items connected to any top connector of this node item """

        return self.__getNodesConnectedToConnectors(self.__topConnectors)

    def __removeConnector(self, connectors, indexToRemove):
        """ Removes the given connector from this node item """
        self.scene().removeItem(connectors[indexToRemove])
        del connectors[indexToRemove]
        self.__updateConnectorIndices(connectors)
        self.updateLayerData()

    def __updateConnectorIndices(self, connectors):
        """ Recalculates the connector indices after deleting a connector """

        for i in range(0, len(connectors)):
            connectors[i].setIndex(i)
            i += 1

    def getNodesConnectedToBottoms(self):
        """ Returns a list of node items connected to any bottom connector of this node item """

        return self.__getNodesConnectedToConnectors(self.__bottomConnectors)

    def __getNodesConnectedToConnectors(self, connectors):
        """ Returns a list of node items connected to any connector in the given list of connectors """

        connected = list()
        for connector in connectors:
            connectedNodes = connector.getConnectedNodes()
            for node in connectedNodes:
                if node not in connected:
                    connected.append(node)
        return connected

    def itemChange(self, change, value):
        """ Check, whether the item is out of the scenes bounds """
        if change == QGraphicsItem.ItemPositionChange:
            # get the new position
            newPos = value
            oldRect = self.sceneBoundingRect()
            newRect = QRectF(newPos.x(), newPos.y(), oldRect.width(), oldRect.height())
            sceneRect = QRectF(self.scene().sceneRect())

            # check if the left or right side of the new rect is outside the scenes bounds -> move it back inside
            if newRect.left() < sceneRect.left():
                newPos.setX(sceneRect.left())
            elif newRect.left() + newRect.width() > sceneRect.right():
                newPos.setX(sceneRect.right() - newRect.width())

            # check if the top or bottom side of the new rect is outside the scenes bounds -> move it back inside
            if newRect.bottom() > sceneRect.bottom():
                newPos.setY(sceneRect.bottom() - newRect.height())
            elif newRect.top() < sceneRect.top():
                newPos.setY(sceneRect.top())
            return newPos
        return super(NodeItem, self).itemChange(change, value)

    def disableBlobs(self, disable):
        ''' Disable the context menu of the tob and bottom blobs. '''
        for blob in self.getBottomConnectors():
            blob.disableEditing(disable)
        for blob in self.getTopConnectors():
            blob.disableEditing(disable)
