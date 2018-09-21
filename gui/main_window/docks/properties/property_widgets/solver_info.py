import backend.caffe.proto_info as info
from gui.main_window.docks.properties.property_widgets import data
from gui.main_window.docks.properties.property_widgets import layer_info
from gui.main_window.docks.properties.property_widgets.types import *


class SolverPropertyInfoBuilder(data.PropertyInfoBuilder):
    """ Builds info docks for the solver part of the state dictionary """
    def buildInfo(self, name, protoparameter, uri=None):
        if uri == []:
            return SolverRootInfo(name, protoparameter)
        return PropertyInfo(name, protoparameter, uri)
    def buildRootInfo(self, name=""):
        """ Builds "solver" info object of the state dictionary """
        from backend.caffe.path_loader import PathLoader
        proto = PathLoader().importProto()
        protosolver = proto.SolverParameter()

        descr = info.ParameterGroupDescriptor(protosolver)
        params = descr.parameter().copy()
        return self.buildInfo(name,params, [])

class SolverRootInfo(data.PropertyInfo):
    """ Represent the info about the parameters of a solver"""

    def __init__(self, name, params):
        self._name = name
        self.params = params

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
        """ Returns the subparameter of an entry in this dictionary (the layer id subparemter = "parameters","type")"""
        return self.params

    def isEditable(self):
        return True

    def isRequired(self):
        return True

class PropertyInfo(layer_info.PropertyInfo):
    def __init__(self, name, meta, uri):
        super(PropertyInfo,self).__init__(name,meta,uri)

    def isEditable(self):
        uri = self.uri
        if uri and len(uri) > 0:
            if uri in [["net"], ["net_param"]]: return False
        return True

    def isRequired(self):
        uri = self.uri
        if uri and len(uri) > 0:
            if uri in [["net"]]: return True
        return False

    def typeString(self):
        if self.uri == ["type"]:
            return EnumType
        return super(PropertyInfo, self).typeString()

    def enumOptions(self):
        if self.uri == ["type"]:
            return info.CaffeMetaInformation().availableSolverTypes()
        return super(PropertyInfo, self).enumOptions()

    def subparameter(self):
        params = super(PropertyInfo,self).subparameter() #type: dict
        return params
