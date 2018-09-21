# To change this license header, choose License Headers in Project Properties.
# To change this template file, choose Tools | Templates
# and open the template in the prototxt_editor.

from PyQt5 import QtWidgets


class UiStatusBar(QtWidgets.QStatusBar):
    def __init__(self, parent=None):
        QtWidgets.QStatusBar.__init__(self, parent)
        self.modifyWdg = QtWidgets.QLabel()
        self.addPermanentWidget(self.modifyWdg)

    def showModifiedFlag(self, modified):
        if modified:
            self.modifyWdg.setText("Changes *")
        else:
            self.modifyWdg.setText("")
