from PyQt5.QtGui import QPainter, QPen

from gui.main_window.node_editor.node_editor_constants import Constants


class ConnectionItemRenderer:
    """ Class is used to separate the drawing from the logic.
        This class renders a given connection to a graphics scene """

    def __init__(self, connection):
        self.__connection = connection

    def paint(self, painter):
        # use antialiasing
        painter.setRenderHint(QPainter.Antialiasing)

        # connections, connected to layers with the include.phase parameter,
        # have a different opacity than normal connections
        opacity = Constants.itemOpacityInPhase
        if not self.__connection.getNodeEditor().isCurrentPhase(self.__connection.getPhase()):
            opacity = Constants.itemOpacityNotInPhase

        # connections between a layer and a in-place working layer have a different color than normal connections
        connectionColor = Constants.connectionItemColor
        if self.__connection.getIsInPlace():
            connectionColor = Constants.itemInPlaceColor

        # set local color object alpha
        connectionColor.setAlpha(opacity)

        # draw highlight if the connection is selected
        if self.__connection.isSelected():
            selectedColor = Constants.selectedColor
            selectedColor.setAlpha(opacity)
            painter.setPen(QPen(selectedColor, Constants.connectionItemSelectionSize))
            painter.drawPath(self.__connection.path())

        pen = QPen(connectionColor, Constants.connectionItemSize)

        # if the connection is hidden, draw a dashed line at the start and end of the connection
        if self.__connection.getHidden():
            dashes = []

            # calculate the dashes at the start of the connection
            for i in range(0, Constants.connectionItemHiddenDashCount - 1):
                dashes.append(Constants.connectionItemHiddenDashSize / pen.width())
                dashes.append(Constants.connectionItemHiddenDashSpace / pen.width())
            dashes.append(Constants.connectionItemHiddenDashSize / pen.width())

            # calculate the size of the space between the dashed start and dashed end
            middleSpace = self.__connection.path().length()
            middleSpace -= 2 * Constants.connectionItemHiddenDashCount * Constants.connectionItemHiddenDashSize
            middleSpace -= 2 * (Constants.connectionItemHiddenDashCount - 1) * Constants.connectionItemHiddenDashSpace

            dashes.append(middleSpace / pen.width())

            # calculate the dashes at the end of the connection
            for i in range(0, Constants.connectionItemHiddenDashCount):
                dashes.append(Constants.connectionItemHiddenDashSize / pen.width())
                dashes.append(Constants.connectionItemHiddenDashSpace / pen.width())

            pen.setDashPattern(dashes)

        # draw the connection
        painter.setPen(pen)
        painter.drawPath(self.__connection.path())
