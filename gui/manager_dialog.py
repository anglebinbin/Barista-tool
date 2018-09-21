from PyQt5 import QtCore, QtWidgets

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QListWidget


class ManagerDialog(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

        # remember the parent for future use
        self.parent = parent
        self.dict = None

        # main_window settings
        self.setWindowRole("QDialog")
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowFlags(self.windowFlags() & QtCore.Qt.CustomizeWindowHint)
        self.setWindowFlags(self.windowFlags() | Qt.Window | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowMinimizeButtonHint)
        self.resize(800, 600)

        # layouts
        self._layout = QtWidgets.QVBoxLayout(self)
        self._buttonlayout = QtWidgets.QHBoxLayout()
        self._layout.addLayout(self._buttonlayout)

        # item list widget
        self._itemscroll = QListWidget()

    def moveUp(self, subDictName, id):
        """ move the item one position up """
        if id:
            i = self.dict[subDictName].index(id)
            row = self._getIndexinList(id)
            if i > 0 and row > 0:
                j = 1
                item = self._itemscroll.item(row - j)
                # skip hidden items
                while i-j > 0 and item.isHidden():
                    j += 1
                    item = self._itemscroll.item(row - j)

                if not item or item.isHidden():
                    return

                # update dict
                tmp = self.dict[subDictName][i]
                for k in range(0, j):
                    self.dict[subDictName][i-k] = self.dict[subDictName][i-k-1]
                self.dict[subDictName][i-j] = tmp

                widget = self.createWidget(id)

                #move item widgets
                scroll = self._itemscroll.cursor()
                item = self._itemscroll.takeItem(row)
                item.setSizeHint(widget.sizeHint())
                self._itemscroll.insertItem(row - j, item)
                self._itemscroll.setItemWidget(item, widget)
                self._itemscroll.setCursor(scroll)

                self.updateAfterMovement()

    def moveDown(self, subDictName, id):
        """ move the item one position down """
        if id:
            i = self.dict[subDictName].index(id)
            row = self._getIndexinList(id)
            dictLength = len(self.dict[subDictName])
            if i < dictLength - 1 and row < dictLength - 1:
                j = 1
                item = self._itemscroll.item(row + j)
                # skip hidden items
                while i+j < dictLength and item.isHidden():
                    j += 1
                    item = self._itemscroll.item(row + j)

                if not item or item.isHidden():
                    return

                # update dict
                tmp = self.dict[subDictName][i]
                for k in range(0, j):
                    self.dict[subDictName][i + k] = self.dict[subDictName][i + k + 1]
                self.dict[subDictName][i + j] = tmp

                widget = self.createWidget(id)

                #move item widgets
                scroll = self._itemscroll.cursor()
                item = self._itemscroll.takeItem(row)
                item.setSizeHint(widget.sizeHint())
                self._itemscroll.insertItem(row + j, item)
                self._itemscroll.setItemWidget(item, widget)
                self._itemscroll.setCursor(scroll)

                self.updateAfterMovement()

    def createWidget(self, id):
        """ abstract method returning a widget for one entry in the list """
        raise NotImplementedError("Please Implement this method")

    def updateAfterMovement(self):
        """ abstract method """
        raise NotImplementedError("Please Implement this method")
