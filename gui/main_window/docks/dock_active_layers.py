import functools
from PyQt5 import QtCore, QtWidgets

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMenu, QAction, QMessageBox

import backend.caffe.dict_helper as helper
import gui.main_window.docks.properties.property_widgets.data as PropData
from gui.main_window.docks.dock import DockElement


class DockElementActivLayers(DockElement):
    def __init__(self, mainWindow, title):
        DockElement.__init__(self, mainWindow, 'Network Layers')
        self.name = title

        # Set the minimum size parameters
        self.setMinimumHeight(265)
        self.setMinimumWidth(250)

        widget = QtWidgets.QWidget()
        self.layout = QtWidgets.QVBoxLayout()
        widget.setLayout(self.layout)
        self.setWidget(widget)

        self.addTextfieldForSearch()
        self.addTableWidget()



    def addTextfieldForSearch(self):
        textField = QtWidgets.QLineEdit(self)
        textField.setPlaceholderText("Search for layers")
        textField.textChanged.connect(self.searchForLayers)
        self.layout.addWidget(textField)

    def addTableWidget(self):
        self.table = activLayerTable()
        self.layout.addWidget(self.table)

    def searchForLayers(self, layerName):
        self.table.searchForLayers(layerName)

    def getLayersListWidget(self):
        return self.table

    def mousePressEvent(self, QMouseEvent):
        return

    def disableEditing(self, disable):
        ''' Disable the table with all active layers. '''
        if self.table:
            self.table.setDisabled(disable)

class activLayerTable(QtWidgets.QTableWidget):
    def __init__(self):
        QtWidgets.QTableWidget.__init__(self)

        # Set behaviour and layout
        self.setHorizontalHeader(HorizontalHeader(QtCore.Qt.Horizontal, self))
        self.horizontalHeader().setTableWidget(self)
        self.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.horizontalHeader().setStretchLastSection(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        # Set the number of columns as well as their headers, also disabled the vertical headers
        self.setColumnCount(3)
        self.verticalHeader().setVisible(False)
        self.setHorizontalHeaderItem(0, QtWidgets.QTableWidgetItem("Order"))
        self.setHorizontalHeaderItem(1, QtWidgets.QTableWidgetItem("Name"))
        self.setHorizontalHeaderItem(2, QtWidgets.QTableWidgetItem("Type"))

        # Add signal handling when cell is changed by user input
        self.itemChanged.connect(self.cellIsChanged)

        # Initialize internal variables
        self.tableItems = []
        self.tableItemsSearch = []
        self.selectedItemRows = []
        self.selectedItemIds = []

        # Store if the selection was changed by the keyboard or some other event
        self.selectionByKeyboard = 0

        # Set up a variable to store the sorting order, default being Ascending by Name
        self.sortingOrder = (0, QtCore.Qt.AscendingOrder)

        self.reactiveState = None

    def addItem(self, id, name,order, type):
        # Add a new item to the internal data list and update the ui accordingly
        self.tableItems.append(TableItem(id, name,order, self.networkManager.getToolTip(id), type))
        self.updateWithAllElements()

        # Sort the items so that the new item fits in at the right place
        self.sort()

    def __onUpdate(self, uri, reason):
        if uri[0] == "selection":
            self.clearSelection()
            for id in self.reactiveState["selection"]:
                self.addItemToSelection(id)
        if uri[0] == "network":
            network = self.reactiveState["network"]
            uri = uri[1:]
            if uri == ["layerOrder"]:
                for i, id in enumerate(network["layerOrder"]):
                    self.updateItemOrder(id, i)
                self.updateWithAllElements()
                return
            if len(uri) > 1:
                id = uri[1]
                if uri[2:] == ["parameters","name"]:
                    if isinstance(reason, PropData.ReasonUpdated):
                        self.updateItemName(id, reason.newValue)
            else:
                if isinstance(reason, PropData.ReasonKeyAdded):
                    id = reason.key
                    if id in network["layerOrder"]:
                        order = network["layerOrder"].index(id)
                    else:
                        order = 0
                    name = network["layers"][id]["parameters"]["name"]
                    typename = network["layers"][id]["type"].name()
                    self.addItem(id, name, order, typename)
                if isinstance(reason, PropData.ReasonKeyDeleted):
                    id = reason.key
                    self.deleteItemsByID([id])

    def setReactiveState(self, state):
        if self.reactiveState:
            self.reactiveState.someChildPropertyChanged.disconnect(self.__onUpdate)
        self.reactiveState = state
        if self.reactiveState:
            self.reactiveState.someChildPropertyChanged.connect(self.__onUpdate)

    def setSelectedItem(self,id):
        self.selectionByKeyboard -= 1
        self.clearSelection()

        for row in range(0, self.rowCount()):
            if id == self.item(row, 1).id:
                self.item(row, 0).setSelected(True)
                self.item(row, 1).setSelected(True)
                self.item(row, 2).setSelected(True)

                # Set this item as the last one selected
                self.selectedItemRows.append(row)
                self.selectedItemIds.append(id)

                # Make sure the item is visible by scrolling to it
                self.scrollToItem(self.item(row,0))
                break

    def addItemToSelection(self, id):
        self.selectionByKeyboard -= 1
        for row in range(0, self.rowCount()):
            if id == self.item(row, 1).id:
                self.item(row, 0).setSelected(True)
                self.item(row, 1).setSelected(True)
                self.item(row, 2).setSelected(True)

                # Set this item as the last one selected
                self.selectedItemRows.append(row)
                self.selectedItemIds.append(id)

                # Make sure the item is visible by scrolling to it
                self.scrollToItem(self.item(row, 0))
                break

    def removeItemFromSelection(self, id):
        self.selectionByKeyboard -= 1
        for row in range(0, self.rowCount()):
            if id == self.item(row, 1).id:
                self.item(row, 0).setSelected(False)
                self.item(row, 1).setSelected(False)
                self.item(row, 2).setSelected(False)

                # Set this item as the last one selected
                self.selectedItemRows.remove(row)
                self.selectedItemIds.remove(id)

                # Make sure the item is visible by scrolling to it
                self.scrollToItem(self.item(row, 0))
                break

    def setSelectedItems(self, ids):
        self.selectionByKeyboard -= 1
        self.clearSelection()

        for row in range(0, self.rowCount()):
            for id in ids:
                if id == self.item(row, 1).id:
                    self.item(row, 0).setSelected(True)
                    self.item(row, 1).setSelected(True)
                    self.item(row, 2).setSelected(True)

                    # Set this item as the last one selected
                    self.selectedItemRows.append(row)
                    self.selectedItemIds.append(id)

                    # If there is only one selected item, make it visible by scrolling to it
                    if len(ids) == 1:
                        self.scrollToItem(self.item(row, 0))
                        break

    def clearSelection(self):
        self.setCurrentItem(None)
        self.selectedItemRows = []
        self.selectedItemIds = []

    def deleteItemsByID(self, ids):
        for id in ids:
            for i in range(0, len(self.tableItems)):
                if self.tableItems[i].id == id:
                    del self.tableItems[i]
                    break;

        # Update the list with all elements
        self.updateWithAllElements()

    def clearTable(self):
        self.clearContents()
        self.tableItems = []
        self.tableItemsSearch = []

    def updateWithAllElements(self):
        self.update(self.tableItems)

    def update(self, list):
        # Only delete the contents so that the headers are still left
        self.clearContents()

        # Set the size of the widget
        self.setRowCount(len(list))

        # Set all items with their corresponding positions, then sort them
        for row in range(0, len(list)):
            self.setItem(row, 0, TableItemWidgetOrder(list[row].order, list[row].id, list[row].toolTip))
            self.setItem(row, 1, TableItemWidgetName(list[row].name, list[row].id, list[row].toolTip))
            self.setItem(row, 2, TableItemWidgetType(list[row].type, list[row].toolTip))
        self.sort()

        # Re-select the items that had been selected
        for row in range(0, self.rowCount()):
            for id in self.selectedItemIds:
                if self.item(row, 1).id == id:
                    self.item(row, 0).setSelected(True)
                    self.item(row, 1).setSelected(True)
                    self.item(row, 2).setSelected(True)
                    break

    def sort(self):
        'Sorts the items according to the sorting option used by user, default is Ascending Order by Name'
        self.sortItems(self.sortingOrder[0], self.sortingOrder[1])

    def updateItemName(self, id, name):
        for row in range(0, len(self.tableItems)):
            if self.tableItems[row].getID() == id:
                self.tableItems[row].setName(name)
                break
        self.updateWithAllElements()

    def updateItemOrder(self, id, order):
        for row in range(0,len(self.tableItems)):
            if self.tableItems[row].getID() == id:
                self.tableItems[row].setOrder(order)
                break

    def searchForLayers(self, layerName):
        self.tableItemsSearch = []

        for i in range(0, len(self.tableItems)):
            if layerName.lower() in self.tableItems[i].name.lower():
                self.tableItemsSearch.append(self.tableItems[i])

        # Update the table with the searched items, so that only those are shown
        self.update(self.tableItemsSearch)

    def scrollToItemByID(self, id):
        for row in range(0, self.rowCount() - 1):
            if self.item(row, 0).getID() == id:
                self.scrollToItem(self.item(row, 0))

    def cellIsChanged(self, tableItem):
        if isinstance(tableItem, TableItemWidgetName):
            if(tableItem.isEdited()):
                # Store the table item ID
                id = tableItem.getID()

                # Change the name of the item in the internal table and all other elements
                #self.networkManager.updateName(tableItem.getID(), tableItem.text())
                h = helper.DictHelper(self.networkManager.network) # type: helper.DictHelper
                h.layerParams(id)["name"] = tableItem.text()


                # Scroll to the renamed item to make sure that it is visible
                self.scrollToItemByID(id)

    def mousePressEvent(self, QMouseEvent):
        # Check if the user has clicked an item
        if self.itemAt(QMouseEvent.pos()) != None:
            # Get the current row and id of the item belonging to it
            row = self.itemAt(QMouseEvent.pos()).row()
            id = self.item(row, 1).getID()

            # On left button change the selection
            if QMouseEvent.button() == Qt.LeftButton:
                # Depending on whether the user is pressing the ctrl or shift key, add to or range selection
                if QMouseEvent.modifiers() & Qt.ControlModifier:
                    # If the item is already selected, remove it from selection
                    if self.item(row, 1).isSelected():
                        self.networkManager.removeLayerFromSelection(id)
                    else:
                        self.networkManager.addLayerToSelection(id)
                elif QMouseEvent.modifiers() & Qt.ShiftModifier:
                    # The Row of the last selected element is stored as the last element of selectedItemRows
                    lastItemRow = self.selectedItemRows[len(self.selectedItemRows) - 1]

                    # Clear the selection
                    # self.networkManager.clearSelection()

                    # Select items depending on the position of the clicked item
                    if lastItemRow < row:
                        # Start at row and select everything to the last selected element
                        for i in range(lastItemRow, row + 1):
                            self.networkManager.addLayerToSelection(self.item(i, 1).getID())
                    else:
                        # Start at last selected item and select everything up to row
                        for i in range(lastItemRow, row - 1, -1):
                            self.networkManager.addLayerToSelection(self.item(i, 1).getID())
                else:
                    self.networkManager.setSelection(id)

            # On right button open the context menu
            if QMouseEvent.button() == Qt.RightButton:
                # Set the selection to the clicked item
                self.networkManager.setSelection(id)

                # Show the context menu
                self.showContextMenu(QMouseEvent.globalPos(), id)
        else:
            # Otherwise, clear the selection
            self.networkManager.clearSelection()

    def mouseMoveEvent(self, QMouseEvent):
        return

    def mouseReleaseEvent(self, QMouseEvent):
        return

    def mouseDoubleClickEvent(self, QMouseEvent):
        # Check if user clicked an actual item
        clickedItem = self.itemAt(QMouseEvent.pos())

        # Enable editing of the item on double click, editing is only enabled for the name column
        if isinstance(clickedItem, TableItemWidgetName):
            clickedItem.setEdited(True)
            self.editItem(self.itemAt(QMouseEvent.pos()))

    def keyReleaseEvent(self, QKeyEvent):
        # Delete on del key
        if QKeyEvent.key() == QtCore.Qt.Key_Delete:
            self.networkManager.deleteSelectedLayers()
        # Switch selection to next item on tab
        elif QKeyEvent.key() == QtCore.Qt.Key_Tab:
            # Get the row of the last selected element
            row = self.selectedItemRows[len(self.selectedItemRows) - 1]

            # If the last item has been reached start at the beginning
            if row == self.rowCount() - 1:
                self.networkManager.setSelection(self.item(0, 1).id)
            else:
                self.networkManager.setSelection(self.item(row + 1, 1).id)
        # Switch to or add to selection on arrow down
        elif QKeyEvent.key() == QtCore.Qt.Key_Down:
            if self.rowCount() == 0:
                return # abort
            # Get the row of the last selected element
            if len(self.selectedItemRows) > 0:
                row = max(self.selectedItemRows)
            else:
                row = -1

            # If last selection event was not done via keyboard, clear the selection
            # if self.selectionByKeyboard < 0:
            #     try:
            #         self.networkManager.setSelection(self.item(row, 1).id)
            #     except AttributeError:
            #         pass

            # Save that the last edit was done by keyboard
            self.selectionByKeyboard = 1

            # If the last item has been reached do nothing
            if not row == self.rowCount() - 1:
                # Add to the selection if shift is held down
                if QKeyEvent.modifiers() & Qt.ShiftModifier:
                    # If the next item is already selected, remove the current from selection
                    if self.selectedItemRows.__contains__(row + 1):
                        if self.selectedItemRows.__contains__(row):
                            self.networkManager.removeLayerFromSelection(self.item(row, 1).id)
                    else:
                        self.networkManager.addLayerToSelection(self.item(row + 1, 1).id)

                else:
                    self.networkManager.setSelection(self.item(row + 1, 1).id)
                    self.currentSelectedRow = self.item(row + 1, 1).id
        # Switch to or add to selection on arrow up
        elif QKeyEvent.key() == QtCore.Qt.Key_Up:
            if self.rowCount() == 0:
                return # abort
            # Get the row of the last selected element
            # row = self.selectedItemRows[len(self.selectedItemRows) - 1]
            if len(self.selectedItemRows) > 0:
                row = min(self.selectedItemRows)
            else:
                row = self.rowCount()

            # If last selection event was not done via keyboard, clear the selection
            # if self.selectionByKeyboard < 0:
            #     try:
            #         self.networkManager.setSelection(self.item(row, 1).id)
            #     except AttributeError:
            #         pass

            # Save that the last edit was done by keyboard
            self.selectionByKeyboard = 1

            # If the first item has been reached do nothing
            if not row == 0:
                # Add to the selection if shift is held down
                if QKeyEvent.modifier() & Qt.ShiftModifier:
                    if self.selectedItemRows.__contains__(row - 1):
                        if self.selectedItemRows.__contains__(row):
                            self.networkManager.removeLayerFromSelection(self.item(row, 1).id)
                    else:
                        self.networkManager.addLayerToSelection(self.item(row - 1, 1).id)
                else:
                    self.networkManager.setSelection(self.item(row - 1, 1).id)

    def showContextMenu(self, pos, id):
        # Create a menu with context options
        menu = QMenu(self)

        # Add a focus option to context menu
        focusAction = QAction("Focus", self)
        focusAction.triggered.connect(functools.partial(self.networkManager.focusLayer, id))
        menu.addAction(focusAction)

        # Add a delete option to context menu
        deleteAction = QAction('Delete', self)
        deleteAction.triggered.connect(functools.partial(self.networkManager.deleteLayer, id))
        menu.addAction(deleteAction)

        # Show the menu at the current mouse position
        menu.popup(pos)

    def setNetworkManager(self, networkManager):
        self.networkManager = networkManager

    def getNetworkManager(self):
        return self.networkManager

    def setSortingOrder(self, column, order):
        self.sortingOrder = (column, order)

    def getSortingOrder(self):
        return self.sortingOrder

class TableItem():
    def __init__(self, id, name,order, toolTip, type):
        self.name = name
        self.id = id
        self.order = order
        self.toolTip = toolTip
        self.type = type

    def getID(self):
        return self.id


    def getName(self):
        return self.name

    def setName(self,name):
        self.name = name

    def setOrder(self,order):
        self.order = order

class TableItemWidgetOrder(QtWidgets.QTableWidgetItem):
    def __init__(self, order,id, tooltip):
        QtWidgets.QTableWidgetItem.__init__(self, self._longString(order))
        self.id = id
        self.order = order
        #self.setToolTip(tooltip)
        self.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)

    def getID(self):
        return self.id

    def setOrder(self, order):
        self.order = order

    def getOrder(self):
        return self.order

    def _longString(self,number):
        strg = str(number)
        while len(strg)<3:
            strg = "0"+strg
        return strg

class TableItemWidgetName(QtWidgets.QTableWidgetItem):
    def __init__(self, name, id, tooltip):
        QtWidgets.QTableWidgetItem.__init__(self, name)
        self.name = name
        self.id = id
        self.edited = False
        #self.setToolTip(tooltip)

    def setEdited(self, bool):
        self.edited = bool

    def isEdited(self):
        return self.edited

    def getID(self):
        return self.id

    def setName(self, name):
        self.name = name

    def getName(self):
        return self.name

class TableItemWidgetType(QtWidgets.QTableWidgetItem):
    def __init__(self, type, tooltip):
        QtWidgets.QTableWidgetItem.__init__(self, type)

        self.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        #self.setToolTip(tooltip)

class HorizontalHeader(QtWidgets.QHeaderView):
    def __init(self, orientation, parent):
        QtWidgets.QHeaderView.__init__(orientation, parent)

    def setTableWidget(self, tableWidget):
        # Save the parent widget for access to current sorting order
        self.tableWidget = tableWidget

        # Set Sorting indicator so that it is Ascending Order by Name, then show sorting indicator
        self.setSortIndicator(1, QtCore.Qt.AscendingOrder)
        self.setSortIndicatorShown(True)

    def mousePressEvent(self, QMouseEvent):
        # Get the index from the element itself and the current order from the table widget
        index = self.logicalIndexAt(QMouseEvent.pos())
        currentOrder = self.tableWidget.getSortingOrder()[1]

        # Set the new sorting order depending on the current order and clicked element
        if currentOrder == QtCore.Qt.AscendingOrder:
            self.tableWidget.setSortingOrder(index, QtCore.Qt.DescendingOrder)
            self.tableWidget.sort()
            self.setSortIndicator(index, QtCore.Qt.DescendingOrder)
        if currentOrder == QtCore.Qt.DescendingOrder:
            self.tableWidget.setSortingOrder(index, QtCore.Qt.AscendingOrder)
            self.tableWidget.sort()
            self.setSortIndicator(index, QtCore.Qt.AscendingOrder)

        # Show the sorting indicator
        self.setSortIndicatorShown(True)

    def mouseMoveEvent(self, QMouseEvent):
        return

    def mouseReleaseEvent(self, QMouseEvent):
        return
