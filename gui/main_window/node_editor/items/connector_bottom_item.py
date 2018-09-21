from PyQt5.QtWidgets import QMenu
from gui.main_window.node_editor.items.connector_item import ConnectorItem


class ConnectorBottomItem(ConnectorItem):
    """ Class to provide bottom connector functionality """

    def __init__(self, index, nodeItem, nodeEditor, parent=None):
        super(ConnectorBottomItem, self).__init__(index, nodeItem, nodeEditor, parent)

    def isTopConnector(self):
        """ Returns whether the connector is a top connector (implementation for parent class) """
        return False

    def isInPlace(self):
        """ Returns whether the connector is owned by an in-place working layer
            (implementation for parent class)  """
        return self._nodeItem.getIsInPlace()

    def getConnectedNodes(self):
        """ Returns a list of node items, connected to this connector (implementation for parent class) """

        nodes = list()

        # for each connection get the node connected to the top of the connection
        for connection in self._connections:
            connectionsTopConnector = connection.getTopConnector()
            if connectionsTopConnector is not None:
                nodes.append(connectionsTopConnector.getNodeItem())
        return nodes

    def addConnection(self, connection):
        """ Adds a connection to the connector and sets the end of the connection to this connectors position
            (implementation for parent class) """
        self._connections.append(connection)
        connection.setEnd(self.scenePos())

    def updateConnectionPositions(self):
        """ Updates the connected connections, sets the end of all connected connections to this connectors position
            (implementation for parent class) """
        for connection in self._connections:
            connection.setEnd(self.scenePos())

    def contextMenuEvent(self, event):
        """ Context menu for the bottom connector """
        contextMenu = QMenu()
        disconnectBottom = contextMenu.addAction("Disconnect")
        if self.getConnectionCount() == 0:
            disconnectBottom.setEnabled(False)
        removeBottom = contextMenu.addAction("Remove")
        action = contextMenu.exec_(event.screenPos())
        if action is not None:
            if action == removeBottom:
                self._nodeEditor.tryToRemoveBottomBlob(self._nodeItem.getLayerID(), self._index)
            elif action == disconnectBottom:
                self._nodeEditor.disconnectBottomBlob(self._nodeItem.getLayerID(), self._index)
