import platform
from PyQt5 import QtCore, QtGui
from PyQt5 import QtWidgets

from PyQt5.QtCore import pyqtSignal

from gui.main_window.docks.properties.property_widgets.data import PropertyDataObject, PropertyDataListObject
from gui.main_window.docks.properties.property_widgets.type_widgets import WdgCatalog
from gui.main_window.docks.properties.property_widgets.types import *


def clearLayout(lay):
    """ Removes every widget in the given layout """
    for i in reversed(range(lay.count())):
        item = lay.itemAt(i) # type: QtWidgets.QLayoutItem
        lay.removeItem(item)
        wdg = item.widget()
        if wdg is None:
            childLay = item.layout()
            clearLayout(childLay)
        else:
            wdg.setParent(None)
            wdg.deleteLater()


class PropertyEditWdg(QtWidgets.QScrollArea):
    """ This is the main widget for showing the properties.
        It should be used in the dock element for example.
    """

    def __init__(self, parent=None, data = None):
        """ Construct this object with the parent (a widget)
            and the data (PropertyData/-Object).
            Through this widget the user can manipulate
            the data. data can be None, so there is no
            data set.
        """
        super(PropertyEditWdg, self).__init__(parent)
        self.setWidgetResizable(True)
        self.content = None
        if data:
            self.setData(data)

    def setData(self, data):
        """ Set the data (may replace old one) with the given one """
        self.content = GroupWdg(data)
        # lay = QtWidgets.QVBoxLayout()
        # lay.addWidget(val)
        # self.setLayout(lay)
        self.setWidget(self.content)

    def disableEditing(self, disable):
        """ Disable Editing of the data """
        if self.content:
            self.content.setDisabled(disable)

class RepeatedWrapper(QtWidgets.QGroupBox):
    """ A Widget for showing a list of values """

    def __init__(self, data,  parent=None):
        super(RepeatedWrapper, self).__init__(parent)
        # Layout to add the child widgets
        # Have to be a GridLayout.
        self._childlay = QtWidgets.QGridLayout()
        self._childlay.setHorizontalSpacing(2)
        # Layout for the top-remove button
        self._topLay = QtWidgets.QHBoxLayout()
        # Layout of the whole object
        self._lay = QtWidgets.QVBoxLayout()
        self._lay.addLayout(self._topLay)
        self._lay.addLayout(self._childlay)
        self._lay.addStretch()
        # self._lay.setContentsMargins(1,1,1,1)
        self.setLayout(self._lay)
        self.data = data #type: PropertyDataListObject

        self.nameLabel = QtWidgets.QLabel(data.info().name())
        self.setToolTip(getTooltipString(self.data.info().description()))

        # \/ exclusive value
        self.lastChildRow = self._buildChilds(self.data.value())

        self.data.propertyChanged.connect(self._buildChilds)

        # Layout for the add-Button
        bottomLay = QtWidgets.QHBoxLayout()
        self._lay.addLayout(bottomLay)
        bottomLay.addWidget(self.nameLabel,self.lastChildRow)
        bottomLay.addStretch()
        addButton = QtWidgets.QToolButton(self)
        addButton.clicked.connect(self.addOne)
        addButton.setText("+")
        bottomLay.addWidget(addButton,self.lastChildRow)

    def _clear(self):
        """ Clear the Layout so there is no widget anymore """
        clearLayout(self._childlay)
        self.lastChildRow = 0

    def _buildChilds(self, childs):
        """ Build the widget for every entry in the list """
        self._clear()
        # if remove button is clicked
        def removeCallback(idx):
            return lambda: self.data.removeObject(idx)
        i = 1 # Current entry-idx in the GridLayout
        for (idx,element) in enumerate(childs): #type: (int,PropertyDataObject)
            # Build the widget
            wdg = WdgCatalog[element.info().typeString()](element,self)
            # The remove button
            remButton = QtWidgets.QToolButton(self)
            trashIcon = QtGui.QPixmap('resources/trash.png')
            remButton.setIcon(QtGui.QIcon(trashIcon))
            remButton.clicked.connect(removeCallback(idx))
            wdg.setupInTableLayout(self._childlay,idx,remButton)
            i += 1
        self.nameLabel.setVisible(len(childs) == 0)
        return i

    def setupInTableLayout(self,lay, row, remButton):
        """ Install this widget in the QGridLayout lay """
        def hline():
            line = QtWidgets.QFrame(self)
            line.setFrameShape(QtWidgets.QFrame.HLine)
            line.setFrameShadow(QtWidgets.QFrame.Sunken)
            return line
        # Add the remove button to the top
        # The remove button is given as an argument
        # to this function.
        self._topLay.addWidget(hline())
        self._topLay.addWidget(remButton)
        self._topLay.addWidget(hline())
        # And this widget to the GridLayout
        lay.addWidget(self, row,0,1,3)

    def addOne(self):
        """ Add a new entry to the list using
            the default value (prototypeValue)
            of the PropertyInfo of the data
        """
        self.data.pushBack(self.data.prototypeValue())

class GroupWdg(QtWidgets.QGroupBox):
    """ Widget for a group of values """

    class Model(QtCore.QAbstractListModel):
        """ List Model for the autocompletion in 'New Property' Text-Field """
        def __init__(self, data, parent=None):
            super(GroupWdg.Model, self).__init__(parent)
            self.data = data #type: PropertyData

        def newProperties(self):
            """ Return a list of properties which are not
                set in the GroupData
            """
            all = self.data.allAvailableProperties()
            given = [prop.info().name() for prop in self.data.givenProperties()]
            res = []
            for name in all:
                if not name  in given:
                    res.append(all[name])

            # sort properties alphabetically
            res.sort(key=lambda x: x.name())

            # move deprecated properties to the end of the list
            resFinal = []
            resDeprecated = []
            for property in res:
                if property.deprecated():
                    resDeprecated.append(property)
                else:
                    resFinal.append(property)
            resFinal.extend(resDeprecated)

            return resFinal

        def rowCount(self, idx):
            return len(self.newProperties())

        def data(self, idx, role):
            row = idx.row()
            prop = self.newProperties()[row]
            if role == QtCore.Qt.DisplayRole:
                return prop
            if role ==QtCore.Qt.EditRole:
                return prop.name()
            return None

    class Delegate(QtWidgets.QStyledItemDelegate):
        """ The visual Item of a entry in the autocompletion """
        def __init__(self, parent=None):
            super(GroupWdg.Delegate,self).__init__(parent)

        def paint(self, painter, option, idx):
            # super(Delegate, self).paint(painter, option, idx)
            data = idx.data()
            painter = painter #type: QtGui.QPainter
            painter.save()
            # If the mouse is over this item
            if option.state & QtWidgets.QStyle.State_Selected:
                painter.fillRect(option.rect,option.palette.highlight())
                painter.setBrush(option.palette.highlightedText())
            else:
                painter.fillRect(option.rect,option.palette.base())
            font = painter.font() #type: QtGui.QFont
            # Strike out if the data is deprecated
            font.setStrikeOut(data.deprecated())
            painter.setFont(font)
            painter.drawText(option.rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, data.name())
            painter.restore()

    def __init__(self, data,  parent=None):
        super(GroupWdg, self).__init__(parent)
        self.name = ""
        self._topLay = QtWidgets.QHBoxLayout()
        self._editable = True

        # If data is a ProeprtyDataObject we get more
        # infos which we can use.
        if isinstance(data, PropertyDataObject):
            self.setToolTip(getTooltipString(data.info().description()))
            self.name = data.info().name()
            self._editable = data.info().isEditable()
            data = data.value()

        # Titel der Group-Box
        self.setTitle(self.name)

        self.data = data #type: PropertyData
        self.data.propertyGotGiven.connect(self._addProperty)
        self.data.propertyGotUnGiven.connect(self._buildChilds)

        lay = QtWidgets.QVBoxLayout()
        self.childLay = QtWidgets.QGridLayout()
        # self.childLay.setContentsMargins(2,2,2,2)
        lay.setContentsMargins(3,3,3,3)
        self.childLay.setHorizontalSpacing(2)
        lay.addLayout(self._topLay)
        lay.addLayout(self.childLay)
        lay.addStretch()
        # \/ exclusive
        self.lastChildRow = 0
        self._buildChilds()
        lay.addLayout(self._buildAddLayout())
        self.setLayout(lay)
        self.wdgDict = {}

    def _addProperty(self, property):
        """ Add the property to this group when it become given.
            property is an instance of PropertyDataObject or PropertyData
        """
        def removeCallback(name):
            return lambda: self._removeElement(name)
        # We create a widget depending on the type of the property.
        wdg = WdgCatalog[property.info().typeString()](property,self)
        # Remove Button
        button = QtWidgets.QToolButton(self)
        trashIcon = QtGui.QPixmap('resources/trash.png')
        button.setIcon(QtGui.QIcon(trashIcon))
        wdg.setupInTableLayout(self.childLay, self.lastChildRow, button)
        button.setEnabled(not property.info().isRequired())

        name = property.info().name()
        button.clicked.connect(removeCallback(name))
        self.lastChildRow+=1
        self.wdgDict[property.info().name()] = wdg

    class CompleteLineEdit(QtWidgets.QLineEdit):
        """ The LineEdit with autocompletion """

        """ Signal is emitted when a new text has
            been chosen by the user """
        gotChoice = pyqtSignal(str)

        def __init__(self, parent=None):
            super(GroupWdg.CompleteLineEdit, self).__init__(parent)
            self.returnPressed.connect(lambda: self.gotChoice.emit(self.text()))
            self.gotChoice.connect(self._clear)

        def _clear(self):
            """ Clear completer and text """
            self.completer().setCompletionPrefix("")
            self.clear()

        def focusInEvent(self,ev):
            """ Show completion if the prototxt_editor gets in focus """
            super(GroupWdg.CompleteLineEdit, self).focusInEvent(ev)
            self.showComplete()

        def setCompleter(self, completer):
            super(GroupWdg.CompleteLineEdit,self).setCompleter(completer)
            # completer.activated.connect(self.gotChoice)

        def showComplete(self):
            """ Shows the completion if an completer is set.
                It give the right prefix to the completion.
            """
            if self.completer() is None:
                return
            self.completer().setCompletionPrefix(self.text())
            self.completer().complete()

        def keyPressEvent(self, event):
            """
              Ctrl+Space should show the completer
            """
            super(GroupWdg.CompleteLineEdit,self).keyPressEvent(event)
            ctrl = QtCore.Qt.ControlModifier
            # Qt replace Ctrl with Cmd on macOS but we do not want that
            if platform.system() == "Darwin":
                ctrl = QtCore.Qt.MetaModifier
            if event.modifiers() == ctrl and event.key() == QtCore.Qt.Key_Space:
                self.showComplete()


    def _addElement(self, name):
        """ Add a new property initialized with the default (protoype) value.
            If the name is invalid (e.g. is not a property for this group ),
            the user gets a Popup which informs him
        """
        newOne = self._model.newProperties()
        for item in newOne:
            if item.name() == name:
                self.data.giveProperty(name,item.prototype())
                return
        label = QtWidgets.QLabel(self.tr("This property does not exists"))
        label.setWindowFlags(QtCore.Qt.Popup)
        label.move(self.mapToGlobal(self.editor.geometry().topLeft()+QtCore.QPoint(0,-10)))
        label.show()
        QtCore.QTimer.singleShot(2000, lambda: label.close())

    def _buildAddLayout(self):
        """ Build layout for the autocompletion-LineEdit"""
        lay = QtWidgets.QHBoxLayout()
        # Editor
        self.editor = GroupWdg.CompleteLineEdit()
        self.editor.setPlaceholderText(self.tr("New Property"))
        # Model
        self._model = GroupWdg.Model(self.data)
        # Completer
        completer = QtWidgets.QCompleter()
        completer.setModel(self._model)
        completer.setModelSorting(QtWidgets.QCompleter.CaseInsensitivelySortedModel)
        completer.popup().setItemDelegate(GroupWdg.Delegate(self))
        completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        self.editor.setCompleter(completer)
        lay.addStretch()
        lay.addWidget(self.editor)
        # Signals
        self.editor.gotChoice.connect(self._addElement)
        self.editor.setEnabled(self._editable)
        return lay

    def setupInTableLayout(self,lay, row, remButton):
        """ Setup this widget in parent QGridLayout """
        def hline():
            line = QtWidgets.QFrame(self)
            line.setFrameShape(QtWidgets.QFrame.HLine)
            line.setFrameShadow(QtWidgets.QFrame.Sunken)
            return line
        # Remove button at the top
        self._topLay.addWidget(hline())
        self._topLay.addWidget(remButton)
        self._topLay.addWidget(hline())
        lay.addWidget(self, row,0,1,3)

    def _removeElement(self, name):
        """ Remove the property with the given name from the data
            and this Widget
        """
        self.data.ungiveProperty(name)

    def _clear(self):
        """ Clears all children """
        clearLayout(self.childLay)
        self.lastChildRow = 0
        self.wdgDict = {}

    def _buildChilds(self):
        """ Build the children widget which represent the
            given properties of the PropertyDataGroupObject
        """
        self._clear()
        d = dict([(prop.info().name(), prop) for prop in self.data.givenProperties()])
        keys = d.keys()
        keys.sort()
        for key in keys:
            property = d[key]#type: PropertyDataObject
            self._addProperty(property)

def getTooltipString(description):
    """Ensures that tooltips are shown with newlines. """
    newDescription = ""
    if not description == "":
        newDescription = "<FONT>"
        newDescription += description
        newDescription += "</FONT>"
    return newDescription

WdgCatalog[GroupType] = GroupWdg
WdgCatalog[ListType] = RepeatedWrapper
