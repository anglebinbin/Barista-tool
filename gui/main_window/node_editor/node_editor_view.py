from PyQt5.QtWidgets import QGraphicsView
from PyQt5.QtCore import Qt, QPoint, pyqtSignal

from gui.main_window.node_editor.node_editor_constants import Constants
from gui.main_window.node_editor.node_editor_scene import NodeEditorScene


class NodeEditorView(QGraphicsView):
    # These signals are emitted from within the NodeEditorEventHandler when the
    # actions are clicked from the context menu.
    arrangeVerticallyClicked = pyqtSignal()
    arrangeHorizontallyClicked = pyqtSignal()

    def __init__(self, nodeEditor, parent=None):
        super(NodeEditorView, self).__init__(parent)

        Constants.setPaintDevice(self)

        self.__scene = NodeEditorScene(self, Constants.sceneInitialWidth, Constants.sceneInitialHeight, nodeEditor)
        self.setScene(self.__scene)

        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

        self.eventHandler = None

        self.centerOn(0, 0)

    def setEventHandler(self, eventHandler):
        self.eventHandler = eventHandler

    def scaleSymmetric(self, scaleFactor):
        """
        set scale and zooms the view, regarding the max and min zoom
        """
        scale = self.getScale()*scaleFactor
        # Prevent over scale
        if scale > Constants.viewMinScale:
            factor = (1/self.getScale())*Constants.viewMinScale
            self.scale(factor, factor)
            return
        elif scale < Constants.viewMaxScale:
            factor = (1/self.getScale())*Constants.viewMaxScale
            self.scale(factor, factor)
            return

        # scale
        self.scale(scaleFactor, scaleFactor)

    def getScale(self):
        return self.transform().m11()

    def wheelEvent(self, event):
        self.eventHandler.wheelEvent(event)

    def mouseDoubleClickEvent(self, QMouseEvent):
        return

    def mousePressEvent(self, QMouseEvent):
        self.eventHandler.mousePressEvent(QMouseEvent)

    def mouseMoveEvent(self, QMouseEvent):
        self.eventHandler.mouseMoveEvent(QMouseEvent)

    def mouseReleaseEvent(self, QMouseEvent):
        self.eventHandler.mouseReleaseEvent(QMouseEvent)

    def keyPressEvent(self, QKeyEvent):
        self.eventHandler.keyPressEvent(QKeyEvent)

    def keyReleaseEvent(self, QKeyEvent):
        self.eventHandler.keyReleaseEvent(QKeyEvent)
