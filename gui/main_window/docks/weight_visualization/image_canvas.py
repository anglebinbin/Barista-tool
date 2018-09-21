from PyQt5.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem
)
from PyQt5 import QtCore
from PyQt5.QtGui import QPixmap, QImage, QColor

class ImageCanvas(QGraphicsView):
    """ This class manages the view of the weights. """
    def __init__(self):
        QGraphicsView.__init__(self)
        self.__scene = QGraphicsScene(self)
        self.__item = QGraphicsPixmapItem()
        self.__scene.addItem(self.__item)
        self.setScene(self.__scene)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

        # Change resize policy when hidden, to ensure it takes the same space
        pol = self.sizePolicy()
        pol.setRetainSizeWhenHidden(True)
        self.setSizePolicy(pol)

    def center(self):
        """ Centers the pictures and adjust the zoom-level to maximize the picture."""
        pictureRect = QtCore.QRectF(self.__item.pixmap().rect())
        self.fitInView(pictureRect, QtCore.Qt.KeepAspectRatio)

    def showImage(self, rawImage):
        """ Takes a raw Image and show it in the view. """
        self.__image = self._getPixImage(rawImage)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.__item.setPixmap(self.__image)
        self.__scene = QGraphicsScene(self)
        self.__scene.addItem(self.__item)
        self.setScene(self.__scene)
        #self.center()

    def _getPixImage(self, image):
        """ generate a QPixImage from the raw input Image. """
        height = image.shape[0]
        width = image.shape[1]
        qImage = QImage(width, height, QImage.Format_RGB32)
        for x in range(0, width):
            for y in range(0, height):
                val = int(255*image[y][x])
                qImage.setPixel(x, y, QColor.fromRgb(val, val, val, 1).rgb())
        return QPixmap.fromImage(qImage)

    def wheelEvent(self, event):
        """ Overrides wheel event to allow zooming. """
        mouseDelta = event.angleDelta().y()/120.0
        scale = 1.0 + 0.1*mouseDelta
        self.scale(scale, scale)

    # idea from http://stackoverflow.com/questions/6915106/saving-a-numpy-array-as-an-image-instructions
    def saveImage(self, rawImage, filename):
        image = self._getPixImage(rawImage)
        if not image.save(filename):
            raise IOError("Could not save file in the chosen folder.")
