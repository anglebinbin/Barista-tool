from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QModelIndex, QVariant
from PyQt5.QtWidgets import QAbstractItemView

from gui.main_window.docks.properties.properties_delegate import PropertiesDelegate
from gui.main_window.docks.properties.properties_data_model import PropertiesDataModel
from gui.main_window.docks.properties.properties_suggestion_model import PropertiesSuggestionModel
from gui.main_window.docks.properties.property_widgets.data import *

class PropertiesWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(PropertiesWidget, self).__init__(parent)
        self.disabled = False
        self.setupUi()

    def setupUi(self):
        mainLayout = QtWidgets.QVBoxLayout(self)
        # Create the treeview to display the properties.
        self.model = None
        self.tree = QtWidgets.QTreeView(self)
        self.tree.setObjectName("properties")
        self.tree.setItemDelegate(PropertiesDelegate(self.tree))
        self.tree.setEditTriggers(QtWidgets.QAbstractItemView.AllEditTriggers)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        mainLayout.addWidget(self.tree)
        # Add a label that shows node descriptions.
        self.descriptionLabel = QtWidgets.QLabel("", self)
        mainLayout.addWidget(self.descriptionLabel)
        self.descriptionLabel.setObjectName('infoText')
        self.descriptionLabel.setWordWrap(True)
        # Create buttons to add and remove properties.
        buttonLayout = QtWidgets.QHBoxLayout()
        buttonLayout.addStretch()
        mainLayout.addLayout(buttonLayout)
        # Add ComboBox to select properties.
        self.propertyBox = QtWidgets.QComboBox(self)
        self.propertyBox.setModel(PropertiesSuggestionModel())
        buttonLayout.addWidget(self.propertyBox, 1)
        # Add Buttons to add and remove properties.
        self.addButton = QtWidgets.QPushButton("Add", self)
        self.addButton.clicked.connect(self.addClickedHandler)
        buttonLayout.addWidget(self.addButton, 0)
        self.removeButton = QtWidgets.QPushButton("Remove", self)
        buttonLayout.addWidget(self.removeButton, 0)
        self.removeButton.clicked.connect(self.removeClickedHandler)

        self.rowChangedHandler(QModelIndex(), QModelIndex())

    def setModel(self, model):
        self.model = model
        self.tree.setModel(model)
        self.tree.selectionModel().currentRowChanged.connect(self.rowChangedHandler)
        self.tree.expandAll()
        self.tree.setCurrentIndex(self.model.index(0, 0, QModelIndex()))

    def rowChangedHandler(self, current, previous):
        node = current.internalPointer()
        isRoot = node is not None and node == self.model.root
        self.propertyBox.setEnabled((isinstance(node, PropertyDataGroupObject) or isRoot) and not self.disabled)
        self.propertyBox.setVisible(isinstance(node, PropertyDataGroupObject) or isRoot)
        # disable add and remove buttons in property widget
        if ((isinstance(node, PropertyDataListObject) and ("top" in node.uri() or "bottom" in node.uri()))) \
            or (isinstance(node, PropertyDataObject) and ("top" in node.uri() or "bottom" in node.uri())):
                self.addButton.setDisabled(True)
                self.removeButton.setDisabled(True)
        else:
            self.addButton.setEnabled((not current.isValid() or isinstance(node, PropertyDataGroupObject) or isRoot or isinstance(node, PropertyDataListObject)) and not self.disabled)
            self.removeButton.setEnabled(current.isValid() and not isRoot and not node.info().isRequired() and not self.disabled)

        if isinstance(node, PropertyDataGroupObject):
            self.propertyBox.setModel(PropertiesSuggestionModel(node.value()))
        elif isRoot:
            self.propertyBox.setModel(PropertiesSuggestionModel(node))
        else:
            self.propertyBox.setModel(PropertiesSuggestionModel())

        # Show description.
        if node is not None:
            if isinstance(node, PropertyDataObject):
                self.descriptionLabel.setText(node.info().description())
            else:
                self.descriptionLabel.setText('')

    def addClickedHandler(self):
        index = self.tree.selectionModel().currentIndex()
        if not index.isValid():
            return
        node = index.internalPointer()
        isRoot = node is not None and node == self.model.root
        # Add to group or root.
        if isinstance(node, PropertyDataGroupObject) or isRoot:
            prop = self.propertyBox.currentData(QtCore.Qt.UserRole)
            try:
                self.model.addToGroup(index, prop.name(), prop.prototype())
            except Exception as e:
                QtWidgets.QMessageBox.critical(self,
                                               self.tr("Failed to add property."),
                                               self.tr(type(e).__name__ + ": " + str(e)))
                return
            self.propertyBox.model().update()
        # Add to list.
        elif isinstance(node, PropertyDataListObject):
            value = node.prototypeValue()
            self.model.addToList(index, value)

    def removeClickedHandler(self):
        index = self.tree.selectionModel().currentIndex()
        if index.isValid() and not index.internalPointer().info().isRequired():
            self.model.removeNode(index)
            self.propertyBox.model().update()

    def disableEditing(self, disable):
        """ Disable Editing of the tree """
        self.disabled = disable
        if disable:
            self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.propertyBox.setDisabled(disable)
            self.addButton.setDisabled(disable)
            self.removeButton.setDisabled(disable)
        else:
            self.tree.setEditTriggers(QtWidgets.QAbstractItemView.AllEditTriggers)
