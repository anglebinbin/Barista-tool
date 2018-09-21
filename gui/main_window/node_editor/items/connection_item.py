from PyQt5.QtWidgets import QGraphicsPathItem, QMenu
from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QPainterPath, QPainterPathStroker
from gui.main_window.node_editor.items.renderer.connection_item_renderer import ConnectionItemRenderer
from gui.main_window.node_editor.node_editor_constants import Constants


class ConnectionItem(QGraphicsPathItem):
    """ A ConnectionItem represents a top-bottom connection in the graphics scene """

    def __init__(self, nodeEditor, parent=None):
        super(ConnectionItem, self).__init__(parent)

        # make selectable
        self.setFlag(QGraphicsPathItem.ItemIsSelectable, True)

        # draw behind node items
        self.setZValue(0.5)

        self.__isInPlace = False
        self.__nodeEditor = nodeEditor

        self.__hidden = False

        self.__topConnector = None
        self.__bottomConnector = None

        self.__start = QPointF(0, 0)
        self.__end = QPointF(0, 0)

        # create a renderer to separate drawing from logic
        self.__renderer = ConnectionItemRenderer(self)

        self.__updatePath()

    def paint(self, painter, option, widget=None):
        self.__renderer.paint(painter)

    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(Constants.connectionItemSize *3)
        return stroker.createStroke(self.path())

    def setStart(self, start):
        """ Sets the start position of the connection and recalculates the path """

        self.__start = start
        self.__updatePath()

    def setEnd(self, end):
        """ Sets the end position of the connection and recalculates the path """

        self.__end = end
        self.__updatePath()

    def getTopConnector(self):
        """ Returns the connections top connector """
        return self.__topConnector

    def getBottomConnector(self):
        """ Returns the connections bottom connector """
        return self.__bottomConnector

    def setConnector(self, connector):
        """ Sets the top/bottom connector of the connection. Whether the top or bottom connector gets set,
        is decided by information provided by the connector """

        if connector.isTopConnector():
            self.setTopConnector(connector)
        else:
            self.setBottomConnector(connector)

    def setTopConnector(self, connector):
        """ Sets the top connector and updates the connections path """

        self.__topConnector = connector
        self.__start = connector.scenePos()

        self.updateData()
        self.__updatePath()

    def setBottomConnector(self, connector):
        """ Sets the bottom connector and updates the connections path """

        self.__bottomConnector = connector
        self.__end = connector.scenePos()

        self.updateData()
        self.__updatePath()

    def setHidden(self, hidden):
        """ Sets the connection to be hidden/shown and updates the rendering """

        self.__hidden = hidden
        self.update()

    def updateMousePosition(self, pos):
        """ Updates the start/end of the connection if the connection is getting dragged (created)  """

        if self.__topConnector is None:
            self.__start = pos
        elif self.__bottomConnector is None:
            self.__end = pos

        self.__updatePath()

    def updateData(self):
        """ Updates the connections internal in-place and phase variables to update the rendering """

        # set in-place
        if self.__bottomConnector is not None:
            self.__isInPlace = self.__bottomConnector.isInPlace()
        else:
            self.__isInPlace = False

        # update
        self.update()

    def __updatePath(self):
        """ Updates the connections path, using the start and end points """

        path = QPainterPath(self.__start)

        # the end point is further left than the start point, so draw two half circles and a straight line
        if self.__start.x() > self.__end.x():
            yDiff = abs(self.__end.y() - self.__start.y())
            middleY = (self.__start.y() + self.__end.y()) / 2

            # calculate the control points needed for the first half circle
            curve1End = QPointF(self.__start.x(), middleY)
            curve1CP1 = QPointF(self.__start.x() + yDiff / 2, self.__start.y())
            curve1CP2 = QPointF(self.__start.x() + yDiff / 2, middleY)

            # calculate the control points needed for the second half circle
            curve2Start = QPointF(self.__end.x(), middleY)
            curve2CP1 = QPointF(self.__end.x() - yDiff / 2, middleY)
            curve2CP2 = QPointF(self.__end.x() - yDiff / 2, self.__end.y())

            # draw the first half circle
            path.cubicTo(curve1CP1.x(), curve1CP1.y(), curve1CP2.x(), curve1CP2.y(), curve1End.x(), curve1End.y())

            # draw the straight line
            path.lineTo(curve2Start.x(), curve2Start.y())

            # draw the second half circle
            path.cubicTo(curve2CP1.x(), curve2CP1.y(), curve2CP2.x(), curve2CP2.y(), self.__end.x(), self.__end.y())

        # the start point is further left than the end point, so draw a Bezier curve between both
        else:
            path.cubicTo((self.__start.x() + self.__end.x()) / 2, self.__start.y(),
                         (self.__start.x() + self.__end.x()) / 2, self.__end.y(),
                         self.__end.x(), self.__end.y())

        self.setPath(path)

        self.update()

    def checkSameConnectorTypeRestriction(self, connector):
        """ Check, whether the connector type (top/bottom) is already set in the connection """

        if self.__topConnector is not None and connector.isTopConnector():
            return False
        elif self.__bottomConnector is not None and not connector.isTopConnector():
            return False
        return True

    def getConnectorIfNotFullyConnected(self):
        """ Returns the only connected connector, if only one connector is connected """

        if self.__topConnector is not None and self.__bottomConnector is None:
            return self.__topConnector
        elif self.__topConnector is None and self.__bottomConnector is not None:
            return self.__bottomConnector
        return None

    def getHidden(self):
        """ Returns whether the connection is hidden """
        return self.__hidden

    def getNodeEditor(self):
        """ Returns the node prototxt_editor object (for the renderer) """
        return self.__nodeEditor

    def getPhase(self):
        """ Returns the internal phase """
        if self.getTopConnector() is not None:
            return self.getTopConnector().getPhase()
        else:
            return self.getBottomConnector().getPhase()

    def getIsInPlace(self):
        """ Returns the internal in-place value """
        return self.__isInPlace

    def contextMenuEvent(self, event):
        """ Creates the context menu """
        contextMenu = QMenu()

        menuText = "Hide"
        if self.__hidden:
            menuText = "Show"

        # add action to show/hide the connection
        toggleHideAction = contextMenu.addAction(menuText)
        if not self.__nodeEditor.disable:
            removeAction = contextMenu.addAction("Remove")


        # show context menu
        action = contextMenu.exec_(event.screenPos())
        if action is not None:
            if action == toggleHideAction:
                self.__hidden = not self.__hidden
                if self.__hidden:
                    self.__nodeEditor.tryToAddHiddenConnection(self)
                else:
                    self.__nodeEditor.tryToRemoveHiddenConnection(self)
                self.update()

            elif not self.__nodeEditor.disable and action == removeAction:
                # deselect all Layers
                self.__nodeEditor.tryToClearSelection()
                # deselect all other connections
                for item in self.__nodeEditor.getScene().selectedItems():
                    item.setSelected(False)
                # select this connection
                self.setSelected(True)
                # remove this connection
                self.__nodeEditor.tryToDeleteSelection()
