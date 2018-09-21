import copy
import os
from shutil import copyfile

import backend.caffe.proto_info as info
from backend.barista.utils.logger import Log
from backend.caffe import loader
from backend.caffe import saver
from backend.caffe.dict_helper import DictHelper
from gui.input_manager.database_object import DatabaseObject


class DeployedNet:
    """Based on a given network dictionary, an instance of this class (creates and) provides all data necessary to
    export a deployed version of the network.

    The applied rules are based on the information provided in the following caffe wiki page:
    https://github.com/BVLC/caffe/wiki/Using-a-Trained-Network:-Deploy

    In summary, the following actions are performed automatically:
    - remove all data layers
    - remove all layers that require any labels
    - insert new input layers
    - append a new Softmax layer (only if none does exist yet and a SoftmaxWithLoss layer used to be included)

    Finally, by calling saveProtoTxtFile() the following is done:
    - copy the modified prototxt file and the associated caffe model file to the

    Restrictions:
    - Each data layer must not have more than two top blobs (a general restriction of caffe). Raises a warning.
    - At least the label blob name must follow the naming conventions (so it's always called "label"). Raises a warning.
    - The shape of a Data layer can only be determined automatically, if the layer type is either "Data"
      (LMDB or LEVELDB) or "HDF5Data". Otherwise, a warning will inform the user about necessary manual changes.
    """

    def __init__(self, netPrototxtContents):
        """Create a deployment version of the given network.

        netPrototxtContents: string
            The contents of the prototxt file to deploy.
        """

        # create a logger id
        self._logId = Log.getCallerId('deployment')
        self._originalNetworkDictionary = loader.loadNet(netPrototxtContents)
        # init further attributes
        self._dataLayers = dict()  # a dictionary containing all data layers. keys are the layer ids.
        self._labelBlobNames = []  # a list containing all names of blobs, that represent any labels
        self._dataBlobNames = []  # a list containing all names of blobs, that represent any input data
        self._inputBlobShapes = dict()  # the keys of this dictionary equal self._dataBlobNames.
        self._deployedNetworkDictionary = copy.deepcopy(self._originalNetworkDictionary)
        self._dHelper = DictHelper(self._deployedNetworkDictionary)

        # start deployment
        self._createDeployedNetwork()

    def _createDeployedNetwork(self):
        """Create a deployed version of self._originalNetworkDictionary and save it in self._deployedNetworkDictionary.

        Requires self._originalNetworkDictionary to be set before.
        """
        # ensure that at least one layer does exist
        if len(self._deployedNetworkDictionary["layers"]) <= 0:
            raise ValueError("Can not create deployment network, because the original one does not contain any layers.")

        self._searchDataLayers()
        self._removeDataLayers()
        self._removeLayersUsingLabels()
        self._insertInputLayers()
        self._addSoftmax()

    def getProtoTxt(self):
        """return the content of self._deployedNetworkDictionary as a prototxt string."""

        return saver.saveNet(self._deployedNetworkDictionary)

    def _searchDataLayers(self):
        """Search for all data layers in self._originalNetworkDictionary and store them in self._dataLayers.

        Additionally, the names of all top blobs containing label data will be saved in self._labelBlobNames.
        """
        nLabelBlobUndetermined = 0  # check whether some label blobs couldn't be determined automatically
        nTooManyTopBlobs = 0  # check whether some data layers do have too many top blobs
        for id, layer in self._originalNetworkDictionary["layers"].iteritems():
            if layer["type"].isDataLayer():
                self._dataLayers[id] = layer

                # validate number of top blobs
                if "top" in layer["parameters"] and len(layer["parameters"]["top"]) > 2:
                    nTooManyTopBlobs += 1

                # remember the associated label blob name
                labelBlobName = self._getLabelBlobName(layer)
                if labelBlobName is not None and labelBlobName not in self._labelBlobNames:
                    self._labelBlobNames.append(labelBlobName)
                elif labelBlobName is None:
                    nLabelBlobUndetermined += 1

                # remember the associated data blob name and its shape
                dataBlobName = self._getDataBlobName(layer)
                if dataBlobName is not None and dataBlobName not in self._dataBlobNames:
                    self._dataBlobNames.append(dataBlobName)

                    # calculate the shape (this assumes that data layers with the same name are using the same shape)
                    blobShape = []  # will be left empty, if shape cannot be calculated automatically
                    if layer["type"].name() in ["Data", "HDF5Data"]:

                        if layer["type"].name() == "Data":
                            path = layer["parameters"].get("data_param", {}).get("source")
                            type = layer["parameters"].get("data_param", {}).get("backend")
                        elif layer["type"].name() == "HDF5Data":
                            path = layer["parameters"].get("hdf5_data_param", {}).get("source")
                            type = "HDF5TXT"

                        if path is not None and type is not None:
                            db = DatabaseObject()
                            db.openFromPath(path, type)
                            blobShapeTupel = db.getDimensions()
                            if blobShapeTupel is not None:
                                blobShapeTupel = blobShapeTupel.get(dataBlobName)
                                if blobShapeTupel is not None:
                                    blobShape = list(blobShapeTupel)

                    self._inputBlobShapes[dataBlobName] = blobShape

        # show warning, if some label blobs do not have the correct name
        if nLabelBlobUndetermined > 0:
            Log.log("{} data layers might have been handled incorrectly, because their top blobs are named "
                    "unconventionally. Please change the name of the blobs which provide labels to \"label\".".format(
                nLabelBlobUndetermined
            ), self._logId)

        # show warning, if some data layers have too many top blobs
        if nTooManyTopBlobs > 0:
            Log.log("{} data layers have too many top blobs. The native caffe version does support only a maximum of 2 "
                    "top blobs per data layer. Deployment result might be incorrect.".format(
                nTooManyTopBlobs
            ), self._logId)


    def _removeDataLayers(self):
        """Remove all data layers from the deployed Network."""
        for id, layer in self._dataLayers.iteritems():
            self._dHelper.removeLayer(id)

    def _removeLayersUsingLabels(self):
        """Remove all layers that require labels as an input."""
        # iterate over the original(!) net, but delete from the deployment(!) net
        for id, layer in self._originalNetworkDictionary["layers"].iteritems():
            if self._isLayerRequiringLabels(layer):
                self._dHelper.removeLayer(id)

    def _isLayerRequiringLabels(self, layer):
        """Return true, iff the given layer requires any labels as an input."""
        if "bottom" in layer["parameters"]:
            for bottomBlob in layer["parameters"]["bottom"]:
                if bottomBlob in self._labelBlobNames:
                    return True
        return False

    def _getLabelBlobName(self, layer):
        """Get the name of the layer's top blob that represents any labels.

        Require: layer must be a data layer.
        According to http://caffe.berkeleyvision.org/tutorial/data.html, the label blob is always called "label".
        Note: This method might need to be adjusted to be able handling further special cases.
        """
        if "top" in layer["parameters"] and "label" in layer["parameters"]["top"]:
            return "label"
        else:
            return None

    def _getDataBlobName(self, layer):
        """Get the name of the layer's top blob, that represents any input data.

        Require: layer must be a data layer.
        According to http://caffe.berkeleyvision.org/tutorial/data.html, the data blob is always called "data". However,
        the following implementation allows handling (some) special cases by changing only the implementation of
        _getLabelBlobName().
        """
        labelBlobName = self._getLabelBlobName(layer)
        if "top" in layer["parameters"]:
            for topBlobName in layer["parameters"]["top"]:
                if topBlobName != labelBlobName:
                    return topBlobName
        return None

    def _insertInputLayers(self):
        """Insert new input layers with fixed dimensions.

        Note that, the number of newly-added input layer might be lower than the number of previously-removed data
        layers. On the one hand, we will add only one new input layer for each unique data blob name, while multiple
        data layers might have used the same data blob name. On the other hand, input layers will only be added, if
        at least one other layer is using the provided data.
        """
        inputLayerType = info.CaffeMetaInformation().availableLayerTypes()["Input"]
        inputLayerNr = 1
        for dataBlobName in self._dataBlobNames:

            # create a new input layer with default values and add it to the deployment net
            name = self._getNewInputLayerName(inputLayerNr)
            inputLayer, inputLayerId = self._dHelper.addLayer(inputLayerType, name, inputLayerNr-1)

            # modify the layer template
            inputLayer["parameters"]["top"] = [dataBlobName]

            # set input_param.shape with batch size 1 and the dimensions of the first data element
            inputLayer["parameters"]["input_param"] = dict()
            inputLayer["parameters"]["input_param"]["shape"] = []
            inputLayer["parameters"]["input_param"]["shape"].append(dict())
            inputLayer["parameters"]["input_param"]["shape"][0]["dim"] = self._inputBlobShapes[dataBlobName]
            inputLayer["parameters"]["input_param"]["shape"][0]["dim"].insert(0, 1)

            # prepare next input layer
            inputLayerNr += 1

        # check whether there is any shape that could not be determined automatically and needs to be set manually
        inputShapeWarning = False
        for inputShape in self._inputBlobShapes:
            if len(inputShape) < 1:
                inputShapeWarning = True
                break
        if inputShapeWarning:
            Log.log("At least one input shape could not be determined automatically. Please open the created prototxt "
                    "and manually fix all input shapes which include only the batch size (1).", self._logId)

    def _getNewInputLayerName(self, inputLayerNr):
        """Get the name for a new input layer.

        If only one input layer will be added, the name will always be "data". Otherwise, inputLayerNr will be added as
        a suffix.
        """
        name = "data"

        if len(self._dataBlobNames) > 1:
            name += str(inputLayerNr)

        return name

    def _addSoftmax(self):
        """Add a softmax layer to the very end of the net, but only if a SoftmaxWithLoss layer was used before."""

        # check whether the net used to contain a SoftmaxWithLoss layer
        softmaxWithLossWasUsed = False
        for id, layer in self._originalNetworkDictionary["layers"].iteritems():
            if layer["type"].name() == "SoftmaxWithLoss":
                softmaxWithLossWasUsed = True
                break

        if softmaxWithLossWasUsed:
            # ensure that the remaining deployment net has at least one layer
            if len(self._deployedNetworkDictionary["layers"]) > 0:

                softmaxLayerType = info.CaffeMetaInformation().availableLayerTypes()["Softmax"]

                # do not add another softmax, if the current deployment network already contains one
                softmaxAlreadyIncluded = False
                for id, layer in self._deployedNetworkDictionary["layers"].iteritems():
                    if layer["type"].name() == softmaxLayerType.name():
                        softmaxAlreadyIncluded = True
                        break

                if not softmaxAlreadyIncluded:
                    # get the very last layer
                    lastLayerId = self._deployedNetworkDictionary["layerOrder"][-1]
                    lastLayer = self._deployedNetworkDictionary["layers"][lastLayerId]

                    # ensure that the determined last layer does have a top blob
                    if "top" in lastLayer["parameters"] and len(lastLayer["parameters"]["top"]) > 0:

                        # create new softmax layer with default values and add it to the deployment net
                        name = "softmax"
                        position = len(self._deployedNetworkDictionary["layers"])
                        softmaxLayer, softmaxLayerId = self._dHelper.addLayer(softmaxLayerType, name, position)

                        # connect the softmax layer with the existing network
                        softmaxLayer["parameters"]["bottom"] = [lastLayer["parameters"]["top"][0]]

                        # name the output
                        softmaxLayer["parameters"]["top"] = ["probabilities"]
                    else:
                        Log.log("Could not add Softmax layer as the very last layer of the deployment net does not have any "
                                "top blobs.",
                                self._logId)
            else:
                Log.log("Could not add Softmax layer as the remaining deployment net does not have any layers.",
                        self._logId)
