from PyQt5.QtWidgets import QGraphicsItem
from gui.main_window.node_editor.items.renderer.connector_item_renderer import ConnectorItemRenderer


class ConnectorItem(QGraphicsItem):
    """ Class to provide basic functionality for top and bottom connectors.
        This class should not get instanced. """
    def __init__(self, index, nodeItem, nodeEditor, parent=None):
        super(ConnectorItem, self).__init__(parent)

        # set flag to get position changed to update connected connections
        self.setFlag(QGraphicsItem.ItemSendsScenePositionChanges, True)

        # draw above the node item
        self.setZValue(2.0)

        self._nodeEditor = nodeEditor
        self._nodeItem = nodeItem

        self._index = index
        self._blobName = ""
        self._connections = list()

        # create a renderer to draw the connector
        self._renderer = ConnectorItemRenderer(self)

    def boundingRect(self):
        return self._renderer.boundingRect()

    def addConnection(self, connection):
        """ Adds a connection to the connector (should get implemented in subclass) """
        return

    def removeConnection(self, connection):
        """ Removes a connection """
        self._connections.remove(connection)

    def paint(self, painter, option, widget=None):
        """ Draws the connector """
        self._renderer.paint(painter)

    def setIndex(self, index):
        """ Sets the index of the connector in the node item """
        self._index = index

    def isConnected(self):
        """ Returns True if there is any connection, False otherwise"""
        return len(self._connections) > 0

    def isInPlace(self):
        """ Returns whether the connector is connected to a in-place working layer
            (should get implemented in subclass) """
        return

    def getNodeEditor(self):
        """ Returns the NodeEditor object (for the renderer) """
        return self._nodeEditor

    def getNodeItem(self):
        """ Returns the owning node item """
        return self._nodeItem

    def setBlobName(self, blobName):
        """ Sets the blobs name """
        self._blobName = blobName

    def getBlobName(self):
        """ Returns the blob name """
        return self._blobName

    def getPhase(self):
        """ Returns the phase of the connector (phase of the owning node item) """
        return self._nodeItem.getPhase()

    def getIndex(self):
        """ Returns the index of hte connector in the node item """
        return self._index

    def isTopConnector(self):
        """ Returns whether the connector is a top connector (should get implemented in subclass)"""
        return

    def updateConnectionPositions(self):
        """ Updates the connected connections (should get implemented in subclass) """
        return

    def getConnectedNodes(self):
        """ Returns a list of node items, connected to this connector (should get implemented in subclass) """
        return

    def getConnections(self):
        """ Returns a list of connection items, connected to this connector """
        return self._connections

    def getConnectionCount(self):
        """ Returns the number of connections, connected to this connector """
        return len(self._connections)

    def hasPhaseConnection(self, phase):
        """ Checks whether the connector is connected to a layer in the given phase """
        for connection in self._connections:
            if connection.getPhase() == "" or connection.getPhase() == phase:
                return True
        return False

    def getConnectedLayers(self):
        """ Returns a list of layer IDs of all connected layers """
        layerIDs = list()
        connectedNodes = self.getConnectedNodes()
        for node in connectedNodes:
            layerIDs.append(node.getLayerID())
        return layerIDs

    def itemChange(self, change, value):
        """ Update all connections, connected to this connector """
        if change == QGraphicsItem.ItemScenePositionHasChanged:
            self.updateConnectionPositions()

        return super(ConnectorItem, self).itemChange(change, value)

    def disableEditing(self, disable):
        ''' Disable the context menu of the blob. '''
        self.setEnabled(not disable)