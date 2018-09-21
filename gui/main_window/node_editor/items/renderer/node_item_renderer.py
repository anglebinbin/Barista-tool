from PyQt5.QtCore import QRectF, Qt, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient

from gui.main_window.node_editor.node_editor_constants import Constants
from gui.main_window.node_editor.layer_color_definitions import LayerColorDefinitions


class TextRect:
    """ Used to store values required for text positioning and rendering """
    def __init__(self, text, rect, font = None):
        self.text = text
        self.rect = rect
        self.font = font


class NodeItemRenderer:
    """ Class is used to separate the drawing from the logic.
        This class renders a given node to a graphics scene """

    __blobConnectorSizeWithPadding = Constants.nodeItemConnectorPaddding * 2 + Constants.connectorItemOuterSize

    def __init__(self, nodeItem):
        self.__nodeItem = nodeItem

        # create lists to store TextRects for the node item
        self.__headRects = list()
        self.__blobTopNameRects = list()
        self.__blobBottomNameRects = list()

        # create Qt rects for the head and body area
        self.__rectHead = QRectF(0, 0, 1, 1)
        self.__rectBlobArea = QRectF(0, 0, 1, 1)

        # create Qt rect for enclosing rects used as bounding rects
        self.__rectAll = QRectF(0, 0, 1, 1)
        self.__rectAllSelected = QRectF(0, 0, 1, 1)

        self.__hasCurrentPhase = True

        self.update()

    def boundingRect(self):
        # selected layers have a outer 'glow', so selected layers are bigger than not selected layers
        if self.__nodeItem.isSelected():
            return self.__rectAllSelected
        else:
            return self.__rectAll

    def update(self):
        """ Recalculates positions of name, type, blobs, etc. """

        # clear lists
        del self.__headRects[:]
        del self.__blobTopNameRects[:]
        del self.__blobBottomNameRects[:]

        # get size of the name
        nameWidth = Constants.nodeItemFontNameMetrics.width(self.__nodeItem.getName()) + Constants.nodeItemHeadPadding
        nameHeight = Constants.nodeItemFontTypeMetrics.height()
        self.__headRects.append(TextRect(self.__nodeItem.getName(), QRectF(0, 0, nameWidth, nameHeight),
                                         Constants.nodeItemFontName))

        # get size of the type
        typeWidth = Constants.nodeItemFontTypeMetrics.width(self.__nodeItem.getTypeString()) + Constants.nodeItemHeadPadding
        typeHeight = Constants.nodeItemFontTypeMetrics.height()
        self.__headRects.append(TextRect(self.__nodeItem.getTypeString(), QRectF(0, 0, typeWidth, typeHeight), Constants.nodeItemFontType))

        # get size of the phase (if the node has the paramter include.phase
        if len(self.__nodeItem.getPhase()) > 0:
            phaseString = "Phase: " + self.__nodeItem.getPhase()
            phaseWidth = Constants.nodeItemFontTypeMetrics.width(phaseString) + Constants.nodeItemHeadPadding
            phaseHeight = Constants.nodeItemFontTypeMetrics.height()
            self.__headRects.append(TextRect(phaseString, QRectF(0, 0, phaseWidth, phaseHeight),
                                             Constants.nodeItemFontType))

        # calculate rect width and height for names of blobs
        topBlobsInfo = self.__buildBlobNameRectList(self.__nodeItem.getTopConnectors())
        bottomBlobsInfo = self.__buildBlobNameRectList(self.__nodeItem.getBottomConnectors())
        self.__blobTopNameRects = topBlobsInfo[0]
        self.__blobBottomNameRects = bottomBlobsInfo[0]

        blobAreaWidth = 2 * self.__blobConnectorSizeWithPadding + Constants.nodeItemConnectorPaddding + \
                        bottomBlobsInfo[1] + topBlobsInfo[1]
        blobAreaHeight = max(topBlobsInfo[2], bottomBlobsInfo[2], Constants.nodeItemMinBlobAreaHeight)

        # calculate the total width of the node
        rectWidth = blobAreaWidth
        for textRect in self.__headRects:
            rectWidth = max(rectWidth, textRect.rect.width())

        # change the width of the head rects to be the full width of the node
        self.__updateHeadRects(rectWidth, self.__headRects)

        # calculate the total node height
        rectHeight = self.__rectHead.bottom() +  blobAreaHeight

        # create Qt rects for the body and enclosing width the top left at (0, 0)
        self.__rectBlobArea = QRectF(0, self.__rectHead.bottom(), rectWidth, blobAreaHeight)
        self.__rectAll = QRectF(0, 0, rectWidth, rectHeight)

        # calculate a larger box to support selection (outer glow)
        selSize = Constants.nodeItemSelectionSize
        self.__rectAllSelected = QRectF(self.__rectAll.left() - selSize, self.__rectAll.top() - selSize,
                                     self.__rectAll.width() + 2 * selSize, self.__rectAll.height() + 2 * selSize)

        # after calculating the total width, adjust the name rects to align at the left/right
        self.__adjustBlobNameRectPositions(self.__blobTopNameRects, self.__rectAll.width(), self.__rectHead.bottom(), False)
        self.__adjustBlobNameRectPositions(self.__blobBottomNameRects, self.__rectAll.width(), self.__rectHead.bottom(), True)

    def __updateHeadRects(self, finalWidth, headRects):
        """ Resizes the size of the head text rect after the total needed width was calculated """

        totalHeadHeight = 0
        for x in range(0, len(headRects)):
            # special case for the first head text -> start at (0, 0) and has space at the top
            if x == 0:
                headRects[x].rect = QRectF(0, 0, finalWidth, headRects[x].rect.height() + Constants.nodeItemTextMargin)
            # special case for the last head text -> has space at the bottom
            elif x == len(headRects) - 1:
                headRects[x].rect = QRectF(0, headRects[x-1].rect.bottom(), finalWidth,
                                           headRects[x].rect.height() + Constants.nodeItemTextMargin)
            else:
                headRects[x].rect = QRectF(0, headRects[x-1].rect.bottom(), finalWidth, headRects[x].rect.height())

            # add the rects height to the total head rect height
            totalHeadHeight += headRects[x].rect.height()

        # create Qt rect for the head part
        self.__rectHead = QRectF(0, 0, finalWidth, totalHeadHeight)

    def __buildBlobNameRectList(self, connectors):
        """ Creates rects for all top/bottom connectors (bounding rect for the text only) """

        # check if the connector or the blob name text is higher
        blobNameHeightRect = max(Constants.nodeItemFontBlobMetrics.height(), self.__blobConnectorSizeWithPadding)

        blobNameRectList = list()

        maxWidth = 0
        height = 0

        # for each connector calculate the width of the name and create a Qt rect.
        # calculate the max width of all blob names and the total height
        for item in connectors:
            blobName = item.getBlobName()
            blobNameWidth = Constants.nodeItemFontBlobMetrics.width(blobName) + Constants.nodeItemTextMargin
            blobRect = QRectF(0, 0, blobNameWidth, blobNameHeightRect)
            blobNameRectList.append(TextRect(blobName, blobRect))
            maxWidth = max(maxWidth, blobNameWidth)
            height += blobNameHeightRect

        return blobNameRectList, maxWidth, height

    def __adjustBlobNameRectPositions(self, blobRectNames, totalWidth, aboveHeight, atLeftBorder):
        """ Recalculates the blob name rects after the total width of the node was calculated """
        i = 0

        for item in blobRectNames:
            # position at the left side of the node
            x = self.__blobConnectorSizeWithPadding

            # or position at the right side of the node
            if not atLeftBorder:
                x = totalWidth - self.__blobConnectorSizeWithPadding - item.rect.width()

            # calculate starting position (head size + position in body)
            item.rect = QRectF(x, aboveHeight + i * item.rect.height(), item.rect.width(), item.rect.height())

            i += 1

    def updateConnectorPositions(self, connectors, atLeftBorder):
        """ Repositions the connector items after the new size of the node was calculated """

        i = 0
        for item in connectors:
            # position the connector item at the left border of the node,left of the blob name rect
            x = Constants.nodeItemConnectorPaddding + Constants.connectorItemOuterSize / 2

            # or at the right border of the node, right of the blob name rect
            if not atLeftBorder:
                x = self.__rectAll.width() - Constants.nodeItemConnectorPaddding - Constants.connectorItemOuterSize + \
                    Constants.connectorItemOuterSize / 2

            # set the y coordinate of the connector item to be at the center of the blob name rect
            y = self.__rectHead.bottom() + Constants.nodeItemConnectorPaddding + Constants.connectorItemOuterSize / 2 + \
                i * self.__blobConnectorSizeWithPadding

            item.setPos(QPointF(x, y))
            i += 1

    def paint(self, painter):
        # use antialiasing for both text and box
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        # get the opacity of the node item, layers with the include.phase parameter have a different opacity
        opacity = Constants.itemOpacityInPhase
        if not self.__nodeItem.getNodeEditor().isCurrentPhase(self.__nodeItem.getPhase()):
            opacity = Constants.itemOpacityNotInPhase

        # draw a outer 'glow' around the node item if the node is selected
        if self.__nodeItem.isSelected():
            selectedColor = Constants.selectedColor
            selectedColor.setAlpha(opacity)
            painter.setPen(QPen(selectedColor, Constants.nodeItemSelectionSize))
            painter.drawRect(self.__rectAllSelected)
            painter.fillRect(self.__rectAllSelected, QBrush(selectedColor))

        # get the type color for the header (name and type)
        typeColor = LayerColorDefinitions.getTypeColor(self.__nodeItem.getType())
        typeColor.setRgb(typeColor.red(), typeColor.green(), typeColor.blue(), opacity)

        # get background color
        backgroundColor = Constants.itemBackgroundColorLight
        backgroundColor.setAlpha(opacity)

        # set a linear gradient for the header (type color -> background color)
        gradient = QLinearGradient(0, self.__rectHead.top(), 0, self.__rectHead.bottom())
        gradient.setColorAt(0, typeColor)
        gradient.setColorAt(0.5, backgroundColor)

        # draw background and border for the header
        painter.fillRect(self.__rectHead, QBrush(gradient))

        # draw background for the blob area
        painter.fillRect(self.__rectBlobArea, QBrush(backgroundColor))
        borderColor = Constants.itemBorderColor
        if self.__nodeItem.getIsInPlace():
            borderColor = Constants.itemInPlaceColor
        borderColor.setAlpha(opacity)
        painter.setPen(QPen(borderColor, Constants.nodeItemBorderSize))

        # draw outer border around the node
        painter.drawRect(self.__rectAll)

        # draw a line to separate header and connectors
        borSize = Constants.nodeItemBorderSize
        painter.setPen(QPen(borderColor, borSize))
        painter.drawLine(self.__rectHead.left() + borSize / 2, self.__rectHead.bottom() - borSize / 2,
                         self.__rectHead.right() - borSize / 2, self.__rectHead.bottom() - borSize / 2)

        painter.setPen(QPen(QColor(0, 0, 0, opacity)))

        # draw text of header
        if len(self.__headRects) > 1:
            # align the first head text at the bottom to provide some space at the top
            painter.setFont(self.__headRects[0].font)
            painter.drawText(self.__headRects[0].rect, Qt.AlignHCenter | Qt.AlignBottom, self.__headRects[0].text)

            # align other head texts at the center
            for i in range(1, len(self.__headRects) - 1):
                painter.setFont(self.__headRects[i].font)
                painter.drawText(self.__headRects[i].rect, Qt.AlignCenter, self.__headRects[i].text)

            # align the last head text at the top to provide some space at the bottom
            painter.setFont(self.__headRects[-1].font)
            painter.drawText(self.__headRects[-1].rect, Qt.AlignHCenter | Qt.AlignTop, self.__headRects[-1].text)

        # there is only one head text, so align it at the center
        elif len(self.__headRects) == 1:
            painter.setFont(self.__headRects[0].font)
            painter.drawText(self.__headRects[0].rect, Qt.AlignHCenter | Qt.AlignCenter, self.__headRects[0].text)

        # draw blob names
        painter.setFont(Constants.nodeItemFontBlob)
        for item in self.__blobBottomNameRects:
            painter.drawText(item.rect, Qt.AlignVCenter | Qt.AlignLeft, item.text)
        for item in self.__blobTopNameRects:
            painter.drawText(item.rect, Qt.AlignVCenter | Qt.AlignRight, item.text)
