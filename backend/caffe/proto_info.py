from google.protobuf.descriptor import FieldDescriptor
import sys, inspect
from backend.caffe import proto_description
import re
import copy

"""This module dynamically provides meta information about the available caffe parameters.

If the compiled caffe version is changed, the provided meta information will change, too.
Use these information to show available options in the gui.
Example to get all layer types: types = CaffeMetaInformation().availableLayerTypes()
"""

moreLayerNameParameter = {
    "Deconvolution": "ConvolutionParameter"
}

class Singleton(type):
    """This metaclass is used to provide the singleton pattern in a generic way.

    See http://stackoverflow.com/a/6798042 for source and further explanation.
    TODO outsource this class to use the same pattern in the complete project?
    """
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class UnknownLayerTypeException(Exception):
    def __init__(self, msg):
        self._msg = msg

    def __str__(self):
        return self._msg


class CaffeMetaInformation:
    """This class is the main interface for any usage outside of this module.

    It provides various meta information about the compiled caffe version and its available features.
    Singleton is used to ensure that all constant data is generated only once.
    """
    __metaclass__ = Singleton

    def __init__(self):
        self.updateCaffeMetaInformation()


    def updateCaffeMetaInformation(self):
        self.__initAvailableParameterGroupDescriptors()
        self.__initAvailableLayerTypes()
        self.__initAvailableSolverTypes()

    def __initAvailableParameterGroupDescriptors(self):
        """Generate information about available parameter only once using this method.

        See description of self.availableParameterGroupDescriptors().
        """
        from backend.caffe.path_loader import PathLoader
        proto = PathLoader().importProto()
        current_module = sys.modules[proto.__name__]
        res = {}
        for (el,val) in inspect.getmembers(current_module, inspect.isclass):
            res[el] = ParameterGroupDescriptor(val)
        self._availableParameterGroupDescriptors = res

    def __initAvailableLayerTypes(self):
        """Generate information about available layer types only once.

        self.__initAvailableParameterGroupDescriptors() needs to be called before this method."""
        from backend.caffe.path_loader import PathLoader
        caffe = PathLoader().importCaffe()
        layerNameMainParts = list(caffe.layer_type_list())

        res = {}
        paramsPerLayerType = {}

        # calculate common parameters of all layer types
        # by removing all which will be used for one specific layer type only
        # also keep in mind which ones have been removed to readd them to specific layers
        commonParams = self._availableParameterGroupDescriptors["LayerParameter"].parameter() #use .parameter() on purpose
        layerSpecificParameters = set()
        for nameMainPart in layerNameMainParts:
            specificParamsName = [nameMainPart + "Parameter"]
            if moreLayerNameParameter.has_key(nameMainPart):
                specificParamsName.append( moreLayerNameParameter[nameMainPart])
            paramsPerLayerType[nameMainPart] = {}
            for key, value in commonParams.items():
                if value.isParameterGroup() and value.parameterName() in specificParamsName:
                    paramsPerLayerType[nameMainPart][key] = value
                    layerSpecificParameters.add(key)


        # special case: shared params for loss layers
        key = "loss_param"
        value = commonParams[key]
        del commonParams[key]
        for nameMainPart in layerNameMainParts:
            if LayerType.getCategoryByName(nameMainPart) == LayerType.CATEGORY_LOSS:
                paramsPerLayerType[nameMainPart][key] = value

        # TODO is there a special case for the TransformationParameter?

        # create each layer type after one another
        for nameMainPart in layerNameMainParts:

            # add common params to the specific ones
            layerTypeParam = paramsPerLayerType[nameMainPart].keys()
            paramsPerLayerType[nameMainPart].update(commonParams)

            irrelevant = layerSpecificParameters.difference(layerTypeParam)
            res[nameMainPart] = LayerType(nameMainPart, paramsPerLayerType[nameMainPart], layerTypeParam, irrelevant)

        self._commonParams = commonParams
        self._availableLayerTypes = res

    def __initAvailableSolverTypes(self):
        """Generate information about available solver types only once.

        self.__initAvailableParameterGroupDescriptors() needs to be called before this method."""
        from backend.caffe.path_loader import PathLoader
        proto = PathLoader().importProto()

        # DO NOT REMOVE the following import statement, although your IDE might say it's unused. It's not!
        from caffe._caffe import Solver as SolverBaseClassInfo

        # Unfortunately, there isn't a preexisting method to get all solver (names).
        # But, there is a base class which is subclassed by all existing solvers.
        # Use those subclasses to gain the names of all solvers.
        solverNamesFull = [cls.__name__ for cls in vars()['SolverBaseClassInfo'].__subclasses__()]

        # All those names end with the suffix "Solver".
        # Remove that suffix to be consistent with the names of available LayerTypes.
        solverNameMainParts = []
        for name in solverNamesFull:
            solverNameMainParts.append(name.replace("Solver",""))

        # Get all (common) params of a solver type
        # TODO try to separate params which should be available only for a specific SolverType.
        # Unfortunately, there doesn't seem to exist any way to automatically do that. There are only a few comments
        # in the caffe.proto file which would allow hardcoding some special cases. But is that a good idea?
        commonParams = self._availableParameterGroupDescriptors[
            "SolverParameter"].parameter()  # use .parameter() on purpose

        # create each solver type after one another
        res = {}
        for nameMainPart in solverNameMainParts:
            res[nameMainPart] = SolverType(nameMainPart, commonParams)

        self._availableSolverTypes = res

    def availableParameterGroupDescriptors(self):
        """Return all available Parameter (e.g. Layer-Parameter) for Caffe as an dictionary.

        The key is the name of the parameter and the value is an instance of the helper class ParameterGroupDescriptor.
        This is the most general way of getting any caffe meta information.
        """
        return self._availableParameterGroupDescriptors

    def availableLayerTypes(self):
        """Return a dictionary containing all layer types which are available in caffe.

        The key is the name of the layer type (without the suffix 'Layer'. e.g. 'SoftMax' instead of 'SoftMaxLayer')
        and the value is an object of the class LayerType.
        """
        return self._availableLayerTypes

    def getLayerType(self, typename):
        """ Returns the layer type for typename or throws an UnknownLayerTypeException
        if a type with typename is not known. """
        if typename not in self._availableLayerTypes:
            raise UnknownLayerTypeException("Network contains an unknown layer type '{}'.".format(typename))
        return self._availableLayerTypes[typename]

    def commonParameters(self):
        """ Return parameters all layers share.
            It is missing specific paremeters like "inner_product_param"
            or "convolution_param".
        """
        return self._commonParams

    def availableSolverTypes(self):
        """Return a dictionary containing all solver types which are available in caffe.

        The key is the name of the solver type (without the suffix 'Solver'. e.g. 'SGD' instead of 'SGDSolver')
        and the value is an object of the class SolverType.
        """
        return self._availableSolverTypes

    def availableNetParameters(self):
        """Return a list containing all available parameters of a net.

        Note that, this differs a little bit from the way you get the parameters of a solver or layer, as we don't
        got different net types.
        Also pay attention to the fact, that the returned list will of course contain the parameter "layer". Because
        this parameter is only a general description of all layers at once, you will probably want to use
        availableLayerTypes() instead.
        """
        return self._availableParameterGroupDescriptors['NetParameter'].parameter()

class TopLevelEntityType:
    """This class represents entities of special importance for our project.

    According to the caffe.proto file, those entities are normal ParameterGroupDescriptor (/Message) docks.
    But the proto file doesn't add a hierarchy for the top level. This hierarchy will be added by inheriting from this
    class.
    The already complete list of top level entities is probably: LayerType, SolverType
    """

    def __init__(self, name, parameters):
        self._name = name
        self._parameters = parameters

    def name(self):
        """The name extended by the correct suffix (e.g. 'Layer') equals the name of its C++ class."""
        return self._name

    def parameters(self):
        """Return a dictionary containing all available parameters for this TopLevelEntityType.

        Each parameter will be an instance of a subclass of Parameter.
        """
        return self._parameters

class LayerType(TopLevelEntityType):
    """An object of this class represents one type of layer that is available in caffe.

    The name of such an object is for instance "Softmax" or "InnerProduct".

    The parameters of a LayerType include general parameters which are available for all LayerTypes as well as specific
    ones which are only available for this particular LayerType.
    """

    CATEGORY_NONE = 0
    CATEGORY_LOSS = 1
    CATEGORY_DATA = 2 # == input
    CATEGORY_ACTIVATION = 3
    # TODO (try to) implement further categories

    def __init__(self, name, parameters, layerParamKeys=[], seemsNotRelevantParams=set()):
        TopLevelEntityType.__init__(self, name, parameters)
        self._category = self.getCategoryByName(self._name)
        self._layerParamKeys = layerParamKeys
        self._irrelevant = seemsNotRelevantParams

    def category(self):
        """Return the category of this LayerType.

        The category is described by one of the class constants CATEGORY_<xy>.
        """
        return self._category


    def layerParamKeys(self):
        """The paremter key for the specific parmeters of this Layertype
           E.g. ["inner_product_param"] for the InnerProduct-Layer
        """
        return self._layerParamKeys

    def probablyIrrelevantParameter(self):
        """ Return a set of parameter which seems not to belong to this layer """
        return self._irrelevant

    def isLossLayer(self):
        return self._category == self.CATEGORY_LOSS

    def isDataLayer(self):
        return self._category == self.CATEGORY_DATA

    def isActivationLayer(self):
        return self._category == self.CATEGORY_ACTIVATION

    def allowsInPlace(self):
        inPlaceLayers = ['Dropout']
        return self._name in inPlaceLayers or self.isActivationLayer()

    @staticmethod
    def getCategoryByName(layerTypeName):
        """Given its name, determine which category a LayerType does belong to."""
        # !!! hard coded list of activation layers could cause problems when more layers are added in caffe
        if layerTypeName in ["ReLU", "PReLU", "ELU", "Sigmoid", "TanH", "AbsVal", "Power",
                             "Exp", "Log", "BNLL", "Threshold", "Bias", "Scale"]:
            return LayerType.CATEGORY_ACTIVATION
        elif "Loss" in layerTypeName:
            return LayerType.CATEGORY_LOSS
        elif "Data" in layerTypeName:
            return LayerType.CATEGORY_DATA
        else:
            return LayerType.CATEGORY_NONE

    def __copy__(self):
        """See __deepcopy__."""
        result = CaffeMetaInformation().availableLayerTypes()[self._name]
        return result

    def __deepcopy__(self, memo):
        """Override the deepcopy behavior used in copy.deepcopy() and pickle().

        The protobuf object stored in self._field can't be pickeled, which will also result in an exception each time we
        try to call copy.deepcopy() on any list/dict/etc. that contains an object of this class. We need to do this e.g.
        in network_manager._refreshStateFromHistory(). This method solves the problem by just recreating an object with
        the same information as the original one without copying anything else. That's actually everything we need.
        """
        result = CaffeMetaInformation().availableLayerTypes()[self._name]
        memo[id(self)] = result
        return result

class SolverType(TopLevelEntityType):
    """Currently, the following SolverTypes do exist: 'SGD', 'Nesterov', 'AdaGrad', 'RMSProp', 'AdaDelta', 'Adam'"""

class ParameterGroupDescriptor:
    """A ParameterGroupDescriptor is a general description of a ParameterGroup without being used as a concrete parameter.

    The idea is equivalent to a Message in the Google Protobuf definition.
    """

    def __init__(self,protoclass, descriptor=None):
        self._protoclass = protoclass
        if descriptor is None and protoclass is not None:
            self._desc = protoclass.DESCRIPTOR
        else:
            self._desc = descriptor

    def protoclass(self):
        """ Return the protoclass associated with this descriptor """
        return self._protoclass

    def name(self):
        return self._desc.name

    def parameter(self):
        """Return a dictionary containing all parameters of this group.

        The parameter name is used as the key while each value is an instance of the class Parameter. This instance can
        be used too gain further information.
        """
        res = dict()
        for x in self._desc.fields:
            if x.type == FieldDescriptor.TYPE_MESSAGE:
                parameter = ParameterGroup(x)
            elif x.type == FieldDescriptor.TYPE_ENUM:
                parameter = ParameterEnum(x)
            else:
                parameter = ParameterPrimitive(x)

            res[x.name] = parameter

        return res

    def __eq__(self, other):
        return self._desc.full_name == other._desc.full_name

class Parameter:
    """This class represents a single parameter which can be specified in the .prototxt file.

    There are various use cases for a parameter of this type.
    It might be usable only for the net definition, the solver definition, or both.
    A parameter also does not necessarily need to be a top-level parameter, meaning it might only be used
    as the value of another parameter, too.
    A Parameter is also a single property of a ParameterGroupDescriptor and therefore sometimes referred to as a
    'property', too.
    An object of this (abstract) class will always be an instance of one of the following subclasses:
    ParameterPrimitive, ParameterEnum or ParameterGroup.

    TODO this base class should not be allowed to instantiate and should therefore be an abstract class,
    but that doesn't make sense in python, does it?
    """

    string_dict = {
        FieldDescriptor.TYPE_BOOL: "bool",
        FieldDescriptor.TYPE_BYTES: "bytes",
        FieldDescriptor.TYPE_DOUBLE: "double",
        FieldDescriptor.TYPE_ENUM: "enum",
        FieldDescriptor.TYPE_FIXED32: "fixed32",
        FieldDescriptor.TYPE_FIXED64: "fixed64",
        FieldDescriptor.TYPE_FLOAT: "float",
        # FieldDescriptor.TYPE_GROUP: "group",
        FieldDescriptor.TYPE_INT32: "int32",
        FieldDescriptor.TYPE_INT64: "int64",
        FieldDescriptor.TYPE_MESSAGE: "message",
        FieldDescriptor.TYPE_SFIXED32: "sfixed32",
        FieldDescriptor.TYPE_SFIXED64: "sfixed64",
        FieldDescriptor.TYPE_SINT32: "sint32",
        FieldDescriptor.TYPE_SINT64: "sint64",
        FieldDescriptor.TYPE_STRING: "string",
        FieldDescriptor.TYPE_UINT32: "uint32",
        FieldDescriptor.TYPE_UINT64: "uint64",
    }

    def __init__(self,field):
        self._field = field
        self._description = proto_description.CaffeProtoParser().description(field.containing_type.name, field.name)
        self._initIsDeprecated()

    def _initIsDeprecated(self):
        """Call this whenever a new description has been set."""
        self._isDeprecated = re.search("deprecated", self._description, re.IGNORECASE) is not None

    def isDeprecated(self):
        return self._isDeprecated

    def description(self):
        """Get a string describing this parameter in a human-readable way."""
        return self._description

    def fieldName(self):
        """Return the name of this property (with underscores, not camelcase).

        This is not the same as the name of the parameter's type. Therefore this method is not called 'name()'.
        Pay additional attention to possible confusion with the name of the ParameterGroupDescriptor, if this element
        is a ParameterGroup.
        """
        return self._field.name

    def isOptional(self):
        """Return true iff the parameter is optional, this includes if it's repeated.
           (Repeated mean 0-n)
        """
        return self._field.label == FieldDescriptor.LABEL_OPTIONAL or self.isRepeated()

    def isRequired(self):
        """ Return the opposite of isOptional"""
        return not self.isOptional()
        # return self._field.label == FieldDescriptor.LABEL_REQUIRED

    def isRepeated(self):
        """ Return true iff the parameter is repeated. Repeated values may contain 0 entries"""
        return self._field.label == FieldDescriptor.LABEL_REPEATED

    def isParameterGroup(self):
        """Return true iff this parameter is a combination of other parameter."""
        return self._field.type == FieldDescriptor.TYPE_MESSAGE

    def defaultValue(self):
        # We make a copy, so no one can override the default value
        return copy.deepcopy(self._field.default_value)

    def __eq__(self, other):
        return self._field.full_name == other._field.full_name and self.fieldName() == other.fieldName()

    def type(self):
        """The type is descript by one of the constants FieldDescriptor.TYPE_<xy>."""
        return self._field.type

    def typeString(self):
        """Return a human-readable string describing the type (e.g. "bool", "int32", ..). """
        return Parameter.string_dict[self._field.type]

    def isBool(self):
        return self.type() == FieldDescriptor.TYPE_BOOL

    def isString(self):
        return self.type() == FieldDescriptor.TYPE_STRING

    def isInt(self):
        """Combine all possible tests of integer (does not differ: uint vs int vs sint)."""
        return self.type() == FieldDescriptor.TYPE_INT32 or self.type() == FieldDescriptor.TYPE_INT64 or \
               self.type() == FieldDescriptor.TYPE_SINT32 or self.type() == FieldDescriptor.TYPE_SINT64 or \
               self.type() == FieldDescriptor.TYPE_UINT32 or self.type() == FieldDescriptor.TYPE_UINT64 or \
               self.type() == FieldDescriptor.TYPE_FIXED32 or self.type() == FieldDescriptor.TYPE_FIXED64 or \
               self.type() == FieldDescriptor.TYPE_SFIXED32 or self.type() == FieldDescriptor.TYPE_SFIXED64

    def isSInt(self):
        return self.type() == FieldDescriptor.TYPE_SINT32 or self.type() == FieldDescriptor.TYPE_SINT64 or \
               self.type() == FieldDescriptor.TYPE_SFIXED32 or self.type() == FieldDescriptor.TYPE_SFIXED64

    def isUInt(self):
        return self.type() == FieldDescriptor.TYPE_UINT32 or self.type() == FieldDescriptor.TYPE_UINT64 or \
               self.type() == FieldDescriptor.TYPE_FIXED32 or self.type() == FieldDescriptor.TYPE_FIXED64

    def isBytes(self):
        return self.type() == FieldDescriptor.TYPE_BYTES

    def isFloat(self):
        return self.type() == FieldDescriptor.TYPE_FLOAT

    def isDouble(self):
        return self.type() == FieldDescriptor.TYPE_DOUBLE

    def isEnum(self):
        return self.type() == FieldDescriptor.TYPE_ENUM



class ParameterPrimitive(Parameter):
    """An Object of this class represents a primitive data type like int, bool, string etc."""

class ParameterEnum(Parameter):
    """An Object of this class represents an enumeration.

    TODO throw exception in constructor if self._field.type != FieldDescriptor.TYPE_ENUM
    """

    def availableValues(self):
        """Return all available values possible for this enum."""
        return [x.name for x in self._field.enum_type.values]

    def defaultValue(self):
        return self.availableValues()[self._field.default_value]

def resetCaffeProtoModulesvar():
    global _caffeprotomodulesvar
    _caffeprotomodulesvar = None

def _caffeProtobufModules():
    """ Returns all available Classes of caffe_pb2 in a dictionary """
    from backend.caffe.path_loader import PathLoader
    proto = PathLoader().importProto()
    global _caffeprotomodulesvar
    if _caffeprotomodulesvar is None:
        current_module = sys.modules[proto.__name__]
        _caffeprotomodulesvar = dict(inspect.getmembers(current_module, inspect.isclass))
    return _caffeprotomodulesvar

class ParameterGroup(ParameterGroupDescriptor, Parameter):
    """An Object of this class is a ParameterGroupDescriptor which is used as a Parameter of another ParameterGroupDescriptor.

    TODO throw exception in constructor if self._field.type != FieldDescriptor.TYPE_MESSAGE:
    """

    def __init__(self, field):
        Parameter.__init__(self, field)
        ParameterGroupDescriptor.__init__(self, None, descriptor=field.message_type)
        self._protoclass = _caffeProtobufModules()[self.parameterName()]

        # refresh description as this type of parameter got additional default values
        self._description = proto_description.CaffeProtoParser().description(field.containing_type.name, field.name,
                                                                             field.message_type.name)
        self._initIsDeprecated()

    def parameterName(self):
        """Get the ParameterGroupDescriptor name.

        Just an alias for the name() method to prevent confusion caused by the polymorphism.
        """
        return self.name()
