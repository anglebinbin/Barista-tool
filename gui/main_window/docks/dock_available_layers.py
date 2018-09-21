from PyQt5 import QtCore, QtWidgets
from PyQt5 import QtGui

import backend.caffe.proto_info as info
from gui.main_window.docks.dock import DockElement

class DockElementLayers(DockElement):
    def __init__(self, mainWindow, title):

        # Set title and initialize the dock widget
        DockElement.__init__(self, mainWindow, title)
        self.name = title
        widget = QtWidgets.QWidget()
        self.layout = QtWidgets.QVBoxLayout()

        # Add the text field and the layer list to the widget
        self.addDescription()
        self.addTextfieldForSearch()
        self.addListOfAllLayers()

        self.allLayersDict = info.CaffeMetaInformation().availableLayerTypes()
        self.allLayers = self.dictionaryToList(self.allLayersDict)
        self.setAllLayersNewLayerList(self.allLayers)

        widget.setLayout(self.layout)
        self.setWidget(widget)

    def addDescription(self):
        descriptionLabel = QtWidgets.QLabel("Drag and drop any of the available layers to the network canvas to add a new layer.", self)
        descriptionLabel.setObjectName("infoText")
        descriptionLabel.setWordWrap(True)
        # Set the object name so that the global stylesheet for info text will be applied.
        # descriptionLabel.setStyleSheet("color: rgba(0, 0, 0, 125)")
        self.layout.addWidget(descriptionLabel)

    def addTextfieldForSearch(self):
        textField = QtWidgets.QLineEdit(self)
        textField.setPlaceholderText("Search for Layers")
        textField.textChanged.connect(self.searchForLayers)
        self.layout.addWidget(textField)

    def addListOfAllLayers(self):
        #used: http://pyqt.sourceforge.net/Docs/PyQt4/qlistwidget.html
        self.allLayersWindow = QtWidgets.QListWidget(self)

        # Enable dragging of list elements, connect item pressed action so that current item is saves for drag and drop
        self.allLayersWindow.setDragEnabled(True)
        self.allLayersWindow.itemPressed.connect(self.startDragAction)

        #show all Layers in list
        self.layout.addWidget(self.allLayersWindow)

        self.updateListOfAllLayers()

    def updateListOfAllLayers(self):
        info.CaffeMetaInformation().updateCaffeMetaInformation()
        self.allLayersDict = info.CaffeMetaInformation().availableLayerTypes()
        self.allLayers = self.dictionaryToList(self.allLayersDict)
        self.setAllLayersNewLayerList(self.allLayers)
        self.updateAllLayersWindowNewList(self.allLayers)

    def dictionaryToList(self,dictionary):
        list = [None]*len(dictionary)
        for i in range(0,len(dictionary)):
            list[i] = dictionary.keys()[i]
        return list

    def setAllLayersNewLayerList(self,list):
        self.allLayers = list

    def setAllLayersAddLayerList(self, list):
        '''this function adds the layername that are in list to the list self.allLayers'''
        for i in range(0,len(list)):
            isIn =1
            for j in range(0,len(self.allLayers)):
                if list[i] == self.allLayers[j]:
                    isIn = 0

            if(isIn):
                self.allLayers.append(list[i])

    def updateAllLayersWindowNewList(self,newList):
        '''this function updates the list that shows the Layer with a given list,
        in this main_window are only the names of the layers represented'''
        self.allLayersWindow.clear()
        for i in range(0,len(newList)):
            self.allLayersWindow.addItem(newList[i])
        self.allLayersWindow.sortItems(0)

    def updateAllLayersWindowAddList(self,listToAdd):
        '''this function updates the layerwindow and adds the given list to the layers that are allready shown,
        in this main_window are only the name of the layers represented'''
        for i in range(0,len(listToAdd)):
            if len(self.allLayersWindow.findItems(listToAdd[i],QtCore.Qt.MatchExactly)) is 0:
                self.allLayersWindow.addItem(listToAdd[i])
        self.allLayersWindow.sortItems(0)

        #todo: write a function to search for a special layer and show only that one
    def searchForLayers(self,layerName):
        list = []
        #search in list of all Layers which are layerName
        for i in range(0,len(self.allLayers)):
            if layerName.lower() in self.allLayers[i].lower():
                list.append(self.allLayers[i])
        self.updateAllLayersWindowNewList(list)


        #todo: create a function to drag and drop the layer into the main main_window to create a new network
    def startDragAction(self):
        mimeData = QtCore.QMimeData()
        mimeData.setText(self.allLayersWindow.currentItem().text())

        drag = QtGui.QDrag(self)
        drag.setMimeData(mimeData)

        drag.exec_()

    def disableEditing(self, disable):
        """ Disable the table with all available layers. """
        if self.allLayersWindow:
            self.allLayersWindow.setDisabled(disable)
