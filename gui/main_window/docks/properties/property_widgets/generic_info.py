import copy

from gui.main_window.docks.properties.property_widgets import data
from gui.main_window.docks.properties.property_widgets.types import *


class GenericBuilderException(Exception):
    pass

class GenericInfoBuilder(data.PropertyInfoBuilder):
    """ This class can can build infos from a description which 
        is a dictionary which looks like this:
    {
        "type": GroupType, # type information, not optional
        "name": "Bla", # name of this property, not optional
        "prototype": {}, # a value of which a copy will be a default value, not optional. If it is a function, the function get called, but nothing will be copied then
        "entries": [ # if Group, we have need the infos of the entries, not optional for this type
            {
                "name": "BlaSub",
                "type": IntType, # type is int
                "prototype": 0 # the default value 
            },
            {
                "name": "BlaSubList",
                "type": ListType, # A list
                "prototype": []
                "entry": { # A list contains homogeneous entries
                           # Which should be described here
                    "name": "ListEntry",
                    "type": IntType,
                    "prototype": 0
                }
                # alternatively to entry we can set
                # "typeEntry": IntType
            },
            {
                "name": "BlaSubDict",
                "type": DictType, # A Dictionary
                "prototype": {}
                "entry": { # A dictionary contains homogeneous values
                           # (and String-Keys)
                           # Which should be described here
                    "name": "DictEntry",
                    "type": FloatType,
                    "prototype": 0.2
                }
                # alternatively to entry we can set
                # "typeEntry": FloatType
            },
            {
                "name": "SomeEnum",
                "type": EnumType,
                "prototype": "A",
                "enumOptions": ["A","B"]
            },
            { # If we want to redirect infos to another
              # builder, we can use the "builder"-attribute.
              # With the "info"-entry, this class will represents the info.
              # If the argument is a function, the function get called
              # If info and builder are set, there is no need for other keys
              "info": SomeOtherInfoClass
              # Builder should always been set if info is set and the type in info is GroupType
              "builder": SomeOtherInfoBuilder,

              # A function changes the uri for 
              # the builder.
              # If not set the builder gets the whole uri
              "urifunc": lambda uri: uri[:3]
              }
        ]
        # Other available entries have the same name
        # as the function in PropertyInfo class
    }
    """

    def __init__(self, infodescritpion):
        self._infodescritpion = infodescritpion

    def buildInfo(self, name, protoparameter, uri=None):
        descr = self._infodescritpion
        def req(name):
            try:
                return descr[name]
            except KeyError:
                raise GenericBuilderException("Key '{}' needed for {}".format(name, descr))
        for i, uripart in enumerate(uri):
            if "info" in descr:
                descrtype = descr["info"].typeString()
            else:
                descrtype = req( "type" )
            if not descrtype in [ListType, GroupType, DictType]:
                raise GenericBuilderException("Cannot build info for {} because {} is a primitive".format(uri, uri[:i+1]))

            if "builder" in descr:
                urifunc = lambda x: x
                if "urifunc" in descr:
                    urifunc = descr["urifunc"]
                return descr["builder"].buildInfo(name, protoparameter, urifunc(uri))
            elif descrtype == GroupType:
                entries = descr["entries"]
                for entry in entries:
                    try:
                        if "info" in entry:
                            if entry["info"].name() == uri[i]:
                                descr = entry
                                break
                        elif entry["name"] == uri[i]:
                            descr = entry
                            break
                    except KeyError:
                        raise GenericBuilderException("Key 'name' needed for {}".format(entry))
            elif descrtype in [ListType, DictType]:
                descr = req( "entry" )
        

        if "info" in descr:
            return descr["info"]
        else:
            return GenericInfoWrapper(descr)

    def buildRoot(self):
        if "info" in self._infodescritpion:
            return self._infodescritpion["info"]
        return GenericInfoWrapper(self._infodescritpion)


class GenericInfoWrapper(data.PropertyInfo):
    """ Builds PropertyInfo on a info description (see the dictionaries GenericInfoBuilder) """

    def __init__(self, description):
        self._description = description

    def name(self):
        return self.__requiredType("name")

    def typeEntryString(self):
        if "typeEntry" in self._description:
            return self._description["typeEntry"]
        return self.typeString()

    def typeString(self):
        return self.__requiredType("type")

    def __requiredType(self, name):
        # Make own exception if key does not exist
        try:
            return self._description[name]
        except KeyError:
            raise GenericBuilderException("Entry {} needed in info-description".format(name))

    def __entryOr(self, name, default):
        # Returns default if name is not in self._description
        if name in self._description:
            return self._description[name]
        return default

    def entryInfo(self):
        if "entry" in self._description:
            entry = self._description["entry"]
            if "info" in entry:
                return entry["info"]
            return GenericInfoWrapper(entry)
        else:
            return super(GenericInfoWrapper, self).entryInfo()

    def enumOptions(self):
        return self.__entryOr("enumOptions", [])
    def deprecated(self):
        return self.__entryOr("deprecated", False)
    def description(self):
        return self.__entryOr("description", "")
    def prototype(self):
        prototype = self.__requiredType("prototype")
        if type(prototype) == function:
            return prototype()
        return copy.deepcopy(prototype)
    def subparameter(self):
        if self.typeString() == GroupType:
            subdescr = self.__requiredType("entries")
            res = {}
            for descr in subdescr:
                # We set them to None, because GenericInfoBuilder
                # does not handle  protoparameter directly.
                # So every value should be fine
                if "info" in descr:
                    res[descr["info"].name()] = None
                elif "name" in descr:
                    res[descr["name"]] = None
                else:
                    raise GenericBuilderException("{} needs a name".format(descr))
            return res
        return []
    def isEditable(self):
        return self.__entryOr("isEditable", True)
    def isRequired(self):
        return self.__entryOr("isRequired", True)
