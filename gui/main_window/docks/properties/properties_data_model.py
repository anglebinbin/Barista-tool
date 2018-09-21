from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.Qt import QApplication
from PyQt5.QtCore import QModelIndex, QVariant
from gui.main_window.docks.properties.property_widgets.data import *
from gui.main_window.docks.properties.property_widgets.types import *

def getChild(data, row):
    if isinstance(data, PropertyDataGroupObject):
        data = data.value()

    if isinstance(data, PropertyData):
        key = sortPropertyKeys(data.getBoringDict().keys())[row]
        c = data.getChildDataObject(key)
    elif isinstance(data, PropertyDataDictObject):
        key = sortPropertyKeys(data.value().keys())[row]
        c = data.value()[key]
    else:
        c = data.value()[row]
    return c

def getChildCount(data):
    if isinstance(data, PropertyDataGroupObject):
        data = data.value()

    if isinstance(data, PropertyData):
        return len(data.givenProperties())
    elif isinstance(data, PropertyDataListObject):
        return len(data.value())
    elif isinstance(data, PropertyDataDictObject):
        return len(data.value())
    return 0

def getColumnCount(data):
    return 2

def getParent(data, root):
    # IMPORTANT: PropertyDataGroupObject and contained PropertyData have the same
    # uri.
    if root == data:
        return None
    # Find uri from root to parent.
    uri = data.uri()[len(root.uri()):-1]
    for key in uri:
        try:
            if isinstance(root, PropertyData):
                root = root.getChildDataObject(key)
            elif isinstance(root, PropertyDataGroupObject):
                root = root.value().getChildDataObject(key)
            else:
                root = root.value()[key]
        except:
            print("[ERROR] Key '%s' unexpectedly not found in property '%s'." % (str(key), str(root.value())))
            return None
    return root

def getRow(data, root):
    parent = getParent(data, root)
    key = data.uri()[-1]
    if isinstance(parent, PropertyData):
        return sortPropertyKeys(parent.getBoringDict().keys()).index(key)
    elif isinstance(parent, PropertyDataDictObject):
        return sortPropertyKeys(parent.values().keys()).index(key)
    elif isinstance(parent, PropertyDataListObject):
        return key
    return 0

def getName(data):
    return str(data.uri()[-1])

def getValue(data):
    if type(data) != PropertyDataObject:
        return ''
    return data.value()

def isRequired(data):
    return not isinstance(data, PropertyDataObject) or data.info().isRequired()

def isEditable(data):
    # if type(data) == PropertyDataObject:
    #     print(data.info())
    return type(data) == PropertyDataObject and data.info().isEditable()

def hasProperty(data, key):
    try:
        return key in data
    except:
        return False

def sortPropertyKeys(keys):
    # Sort the keys normally.
    result = sorted(keys)
    # Then bring the 'name' and 'type' properties to the front of the list if
    # they are available.
    if 'top' in result:
        result.insert(-1, result.pop(result.index('top')))
    if 'bottom' in result:
        result.insert(-1, result.pop(result.index('bottom')))
    if 'type' in result:
        result.insert(0, result.pop(result.index('type')))
    if 'name' in result:
        result.insert(0, result.pop(result.index('name')))
    return result


class PropertiesDataModel(QtCore.QAbstractItemModel):
    def __init__(self, data, parent=None):
        """
        data : PropertyData
        """
        super(PropertiesDataModel, self).__init__(parent)
        self.root = data

    def data(self, index, role):
        """ Only return display data. """
        if not index.isValid():
            return QVariant()
        node = index.internalPointer()
        dataList = node.uri()
        if role == QtCore.Qt.DecorationRole and index.column() == 0:
            if type(node) == PropertyDataObject:
                if 'top' in dataList or 'bottom' in dataList:
                    return QtGui.QIcon('resources/blob.svg')
                else:
                    return QtGui.QIcon('resources/property.svg')
                # return QtGui.QIcon('resources/property.svg')
            else:
                if 'top' in dataList or 'bottom' in dataList:
                    return QtGui.QIcon('resources/blob.svg')
                else:
                    return QtGui.QIcon('resources/group.svg')
            # return QApplication.instance().style().standardIcon(getattr(QtWidgets.QStyle, 'SP_DirIcon'))
        if role == QtCore.Qt.ForegroundRole and isinstance(node, PropertyDataObject) and not isEditable(node) and index.column() > 0:
            return QtGui.QBrush(QtGui.QColor(125, 125, 125))
        if role == QtCore.Qt.ToolTipRole and isinstance(node, PropertyDataObject):
            if node.info().description() == '':
                return '<FONT>No info available.</FONT>'
            return '<FONT>' + node.info().description() + '</FONT>'
        if role == QtCore.Qt.DisplayRole:
            return getName(node) if index.column() == 0 else getValue(node)
        return QVariant()

    def rowCount(self, parent):
        # If parent is invalid, we show the root node only, so we have 1 row.
        if not parent.isValid():
            return 1
        parentNode = parent.internalPointer()
        return getChildCount(parentNode)

    def columnCount(self, index):
        if not index.isValid():
            return 2
            # parentNode = self.root
        else:
            parentNode = index.internalPointer()
        return getColumnCount(parentNode)

    def flags(self, index):
        if index.isValid() and index.column() > 0 and isEditable(index.internalPointer()):
            return QtCore.Qt.ItemIsEditable |  super(PropertiesDataModel, self).flags(index)
        return super(PropertiesDataModel, self).flags(index)

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            if section == 0:
                return "Property"
            if section == 1:
                return "Value"
        return QVariant()

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        if not parent.isValid():
            return self.createIndex(row, column, self.root)
            # parentNode = self.root
        else:
            parentNode = parent.internalPointer()
        childNode = getChild(parentNode, row)
        if childNode is not None:
            return self.createIndex(row, column, childNode)
        return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        childNode = index.internalPointer()
        parentNode = getParent(childNode, self.root)
        if parentNode is None:
            return QModelIndex()
        row = getRow(parentNode, self.root)
        if row is None:
            return QModelIndex()
        return self.createIndex(row, 0, parentNode)

    # Below is everything that's required for writing to the model.
    def setData(self, index, value, role):
        if not index.isValid():
            return False
        node = index.internalPointer()
        if type(node) != PropertyDataObject or role != QtCore.Qt.EditRole:
            return False

        try:
            if index.internalPointer().info().typeString() == IntType:
                value = int(value)
            elif index.internalPointer().info().typeString() == FloatType:
                value = float(value)
            elif index.internalPointer().info().typeString() == BoolType:
                value = bool(value)
            # TODO: EnumType
            index.internalPointer().setValue(value)
            self.dataChanged.emit(index, index)
        except:
            print('[ERROR] failed to set value of %s, because it had an invalid type.' % (getName(node)))
            return False
        return True

    def setHeaderData(self, section, orientation, value, role):
        return NotImplementedError()

    def addToGroup(self, parent, key, value=None):
        # Make sure that we add this as a child of the first column, to prevent
        # GUI update issues.
        parent = self.index(parent.row(), 0, parent.parent())
        parentNode = parent.internalPointer()
        if not isinstance(parentNode, PropertyDataGroupObject) and not parentNode == self.root:
            return False
        node = parentNode if parentNode == self.root else parentNode.value()
        keys = node.getBoringDict().keys()
        if key in keys:
            return False
        keys.append(key)
        row = sortPropertyKeys(keys).index(key)
        self.beginInsertRows(parent, row, row)
        if value is None:
            node.givePropertyDefault(key)
        else:
            node.giveProperty(key, value)
        self.endInsertRows()
        return True

    def addToList(self, parent, value):
        # Make sure that we add this as a child of the first column, to prevent
        # GUI update issues.
        parent = self.index(parent.row(), 0, parent.parent())
        parentNode = parent.internalPointer()
        if not isinstance(parentNode, PropertyDataListObject):
            return False
        row = len(parentNode.value())
        self.beginInsertRows(parent, row, row)
        parentNode.pushBack(value)
        self.endInsertRows()
        return True

    def removeNode(self, index):
        node = index.internalPointer()
        parent = self.parent(index)
        parentNode = getParent(node, self.root)
        # We are only allowed to remove nodes when the parent is root, or and
        # instance of PropertyDataGroupObject or PropertyDataListObject.
        if parentNode == self.root:
            self.beginRemoveRows(parent, index.row(), index.row())
            parentNode.ungiveProperty(node._idx)
            self.endRemoveRows()
        elif isinstance(parentNode, PropertyDataGroupObject):
            self.beginRemoveRows(parent, index.row(), index.row())
            parentNode.value().ungiveProperty(node._idx)
            self.endRemoveRows()
        elif isinstance(parentNode, PropertyDataListObject):
            self.beginRemoveRows(parent, index.row(), index.row())
            parentNode.removeObject(node._idx)
            self.endRemoveRows()
        # Otherwise we print an error message.
        else:
            print("[ERROR] Cannot remove property from node of type %s" % str(type(parentNode)))
            return False
