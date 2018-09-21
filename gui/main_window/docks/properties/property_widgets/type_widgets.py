from PyQt5 import QtCore, QtGui
from PyQt5 import QtWidgets

from PyQt5.QtCore import pyqtSignal

from gui.main_window.docks.properties.property_widgets.data import StringType, IntType, EnumType, FloatType, BoolType, PropertyDataObject


class TwoTypeWdg:
    """ TwoTypeWdg is a class which defines setupInTableLayout
        using exactly two widget:
        * one label for the name
        * one widget defines by its subclasses in _initValueWdg

        Child classes can use self._parent to get the parent widget.
        They can use self.data to get the PropertyDataObject 
        this Widget represents.
    """

    def __init__(self, data, parent=None):
        """ Build TwoTypeWdg with given parent widget 
            and the instance of  PropertyDatObject named data.
            The name of the name-label will be the value
            of data.info().name().
        """
        # super(TwoTypeWdg, self).__init__(parent)
        self.data = data #type: PropertyDataObject
        self._parent = parent
        self.nameWdg = QtWidgets.QLabel(self.data.info().name(),parent)
        self.valueWdg = self._initValueWdg()
        self.valueWdg.setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed))
        self.nameWdg.setSizePolicy(QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed))
        font = self.nameWdg.font() #type: QtGui.QFont
        # self.nameWdg.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        if self.data.info().deprecated():
            font.setStrikeOut(True)
        self.nameWdg.setFont(font)
        self.nameWdg.setToolTip(getTooltipString(self.data.info().description()))
        self.valueWdg.setToolTip(getTooltipString(self.data.info().description()))
        if not data.info().isEditable():
            self.nameWdg.setEnabled(False)
            self.valueWdg.setEnabled(False)

    def setupInTableLayout(self, lay, row, remButton):
        """ Setup this object into a QGridLayout 
            row is the specific row to insert the widgets
            remButton is the Remove-Button which should
                      be inserted into the GridLayout 
                      by this function, too
        """
        lay = lay #type: QtWidgets.QGridLayout
        lay.addWidget(self.nameWdg, row, 0,1,1)
        lay.addWidget(self.valueWdg, row, 1,1,1)
        lay.addWidget(remButton, row, 2,1,1)

    def _initValueWdg(self):
        """ This function should be overriden by every child
            It should return the Widget which represents the value
            of the PropertyDataObject.
        """
        pass

class StringWdg(TwoTypeWdg):
    """ A Line-Editor  for edit simple text """

    class Editor(QtWidgets.QLineEdit):
        """ The LineEdit-Widget """

        """ This signal is emitted every time the value of this prototxt_editor
            should propagate changes.
            For example not every text change emits this signals.
            Only when the prototxt_editor gets deselected or enter is pressed
            this signal is emitted.
        """
        saveChange = pyqtSignal(str)

        def __init__(self, text="", parent=None):
            super(StringWdg.Editor, self).__init__(text,parent)
            self.customContextMenuRequested.connect(self.openCtxMenu)
            self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            self.returnPressed.connect(self._checkForChangesAndEmitIf)
            self.__textInData = text

        def openCtxMenu(self,pos):
            """ Add "From File" and "From Path" to the context menu """
            menu = self.createStandardContextMenu() # type: QtWidgets.QMenu

            menu.addSeparator()
            menu.addAction(self.tr("From &File"), self.selectFile)
            menu.addAction(self.tr("From &Path"), self.selectPath)


            menu.exec_(self.mapToGlobal(pos))

        def setTextWithChangeDetection(self, text):
            """ This method should be use from other to set the text of 
                this widget. It updates the widget text but also updates
                the variable represents the last text data.
                So the function _checkForChangesAndEmitIf works.
            """
            self.__textInData = text
            self.setText(text)

        def _checkForChangesAndEmitIf(self):
            """ Check is the new text does not equal
                the last one and emit signals if not equal
            """
            if self.text() != self.__textInData:
                self.saveChange.emit(self.text())

        def focusOutEvent(self, event):
            super(StringWdg.Editor, self).focusOutEvent(event)
            self._checkForChangesAndEmitIf()

        def selectFile(self):
            """ When clicking 'From File' """
            filename,_ = QtWidgets.QFileDialog.getOpenFileName(self)
            if len(filename) == 0:
                return
            self.setText(filename)
        def selectPath(self):
            """ When clicking 'From Path' """
            dirname = QtWidgets.QFileDialog.getExistingDirectory(self)
            if len(dirname) == 0:
                return
            self.setText(dirname)



    def _initValueWdg(self):
        wdg = StringWdg.Editor(self.data.value(),self._parent)
        wdg.saveChange.connect(lambda: self.data.setValue(wdg.text()))
        wdg.childEvent
        self.data.propertyChanged.connect(wdg.setTextWithChangeDetection)
        return wdg

class IntWdg(TwoTypeWdg):
    """ A Spinbox which represent integer values """

    # The maximal and minimal values of an Integer
    MAX_RANGE = -pow(2, 31), pow(2, 31-1)
    class SpinBox(QtWidgets.QSpinBox):
        """ The SpinBox widget """
        def __init__(self, parent=0):
            super(IntWdg.SpinBox, self).__init__(parent)
            self.setFocusPolicy(QtCore.Qt.StrongFocus )

        # idea from http://stackoverflow.com/questions/5821802/qspinbox-inside-a-qscrollarea-how-to-prevent-spin-box-from-stealing-focus-when
        def wheelEvent(self, event):
            if not self.hasFocus():
                event.ignore()
            else:
                QtWidgets.QSpinBox.wheelEvent(self, event)

    def _initValueWdg(self):
        wdg = IntWdg.SpinBox(self._parent)
        wdg.setRange(*self.MAX_RANGE)
        wdg.setValue(self.data.value())
        wdg.valueChanged.connect(self.data.setValue)
        self.data.propertyChanged.connect(wdg.setValue)
        return wdg

class FloatWdg(TwoTypeWdg):
    """ A Spinbox which represent float values """
    MAX_RANGE = -pow(2, 31), pow(2, 31-1)
    class SpinBox(QtWidgets.QDoubleSpinBox):
        """ The Spinbox Widget """
        def __init__(self, parent=0):
            super(FloatWdg.SpinBox, self).__init__(parent)
            self.setFocusPolicy(QtCore.Qt.StrongFocus )
            # self.setDecimals(323)
            self.setDecimals(15)
            self.setSingleStep(0.05)

        # idea from http://stackoverflow.com/questions/5821802/qspinbox-inside-a-qscrollarea-how-to-prevent-spin-box-from-stealing-focus-when
        def wheelEvent(self, event):
            if not self.hasFocus():
                event.ignore()
            else:
                QtWidgets.QDoubleSpinBox.wheelEvent(self, event)

        def textFromValue(self, value):
            """ Change the text of this SpinBox such that the widget
                does not show unneeded zeros after the decimal point
            """
            stringValue = super(FloatWdg.SpinBox, self).textFromValue(value)
            while len(stringValue) > 2 and stringValue[-1] == "0" and stringValue[-2] != ",":
                stringValue = stringValue[0:-1]
            return stringValue

    def _initValueWdg(self):
        wdg = FloatWdg.SpinBox(self._parent)
        wdg.setRange(*self.MAX_RANGE)
        wdg.setValue(self.data.value())
        wdg.valueChanged.connect(self.data.setValue)
        self.data.propertyChanged.connect(wdg.setValue)
        return wdg


class EnumWdg(TwoTypeWdg):
    """ Combobox for Enums """

    def _initValueWdg(self):
        wdg = QtWidgets.QComboBox(self._parent)
        wdg.addItems(self.data.info().enumOptions())
        wdg.currentTextChanged.connect(self.data.setValue)
        self.data.propertyChanged.connect(wdg.setCurrentText)
        wdg.setCurrentText(self.data.value())
        return wdg

class BoolWdg(TwoTypeWdg):
    """ Checkbox for Bools"""

    def _initValueWdg(self):
        wdg = QtWidgets.QCheckBox(self._parent)
        wdg.stateChanged.connect(lambda s: self.data.setValue(wdg.isChecked()))
        self.data.propertyChanged.connect(wdg.setChecked)
        wdg.setChecked(self.data.value())
        return wdg

# Export Widget 
WdgCatalog={
    StringType: StringWdg,
    IntType: IntWdg,
    FloatType: FloatWdg,
    EnumType: EnumWdg,
    BoolType: BoolWdg,
}


def getTooltipString(description):
    """Ensures that tooltips are shown with newlines. """
    newDescription = ""
    if not description == "":
        newDescription = "<FONT>"
        newDescription += description
        newDescription += "</FONT>"
    return newDescription
