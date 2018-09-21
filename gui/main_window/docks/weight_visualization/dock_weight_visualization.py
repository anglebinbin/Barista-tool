import os

from PyQt5.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QMessageBox,
    QWidget,
    QPushButton,
    QFileDialog,
    QSizePolicy
)

from backend.barista.utils.logger import Log
from backend.barista.utils.logger import LogCaller
from backend.caffe import loader
from backend.barista.session.session import Session
from backend.barista.session.client_session import ClientSession
from gui.main_window.docks.dock import DockElement
from gui.main_window.docks.weight_visualization.image_canvas import ImageCanvas
from gui.main_window.docks.weight_visualization.weights import calculateConvWeights
from gui.main_window.docks.weight_visualization.weights import loadNetParameter


class DockElementWeightPlotter(DockElement, LogCaller):
    """ This dock element displays the weights of a layer in a selected
    session's snapshot. Currently only convolutional layer are supported.
    The canvas renders the convolutional filter's weights in a grid layout.
    The selection of sessions, snapshots and layers is possible by selecting
    them in one of the three comboboxes.
    """

    ALLOWED_LAYERTYPES = {"Convolution"}

    class SelectComboBox(QComboBox):
        """ This class is a template for the combobox needed to choose the snapshots, layers, and session"""
        # emptyMessage gets printed on the Combobox when no element has been added to it.
        def __init__(self, emptyMessage):
            QComboBox.__init__(self)
            # Change layout to neatly fit the text
            self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)
            self.setSizeAdjustPolicy(self.AdjustToContents)

            self.__emptyMessage = emptyMessage

        def replaceItems(self, idList):
            """ Replace all items with the current List"""
            self.clear()
            if idList is None or idList == []:
                self.setEnabled(False)
                self.addItems([self.__emptyMessage])
                self.setCurrentText(self.__emptyMessage)
            else:
                self.setEnabled(True)
                QComboBox.addItems(self, idList)

    def __init__(self, mainWindow, title):
        DockElement.__init__(self, mainWindow, title)

        self.caller_id = None

        self.__setupGui()

        # Initialize the comboboxes needed
        self.sessionComboBox.activated['QString'].connect(self.__setCurrentSession)
        self.snapshotComboBox.activated['QString'].connect(self.__setCurrentSnapshot)
        self.layerComboBox.activated['QString'].connect(self.__setCurrentLayer)

        self.__currentSessionId = None
        self.__currentSnapshotId = None
        self.__currentLayerName = None
        self.__currentNet = None

        self.__sessionDict = {}
        # Stores the snapshots which has been selected by the user, to load them faster the next time they are needed.
        self.__alreadyOpenSnapshots = {}

    def __setupGui(self):
        """Add layouts and populate them with widgets"""
        self.mainWidget = QWidget()
        self.mainLayout = QVBoxLayout(self.mainWidget)
        self.setWidget(self.mainWidget)

        # Create the comboboxes to select a visualization.
        self.selectionLayout = QHBoxLayout()
        self.mainLayout.addLayout(self.selectionLayout)
        self.sessionComboBox = DockElementWeightPlotter.SelectComboBox("No sessions")
        # Set the sessionComboBox's size policy to force it to display the whole name.
        self.sessionComboBox.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.selectionLayout.addWidget(self.sessionComboBox)
        self.snapshotComboBox = DockElementWeightPlotter.SelectComboBox("No snapshots")
        self.selectionLayout.addWidget(self.snapshotComboBox)
        self.layerComboBox = DockElementWeightPlotter.SelectComboBox("No layers")
        self.selectionLayout.addWidget(self.layerComboBox)
        # Create the 'Save as Image..' button right aligned and connect it's signal.
        self.selectionLayout.addStretch()
        self.saveImageButton = QPushButton("Save as Image..")
        self.saveImageButton.clicked.connect(self.__saveImage)
        self.selectionLayout.addWidget(self.saveImageButton)
        # Create the canvas to display the plot.
        self.canvasWidget = ImageCanvas()
        self.mainLayout.addWidget(self.canvasWidget)


    def __setCurrentSession(self, sid):
        if self.__currentSessionId == sid:
            return
        self.__currentSessionId = sid
        self.__updateSnapshotList()
        self.__updateLayerList()
        self.__updateCanvas()

    def __setCurrentSnapshot(self, sid):
        if self.__currentSnapshotId == sid:
            return
        self.__currentSnapshotId = sid
        self.__updateCanvas()

    def __setCurrentLayer(self, lid):
        if self.__currentLayerName == lid:
            return
        self.__currentLayerName = lid
        self.__updateCanvas()

    def __updateCanvas(self):
        """ Updates the current shown picture with the current settings """
        # Load model
        self.__currentNet = self.__getNetwork()
        if self.__currentNet:
            self.saveImageButton.setEnabled(True)
            image = calculateConvWeights(self.__currentNet, self.__currentLayerName)
            if image is not None:
                self.canvasWidget.showImage(image)
            self.canvasWidget.show()
        else:
            # Hide canvas when no snapshot, session or layer can be chosen
            self.canvasWidget.hide()
            self.saveImageButton.setEnabled(False)

    def __getNetwork(self, sess_id=None, snap_id=None):
        """ Return the caffe network of the current session and snapshot.
        """
        if sess_id is None:
            sess_id = self.__currentSessionId
        if snap_id is None:
            snap_id = self.__currentSnapshotId
        if sess_id and snap_id:
            # Creates a Dictionary of Sessions Ids, which contains Snapshot Ids
            # which point to Layer Id which point to
            # already opened Networks.
            net = None
            if sess_id in self.__alreadyOpenSnapshots:
                session_snapshots = self.__alreadyOpenSnapshots[sess_id]
                if snap_id in session_snapshots:
                    net = session_snapshots[snap_id]
            if net:
                # cached net found
                return net
            else:
                # snapshot was accessed for the first time
                # create and cache the net
                session = self.__sessionDict[sess_id]
                snapName = snap_id.replace('solverstate', 'caffemodel')
                if isinstance(session, ClientSession):
                    net = session.loadNetParameter(snapName)
                    if net is None:
                        return
                else:
                    snapshotPath = session.getSnapshotDirectory()
                    snapshotPath = str(os.path.join(snapshotPath, snapName))
                    if not os.path.exists(snapshotPath):
                        Log.error('Snapshot file '+snapshotPath+' does not exist!', self.getCallerId())
                        return
                    net = loadNetParameter(snapshotPath)
                if net is not None:
                    if sess_id not in self.__alreadyOpenSnapshots.keys():
                        self.__alreadyOpenSnapshots[sess_id] = {snap_id: net}
                    else:
                        self.__alreadyOpenSnapshots[sess_id][snap_id] = net
                    return net
                else:
                    # Show a warning message
                    Log.error('The hdf5 snapshot format is not supported for the weight visualization! '
                              'This can be changed by setting the snapshot_format parameter in the solver properties.', self.getCallerId())

    def updatePlotter(self, sessionDict):
        """ Updates the comboboxes and redraws the weight image.
        """
        # convert ids to string
        self.__sessionDict = {
            "Session " + str(sid):
            session for sid, session in sessionDict.iteritems()
        }
        self.__updateSessionsList()
        self.__updateSnapshotList()
        self.__updateLayerList()
        self.__updateCanvas()

    def __updateSessionsList(self):
        """ Should be called, if the Id-List changes. Updates the session
        Combobox.
        """
        # get a ordered List from the session-dictionary
        idList = map(
            lambda tuple: tuple[0],
            sorted(self.__sessionDict.items(),
                   key=lambda id: id[1].getSessionId()))
        # updates the sessionCombobox with the current sessions
        self.sessionComboBox.replaceItems(idList)

        # Tries to apply the last selected session, if it exist (could be
        # deleted). If not, select the last one(assume sorted)
        if self.__currentSessionId is None or self.__currentSessionId not in idList:
            if idList == []:
                self.__currentSessionId = None
            else:
                self.__currentSessionId = idList[-1]
        self.sessionComboBox.setCurrentText(self.__currentSessionId)

    def __updateSnapshotList(self):
        """ Should be called, if the Id-List changes. Updates the snapshot
        Combobox.
        """
        # assert that there is a current session to show
        if self.__currentSessionId is not None:
            snapshotDict = self.__sessionDict[self.__currentSessionId].getSnapshots()
            snapshotsIdList = map(
                lambda tuple: tuple[1],
                sorted(snapshotDict.items(), key=lambda id: id[0]))
        else:
            snapshotsIdList = []
        # update the snapshotCombobox with the current snapshots
        self.snapshotComboBox.replaceItems(snapshotsIdList)
        # Select the last snapshot, or None if there are none
        if not snapshotsIdList == []:
            self.__currentSnapshotId = snapshotsIdList[-1]
        else:
            self.__currentSnapshotId = None
        self.snapshotComboBox.setCurrentText(self.__currentSnapshotId)

    def __updateLayerList(self):
        """ Update the layer list with available layers found in the net
        description.
        """

        # getLayers

        if self.__currentSessionId is not None:
            session = self.__sessionDict[self.__currentSessionId]
            if isinstance(session, ClientSession):
                netInternal = session.loadInternalNetFile()
                currentNetwork = loader.loadNet(netInternal)
                layerNames = map(
                    lambda layer: layer["parameters"]["name"],
                    filter(
                        lambda layer: layer["type"].name() in self.ALLOWED_LAYERTYPES,
                        currentNetwork["layers"].values()
                    )
                )
                layerNameList = sorted(layerNames)
            else:
                try:
                    currentNetworkPath = session.getInternalNetFile()
                    file = open(currentNetworkPath, 'r')
                    currentNetwork = loader.loadNet(file.read())
                    # get all the names of the layers, which match the desired type
                    layerNames = map(
                        lambda layer: layer["parameters"]["name"],
                        filter(
                            lambda layer: layer["type"].name() in self.ALLOWED_LAYERTYPES,
                            currentNetwork["layers"].values()
                        )
                    )
                    layerNameList = sorted(layerNames)
                except IOError:
                    callerId = Log.getCallerId('weight-plotter')
                    Log.error("Could not open the network of this session.", callerId)
                    layerNameList =[]
        else:
            layerNameList =[]
        # updates the layer Combobox with the current layers
        self.layerComboBox.replaceItems(layerNameList)
        if self.__currentLayerName is None or self.__currentLayerName not in layerNameList:
            if not layerNameList == []:
                self.__currentLayerName = layerNameList[-1]
            else:
                self.__currentLayerName = None
        self.layerComboBox.setCurrentText(self.__currentLayerName)

    def __saveImage(self):
        """ Gives the user the opportunity to save the image on disk.
            The user can choose from allowed extension, and is alerted if the entered extension is not valid.
            If no extension is entered by the user, the extension is set to png.
        """
        allowedExtensions = [".png", ".bmp", ".jpeg", ".jpg"]
        allowedAsString = str(reduce(lambda x, y: x + y, map(lambda x: " *" + x, allowedExtensions)))
        callerId = self.getCallerId()
        try:
            filename = ""
            # While the entered extension does not matches the allowd extensions
            while not self.__validateFilename(filename, allowedExtensions):
                fileDialog = QFileDialog()
                fileDialog.setDefaultSuffix("png")
                filenameArray = fileDialog.getSaveFileName(
                    self,
                    "Save File",
                    filename,
                    allowedAsString
                )
                filename = filenameArray[0]
                if filename != "":
                    _, extension = os.path.splitext(filename)
                    # If no extension has been entered, append .png
                    if extension == "":
                        filename += ".png"
                else:
                    # If user clicks on abort, leave the loop
                    break
                # Show an alert message, when an unknown extension has been entered
                if not  self.__validateFilename(filename, allowedExtensions):
                    msg = QMessageBox()
                    msg.setIcon(QMessageBox.Warning)
                    msg.setWindowTitle("Warning")
                    msg.setText("Please enter a valid extension:\n"
                                + allowedAsString)
                    msg.exec_()
            if filename != "":
                if self.__currentNet:
                    image = calculateConvWeights(self.__currentNet, self.__currentLayerName)
                    self.canvasWidget.saveImage(image, filename)
                    Log.log("Saved image under " + filename, callerId)
                else:
                    Log.error("Try to save image of weights without a network being loaded.", callerId)
        except Exception as e:
            Log.error("Saving the file failed. " + str(e), callerId)

    # LogCaller

    def getCallerId(self):
        """ Return the unique caller id for this session
        """
        if self.caller_id is None:
            self.caller_id = Log.getCallerId('weight-plotter')
        return self.caller_id

    def __validateFilename(self, filename, allowedExtensions):
        """ Checks if filename is valid, returns corresponding boolean"""
        _, extension = os.path.splitext(filename)
        if extension not in allowedExtensions:
            return False
        else:
            return True
