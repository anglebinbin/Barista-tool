from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QModelIndex, QVariant
from gui.main_window.docks.properties.property_widgets.data import *
from gui.main_window.docks.properties.property_widgets.types import *

class PropertiesDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super(PropertiesDelegate, self).__init__(parent)

    def createEditor(self, parent, options, index):
        if index.column() == 0:
            return super(PropertiesDelegate, self).createEditor(parent, options, index)

        if index.internalPointer().info().typeString() == EnumType:
            return self.createEnumEditor(parent, options, index)
        elif index.internalPointer().info().typeString() == FloatType:
            return self.createFloatEditor(parent, options, index)
        elif index.internalPointer().info().typeString() == IntType:
            return self.createIntEditor(parent, options, index)
        elif index.internalPointer().info().typeString() == BoolType:
            return self.createBoolEditor(parent, options, index)
        return super(PropertiesDelegate, self).createEditor(parent, options, index)

    def createEnumEditor(self, parent, options, index):
        data = index.internalPointer()
        comboBox = QtWidgets.QComboBox(parent)
        comboBox.addItems(data.info().enumOptions())
        comboBox.setCurrentText(data.value())
        return comboBox

    def createBoolEditor(self, parent, options, index):
        data = index.internalPointer()
        comboBox = QtWidgets.QComboBox(parent)
        comboBox.addItem("true")
        comboBox.addItem("false")
        comboBox.setCurrentText(str(data.value()).lower())
        return comboBox

    def createFloatEditor(self, parent, options, index):
        data = index.internalPointer()
        spinBox = QtWidgets.QDoubleSpinBox(parent)
        spinBox.setRange(-pow(2, 31), pow(2, 31-1))
        spinBox.setFocusPolicy(QtCore.Qt.StrongFocus )
        spinBox.setDecimals(15)
        spinBox.setSingleStep(0.05)
        spinBox.setValue(data.value())
        return spinBox

    def createIntEditor(self, parent, options, index):
        data = index.internalPointer()
        spinBox = QtWidgets.QSpinBox(parent)
        spinBox.setRange(-pow(2, 31), pow(2, 31-1))
        spinBox.setFocusPolicy(QtCore.Qt.StrongFocus )
        spinBox.setValue(data.value())
        return spinBox

    def setEditorData(self, editor, index):
        data = index.internalPointer()
        if isinstance(editor, QtWidgets.QComboBox):
            if index.internalPointer().info().typeString() == BoolType:
                editor.setCurrentText(str(data.value()).lower())
            else:
                editor.setCurrentText(data.value())
        elif isinstance(editor, QtWidgets.QSpinBox) or isinstance(editor, QtWidgets.QDoubleSpinBox):
            editor.setValue(data.value())
        elif isinstance(editor, QtWidgets.QLineEdit):
            editor.setText(data.value())
        else:
            super(PropertiesDelegate, self).setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        if isinstance(editor, QtWidgets.QComboBox):
            if index.internalPointer().info().typeString() == BoolType:
                model.setData(index, True if editor.currentText() == "true" else False, QtCore.Qt.EditRole)
            else:
                model.setData(index, editor.currentText(), QtCore.Qt.EditRole)
        elif isinstance(editor, QtWidgets.QSpinBox) or isinstance(editor, QtWidgets.QDoubleSpinBox):
            model.setData(index, editor.value(), QtCore.Qt.EditRole)
        elif isinstance(editor, QtWidgets.QLineEdit):
            model.setData(index, editor.text(), QtCore.Qt.EditRole)
        else:
            super(PropertiesDelegate, self).setModelData(editor, model, index)
