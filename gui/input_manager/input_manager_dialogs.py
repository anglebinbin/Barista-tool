import copy
import os
from PyQt5 import QtWidgets
from PyQt5 import QtGui
from PyQt5 import QtCore

from gui.host_manager.remote_file_dialog import *


class SelectableListView(QtWidgets.QListView):
    """This ListView is able to toggle and untoggle the current item, which row was clicked anywhere"""
    clickedSignal = QtCore.pyqtSignal()

    def __init__(self, parent):
        self.parent = parent
        QtWidgets.QListView.__init__(self, parent)
        self.clickedSignal.connect(self.toggleClicked)

    def toggleClicked(self):
        #toggle the checkbox for the selected row
        selectedRows = self.selectedIndexes()
        if len(selectedRows) == 1:
            selectedItem = self.parent.listModel.item(selectedRows[0].row())
            checkState = Qt.Checked if selectedItem.checkState() == Qt.Unchecked else Qt.Unchecked
            item = self.parent.listModel.item(selectedRows[0].row())
            item.setCheckState(checkState)

    def mouseReleaseEvent(self, event):
        #if a single click appears, the user have to toggle the checkbox itself
        super(SelectableListView, self).mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        #with a doubleclick the user can toggle the checkbox by clicking anywhere in the row
        self.clickedSignal.emit()


class CheckBoxDialog(QtWidgets.QDialog):
    """ A Dialog presenting items to the user as a List with Checkboxes
    """

    def __init__(self, parent=None):
        QtWidgets.QDialog.__init__(self, parent)

        self.setWindowModality(Qt.ApplicationModal)

        # layouts
        self.layout = QtWidgets.QVBoxLayout(self)
        self.buttonLayout = QtWidgets.QHBoxLayout()

        # elements
        self.label = QtWidgets.QLabel("")
        self.list = SelectableListView(self)
        self.list.setSelectionMode(QtWidgets.QListView.ExtendedSelection)
        self.listModel = QtGui.QStandardItemModel(self)
        self.list.setModel(self.listModel)
        self.pb_ok = QtWidgets.QPushButton("Ok")
        self.pb_can = QtWidgets.QPushButton("Cancel")
        self.pb_toggle = QtWidgets.QPushButton("Toggle Selected")
        self.pb_selall = QtWidgets.QPushButton("Check All")
        self.pb_selnone = QtWidgets.QPushButton("Check None")

        # add elements to layouts
        self.buttonLayout.addWidget(self.pb_selall)
        self.buttonLayout.addWidget(self.pb_selnone)
        self.buttonLayout.addWidget(self.pb_toggle)
        self.buttonLayout.addStretch(40)
        self.buttonLayout.addWidget(self.pb_ok)
        self.buttonLayout.addWidget(self.pb_can)

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.list)
        self.layout.addLayout(self.buttonLayout)

        # connect the buttons
        self.pb_selall.clicked.connect(self.selectAll)
        self.pb_selnone.clicked.connect(self.selectNone)
        self.pb_toggle.clicked.connect(self.toggleSelected)
        self.pb_ok.clicked.connect(self.accept)
        self.pb_can.clicked.connect(self.close)

        self.pb_ok.setDefault(True)
        self.pb_ok.setFocus()


    def selectAll(self):
        for index in range(self.listModel.rowCount()):
            item = self.listModel.item(index)
            item.setCheckState(Qt.Checked)

    def selectNone(self):
        for index in range(self.listModel.rowCount()):
            item = self.listModel.item(index)
            item.setCheckState(Qt.Unchecked)

    def toggleSelected(self):
        selectedRows = self.list.selectedIndexes()
        if len(selectedRows) > 0:
            firstItem = self.listModel.item(selectedRows[0].row())
            checkState = Qt.Checked if firstItem.checkState() == Qt.Unchecked else Qt.Unchecked
            for index in selectedRows:
                item = self.listModel.item(index.row())
                item.setCheckState(checkState)

class DatabaseCheckBoxDialog(CheckBoxDialog):
    """ A Dialog presenting found files to the user as a List with Checkboxes
        can return a List with only selected Items in it"""
    def __init__(self, fileList, root, parent=None):
        CheckBoxDialog.__init__(self, parent)

        self.setWindowTitle("Choose Databases")
        self.resize(700, 500)
        self.label.setText("Choose the Databases you want to add")
        self.fileList = fileList
        self.root = root

        # add content to the list
        if self.fileList:
            if isinstance(self.fileList[0], type(str())):
                self.fillStr()
            elif isinstance(self.fileList[0], type(dict())):
                self.fillAddSearch()

    def fillAddSearch(self):
        for file in self.fileList:
            path = os.path.relpath(file["filepath"], self.root+"/..")
            item = QtGui.QStandardItem(path)
            item.setToolTip(file["filepath"])
            item.setCheckable(True)
            item.setCheckState(Qt.Checked)
            item.setEditable(False)
            self.listModel.appendRow(item)

    def fillStr(self):
        for file in self.fileList:
            item = QtGui.QStandardItem(file)
            item.setCheckable(True)
            item.setCheckState(Qt.Checked)
            item.setEditable(False)
            self.listModel.appendRow(item)

    def getFileList(self):
        # delete all unchecked items from the list
        for index in reversed(range(self.listModel.rowCount())):
            item = self.listModel.item(index)
            if item.isCheckable() and item.checkState() == QtCore.Qt.Unchecked:
                del self.fileList[index]
        return self.fileList


class AssignLayerCheckBoxDialog(CheckBoxDialog):
    """ A Dialog presenting layers to the user as a List with Checkboxes
        can return a list of layer's id, name and their check state"""
    def __init__(self, itemsList, parent=None):
        CheckBoxDialog.__init__(self, parent)

        self.setWindowTitle("Choose Layers")
        self.resize(400, 300)
        self.label.setText("Assign layers to the database")
        self.itemsList = copy.deepcopy(itemsList)

        # add content to the list
        if self.itemsList:
            self.createCheckboxes()

    def createCheckboxes(self):
        for layerid, layername, assigned in self.itemsList:
            item = QtGui.QStandardItem(layername)
            item.setCheckable(True)
            if assigned:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
            item.setEditable(False)
            self.listModel.appendRow(item)

    def getSelectedLayersList(self):
        # delete all unchecked items from the list
        for index in reversed(range(self.listModel.rowCount())):
            item = self.listModel.item(index)
            if item.isCheckable():
                self.itemsList[index][2] = (item.checkState() == Qt.Checked)
        return self.itemsList


class TableEditor(QtWidgets.QDialog):

    def __init__(self, path=False, parent=None):
        QtWidgets.QDialog.__init__(self, parent)

        # get labels whether there is a given path or not
        if path:
            windowTitle = "HDF5 Textfile Editor" + " - " + os.path.basename(path)
            savelabel = "Save"
        else:
            windowTitle = "HDF5 Textfile Editor"
            savelabel = "Save as"

        # window settings
        self.setWindowTitle(windowTitle)
        self.setWindowModality(Qt.ApplicationModal)
        self.resize(500, 600)

        # layouts
        self.layout = QtWidgets.QVBoxLayout(self)
        self.topLayout = QtWidgets.QHBoxLayout()
        self.buttonLayout = QtWidgets.QHBoxLayout()

        # buttons
        self.label = QtWidgets.QLabel("Add, remove and edit lines below:")
        self.pb_save = QtWidgets.QPushButton(savelabel)
        self.pb_cancel = QtWidgets.QPushButton("Cancel")
        self.pb_addline = QtWidgets.QPushButton("Add Line")
        self.pb_rmline = QtWidgets.QPushButton("Remove Line")
        self.pb_addfile = QtWidgets.QPushButton("Add File(s)")

        # table
        self.table = self.CustomTable()
        self.table.insertColumn(0)
        self.table.insertColumn(1)
        self.table.setHorizontalHeaderLabels(["Path", "Availibility"])
        self.icon_exists = QtGui.QIcon("resources/valid.png")
        self.icon_missing = QtGui.QIcon("resources/invalid.png")
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)

        # textfile
        self.path = path
        if path:
            try:
                self.txtfile = open(self.path, "r").read().splitlines()

                for counter, line in enumerate([line for line in self.txtfile if line]):
                    self.table.insertRow(counter)
                    self.table.setItem(counter, 0, QtWidgets.QTableWidgetItem(line))
                    self.fillCheckItem(counter, line)
            except IOError:
                return

        # add elements to layouts
        self.topLayout.addWidget(self.label)
        self.topLayout.addStretch()
        self.buttonLayout.addWidget(self.pb_addline)
        self.buttonLayout.addWidget(self.pb_rmline)
        self.buttonLayout.addWidget(self.pb_addfile)
        self.buttonLayout.addStretch()
        self.buttonLayout.addWidget(self.pb_save)
        self.buttonLayout.addWidget(self.pb_cancel)
        self.layout.addLayout(self.topLayout)
        self.layout.addWidget(self.table)
        self.layout.addLayout(self.buttonLayout)

        # connect the buttons and the table
        self.pb_save.clicked.connect(self.save)
        self.pb_cancel.clicked.connect(self.close)
        self.pb_addline.clicked.connect(self.addLine)
        self.pb_rmline.clicked.connect(self.removeLine)
        self.pb_addfile.clicked.connect(self.addFiles)
        self.table.cellChanged.connect(self.reload)
        self.table.dropped.connect(self.addFiles)

        self.pb_save.setDefault(True)
        self.pb_save.setFocus()
        self.exec_()

    def addLine(self):
        """ adds one row to the table """
        index = self.table.rowCount()
        self.table.insertRow(index)
        self.table.setItem(index, 0, QtWidgets.QTableWidgetItem(""))
        self.fillCheckItem(index, "")
        self.reload()

    def addItem(self, index, path):
        """ adds an item in a given row to the table """
        filepath, ext = os.path.splitext(path)
        if ext == ".h5" or ext ==".hdf5":
            self.table.setItem(index, 0, QtWidgets.QTableWidgetItem(path))
            return True
        else:
            return False

    def removeLine(self):
        for index in reversed(self.table.selectedIndexes()):
            self.table.removeRow(index.row())

    def addFiles(self, files=[]):
        """ gets called when add File button gets clicked """
        if not files:
            fileDialog = self.CustomFileDialog()
            execAccepted = fileDialog.exec_()
            files, openClicked = fileDialog.getReturnState()
            if not (execAccepted or openClicked):
                return

        def append(path):
            nameFound = False
            if len(self.table.selectedIndexes()) > 0:
                item = self.table.selectedIndexes()[0]
                if len(self.table.item(item.row(), 0).text()) == 0:
                    nameFound = True
                    self.addItem(item.row(), path)
            if not nameFound:
                emptyFound = False
                for index in range(self.table.rowCount()):
                    item = self.table.item(index, 0)
                    if item.text() == "":
                        emptyFound = True
                        break
                if not emptyFound:
                    index = self.table.rowCount()
                    self.addLine()
                self.addItem(index, path)
        for path in files:
            if os.path.isfile(path):
                append(path)
            elif os.path.isdir(path):
                for root, dirs, files in os.walk(path):
                    for name in reversed(files):
                        filepath, extension = os.path.splitext(os.path.join(root, name))
                        if extension == ".h5" or extension == ".hdf5":
                            append(filepath+extension)

        self.reload()

    def checkIfExists(self, path):
        return os.path.exists(path)

    def fillCheckItem(self, index, line):
        """ checks wether a path is valid or missing """
        if self.checkIfExists(line):
            ext = os.path.splitext(line)[1]
            if ext == ".h5" or ext == ".hdf5":
                icon = self.icon_exists
                label = "found"
            else:
                icon = self.icon_missing
                label = "invalid"
        else:
            icon = self.icon_missing
            label = "empty" if line == "" else "missing"
        self.table.setItem(index, 1, QtWidgets.QTableWidgetItem(icon, label))
        item = self.table.item(index, 1)
        item.setFlags(Qt.NoItemFlags)

    def reload(self, row=0, column=0):
        """ reloads all path avalabilities """
        if column == 0:
            for index in range(self.table.rowCount()):
                item = self.table.item(index, 0)
                try:
                    self.fillCheckItem(index, item.text())
                except AttributeError:
                    self.table.setItem(index, 1, QtWidgets.QTableWidgetItem(self.icon_missing, "missing"))

    def save(self):
        if self.path:
            txtfile = open(self.path, "w+")
            for index in range(self.table.rowCount()):
                line = self.table.item(index, 0).text()
                if self.checkIfExists(line):
                    txtfile.write(line+"\n")
            txtfile.close()
            self.accept()
        else:
            path, type = QtWidgets.QFileDialog.getSaveFileName(self, "Select a new Filename", QtCore.QDir.homePath(), "HDF5TXT (*.txt)")
            if len(path) > 0:
                path, extension = os.path.splitext(path)
                path = path + ".txt"  # ensure .txt is the suffix
                self.path = path
                txtfile = open(path, "w+")
                for index in range(self.table.rowCount()):
                    line = self.table.item(index, 0).text()
                    if self.checkIfExists(line):
                        txtfile.write(line+"\n")
                txtfile.close()
                self.accept()

    def keyReleaseEvent(self, QKeyEvent):
        if QKeyEvent.key() == QtCore.Qt.Key_Delete:
            self.removeLine()

    class CustomTable(QtWidgets.QTableWidget):

        dropped = pyqtSignal(list)

        def __init__(self, parent=None):
            QtWidgets.QWidget.__init__(self, parent)
            self.setAcceptDrops(True)

        def dragEnterEvent(self, event):
            if event.mimeData().hasUrls:
                event.accept()
            else:
                event.ignore()

        def dragMoveEvent(self, event):
            if event.mimeData().hasUrls:
                event.accept()
            else:
                event.ignore()

        def dropEvent(self, event):
            if event.mimeData().hasUrls:
                event.setDropAction(QtCore.Qt.CopyAction)
                event.accept()

                links = []
                for url in event.mimeData().urls():
                    links.append(str(url.toLocalFile()))

                self.dropped.emit(links)
            else:
                event.ignore()

    class CustomFileDialog(QtWidgets.QFileDialog):
        """ to get Folders OR Files"""
        def __init__(self, parent=None):
            QtWidgets.QFileDialog.__init__(self, parent)
            self.setWindowTitle("Select a Folder or hdf5 files")
            self.setFileMode(QtWidgets.QFileDialog.ExistingFiles)
            self.setNameFilter("HDF5 (*.h5 *.hdf5);; Directories")
            buttons = self.findChildren(QtWidgets.QPushButton)
            self.openBtn = [x for x in buttons if 'open' in str(x.text()).lower()][0]
            self.openBtn.clicked.disconnect()
            self.cancelBtn = [x for x in buttons if 'cancel' in str(x.text().lower())][0]
            self.cancelBtn.clicked.disconnect()
            # TODO: Open Button Label could be changed, LookIn however doesnt work yet
            # self.setLabelText(QtWidgets.QFileDialog.Accept, "Choose")
            # self.setLabelText(QtWidgets.QFileDialog.LookIn, "Choose")
            self.openBtn.clicked.connect(self.openClick)
            self.cancelBtn.clicked.connect(self.close)
            self.openClicked = 0

        def openClick(self):
            self.openClicked = 1
            self.hide()

        def getReturnState(self):
            return self.selectedFiles(), self.openClicked
