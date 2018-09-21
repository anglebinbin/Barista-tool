import backend.caffe.proto_info as info
from gui.main_window.docks.properties.property_widgets import data
from gui.main_window.docks.properties.property_widgets.types import *

class LayerPropertyInfoBuilder(data.PropertyInfoBuilder):
    def buildInfo(self, name, protoparameter, uri):
        if uri == []:
            return LayerParamInfo(name, protoparameter)
        return PropertyInfo(name, protoparameter, uri)

    def buildRootInfo(self, name, type):
        """ Builds a info object for the whole layer
            type should be an instance of ProtoInfo.LayerType
            name is the name which the info type should have
        """
        params = type.parameters()
        return self.buildInfo(name, params, [])


class PropertyInfo(data.PropertyInfo):
    """ This Class gives infos about a type in properties """
    def __init__(self, name, meta,uri):
        self._name = name #type: str
        self.meta = meta #type: info.Parameter
        self.uri = uri #type: list


    def typeEntryString(self):
        """ Give the type as String. 
            If the type is a list, returns the type of the entries.
        """
        if self.meta.isInt():
            return IntType
        if self.meta.isDouble() or self.meta.isFloat():
            return FloatType
        if self.meta.isString():
            return StringType
        if self.meta.isEnum():
            return EnumType
        if self.meta.isParameterGroup():
            return GroupType
        if self.meta.isBool():
            return BoolType

    def typeString(self):
        """ Give the type as String (see StringType, IntType,...)"""
        if self.meta.isRepeated():
            return ListType
        return self.typeEntryString()

    def enumOptions(self):
        return self.meta.availableValues()

    def name(self):
        """ Return the name of this property """
        return self._name
    def deprecated(self):
        """ Return true iff this property is deprecated """
        return self.meta.isDeprecated()

    def description(self):
        """ Return a decription of this property """
        return self.meta.description()

    def prototype(self):
        """ Returns a raw value of a default type """
        default = self.meta.defaultValue()
        if default is None:
            return data.prototypeOfType(self)
        return default

    def subparameter(self):
        return self.meta.parameter()

    def isEditable(self):
        uri = self.uri
        if uri and len(uri) > 0: 
            if uri in [["type"]]: return False
            if uri in [["bottom"]]: return False
            if uri in [["top"]]: return False
            # if uri[0] in ["bottom"]: return False
        return True

    def isRequired(self):
        uri = self.uri
        if uri and len(uri) > 0:
            return uri in [["name"], ["type"]]
        return False

class LayerParamInfo(data.PropertyInfo):
    """ Give infos about the root parameters of a layer"""
    def __init__(self, name, parameters):
        self._name = name
        self.params = parameters

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
        return self.params
    def isEditable(self):
        return False
    def isRequired(self):
        return False
