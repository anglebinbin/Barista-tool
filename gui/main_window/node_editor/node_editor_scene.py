from PyQt5.QtCore import QLineF
from PyQt5.QtGui import QPen, QColor, QCursor, QTransform
from PyQt5.QtWidgets import QGraphicsScene, QMessageBox

from gui.main_window.node_editor.items.connection_item import ConnectionItem
from gui.main_window.node_editor.items.connector_item import ConnectorItem

from gui.main_window.node_editor.items.node_item import NodeItem
from gui.main_window.node_editor.node_editor_constants import Constants



class NodeEditorScene(QGraphicsScene):
    def __init__(self, view, initialWidth, initialHeight, nodeEditor):
        super(NodeEditorScene, self).__init__(-(initialWidth / 2), -(initialHeight / 2), initialWidth, initialHeight, view)

        self.__view = view
        self.__nodeEditor = nodeEditor
        self.currentlyConnecting = None
        self.disabled = False

        # Create the event handler for this scene
        self.eventHandler = None

    def setEventHandler(self, eventHandler):
        self.eventHandler = eventHandler

    def getNodeEditor(self):
        return self.__nodeEditor

    def getView(self):
        return self.__view

    def startConnection(self, connector, scenePosition):
        """ Creates a new connection item, connected to the connector """

        self.currentlyConnecting = ConnectionItem(self.__nodeEditor)
        self.currentlyConnecting.setConnector(connector)
        self.currentlyConnecting.updateMousePosition(scenePosition)
        self.addItem(self.currentlyConnecting)

    def connectCurrentConnection(self, position):
        """ Try to connect the currently connecting connection.
            If no valid connector was found, the connection disappears """

        # get the item at the position
        itemAt = self.itemAt(position.toPoint(), self.getView().transform())

        # remove the connection (a new connection will get added if there is a valid connector)
        self.removeItem(self.currentlyConnecting)
        connection = self.currentlyConnecting
        self.currentlyConnecting = None


        """ if itemAt is a Connector (Top/Bottom) item (if you pull onto a Blob) """
        if itemAt is not None and isinstance(itemAt, ConnectorItem) and not self.disabled:
            # check, whether the connection is already connected to connector of the given type (top/bottom)
            if connection.checkSameConnectorTypeRestriction(itemAt):
                # get the connectors
                if itemAt.isTopConnector():
                    topConnector = itemAt
                    bottomConnector = connection.getConnectorIfNotFullyConnected()
                else:
                    topConnector = connection.getConnectorIfNotFullyConnected()
                    bottomConnector = itemAt

                # get data needed to notify the underling data structure
                topLayerID = topConnector.getNodeItem().getLayerID()
                bottomLayerID = bottomConnector.getNodeItem().getLayerID()
                topBlobIndex = topConnector.getIndex()
                bottomBlobIndex = bottomConnector.getIndex()

                # notify to change the data
                self.__nodeEditor.tryToConnect(topLayerID, topBlobIndex, bottomLayerID, bottomBlobIndex)

        """ if itemAt is a Node Item (if you pull onto a layer) """
        if itemAt is not None and isinstance(itemAt, NodeItem) and not self.disabled:
            # test if connector starts at a top Blob
            if connection.getConnectorIfNotFullyConnected().isTopConnector():

                # bottomNode is itemAt
                bottomNode = itemAt

                # get layer IDs
                topLayerID = connection.getConnectorIfNotFullyConnected().getNodeItem().getLayerID()
                bottomLayerID = bottomNode.getLayerID()
                topBlobIndex = connection.getConnectorIfNotFullyConnected().getIndex()

                # get the Index of the new Blob, should it be necessary to create one
                # (determined in the following for loop)
                bottomBlobIndex = bottomNode.getBottomConnectorCount()

                # current connection top name and phase
                topBlobName = connection.getConnectorIfNotFullyConnected().getBlobName()
                topBlobPhase = connection.getConnectorIfNotFullyConnected().getPhase()

                # check if there is a connected Node that has a different phase than the currently
                # connecting Node, but has a connection with the same top Blob Name
                topBlobFound = False
                for bottomBlob in bottomNode.getBottomConnectors():
                    if len(bottomBlob.getConnectedNodes()) > 0:
                       for topNode in bottomBlob.getConnectedNodes():
                           for topBlob in topNode.getTopConnectors():
                               if topBlob.getBlobName() == topBlobName and topBlob.getPhase() != topBlobPhase:
                                   bottomBlobIndex = bottomBlob.getIndex()
                                   topBlobFound = True
                                   break

                # otherwise (if no corresponding top Blob was found)
                # get Index of first empty bottom blob (if available)
                counter = -1
                emptyBlobAvailable = False
                if not topBlobFound:
                    for blob in bottomNode.getBottomConnectors():
                        counter += 1
                        if len(blob.getConnectedNodes()) == 0:
                            bottomBlobIndex = counter
                            emptyBlobAvailable = True
                            break

                # add empty bottom blob property
                if not emptyBlobAvailable and not topBlobFound:
                    self.__nodeEditor.tryToAddBottomBlob(bottomLayerID, "")

                # connect nodes
                connected = self.__nodeEditor.tryToConnect(topLayerID, topBlobIndex, bottomLayerID, bottomBlobIndex)

                # if the connection did not work but a new blob was created, remove it
                if not connected and not emptyBlobAvailable and not topBlobFound:
                    bottomNode.removeBottomConnector(bottomBlobIndex)


    def dragEnterEvent(self, event):
        """ Verifies that the data dragged into the widget is correct """

        mimeData = event.mimeData().text()
        if not self.__nodeEditor.getNetworkManager().isValidLayerType(mimeData):
            event.ignore()

    def dragMoveEvent(self, event):
        """ Empty reimplementation """

    def dropEvent(self, event):
        mimeData = event.mimeData().text()
        if self.__nodeEditor.getNetworkManager().isValidLayerType(mimeData):
            # When calculating the replace option, use QCursor because pos() of event is (0, 0) for some reason
            item = self.itemAt(self.__view.mapToScene(self.__view.mapFromGlobal(QCursor.pos())), QTransform())

            if isinstance(item, NodeItem):
                if QMessageBox.warning(self.__view, "Replace Layer",
                                       "Would you like to replace " + item.getName() + " with the new layer?",
                                       QMessageBox.Yes, QMessageBox.No) == QMessageBox.No:
                    item = None

            # Create the new node item
            self.__nodeEditor.tryToCreateLayer(mimeData, event.scenePos().x(), event.scenePos().y())

            # Check if the user wants to replace an old layer with this one
            if item != None:
                # Get the new layer id
                newItem = self.selectedItems()[0]

                # Add top connectors
                for i in range(0, item.getTopConnectorCount()):
                    self.__nodeEditor.tryToAddTopBlob(newItem.getLayerID(), item.getTopConnectors()[i].getBlobName())

                    for j in range(item.getTopConnectors()[i].getConnectionCount()-1, -1, -1):
                        connection = item.getTopConnectors()[i].getConnections()[j]

                        connection.setTopConnector(newItem.getTopConnectors()[i])
                        item.getTopConnectors()[i].removeConnection(connection)
                        newItem.getTopConnectors()[i].addConnection(connection)

                # Add bottom connectors
                for i in range(0, item.getBottomConnectorCount()):
                    self.__nodeEditor.tryToAddBottomBlob(newItem.getLayerID(), item.getBottomConnectors()[i].getBlobName())

                    for j in range(item.getBottomConnectors()[i].getConnectionCount()-1, -1, -1):
                        connection = item.getBottomConnectors()[i].getConnections()[j]

                        connection.setBottomConnector(newItem.getBottomConnectors()[i])
                        item.getBottomConnectors()[i].removeConnection(connection)
                        newItem.getBottomConnectors()[i].addConnection(connection)

                # Translate new item to the exact place of the old item
                newItem.setPos(item.x(), item.y())

                self.__nodeEditor.getNetworkManager().deleteLayer(item.getLayerID())

            # Set keyboard focus to the node prototxt_editor view
            self.__nodeEditor.setKeyboardFocus()
            event.accept()

    def drawBackground(self, painter, rect):
        """ Draws a large and a small grid on the scene """
        
        super(NodeEditorScene, self).drawBackground(painter, rect)

        # SMALL grid
        # do not draw small grid if zoomed out
        smallGridSize = Constants.sceneGridSize
        if self.getView().getScale() < smallGridSize / 10:
            self.drawGrid(rect, smallGridSize, QColor(230, 230, 230), painter)

        # LARGE grid
        # do not draw large grid if zoomed out
        largeGridSize = Constants.sceneGridSize * Constants.sceneLargeGridCells
        if self.getView().getScale() < largeGridSize / 10:
            self.drawGrid(rect, largeGridSize, QColor(200, 200, 200), painter)

    def drawGrid(self, rect, gridSize, color, painter):
        """ Draw visible grid lines in the current view rect
            Concept of grid drawing by Bitto:
            http://www.qtcentre.org/threads/5609-Drawing-grids-efficiently-in-QGraphicsScene"""

        lines = list()
        startX = rect.left() - (rect.left() % gridSize)
        startY = rect.top() - (rect.top() % gridSize)

        # add vertical lines
        x = startX
        while x < rect.right():
            lines.append(QLineF(x, rect.top(), x, rect.bottom()))
            x += gridSize

        # add horizontal lines
        y = startY
        while y < rect.bottom():
            lines.append(QLineF(rect.left(), y, rect.right(), y))
            y += gridSize

        # draw the lines
        painter.setPen(QPen(color))
        painter.drawLines(lines)

    def disableEditing(self, disable):
        """ Disable automatic generation of new blobs. """
        self.disabled = disable
