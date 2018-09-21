from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QPen, QBrush

from gui.main_window.node_editor.node_editor_constants import Constants


class ConnectorItemRenderer:
    """ Class is used to separate the drawing from the logic.
        This class renders a given connector to a graphics scene """

    def __init__(self, connector):
        self.__connector = connector

        # get the outer and inner size of the enclosing rect (inner size is the size of the hole)
        outerSize = Constants.connectorItemOuterSize
        innerSize = Constants.connectorItemInnerSize

        # calculate the Qt rects centered at the center of the rect
        self.__outerRect = QRectF(-(outerSize / 2), -(outerSize / 2),outerSize, outerSize)
        self.__innerRect = QRectF(-(innerSize / 2), -(innerSize / 2), innerSize, innerSize)

    def boundingRect(self):
        return self.__outerRect

    def paint(self, painter):
        # connectors of a layer with the include.phase parameter
        # have a different opacity than normal connectors
        opacity = Constants.itemOpacityInPhase
        if not self.__connector.getNodeEditor().isCurrentPhase(self.__connector.getPhase()):
            opacity = Constants.itemOpacityNotInPhase

        # get colors
        colorInner = Constants.itemBackgroundColorLight
        colorOuter = Constants.itemBackgroundColorDark
        borderColor = Constants.itemBorderColor

        # in place layer connectors have a different color than normal connectors
        if self.__connector.isInPlace():
            colorOuter = Constants.itemInPlaceColor

        # set the colors opacity
        colorInner.setAlpha(opacity)
        colorOuter.setAlpha(opacity)
        borderColor.setAlpha(opacity)

        # draw enclosing rect and rect border
        painter.setPen(QPen(borderColor, 1))
        painter.fillRect(self.__outerRect, QBrush(colorOuter))
        painter.drawRect(self.__outerRect)

        # if the connector is connected, fill the inner rect
        if self.__connector.isConnected():
            painter.fillRect(self.__innerRect, QBrush(colorOuter))
        else:
            painter.fillRect(self.__innerRect, QBrush(colorInner))

        # draw the border of the inner rect
        painter.drawRect(self.__innerRect)