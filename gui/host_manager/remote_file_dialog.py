from os.path import normpath
from PyQt5.QtCore import QAbstractTableModel, Qt, QModelIndex, pyqtSignal
from PyQt5.QtGui import QColor, QIcon
from PyQt5.QtWidgets import QDialog, QGridLayout, QTableView, QAbstractItemView, QComboBox, QPushButton, QLineEdit, \
    QStyle, qApp, QFileIconProvider, QLabel

from backend.networking.net_util import sendMsgToHost
from backend.networking.protocol import Protocol


class RemoteFileDialog(QDialog):
    def __init__(self, host, port, title="", fileFilter="All (*)", dirSelect=False, parent=None):
        QDialog.__init__(self, parent)
        self.fileFilter = fileFilter

        # Set the window Title
        if (title == ""):
            title = "Remote"
        windowtitle = title + " @ " + host + ":" + str(port)
        self.setWindowTitle(windowtitle)
        self.dirselect = dirSelect

        self.returnvalue = ""

        # Build the GUI
        self.layout = QGridLayout(self)
        self.tabview = self.KeyEventTableView()
        self.tabview.verticalHeader().hide()
        self.tabview.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabview.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabview.setFocus()
        self.layout.addWidget(self.tabview, 1, 0, 1, 4)

        # Import Model
        self.model = self.RemoteFileItemModel(host, port, self.dirselect)
        self.tabview.setModel(self.model)

        # Parent Button
        pix_parentdir = qApp.style().standardPixmap(QStyle.SP_FileDialogToParent)
        ico_parentdir = QIcon(pix_parentdir)
        self.pb_parentdir = QPushButton(ico_parentdir, "")
        self.pb_parentdir.setFixedSize(35, 35)
        self.pb_parentdir.setFocusPolicy(Qt.NoFocus)
        self.layout.addWidget(self.pb_parentdir, 0, 0)

        # Refresh Button
        pix_reload = qApp.style().standardPixmap(QStyle.SP_BrowserReload)
        ico_reload = QIcon(pix_reload)
        self.pb_refresh = QPushButton(ico_reload, "")
        self.pb_refresh.setFixedSize(35, 35)
        self.pb_refresh.setFocusPolicy(Qt.NoFocus)
        self.layout.addWidget(self.pb_refresh, 0, 1)

        # Current Dir
        self.le_path = QLineEdit()
        self.le_path.setEnabled(False)
        self.le_path.setFocusPolicy(Qt.NoFocus)
        self.layout.addWidget(self.le_path, 0, 2, 1, 2)

        # File Filter
        self.cb_filter = QComboBox()
        self.cb_filter.addItems([fi.split()[0] for fi in fileFilter.split(";;")])
        if len(fileFilter.split(";;")) == 1:
            self.cb_filter.setEnabled(False)
        self.layout.addWidget(self.cb_filter, 2, 3, 1, 1)

        # Status Label
        self.lbl_status = QLabel("")
        self.layout.addWidget(self.lbl_status, 2, 0, 1, 3)

        # Confirm Button
        self.pb_select = QPushButton("Select")
        self.pb_select.setFocusPolicy(Qt.NoFocus)
        self.layout.addWidget(self.pb_select, 3, 2, 1, 1)

        # Cancel Button
        self.pb_cancel = QPushButton("Cancel")
        self.pb_cancel.setFocusPolicy(Qt.NoFocus)
        self.layout.addWidget(self.pb_cancel, 3, 3, 1, 1)

        # Resize Tabel
        self.tabview.setColumnWidth(0, 400)
        self.tabview.hideColumn(1)
        self.tabview.setColumnWidth(2, 100)
        self.tabview.setColumnWidth(3, 200)
        self.tabview.setMinimumWidth(715)
        self.tabview.setMinimumHeight(400)
        self.adjustSize()

        # Connect Signals
        self.tabview.doubleClicked.connect(self._processInput)  # Confirm on doubleclick
        self.tabview.enterKey.connect(self._processInput)  # Confirm on enter/return
        self.tabview.backKey.connect(self._goToParentDir)  # ParentDir on Backspace
        self.tabview.selectionModel().currentChanged.connect(self._updateLineEdit)  # update current dir
        self.model.updateStatus.connect(self._setStatus)  # update Host connection status
        self.cb_filter.currentIndexChanged.connect(self._updateFilter)  # update FileFilter
        self.pb_parentdir.clicked.connect(self._goToParentDir)  # Button ParentDir
        self.pb_refresh.clicked.connect(self._updateCurrentDir)  # Button Refresh
        self.pb_cancel.clicked.connect(self._cancel)  # Button Cancel
        self.pb_select.clicked.connect(self._processInputButton)  # Button Confirm / Select

        # Fill Model with /home
        self.model.updateModel("/home/", self._createFilter())
        self._updateLineEdit()
        self._updateSelection()

    def _processInput(self):
        """update path or accept selection on double click, enter/return key or button """
        if (self._getCurrentItemType()):
            self.model.updateModel(self._getCurrentItemPath(), self._createFilter())
            self._updateLineEdit()
            self.tabview.scrollToTop()
            self._updateSelection()
        else:
            self._accept()

    def _processInputButton(self):
        if self.dirselect:
            self.returnvalue = self.le_path.text()
            self.close()
        else:
            self._processInput()

    def _createFilter(self):
        """create the filter from the Qt-syntax based on the current selection"""
        current_filter = self.fileFilter.split(";;")[self.cb_filter.currentIndex()]
        current_filter = current_filter.split(" ", 1)[1]
        current_filter = current_filter[1:len(current_filter) - 1]
        current_filter = current_filter.split()
        return current_filter

    def _updateFilter(self):
        """update the model with the current filter"""
        self.model.updateModel(self.model.currentPath, self._createFilter())
        self._updateSelection()

    def _updateLineEdit(self):
        """set the current dir in the line edit"""
        self.le_path.setText(normpath(self.model.currentPath))

    def _getCurrentItemType(self):
        """check if selection is dir"""
        row = self.tabview.currentIndex().row()
        index = self.model.createIndex(row, 1)
        return self.model.data(index, Qt.UserRole)

    def _getCurrentItemPath(self):
        """get the path of the current selection"""
        row = self.tabview.currentIndex().row()
        index = self.model.createIndex(row, 1)
        item = self.model.itemData(index)
        if len(item) == 0:
            return ""
        return item[Qt.DisplayRole]

    def _updateSelection(self):
        """change the selection to the first item"""
        self.tabview.scrollToTop()
        self.tabview.setCurrentIndex(self.model.createIndex(0, 0, ))

    def _goToParentDir(self):
        """go to the parent directory"""
        path = self.model.currentPath + "/.."
        self.model.updateModel(path, self._createFilter())
        self._updateLineEdit()
        self._updateSelection()

    def _updateCurrentDir(self):
        """refresh current directory"""
        self.model.updateModel(self.model.currentPath, self._createFilter())
        self._updateLineEdit()
        self._updateSelection()

    def _cancel(self):
        """close this dialog"""
        self.close()

    def _accept(self):
        """close this dialog and write the returnvalue"""
        self.returnvalue = self._getCurrentItemPath()
        self.close()

    def _setStatus(self, status):
        """set the host connection status in the status label"""
        if status:
            self.lbl_status.setText("")
        else:
            self.lbl_status.setText("Host unreachable!")

    class KeyEventTableView(QTableView):
        """A small helper class to catch the Keys on the TableView"""
        enterKey = pyqtSignal()
        backKey = pyqtSignal()

        def __init__(self):
            QTableView.__init__(self)

        def keyPressEvent(self, keyEvent):
            """Detect the key presses and fire signals"""
            if keyEvent.key() == Qt.Key_Enter or keyEvent.key() == Qt.Key_Return:
                self.enterKey.emit()
                return
            if keyEvent.key() == Qt.Key_Backspace:
                self.backKey.emit()
                return
            super(self.__class__, self).keyPressEvent(keyEvent)

    class RemoteFileItemModel(QAbstractTableModel):
        """Model to convert the file dictionary into a table"""
        updateStatus = pyqtSignal(bool)

        def __init__(self, host, port, dirselect):
            QAbstractTableModel.__init__(self)

            self.host = host
            self.port = port
            self.dirselect = dirselect
            self.currentPath = ""

            self.fileList = list()

        def rowCount(self, QModelIndex_parent=None, *args, **kwargs):
            """return the current row count"""
            return len(self.fileList)

        def columnCount(self, QModelIndex_parent=None, *args, **kwargs):
            """reuturn the current column count"""
            return 4

        def data(self, index, role=None):
            """return the data of the table for different roles"""
            row = index.row()
            if (row < 0 or row >= len(self.fileList)):
                return
            col = index.column()
            file = self.fileList[row]

            if role == Qt.UserRole:  # use the UserRole to check if item is dir
                if file["isDir"]:
                    return True
                return False

            if role == Qt.DisplayRole:  # the text that is shown
                if col == 0:
                    return file["name"]
                if col == 1:
                    return file["path"]
                if col == 2:
                    return file["fileSize"]
                if col == 3:
                    return file["lastChange"]

            if role == Qt.DecorationRole:  # the icon in the first column
                if col == 0:
                    fip = QFileIconProvider()
                    if file["isDir"]:
                        ico = fip.icon(QFileIconProvider.Folder)  # type: QIcon
                        return ico.pixmap(20, 20)
                    ico = fip.icon(QFileIconProvider.File)  # type: QIcon
                    return ico.pixmap(20, 20)

            if role == Qt.BackgroundColorRole:  # make stripes
                if row % 2 == 0:
                    return QColor(Qt.white)
                return QColor(Qt.lightGray).lighter(120)

        def headerData(self, p_int, orient, int_role=None):
            """Change the column names in the header"""
            if int_role == Qt.DisplayRole and orient == Qt.Horizontal:
                return ["Name", "Path", "FileSize", "Last Changed"][p_int]

        def updateModel(self, path="/home/", fileFilter=["*"]):
            """update the model by connecting to the host and asking for a new dir dictionary"""

            msg = {"key": Protocol.GETDIR, "path": path, "filter": fileFilter, "dirSelect": False}
            if self.dirselect:
                msg["dirSelect"] = True
            res = sendMsgToHost(self.host, self.port, msg)
            if res:
                self.currentPath = res["path"]
                oldlen = len(self.fileList)
                newlen = len(res["data"])
                diff = oldlen - newlen

                if diff > 0:
                    self.beginRemoveRows(QModelIndex(), newlen, oldlen - 1)
                    self.fileList = res["data"]  # has to be done here to prevent invalid index exception
                    self.endRemoveRows()

                if diff < 0:
                    self.beginInsertRows(QModelIndex(), oldlen, newlen - 1)
                    self.fileList = res["data"]  # has to be done here to prevent invalid index exception
                    self.endInsertRows()

                if diff == 0:
                    self.fileList = res["data"]
                    self.dataChanged.emit(self.createIndex(0, 0), self.createIndex(newlen, 2))

                self.updateStatus.emit(True)
                return

            self.updateStatus.emit(False)
