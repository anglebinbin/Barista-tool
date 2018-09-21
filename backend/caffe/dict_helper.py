from backend.caffe.loader import _extract_param
import backend.caffe.proto_info as info
import uuid
import copy

from google.protobuf.internal.containers import RepeatedScalarFieldContainer as ProtoList

def isNetDictValid(netdic):
    """ This function returns a tuple (valid, msg). Value is true iff netdic has a valid format.
    If the format is not valid, msg contains a text which describes the problem.
    """
    if not {"layers", "layerOrder"}.issubset(netdic.keys()):
        missing = {"layers","layerOrder"}.difference(netdic.keys())
        return False, "Needed parameters {} not in dictionary".format(list(missing))
    layers =  netdic["layers"]
    order = netdic["layerOrder"]

    #Check if netparameters are valid (except layers)
    netparam = info.CaffeMetaInformation().availableNetParameters().copy()
    del netparam["layers"]
    tmp = netdic.copy()
    del tmp["layers"]
    del tmp["layerOrder"]
    if not _areParameterValid(netparam, tmp):
        return False, "Invalid net paremters"

    # Check for correct types of this special values
    if type(order) != list or type(layers) != dict:
        return False, "layerOrder or layers are invalid types"
    # Test if all ids are in the layerOrder list and vise versa
    if set(layers.keys()) != set(order):
        missingOrder = set(layers.keys()).difference(order)
        missingLayer = set(order).difference(layers.keys())
        return False, "layerOrder and layers does not have same ids - missing ids in layers: {} ; missing ids in order: {}"\
                      .format(missingLayer, missingOrder)
    # Check every sublayer
    for id in order:
        if not {"parameters","type"}.issubset(layers[id].keys()):
            return False, "parameters or type are not in layers subdictionary"
        params = layers[id]["parameters"]
        if params is None:
            return False, "parameters is None, should be at least {'name': '..', 'type': '...'}"
        layer = layers[id]["type"]
        if not isinstance(layer, info.LayerType):
            return False, "layers is {}, expected instance of protoinfo.LayerType".format(layer)
        validparam, msg =  _areParameterValid(layer.parameters(), params)
        if not validparam:
            return False, "Invalid parameters for {}: {}".format(id, msg)

    return True, ""

def _areParameterValid(allparams, paramdict, prefix=""):
    """ Checks if all parameters in paramdict are valid.
        allparams should contain all available parameters names as key
        and the proto-meta-info-class as value.
    """
    def checkType(meta, value, typeprefix):
        pytype = None
        if meta.isParameterGroup():
            if type(value) != dict:
                return False, "Expected dictionary , found {}".format(type(value))
            return _areParameterValid(meta.parameter(), value, typeprefix)
        elif meta.isBool():
            pytype = [bool]
        elif meta.isString():
            pytype = [unicode, str]
        elif meta.isInt():
            pytype = [int, long]
        elif meta.isBytes():
            pass # TODO: What type are bytes?
        elif meta.isFloat() or meta.isDouble():
            pytype = [float]
        elif meta.isEnum():
            pytype = [str, unicode]
        res = type(value) in pytype
        if not res:
            return False, "Expected Type {}, found {}".format(pytype, type(value))
        return True, ""
    for param in paramdict:
        typeprefix=prefix+"."+param
        val = paramdict[param]
        if not allparams.has_key(param):
            return False, "Parameter {}: Parameter not available in Caffe".format(typeprefix)
        meta = allparams[param]
        if meta.isRepeated():
            if not (type(val) is ProtoList or type(val) is list):
                return False, "Parameter {}: Expected repeated entry, found single one".format(typeprefix)
            for i,entry in enumerate(val):
                valid, msg = checkType(meta,entry, typeprefix)
                if not valid:
                    return False, "Parameter {} - idx {}: {}".format(typeprefix, i,msg)
        else:
            valid, msg = checkType(meta,val,typeprefix)
            if not valid:
                return False, "Parameter {}: {}".format(typeprefix,msg)
    return True, ""



def bareNet(name):
    """ Creates a dictionary of a networks with default values where required. """
    from backend.caffe.path_loader import PathLoader
    proto = PathLoader().importProto()
    net = proto.NetParameter()
    descr = info.ParameterGroupDescriptor(net)
    params = descr.parameter().copy()
    del params["layer"]
    del params["layers"]
    res = _extract_param(net, params)
    res["layers"] = {}
    res["layerOrder"] = []
    res["name"] = unicode(name)
    return res

def _bareLayer(layertype, name):
    """ Creates a dictionary of the given layertype with the given name
        initialized with default values if required.
    """
    from backend.caffe.path_loader import PathLoader
    proto = PathLoader().importProto()
    res = {"type": layertype}
    layerParamInst = proto.LayerParameter()
    res["parameters"] = _extract_param(layerParamInst, info.CaffeMetaInformation().commonParameters())
    res["parameters"]["name"] = unicode(name)
    layerparamkeys = layertype.layerParamKeys()
    for layerparamkey in layerparamkeys:
        layerTypeParam = layertype.parameters()[layerparamkey]
        layerTypeParamInst = layerTypeParam.protoclass()()
        res["parameters"][layerparamkey] = _extract_param(layerTypeParamInst, layerTypeParam.parameter())
    res["parameters"]["type"] = unicode(layertype.name())
    return res


class DictHelper:
    """ A helper class to simplify the using of a network dictionary """
    def __init__(self,netdic):
        self._netdic = netdic

    def nameOfLayers(self):
        """ Return a list with all layers of the networks """
        return [x["parameters"]["name"] for x in self._netdic["layers"].values()]

    def nameOfTopBlobs(self):
        """ Return a list with all top blob names in use of the current network """
        names = []
        for id in self._netdic["layers"]:
            if "top" in self.layerPerId(id)["parameters"]:
                for j in range(0, len(self.layerPerId(id)["parameters"]["top"])):
                    names.append(self.layerPerId(id)["parameters"]["top"][j])
        return names

    def netParameters(self):
        """ Return all parameters for the network (excluding layers) """
        return dict([(k,self._netdic[k]) for k in self._netdic if not k in ["layers","layerOrder"]])

    def layerIdsForName(self,name):
        """ Return a list of the ids for every layer with the given name """
        return [x for x in self._netdic["layers"] if self._netdic["layers"][x]["parameters"]["name"] == name]

    def layerType(self,id):
        """ Return the type of the layer with the given id
        """
        return self._netdic["layers"][id]["type"]

    def layerParams(self,id):
        """ Return the parameter of the layer with the given id
        """
        return self._netdic["layers"][id]["parameters"]

    def layerPerId(self, id):
        """ Return the layer with the given id """
        return self._netdic["layers"][id]

    def hasLayerWithId(self,id):
        """ Return true if there is a layer with the given id"""
        return id in self._netdic["layers"]

    def addLayer(self, layertype, name, idx):
        """ Add a new Layer from layertype with the given name
            and initialize it with the default values if required.
            This new layer is added to the intern dictionary at position idx
            and the layer subdictionary will be returned with the id.

            import backend.caffe.protoinfo as info
            convLayer = info.CaffeMetaInformation().availableLayerTypes()["Convolution"]
            newLayer, layerId = dichelperinstance.addLayer(convLayer, "Convolution", 3)
        """
        newLayer = _bareLayer(layertype, name)
        id = str(uuid.uuid4())
        self._netdic["layerOrder"].insert(idx, id)
        self._netdic["layers"][id] = newLayer
        return newLayer, id

    def removeLayer(self, id):
        del self._netdic["layers"][id]
        self._netdic["layerOrder"].remove(id)

    def duplicateLayer(self, id, newName, idx=None):
        """ Duplicate Layer with given id. The new layer has a new random id
            and the new given name.
            The layer will be added at position idx in the layerOrder.
            If idx==None, the idx will be directly beside the old layer.
            This function returns the new layer as dictionary and its id.
            E.g. newLayerDict, newId = dicthelper.duplicateLayer("somerandomid", "Some awesome name")
        """
        oldLayer = self.layerPerId(id)
        newLayer = {
            "type": oldLayer["type"],
            "parameters": copy.deepcopy(oldLayer["parameters"])
        }
        newLayer["parameters"]["name"] = newName
        newId = str(uuid.uuid4())
        if idx is None:
            idx = self._netdic["layerOrder"].index(id)+1
        self._netdic["layerOrder"].insert(idx, newId)
        self._netdic["layers"][newId] = newLayer
        return newLayer, newId

    def dictionary(self):
        return self._netdic

    def layerParameterIsSet(self, layerId, parameterKey):
        """ Check whether the given parameter is set for the given layer.

        :param layerId: The id of the layer to check.
        :param parameterKey: The key of the parameter to check. Might represent a nested parameter concatenated with dots.
        :return:
        """

        isSet = "parameters" in self._netdic["layers"][layerId]

        if isSet:
            paramKeyParts = parameterKey.split(".")
            value = self._netdic["layers"][layerId]["parameters"]
            for paramKeyPart in paramKeyParts:
                if paramKeyPart in value:
                    value = value[paramKeyPart]
                else:
                    isSet = False
                    break

        return isSet

    def layerParameter(self, layerId, parameterKey):
        """ Get a specific parameter for one of the layers.

        :param layerId: The id of the layer.
        :param parameterKey: The key of the requested parameter. Might represent a nested parameter concatenated with dots.
        :return:
        """

        paramKeyParts = parameterKey.split(".")
        value = self._netdic["layers"][layerId]["parameters"]
        for paramKeyPart in paramKeyParts:
            if paramKeyPart in value:
                value = value[paramKeyPart]
            else:
                value = None
                break

        return value

    def setLayerParameter(self, layerId, parameterKey, value):
        """ Set a specific parameter for one of the layers.

        :param layerId: The id of the layer.
        :param parameterKey: The key of the requested parameter. Might represent a nested parameter concatenated with dots.
        :return:
        """

        paramKeyParts = parameterKey.split(".")
        dic = self._netdic["layers"][layerId]["parameters"]
        for key in paramKeyParts[:-1]:
            dic = dic.setdefault(key, {})
        dic[paramKeyParts[-1]] = value
