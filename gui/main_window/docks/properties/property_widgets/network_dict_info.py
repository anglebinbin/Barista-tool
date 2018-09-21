import backend.caffe.proto_info as info
from gui.main_window.docks.properties.property_widgets import data
from gui.main_window.docks.properties.property_widgets import layer_info
from gui.main_window.docks.properties.property_widgets.types import *


class NetworkDictInfoBuilder(data.PropertyInfoBuilder):
    """ Builds info docks for the network-part of the state-dictionary """
    def __init__(self, netdict):
        if type(netdict) == dict:
            self.netdictfunc = lambda: netdict
        else:
            self.netdictfunc = netdict
        self.layerinfo = layer_info.LayerPropertyInfoBuilder()

    def buildInfo(self, name, protoparameter, uri=None):
        if uri == []:
            return NetworkDictInfo(name, protoparameter)
        elif uri == ["layers"]:
            return LayersInfo("layers", LayerIdInfo(""))
        elif uri[0] == "layers":
            id = uri[1]
            layer = self.netdictfunc()["layers"][id]
            if len(uri) == 2:
                return LayerIdInfo(id)
            if uri[2] == "type":
                return LayerTypeInfo()
            if uri[2] == "parameters":
                if uri == ["layers",id,"parameters"]:
                    return self.layerinfo.buildRootInfo(name, layer["type"])
                else:
                    return self.layerinfo.buildInfo(name, protoparameter, uri[3:])
        elif uri == ["layerOrder"]:
            return LayerOrderInfo("layerOrder")
        else:
            return NetworkInfo(name, protoparameter, uri)


    def buildRootInfo(self, name=""):
        """ Builds the information about "network" in the state dictionary """
        prot = info.CaffeMetaInformation().availableNetParameters().copy()
        del prot["layers"]
        del prot["layer"]
        prot["layers"] = "LayerDict"
        prot["layerOrder"] = "LayerOrder"
        return self.buildInfo(name,prot,[])

class LayersInfo(data.PropertyInfo):
    """ Give infos about the entry 'layers' in the network dictionary """
    def __init__(self, name, layerIdInfo):
        self._name = name
        self.paramInfo = layerIdInfo

    def entryInfo(self):
        return self.paramInfo

    def typeString(self):
        return DictType

    def enumOptions(self):
        return []

    def name(self):
        return self._name

    def deprecated(self):
        return False

    def description(self):
        return ""

    def prototype(self):
        return {}

    def subparameter(self):
        """ Returns the subparameter of an entry in this dictionary (the layer id subparemter = "parameters","type")"""
        return self.paramInfo.subparameter()

    def isEditable(self):
        return True

    def isRequired(self):
        return True

class LayerOrderInfo(data.PropertyInfo):
    def __init__(self, name):
        self._name = name

    def typeEntryString(self):
        return StringType

    def typeString(self):
        return ListType

    def enumOptions(self):
        return []

    def name(self):
        return self._name

    def deprecated(self):
        return False

    def description(self):
        return ""

    def prototype(self):
        return []

    def subparameter(self):
        return {}

    def isEditable(self):
        return True

    def isRequired(self):
        return True

class LayerIdInfo(data.PropertyInfo):
    """ Give infos about a layer (with type and parameters) in network dictionary """
    def __init__(self, id):
        self.id = id

    def typeEntryString(self):
        return self.typeString()

    def typeString(self):
        return GroupType

    def enumOptions(self):
        return []

    def name(self):
        return self.id

    def deprecated(self):
        return False

    def description(self):
        return ""

    def prototype(self):
        return {"type": None, "parameters": {}}

    def subparameter(self):
        return {"type": "type", "parameters": "parameters"}

    def isEditable(self):
        return False

    def isRequired(self):
        return False

class LayerTypeInfo(data.PropertyInfo):
    """ Give infos about the type-attribute of a layer network dictionary"""
    def __init__(self):
        pass

    def typeEntryString(self):
        return self.typeString()

    def typeString(self):
        return UnknownType

    def enumOptions(self):
        return []

    def name(self):
        return "type"

    def deprecated(self):
        return False

    def description(self):
        return ""

    def prototype(self):
        return None

    def subparameter(self):
        return {}

    def isEditable(self):
        return False

    def isRequired(self):
        return True

class NetworkInfo(layer_info.PropertyInfo):
    """ Give infos about a non-layer parameter in the network-dictionary"""

    def __init__(self, name, meta,  uri):
        self._name = name
        self.meta = meta
        self.uri = uri

    def isEditable(self):
        return True

    def isRequired(self):
        return self.uri in [[]]

class NetworkDictInfo(data.PropertyInfo):
    """ Give infos about the root of the network dictionary"""
    def __init__(self, name, prot):
        self.prot = prot
        self._name = name

    def typeEntryString(self):
        return self.typeString()

    def typeString(self):
        return GroupType

    def enumOptions(self):
        return []

    def name(self):
        return self._name

    def deprecated(self):
        return False

    def description(self):
        return ""

    def prototype(self):
        return {}

    def subparameter(self):
        return self.prot

    def isEditable(self):
        return True

    def isRequired(self):
        return True
