# To change this license header, choose License Headers in Project Properties.
# To change this template file, choose Tools | Templates
# and open the template in the prototxt_editor.

from PyQt5 import QtGui, QtCore, QtWidgets
import functools

class DockElement(QtWidgets.QDockWidget):
    def __init__(self, mainWindow, title):      
        QtWidgets.QDockWidget.__init__(self, title)
        palette = self.palette()
        palette.setColor(QtGui.QPalette.Window, QtCore.Qt.white)
        self.setPalette(palette)
        self.setAutoFillBackground(1)
        self.adjustSize()
        self.setObjectName(title)
        
        # Connect the visibility changed event to the view manager
        self.visibilityChanged.connect(functools.partial(mainWindow.viewManager.onVisibilityChange))