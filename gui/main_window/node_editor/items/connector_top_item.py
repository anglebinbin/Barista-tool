from PyQt5.QtWidgets import QMenu

from gui.main_window.node_editor.items.connector_item import ConnectorItem


class ConnectorTopItem(ConnectorItem):
    """ Class to provide top connector functionality """

    def __init__(self, index, nodeItem, nodeEditor, parent=None):
        super(ConnectorTopItem, self).__init__(index, nodeItem, nodeEditor, parent)

    def isTopConnector(self):
        """ Returns whether the connector is a top connector (implementation for parent class) """
        return True

    def isInPlace(self):
        """ Returns whether the connector is connected to a in-place working layer
            A top connector is in place if any connected bottom connector is in place.
            (implementation for parent class)  """
        for connection in self._connections:
            if connection.getIsInPlace():
                return True
        return False

    def getConnectedNodes(self):
        """ Returns a list of node items, connected to this connector (implementation for parent class) """
        nodes = list()

        # for each connection get the node connected to the bottom of the connection
        for connection in self._connections:
            connectionsBottomConnector = connection.getBottomConnector()
            if connectionsBottomConnector is not None:
                nodes.append(connectionsBottomConnector.getNodeItem())
        return nodes

    def addConnection(self, connection):
        """ Adds a connection to the connector and sets the start of the connection to this connectors position
            (implementation for parent class) """
        self._connections.append(connection)
        connection.setStart(self.scenePos())

    def updateConnectionPositions(self):
        """ Updates the connected connections, sets the start of all connected connections to this connectors position
            (implementation for parent class) """
        for connection in self._connections:
            connection.setStart(self.scenePos())

    def contextMenuEvent(self, event):
        """ Context menu for the top connector """
        contextMenu = QMenu()
        renameTop = contextMenu.addAction("Change name")
        disconnectTop = contextMenu.addAction("Disconnect")
        if self.getConnectionCount() == 0:
            disconnectTop.setEnabled(False)
        removeTop = contextMenu.addAction("Remove")
        action = contextMenu.exec_(event.screenPos())
        if action is not None:
            if action == removeTop:
                self._nodeEditor.tryToRemoveTopBlob(self._nodeItem.getLayerID(), self._index)
            elif action == renameTop:
                self._nodeEditor.tryToRenameTopBlob(self)
            elif action == disconnectTop:
                self._nodeEditor.disconnectTopBlob(self._nodeItem.getLayerID(), self._index)
