from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QSize


class Sidebar(QWidget):
    # constructor class for sidebar

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.editor = parent

    def sizeHint(self):
        return QSize(self.editor.sidebarWidth(), 0)

    def paintEvent(self, event):
        self.editor.sidebarPaintEvent(event)
