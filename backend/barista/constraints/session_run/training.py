"""
This subpackage contains all constraints that need to be ensured before/during the training only.
So the given methods need to be called each time a new training session is about to be started.
"""
import os
from PyQt5 import QtWidgets

from backend.barista.constraints import common
from backend.caffe.proto_info import CaffeMetaInformation
from gui.network_manager.layer_helper import LayerHelper
from backend.caffe.proto_info import UnknownLayerTypeException


def checkMinimumTrainingRequirements(session, parentGui=None, reportToUser=True):
    """ Check whether the minimum requirements for starting a new training session are met.

    This method should be called whenever a new training session is about to be started. If the returned value isn't
    True, the session start should be aborted.
    TODO implement the same for a evaluation-only net.
    If reportToUser is set to True, which is the default value, the user will be informed about unmet requirements by a 
    message box, including an option to ignore all listed errors.
    :return: True, if everything is okay. False otherwise.
    """

    # validate
    requirements = MinimumTrainingRequirements(session)
    valid = requirements.valid()
    session.setErrorList(requirements.getErrors())
    # list errors and let the user decide whether to ignore the errors
    if (parentGui is not None):
        if reportToUser and not valid:
            valid = requirements.showErrors(parentGui)
        return valid
    else:  # if there is no GUI, return the Error Messages
        return requirements.getErrors()


class MinimumTrainingRequirements:
    """This class is only required inside of checkMinimumTrainingRequirements.

    Do not use as a public interface.
    """
    def __init__(self, session):
        self._session = session

        self._stateData = None
        if session.state_dictionary:
            self._stateData = session.state_dictionary

        # store one error message per unmet requirement in the following list
        self._errorMessages = []

        # start validation
        self._check()

    def showErrors(self, parentGui):
        """ If any errors have been collected, show them in a message box.

        Additionally, to the listed errors, the user will get an option to ignore all errors.
        :param parentGui: The parent GUI to which the shown message box will be bounded.
        :return: Return true, iff no errors occured or the user decided to ignore them.
        """
        valid = self.valid()

        if not valid:
            # accumulate collected error data
            msg = ""
            for msg_part in self._errorMessages:
                if len(msg) > 0:
                    msg += "\n\n"
                msg += msg_part

            # configure message box
            msgBox = QtWidgets.QMessageBox(parentGui)
            msgBox.setIcon(QtWidgets.QMessageBox.Warning)
            msgBox.setText(parentGui.tr("Please check the following constraints.\nIf you decide to ignore this message, "
                                     "it might result in a program crash."))
            msgBox.setInformativeText(parentGui.tr(msg))
            msgBox.setWindowTitle(parentGui.tr("Minimum training requirements aren't met."))
            msgBox.setParent(parentGui)
            msgBox.setStandardButtons(QtWidgets.QMessageBox.Ignore | QtWidgets.QMessageBox.Ok)
            msgBox.setDefaultButton(QtWidgets.QMessageBox.Ok)

            # show message box and receive user input
            clickedButton = msgBox.exec_()

            # if the user clicked "ignore", all errors will be ignored
            valid = clickedButton == QtWidgets.QMessageBox.Ignore

        return valid

    def valid(self):
        """Check whether any constraint has been broken."""
        return len(self._errorMessages) == 0

    def getErrors(self):
        return self._errorMessages

    def _check(self):
        """Start all validations."""
        # TODO check type(self._session) for <class 'backend.barista.session.client_session.ClientSessions'>
        # temporary change the current working dir to allow evaluation of relative paths
        if hasattr(self._session, 'checkTraining'):
            self._errorMessages.extend(self._session.checkTraining())
        elif self._checkLayers():
            self._checkSolver()
            self._checkDataLayerExistence()
            self._checkDataLayerParameters()
            self._checkInputLayer()
            self._checkUniqueBlobNames()

    def _checkLayers(self):
        """Checks ify the network contains layers that are not compatible with the current caffe-version"""
        if  self._stateData is not None:
            layers = []
            for layer in self._stateData["network"]["layers"]:
                layers.append(self._stateData["network"]["layers"][layer]["parameters"]["type"])
            
            try:
                for layer in layers:
                    typename = CaffeMetaInformation().getLayerType(layer)
            except UnknownLayerTypeException as e:
                self._errorMessages.append((e._msg, "Unknown Layer"))
                return False
        return True

    def _checkSolver(self):
        """Check whether all solver constraints are valid."""
        # the base learning rate should be a positive number
        if not hasattr(self._stateData, '__getitem__'):
            self._errorMessages.append(("State data is empty!","..."))
            return
        if self._stateData["solver"] == {u'net': u'net-internal.prototxt'}:
            self._errorMessages.append(("The solver seems to be empty. Please import or define  a solver.\n"
                                       "(You can define a solver with the help of the dock Solver Properties)","No solver."))
        if not ("base_lr" in self._stateData["solver"]
                and common.isPositiveNumber(self._stateData["solver"]["base_lr"])):
            self._errorMessages.append(("The base learning rate (base_lr) must be a positive number.","Invalid base_lr."))

        # the maximum number of iterations should be a positive integer
        if not ("max_iter" in self._stateData["solver"]
                and common.isPositiveInteger(self._stateData["solver"]["max_iter"])):
            self._errorMessages.append(("The maximum number of iterations (max_iter) must be a positive integer.","Invalid max_iter."))

    def _checkUniqueBlobNames(self):
        """Checks for duplicate top blob names in all layers and emits error message if duplicates found except
           if in-place is permitted"""
        # find all 'real' sources of blobs, i.e. layers that produce a blob as output and are not in-place
        blobGenerators = {}  # dictionary that saves the sources for every blob name
        if hasattr(self._stateData, '__getitem__'):
            for layer_id, layer in self._stateData["network"]["layers"].iteritems():
                parameters = layer.get("parameters", {})
                tops = parameters.get("top", [])
                bottoms = parameters.get("bottom", [])
                # if at least one top blob is also a bottom, check if layer allows in-place
                sourced = [blob for blob in tops if blob not in bottoms]
                inPlace = [blob for blob in tops if blob in bottoms]
                if len(inPlace) > 0 and not layer["type"].allowsInPlace():
                    for name in inPlace:
                        self._errorMessages.append((
                                        "{} is reproduced by {}".format(name, parameters.get("name", "[NO NAME]")),
                                        "{} does not support in-place operation".format(parameters.get("name",
                                                                                                       "[NO NAME]"))
                        ))
                # check all blobs that are generated in one layer if they are generated only once in each phase.
                for name in sourced:
                    phase = []  # this list can hold train, test and both
                    p = LayerHelper.getLayerPhase(layer)
                    if p == "":
                        phase = [LayerHelper.PHASE_TEST, LayerHelper.PHASE_TRAIN]
                    else:
                        phase.append(p)

                    # if a blob already exists, check if it was generated before in the same Phase
                    if name in blobGenerators:
                        found_match = False
                        for candidate in blobGenerators[name]:
                            intersection = set(phase).intersection(candidate[1])
                            if len(intersection) > 0:
                                found_match = True
                                self._errorMessages.append(("Sources are {} and {} in phase {}".format(
                                    parameters.get("name", "[NO NAME]"),
                                    candidate[0],
                                    list(intersection)[0]),
                                                        "{} is generated by multiple layers".format(name)))
                        if not found_match:
                            blobGenerators[name].append((parameters.get("name", "[NO NAME]"), phase))
                    else:
                        blobGenerators[name] = [(parameters.get("name", "[NO NAME]"), phase)]

    def _checkDataLayerExistence(self):
        """Check whether at least one data layer exists (during the training phase)."""
        nDataLayerTotal = 0
        nDataLayerTraining = 0
        if not hasattr(self._stateData, '__getitem__'):
            self._errorMessages.append(("State data is empty!","Empty state data."))
            return
        if self._stateData["network"]["layers"] == {}:
            self._errorMessages.append(("There is no net defined. Please import or create a network.","No net."))
        try:
            for layer_id, layer in self._stateData["network"]["layers"].iteritems():
                if layer["type"].isDataLayer():
                    nDataLayerTotal += 1
                    if LayerHelper.isLayerIncludedInTrainingPhase(layer):
                        nDataLayerTraining += 1
        except KeyError:
            self._errorMessages.append(("No network data available.","No network data."))

        # list all available data layers to inform the user about possible options
        typeListMsg = ""
        allTypes = CaffeMetaInformation().availableLayerTypes()
        for key in sorted(allTypes):
            if allTypes[key].isDataLayer():
                if typeListMsg != "":
                    typeListMsg += ", "
                typeListMsg += key
        typeListMsg = " Available types of such a layer are: " + typeListMsg + "."

        if nDataLayerTotal == 0:
            self._errorMessages.append(("There should be at least one data layer in your network.\n" + typeListMsg,"No/invalid input data."))
        elif nDataLayerTraining == 0:
            self._errorMessages.append(("There should be at least one data layer in your network that is included in "
                                       "the training phase.\n" + typeListMsg,"No/invalid input data."))

    def _checkDataLayerParameters(self):
        """Check whether the existing data layers (of the training phase) provide (valid) data.

        required parameters were determined based on http://caffe.berkeleyvision.org/tutorial/layers.html
        """
        if not hasattr(self._stateData, '__getitem__'):
            self._errorMessages.append(("State data is empty!","Empty state data."))
            return

        # a list of pairs. first element of a pair is the name of a layer (type).
        # The second one is the name of the missing parameter.
        self._missingLayerParams = []

        for layer_id, layer in self._stateData["network"]["layers"].iteritems():
            if layer["type"].isDataLayer() and LayerHelper.isLayerIncludedInTrainingPhase(layer):

                if layer["type"].name() == "Data":
                    self._checkDataLayer(layer)
                elif layer["type"].name() == "MemoryData":
                    self._checkMemoryDataLayer(layer)
                elif layer["type"].name() == "HDF5Data":
                    self._checkHDF5DataLayer(layer)
                elif layer["type"].name() == "ImageData":
                    self._checkImageDataLayer(layer)
                elif layer["type"].name() == "WindowData":
                    self._checkWindowDataLayer(layer)
                elif layer["type"].name() == "DummyData":
                    self._checkDummyDataLayer(layer)

        for pair in self._missingLayerParams:
            self._errorMessages.append(("The {} layer must provide the {} parameter.".format(
                pair[0],
                pair[1]
            ),"Missing parameter."))

    def _checkDataLayer(self, layer):
        """Validate a layer of type Data."""
        specificParamKey = "data_param"
        if specificParamKey not in layer["parameters"]:
            self._missingLayerParams.append([layer["type"].name(), specificParamKey])
        else:
            specificParams = layer["parameters"][specificParamKey]
            # source
            if "source" not in specificParams:
                self._missingLayerParams.append([layer["type"].name(), specificParamKey + ".source"])
            elif not os.path.isdir(self._makeAbsPath(specificParams["source"])):
                self._errorMessages.append((
                    "The parameter {} of the layer {}\ndoes not seem to point to a valid directory. \n"
                    "Please import and connect databases (via Input Manager).".format(specificParamKey + ".source", layer["type"].name()),
                "No/invalid input data."))
            # TODO check whether the given directory contains files that fit to the given database type.

            # batch_size
            if "batch_size" not in specificParams:
                self._missingLayerParams.append([layer["type"].name(), specificParamKey + ".batch_size"])
            elif not common.isPositiveInteger(specificParams["batch_size"]):
                self._errorMessages.append(("The batch size (of a {} Layer) must be a positive integer.".format(
                    layer["type"].name()
                ),"Invalid batch size."))

    def _checkMemoryDataLayer(self, layer):
        """Validate a layer of type MemoryData."""
        specificParamKey = "memory_data_param"
        if specificParamKey not in layer["parameters"]:
            self._missingLayerParams.append([layer["type"].name(), specificParamKey])
        else:
            specificParams = layer["parameters"][specificParamKey]

            # batch_size
            if "batch_size" not in specificParams:
                self._missingLayerParams.append([layer["type"].name(), specificParamKey + ".batch_size"])
            elif not common.isPositiveInteger(specificParams["batch_size"]):
                self._errorMessages.append(("The batch size (of a {} Layer) must be a positive integer.".format(
                    layer["type"].name()
                ),"Invalid batch size."))

            # channels
            if "channels" not in specificParams:
                self._missingLayerParams.append([layer["type"].name(), specificParamKey + ".channels"])
            elif not common.isPositiveInteger(specificParams["channels"]):
                self._errorMessages.append(("The number of channels (of a {} Layer) must be a positive integer.".format(
                    layer["type"].name()
                ),"Invalid number of channels."))

            # height
            if "height" not in specificParams:
                self._missingLayerParams.append([layer["type"].name(), specificParamKey + ".height"])
            elif not common.isPositiveInteger(specificParams["height"]):
                self._errorMessages.append(("The height parameter (of a {} Layer) must be a positive integer.".format(
                    layer["type"].name()
                ),"Invalid height parameter."))

            # width
            if "width" not in specificParams:
                self._missingLayerParams.append([layer["type"].name(), specificParamKey + ".width"])
            elif not common.isPositiveInteger(specificParams["width"]):
                self._errorMessages.append(("The width parameter (of a {} Layer) must be a positive integer.".format(
                    layer["type"].name()
                ),"Invalid width parameter."))

            # actually, this layer isn't supported in the training at all. however, the above validation is kept to
            # allow using Barista to build(!) a valid net definition without(!) the possibility to start training.
            self._errorMessages.append(('Layers of type "MemoryData" aren\'t supported yet, as the in-memory data\n'
                                       'reference needs to be specified in the code. So you can\'t run a Barista\n'
                                       'session right now. However, you can use Barista to\n'
                                       'build and export a valid net definition containing this layer type.',"..."))

    def _checkHDF5DataLayer(self, layer):
        """Validate a layer of type HDF5Data."""
        specificParamKey = "hdf5_data_param"
        if specificParamKey not in layer["parameters"]:
            self._missingLayerParams.append([layer["type"].name(), specificParamKey])
        else:
            specificParams = layer["parameters"][specificParamKey]
            # source
            if "source" not in specificParams:
                self._missingLayerParams.append([layer["type"].name(), specificParamKey + ".source"])
            elif not os.path.isfile(self._makeAbsPath(specificParams["source"])):
                self._errorMessages.append((
                    "The parameter {} of the layer {}\ndoes not seem to point to a valid "
                    "file.".format(specificParamKey + ".source", layer["type"].name()),"No/invalid input data."))
            # TODO check whether the given file is really a (valid) HDF5 file.

            # batch_size
            if "batch_size" not in specificParams:
                self._missingLayerParams.append([layer["type"].name(), specificParamKey + ".batch_size"])
            elif not common.isPositiveInteger(specificParams["batch_size"]):
                self._errorMessages.append(("The batch size (of a {} Layer) must be a positive integer.".format(
                    layer["type"].name()
                ),"Invalid batch size."))

    def _checkImageDataLayer(self, layer):
        """Validate a layer of type ImageData."""
        specificParamKey = "image_data_param"
        if specificParamKey not in layer["parameters"]:
            self._missingLayerParams.append([layer["type"].name(), specificParamKey])
        else:
            specificParams = layer["parameters"][specificParamKey]
            # source
            if "source" not in specificParams:
                self._missingLayerParams.append([layer["type"].name(), specificParamKey + ".source"])
            elif not os.path.isfile(self._makeAbsPath(specificParams["source"])):
                self._errorMessages.append((
                    "The parameter {} of the layer {}\ndoes not seem to point to a valid "
                    "file.".format(specificParamKey + ".source", layer["type"].name()),"No/invalid input data."))
            # TODO check whether the given file is really a (valid) text file that contains (valid) image paths.

            # batch_size
            if "batch_size" not in specificParams:
                self._missingLayerParams.append([layer["type"].name(), specificParamKey + ".batch_size"])
            elif not common.isPositiveInteger(specificParams["batch_size"]):
                self._errorMessages.append(("The batch size (of a {} Layer) must be a positive integer.".format(
                    layer["type"].name()
                ),"Invalid batch size."))

    def _checkWindowDataLayer(self, layer):
        """Validate a layer of type WindowData.

        Constraints are described here:
        http://caffe.berkeleyvision.org/doxygen/classcaffe_1_1WindowDataLayer.html#details
        """
        specificParamKey = "window_data_param"
        if specificParamKey not in layer["parameters"]:
            self._missingLayerParams.append([layer["type"].name(), specificParamKey])
        else:
            specificParams = layer["parameters"][specificParamKey]
            # source
            if "source" not in specificParams:
                self._missingLayerParams.append([layer["type"].name(), specificParamKey + ".source"])
            elif not os.path.isfile(self._makeAbsPath(specificParams["source"])):
                self._errorMessages.append((
                    "The parameter {} of the layer {}\ndoes not seem to point to a valid "
                    "file.".format(specificParamKey + ".source", layer["type"].name()),"No/invalid input data."))
            # TODO add further validation checks for this type (problem: documentation lacks a lot).

            # batch_size
            if "batch_size" not in specificParams:
                self._missingLayerParams.append([layer["type"].name(), specificParamKey + ".batch_size"])
            elif not common.isPositiveInteger(specificParams["batch_size"]):
                self._errorMessages.append(("The batch size (of a {} Layer) must be a positive integer.".format(
                    layer["type"].name()
                ),"Invalid batch size."))

    def _checkDummyDataLayer(self, layer):
        """Validate a layer of type DummyData.

        Constraints are described in the comments of the caffe.proto file.
        """
        specificParamKey = "dummy_data_param"
        if specificParamKey not in layer["parameters"]:
            self._missingLayerParams.append([layer["type"].name(), specificParamKey])
        else:
            specificParams = layer["parameters"][specificParamKey]

            # shape
            if "shape" not in specificParams:
                self._missingLayerParams.append([layer["type"].name(), specificParamKey + ".shape"])
            elif not len(specificParams["shape"]) >= 1:
                self._errorMessages.append((
                    "The parameter {} of the layer {}\nneeds at least one value.".format(
                        specificParamKey + ".shape", layer["type"].name()
                    ),"Missing parameter."))

    def _checkInputLayer(self):
        """Check for existence of an input layer.

        Note that, this is about the specific layer type called "Input". This is not about the general group of Data
        layers (see tests above).
        """
        if not hasattr(self._stateData, '__getitem__'):
            self._errorMessages.append(("State data is empty!","Empty state data."))
            return

        for layer_id, layer in self._stateData["network"]["layers"].iteritems():
            if layer["type"].name() == "Input":
                self._errorMessages.append(('Layers of type "Input" aren\'t supported yet, as they are usually not meant\n'
                                           'to be included before deploying the net. So you can\'t run a Barista\n'
                                           'session right now. However, you can use Barista to build and export a valid\n'
                                           'net definition containing this layer type.',"..."))
                break

    def _makeAbsPath(self, path):
        # TODO: remove the print once errorMessages are shown to the user
        if os.path.isabs(path):
            return os.path.normpath(path)
        else:  # if path is a relative path, see if it is relative to the session folder
            sessionDir = self._session.getDirectory()
            offsetDir = os.path.normpath(os.path.abspath(sessionDir))
            candidate = os.path.normpath(os.path.join(offsetDir, path))
            lastCandidate = ''
            while (not os.path.exists(candidate)) and not (candidate == lastCandidate):
                lastCandidate = candidate
                offsetDir = os.path.normpath(os.path.join(offsetDir, os.pardir))
                candidate = os.path.normpath(os.path.join(offsetDir, path))

            if os.path.exists(candidate):
                return candidate
            else:
                print("Could not create an absolute path from: {} and sessionDir {}".format(path, sessionDir))
                return path

    # TODO: remove if not called from anywhere else
    def _makeSessionPath(self, path):
        raise NotImplementedError
        """add ../../ to path to move from project to session level"""
        for i in range(0, self.sessionDirDepth):
            path = os.path.join(os.pardir, path)
        return path
