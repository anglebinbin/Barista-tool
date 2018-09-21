from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import QModelIndex, QVariant
from gui.main_window.docks.properties.property_widgets.data import *

class PropertiesSuggestionModel(QtCore.QAbstractListModel):
    def __init__(self, data=None, parent=None):
        super(PropertiesSuggestionModel, self).__init__(parent)
        self.data = data

    def newProperties(self):
        """ Return a list of properties which are not
            set in the GroupData
        """
        if self.data is None:
            return []
        # Find suggestions as list of available properties that have not been given.
        availableProperties = self.data.allAvailableProperties()
        givenProperties = [prop.info().name() for prop in self.data.givenProperties()]
        suggestions = [prop for name, prop in availableProperties.items() if name not in givenProperties]
        # Sort properties alphabetically.
        suggestions.sort(key=lambda x: x.name())

        # Move deprecated properties to the end of the list.
        suggestionsFinal = []
        suggestionsDeprecated = []
        for prop in suggestions:
            if prop.deprecated():
                suggestionsDeprecated.append(prop)
            else:
                suggestionsFinal.append(prop)
        suggestionsFinal.extend(suggestionsDeprecated)
        return suggestionsFinal

    def rowCount(self, index):
        return len(self.newProperties())

    def data(self, index, role):
        if not index.isValid():
            return QVariant()
        row = index.row()
        if row >= len(self.newProperties()):
            return QVariant()
        prop = self.newProperties()[row]
        if role == QtCore.Qt.ToolTipRole:
            if prop.description() == '':
                return '<FONT>No info available.</FONT>'
            return '<FONT>' + prop.description() + '</FONT>'
        if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
            return prop.name() + ' [' + prop.typeString() + ']'
        if role == QtCore.Qt.UserRole:
            return prop
        return QVariant()

    def update(self):
        self.modelReset.emit()
