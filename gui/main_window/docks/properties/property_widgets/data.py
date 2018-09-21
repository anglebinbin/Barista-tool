from PyQt5.QtCore import QObject, pyqtSignal
import backend.caffe.proto_info as info
from gui.main_window.docks.properties.property_widgets.types import *


class ReasonUpdated:
    """ This class represents an update of a value in PropertyDataObject """
    def __init__(self, oldValue, newValue):
        self.oldValue = oldValue
        self.newValue = newValue
    def __str__(self):
        return "Updated {} to {}".format(self.oldValue, self.newValue)
    def __eq__(self, other):
        if type(other) != type(self): return False
        return other.oldValue == self.oldValue and other.newValue == self.newValue
class ReasonAdded:
    """ This class represents a push in a list in PropertyDataListObject """
    def __init__(self, idx):
        self.idx = idx
    def __str__(self):
        return "Added {}".format(self.idx)
    def __eq__(self, other):
        if type(other) != type(self): return False
        return other.idx == self.idx
class ReasonRemoved:
    """ This class represents a remove in a list in PropertyDataListObject """
    def __init__(self, idx, val):
        self.idx = idx
        self.value = val
    def __str__(self):
        return "Removed {} - value {}".format(self.idx, self.value)
    def __eq__(self, other):
        if type(other) != type(self): return False
        return other.idx == self.idx
class ReasonGiven:
    """ This class represents a new given value in PropertyData """
    def __init__(self, name):
        self.name = name
    def __str__(self):
        return "Given {}".format(self.name)
    def __eq__(self, other):
        if type(other) != type(self): return False
        return other.name == self.name
class ReasonUngiven:
    """ This class represents a value in PropertyData which became deleted """
    def __init__(self, name):
        self.name = name
    def __str__(self):
        return "Ungiven {}".format(self.name)
    def __eq__(self, other):
        if type(other) != type(self): return False
        return other.name == self.name

class ReasonKeyAdded:
    """ This class represents a key/value in PropertyDataDictObject which was added """
    def __init__(self, key):
        self.key = key
    def __str__(self):
        return "Key added {}".format(self.key)
    def __eq__(self, other):
        if type(other) != type(self): return False
        return other.key == self.key

class ReasonKeyDeleted:
    """ This class represents a key/value in PropertyDataDictObject which was deleted """
    def __init__(self, key):
        self.key = key
    def __str__(self):
        return "Key deleted {}".format(self.key)
    def __eq__(self, other):
        if type(other) != type(self): return False
        return other.key == self.key

class PropertyInfoBuilder:
    def buildInfo(self, name, protoparameter, uri=None):
        """ This function should build an info object
            (something which behaves like PropertyInfo)
            for the given parameter.
            name is the name of the info object
            protoparameter is any object which helps build the info object
            uri is a list whicht describes the position of this info
        """
        pass

class PropertyInfo(object):
    """ This Class gives infos about a type in properties """

    def typeEntryString(self):
        """ Give the type as String. 
            If the type is a list/dictionary, returns the type of the entries.
            Only needed if entryInfo won't be overwritten
        """
        pass

    def entryInfo(self):
        """ Returns a info object which describes a entry object
            if the type is a list/dictionary
        """
        return PropertyInfoListEntryWrapper(self)

    def typeString(self):
        """ Give the type as String (see StringType, IntType,...)"""
        pass

    def enumOptions(self):
        """ A list of options if enum """
        pass

    def name(self):
        """ Return the name of this property """
        pass 

    def deprecated(self):
        """ Return true iff this property is deprecated """
        pass

    def description(self):
        """ Return a decription of this property """
        pass

    def prototype(self):
        """ Return a raw value of a default type.
            The result may be changed in other function,
            so you may want to return a copy of your prototype
        """
        pass

    def subparameter(self):
        """ Should  return a dictionary which keys are the subparameter
            and its values are the protoparameter for your PropertyInfoBuilder
            and can be from any type.
            E.g. {"subparameter1": SomeCaffeMetaInfosForExampleIfInfoBuilderWantsThis,
                  "subparameter2": MaySomeVeryDifferentData
                }
        """
        pass

    def isEditable(self):
        pass

    def isRequired(self):
        pass

class PropertyInfoListEntryWrapper(PropertyInfo):
    """ Wraps info such that typeString returns the typeEntryString.
        Useful for dictionary or list subtypes
    """
    def __init__(self, info):
        self._info = info #type: PropertyInfo
    def base(self):
        """ Return the base info-object this object wraps """
        return self._info
    def typeString(self):
        return self._info.typeEntryString()
    def typeEntryString(self):
        return self._info.typeEntryString()
    def entryInfo(self):
        raise LookupError("EntryInfo should not be used twice by using PropertyInfoListEntryWrapper")
    def enumOptions(self):
        return self._info.enumOptions()
    def name(self):
        return self._info.name()
    def deprecated(self):
        return self._info.deprecated()
    def description(self):
        return self._info.description()
    def prototype(self):
        return self._info.prototype()
    def isEditable(self):
        return self._info.isEditable()
    def isRequired(self):
        return self._info.isRequired()
    def subparameter(self):
        return self._info.subparameter()


def propertyObjectForInfo(info):
    """ Returns the subtype of PropertyDataObject
        which should be used with the given type
        in info
    """
    if info.typeString() == GroupType:
        return PropertyDataGroupObject
    if info.typeString() == ListType:
        return PropertyDataListObject
    if info.typeString() == DictType:
        return PropertyDataDictObject
    return PropertyDataObject


def dataBuild(parentContainer, idx, info, infobuilder, subtype=None, parent=None, uri=[], signalcontroller = None):
    """ Builds the value from the raw value given by the parent container 
        (e.g. Dictionary or List) and idx.
        If raw value is primitive, returns a primitive.
        If value is a list, returns a list of PropertyData/-Object.
        If value is Group-Type, returns a PropertyData.
        info is from type PropertyInfo and contains the information 
        of parentContainer[idx].
        infobuilder: instance of PropertyInfoBuilder for 
                     generating  meta informations
        parent is a PropertyDataObject which someChildPropertyChanged will be connected with its childs.
        uri is a identifier for this entry in the whole dictionary (type: list)
    """
    # Here we build Data for an entry of an container (e.g. list, dict).
    # Without subtype=="property" an primitive can be returned, but here
    # this primitive is capsuled in a PropertyDataObject
    if subtype == "Property":
        PData = propertyObjectForInfo(info)
        res = PData(info, parentContainer, idx, infobuilder, uri=uri, signalcontroller=signalcontroller)
        if parent:
            res.someChildPropertyChanged.connect(parent.someChildPropertyChanged)
        return res
    # Group-Type -> Build PropertyData and connect change-signal-propagation
    if info.typeString() == GroupType:
        res = PropertyData(parentContainer[idx],info.subparameter(),infobuilder, uri=uri, signalcontroller=signalcontroller)
        if parent:
            res.someChildPropertyChanged.connect(parent.someChildPropertyChanged)
        return res
    # List -> Recursive build data for every entry
    #         and connect change-signal-propagation for each
    if info.typeString() == ListType:
        res = []
        for i in range(len(parentContainer[idx])):
            data = dataBuild(parentContainer[idx], i, info.entryInfo(), infobuilder, "Property", uri=uri+[i], signalcontroller=signalcontroller)
            if parent:
                data.someChildPropertyChanged.connect(parent.someChildPropertyChanged)
            res.append(data)
        return res
    # Dictionary -> Recursive build data for every key
    #               and connect change-signal-propagation for each
    if info.typeString() == DictType:
        res = {}
        me = parentContainer[idx]
        for key in me:
            data = dataBuild(me, key, info.entryInfo(), infobuilder, "Property", uri=uri+[key], signalcontroller=signalcontroller)
            if parent:
                data.someChildPropertyChanged.connect(parent.someChildPropertyChanged)
            res[key] = data
        return res
    return parentContainer[idx]

import traceback
import sys
class SignalController(object):
    """ Class which can delay signals """
    def __init__(self):
        self.__locked = 0 # Counter how much lock-calls are present
        self._cache = [] # Cache every Signal, which is not emitted yet
        self.__loging = False # Debugging -> Logging to console

    def enableLoging(self):
        """ Let this object print a stack-trace on every emitLater call
           (Debugging purpose)
        """
        self.__loging = True
    def disableLoging(self):
        """ Stop this object from printing a stack-trace on every emitLater call
           (Debugging purpose)
        """
        self.__loging = False
    def isLocked(self):
        return self.__locked > 0

    def emitLater(self, signal, *args):
        """ emit the signal if not locked, otherwhise wait until unlock """
        if self.__loging:
            print("Signal log  - Traceback")
            for item in traceback.extract_stack():
                print(item)
        fun = lambda: signal.emit(*args)
        if self.isLocked():
            self._cache.append(fun)
        else:
            fun()
    def lock(self):
        """ lock the controller, such that the signals get emit when it's unlocked """
        self.__locked += 1
    def unlock(self):
        """ unlock the controller and emit all cached signals """
        if self.__locked == 0:
            return
        self.__locked -= 1
        if not self.isLocked():
            tmp = self._cache
            self._cache = []
            for fun in tmp:
                fun()

    def lockWhileFunction(self,fun):
        """ Lock this object - then call fun - then unlock this object.
            It can happened that the developer forgot to unlock
            for example when the function fun returns at some point.
            It is saver to use the function with lockWhileFunction
        """

        self.lock()
        res = fun()
        self.unlock()
        return res


class PropertyDataObject(QObject):
    """ Represent a property with a value """
    propertyChanged = pyqtSignal(object, object) # second argument is reason for changing
    someChildPropertyChanged = pyqtSignal(list, object)

    def __init__(self, info, parentcontainer, idx, infobuilder, uri=[], parent=None, signalcontroller=None):
        """ info: PropertyInfo like object,
            parentdict: the dictionary/list containing this value
            idx: the idx, can be integer or string
            uri: a identifier for this property 
                    e.g. uri = ['exclude', 2, 'phase']
            infobuilder: instance of PropertyInfoBuilder
            singalController: instance of SignalController for delay signals
        """
        super(PropertyDataObject, self).__init__(parent)
        self._uri = uri
        self._info = info #type: PropertyInfo
        self._parentcontainer = parentcontainer #type: list
        self._idx = idx
        self._propvalue = None
        self.propertyChanged.connect(lambda _, reason: self.someChildPropertyChanged.emit(self._uri, reason))
        self._infobuilder = infobuilder
        self._signalcontroller = signalcontroller # type: SignalController

    def signalController(self):
        """ Returns an object which can delay signals.
            It will delay signals for all docks in this hierarchy.
            That means that the child and parents DataObjects share this signalController
            and locking it will cause every object here to delay its signals.
        """
        return self._signalcontroller

    def uri(self):
        return self._uri

    def _setRawValue(self, val):
        """ Set the value in the wrapped dictionary """
        self._parentcontainer[self._idx] = val

    def _rawValue(self):
        """ Get the value from the wrapped dictionary """
        return self._parentcontainer[self._idx]
        
    def _buildValue(self):
        """ Build the suitable PropertyData.. for the represented value """
        res = dataBuild(self._parentcontainer, self._idx, self._info,self._infobuilder, parent=self, uri=self.uri(), signalcontroller=self._signalcontroller)
        return res

    def info(self):
        """Should return an PropertyInfo like Object"""
        return self._info


    def value(self):
        """ Return the value. If it is primitiv, the primitiv.
            If it is a group returns a PropertyData.
            If it is repeated returns a list of the PropertyDataObject
        """
        if self._propvalue is None:
            self._propvalue = self._buildValue()
        return self._propvalue

    def listGetValue(self):
        """ Return the value, which should be returned on ___getitem___ of the parent"""
        return self.value()
     
    def setValue(self, value):
        """ Update the value of this PropertyDataObject.
            value should be a raw type not something like another PropertyDataObject.
            If the value has a wrong type an exception get raised.
            E.g. propertydata.setValue(42)
                 propertydata.setValue(["a","b"])
            """
        if not checkIsType(value, self.info().typeString()):
            raise ValueError("Expected {} found type {} at {}".format(self.info().typeString(), type(value),self._uri))
        oldVal = self._rawValue()
        if oldVal == value:
            return 
        self._setRawValue(value)
        self._propvalue = None
        self._emitChange(value, ReasonUpdated(oldVal, value))

    def _emitChange(self, value, reason):
        """ Emit change signal with support for SignalController """
        if self._signalcontroller:
            self._signalcontroller.emitLater(self.propertyChanged, value, reason)
        else:
            self.propertyChanged.emit(value, reason)

    def valueOf(self, relative_uri):
        """ Return the value of a child element.
            relative_uri is the uri (a dictionary with the path like 
            ["prop1", "prop2"])
            which is relative to this PropertyDataObject.
            E.g. if we are prop1 the relative uri would 
            look like ["prop2"].
            If no such element found None will be returned.
        """
        val =  self.value()
        # We want this object
        if relative_uri == []:
            return val
        # We want a child object
        idx = relative_uri[0]
        if isinstance(val, PropertyData):
            return val.valueOf(relative_uri)
        # We have no childs => invalid => return None
        return None

    def __str__(self):
        return "{} at {}".format(self.__class__.__name__,self.uri())

def prototypeOfType(info):
    """ Return some default value for the given type in info.
        Useful for a entry in a list.
    """
    info = info #type: PropertyInfo
    entrytype = info.entryInfo().typeString()
    # May return info.entryInfo().prototype() a better solution?!
    if entrytype == StringType:
        return ""
    if entrytype == BoolType:
        return False
    if entrytype == IntType:
        return 0
    if entrytype == FloatType:
        return 0.0
    if entrytype == GroupType:
        return {}
    if entrytype == EnumType:
        return info.enumOptions()[0]
    if entrytype == UnknownType:
        return None
    if entrytype == DictType:
        return {}

class PropertyDataBuildingException(Exception):
    pass

class PropertyDataGroupObject(PropertyDataObject):
    """ Represent a PropertyDataObject containing PropertyData
        It pass through the getitem, setitem, deltitem, contains operations
    """

    def listGetValue(self):
        """ Return the value, which should be returned on ___getitem___ of the parent"""
        return self.value()

    def __getitem__(self, idx):
        return self.value()[idx]

    def __setitem__(self, idx, val):
        self.value()[idx] = val

    def __delitem__(self, idx):
        del self.value()[idx]

    def __contains__(self,key):
        return key in self.value()

class PropertyDataDictObject(PropertyDataObject):
    """ Represent a PropertyDataObject containing a dictionary"""

    class itemiter(object):
        def __init__(self, parent):
            self.parent = parent # type: PropertyDataDictObject
        def __iter__(self):
            for key in self.parent:
                yield key, self.parent[key]


    def iteritems(self):
        return PropertyDataDictObject.itemiter(self)

    def keys(self):
        return self._rawValue().keys()

    def __getitem__(self, idx):
        return self.value()[idx]

    def __setitem__(self, idx, val):
        if idx in self:
            if self.info().entryInfo().typeString() in [ListType, GroupType]:
                # We can not change  PropertyData e.g. because
                # they are built by a fix procedure
                raise ValueError("Can only change primitive types through this function, not list or groups")
            self.value()[idx].setValue(val)
        else:
            self._rawValue()[idx] = val
            newdata = dataBuild(self._rawValue(), idx, self.info().entryInfo(), self._infobuilder, "Property", uri=self.uri()+[idx], signalcontroller=self._signalcontroller)
            newdata.someChildPropertyChanged.connect(self.someChildPropertyChanged)
            self._propvalue[idx] = newdata
            #self._propvalue = self._buildValue()
            self._emitChange(self.value(), ReasonKeyAdded(idx))

    def __delitem__(self, idx):
        v=self._rawValue()#type: list
        del v[idx]
        #self._propvalue = self._buildValue()
        del self._propvalue[idx]
        self._emitChange(self.value(), ReasonKeyDeleted(idx))

    def __contains__(self,key):
        return key in self.value()

    def __iter__(self):
        for key in self.value():
            yield key

    def getBoringDict(self):
        """ Return the underlying dictionary this object operates on """
        return self._rawValue()

    def listGetValue(self):
        """ Return the value, which should be returned on ___getitem___ of the parent"""
        return self

    def setValue(self, value):
        if not checkIsType(value, self.info().typeString()):
            raise ValueError("Expected {} found type {} at {}".format(self.info().typeString(), type(value), self._uri))
        oldVal = self._rawValue()
        if oldVal == value:
            return
        self._setRawValue(value)
        self._propvalue = self._buildValue()
        self._emitChange(self.value(), ReasonUpdated(oldVal, value))

    def valueOf(self, relative_uri):
        val =  self.value()
        # We want this object
        if relative_uri == []:
            return val
        # We want a child object
        idx = relative_uri[0]
        # Uri element id not an index or not valid
        if type(idx) != str or not idx in self:
            return None
        # Call the function of child with right relative uri
        if isinstance(val[idx], PropertyDataObject) or isinstance(val[idx], PropertyData):
            return val[idx].valueOf(relative_uri[1:])
        # If the child is a primitive value but the uri want to
        # step into the next element => Invalid => return None
        return None

class PropertyDataListObject(PropertyDataObject):
    """ Represent a property with multiple values """

    def listGetValue(self):
        """ Return the value, which should be returned on ___getitem___ of the parent"""
        return self

    def pushBack(self, value):
        """ Append the raw value to the list """
        idx = len(self._rawValue())
        self._rawValue().append(value)
        if self._propvalue is None:
            self._propvalue = self._buildValue()
        else:
            newdata = dataBuild(self._rawValue(), idx, self.info().entryInfo(), self._infobuilder, "Property", uri=self.uri()+[idx], signalcontroller=self._signalcontroller)
            newdata.someChildPropertyChanged.connect(self.someChildPropertyChanged)
            self._propvalue.append(newdata)
            #self._propvalue = self._buildValue()
        self._emitChange(self.value(), ReasonAdded(len(self._rawValue())-1))


    def removeObject(self, idx):
        v=self._rawValue()#type: list
        oldval = v[idx]
        del v[idx]
        self._propvalue = self._buildValue()
        self._emitChange(self.value(), ReasonRemoved(idx, oldval))

    def insert(self, idx, val):
        v=self._rawValue()#type: list
        v.insert(idx,val)
        self._propvalue = self._buildValue()
        self._emitChange(self.value(), ReasonAdded(idx))

    def remove(self, val):
        v=self._rawValue()#type: list
        idx = v.index(val)
        v.remove(val)
        self._propvalue = self._buildValue()
        self._emitChange(self.value(), ReasonRemoved(idx, val))

    def index(self,val):
        """ Returns the index of val """
        return self._rawValue().index(val)

    def setValue(self, value):
        if not checkIsType(value, self.info().typeString()):
            raise ValueError("Expected {} found type {} at {}".format(self.info().typeString(), type(value), self._uri))
        oldVal = self._rawValue()
        if oldVal == value:
            return
        self._setRawValue(value)
        self._propvalue = self._buildValue()
        self._emitChange(self.value(), ReasonUpdated(oldVal, value))

    def prototypeValue(self):
        """ Returns a raw value (not something like PropertyDataObject)
            from an new object in this list
        """
        return prototypeOfType(self.info())

    def valueOf(self, relative_uri):
        """ Return the value of a child element.
            relative_uri is the uri (a dictionary with the path like 
            ["listprop", 1, "prop2"])
            which is relative to this PropertyDataListObject.
            E.g. if we are listprop the relative uri would 
            look like [1, "prop2"].
            If no such element found None will be returned.
        """
        val =  self.value()
        # We want this object
        if relative_uri == []:
            return val
        # We want a child object
        idx = relative_uri[0]
        # Uri element id not an index or not valid
        if type(idx) != int or idx < 0 or idx >= len(val):
            return None
        # Call the function of child with right relative uri
        if isinstance(val[idx], PropertyDataObject) or isinstance(val[idx], PropertyData):
            return val[idx].valueOf(relative_uri[1:])
        # If the child is a primitive value but the uri want to
        # step into the next element => Invalid => return None
        return None

    def __getitem__(self, idx):
        item = self.value()[idx]
        return item.listGetValue()

    def __setitem__(self, idx, val):
        item = self.value()[idx]
        if item.info().typeString() in [ListType, GroupType]:
            # We can not change  PropertyData e.g. because
            # they are builded by a fix procedure
            raise ValueError("Can only change primitive types through this function, not list or groups")
        item.setValue(val) 

    def __delitem__(self, idx):
        self.removeObject(idx)

    def __iter__(self):
        for el in self.value():
            yield el.listGetValue()

    def __len__(self):
        return len(self._rawValue())

    def __contains__(self, item):
        for el in self:
            if el == item:
                return True
        return False


class PropertyData(QObject):
    """ Reresent a collection of properties """

    # Gets emit, whenever some property get changed
    # Get called with an identifier list which looks like this
    # ["propname","propnameoflist",3,"antoherchild","someItem"]
    # and a object which represent the reason for emitting
    # (e.g. ReasonUpdated, ReasonGiven, ...)
    someChildPropertyChanged = pyqtSignal(list, object)

    # propertyGotGiven (value: PropertyDataObject)
    propertyGotGiven = pyqtSignal(object)
    # propertyGotUnGiven (name: str)
    propertyGotUnGiven = pyqtSignal(str)

    def __init__(self, valuedict, metadict, infobuilder, uri=[],parent=None, signalcontroller = None):
        """ valudict: Recursive list of {key: value}
            metadict: List of {key: protoinfo.Parameter }
            infobuilder: instance of PropertyInfoBuilder
                         which generates the meta informations used here
        """
        super(PropertyData, self).__init__(parent)
        if type(valuedict) != dict:
            raise PropertyDataBuildingException("valuedict should be a dict, is {} instead at {}".format(type(valuedict), uri))
        self.valuedict = valuedict #type: dict
        if type(metadict) != dict:
            raise PropertyDataBuildingException("Metadict should be a dict, is {} instead at {}".format(type(metadict), uri))
        self.metadict = metadict #type: dict
        self._buildProps = None
        self._uri = uri
        self._infobuilder = infobuilder #type: PropertyInfoBuilder
        self._signalcontroller = signalcontroller #type: SignalController

        self.__allavailprops = None

    def __str__(self):
        return "{} at {}".format(self.__class__.__name__,self.uri())

    def uri(self):
        return self._uri

    def getBoringDict(self):
        """ Return the dictionary this class writes and read on """
        return self.valuedict

    def valueOf(self, relative_uri):
        """ Return the value of a child element.
            relative_uri is the uri (a dictionary with the path like 
            ["prop1", "listprop", 1, "prop2"])
            which is relative to this PropertyData.
            E.g. if we are in PropertyData of prop1 the list would 
            look like ["listprop", 1, "prop2"].
            If no such element found None will be returned.
        """
        if relative_uri == []:
            return None
        for el in self.givenProperties(): #type: PropertyDataObject
            if el.info().name() == relative_uri[0]:
                return el.valueOf(relative_uri[1:])
        return None

    def signalController(self):
        """ Returns an object which can delay signals.
            It will delay signals for all docks in this hierarchy.
            That means that the child and parents DataObjects share this signalController
            and locking it will cause every object here to delay its signals.
        """
        return self._signalcontroller

    def __buildProperty(self, name,  meta):
        meta = meta #type: info.Parameter
        uri = self.uri()+[name]
        info = self._infobuilder.buildInfo(name, meta, uri)
        PropertyType = propertyObjectForInfo(info)
        res = PropertyType(info, self.valuedict, name, self._infobuilder, uri=uri, signalcontroller = self._signalcontroller)
        res.someChildPropertyChanged.connect(self.someChildPropertyChanged)
        return res

    def __buildProperties(self):
        res = []
        for el in self.valuedict:
            res.append(self.__buildProperty(el, self.metadict[el]))
        return res

    def giveProperty(self, name, value):
        """ Add the property "name" to the given one 
            and sets its value to "value".
            value should be the raw value, not something like 
            PropertyDataObject.
            If the property is already given, it gets overwritten
        """
        item = self.getChildDataObject(name)
        allprops = self.allAvailableProperties()
        if not name in allprops:
            raise ValueError("Unexpected key {} in {}".format(name,self._uri))
        if not checkIsType(value,allprops[name].typeString()):
            raise ValueError("Expected {} found type {}".format(allprops[name].typeString(), type(value)))
        if item:
            item.setValue(value)
            return
        self.valuedict[name] = value
        if  self._buildProps is None:
            self.__buildProperties()
        else:
            newProperty = self.__buildProperty(name, self.metadict[name])
            self._buildProps.append(newProperty)
        self._emitGiven(newProperty, name)

    def givePropertyDefault(self, name):
        """ Like giveProperty but instead of give an explicit value the property will
            be initialize with a default value (info.prototype() of this property).
            If the value name is already given, nothing happen.
        """
        if item in self:
            return
        props = self.allAvailableProperties() #type: Dict[str,PropertyInfo]
        if not name in props.keys():
            raise ValueError("Property {} is not a valid one".format(name))
        return self.giveProperty(name, props[name].prototype())


    def _emitGiven(self, newProp, name):
        """ Emit someChildPropertyChanged-signal for giving a property with support for SignalController """
        if self._signalcontroller:
            self._signalcontroller.emitLater(self.propertyGotGiven, newProp)
            self._signalcontroller.emitLater(self.someChildPropertyChanged, self.uri()+[name], ReasonGiven(name))
        else:
            self.propertyGotGiven.emit(newProp)
            self.someChildPropertyChanged.emit(self.uri()+[name], ReasonGiven(name))


    def ungiveProperty(self, name):
        """ Unset the property with the given name """
        del self.valuedict[name]
        for idx, el in enumerate(self._buildProps):
            if el.info().name() == name:
                del self._buildProps[idx]
                break
        self._emitUngiven(name)

    def _emitUngiven(self, name):
        """ Emit someChildPropertyChanged-signal for ungiving a property with support for SignalController """
        if self._signalcontroller:
            self._signalcontroller.emitLater(self.propertyGotUnGiven, name)
            self._signalcontroller.emitLater(self.someChildPropertyChanged, self.uri()+[name], ReasonUngiven(name))
        else:
            self.propertyGotUnGiven.emit(name)
            self.someChildPropertyChanged.emit(self.uri()+[name], ReasonUngiven(name))

        

    def allAvailableProperties(self):
        """ Returns a dictionary, which looks like this:
            { "name_of_property1": PropertyInfo1,...}
        """
        if self.__allavailprops: # Lazy initialization
            return self.__allavailprops
        res = {}
        for key in self.metadict: # type: str
            res[key] = self._infobuilder.buildInfo(key, self.metadict[key], self.uri()+[key])
        self.__allavailprops = res

        return res

    def givenProperties(self):
        """ Returns a list with infos about all properties:
            Structure looks like this:
            [
                PropertyDataObject(), ...
            ]
        """
        if self._buildProps is None:
            self._buildProps = self.__buildProperties()
        return self._buildProps

    def getChildDataObject(self, key):
        """ Return the child PropertyDataObject of the given key """
        props = self.givenProperties()
        for element in props: # type: PropertyDataObject
            if element.info().name() == key:
                return element
        return None


    def __getitem__(self, key):
        """ Returns the value of the child object with the given key, if it's given """
        el = self.getChildDataObject(key)
        if el is None:
            raise ValueError("PropertyData does not have the value {} defined at {}".format(key, self._uri))
        return el.listGetValue()

    def __setitem__(self, key, val):
        """ Sets the property key to the value val, if it is a primitive (not a list or another group) """
        allProps = self.allAvailableProperties()
        if not key in allProps:
            raise ValueError("Property {} cannot be set this property is not valid".format(key)) 
        info = self.allAvailableProperties()[key]
        if info.typeString() in [ListType, GroupType]:
            # We can not change  PropertyData e.g. because
            # they are builded by a fix procedure
            raise ValueError("Can only change primitive types through this function, not list or groups")
        self.giveProperty(key,val)

    def __contains__(self,key):
        """ Return true iff the value key is a given property """
        props = self.givenProperties()
        for element in props: #type: PropertyDataObject
            if element.info().name() == key:
                return True
        return False

    def __delitem__(self, key):
        self.ungiveProperty(key)

    def __iter__(self):
        props = self.givenProperties()
        for element in props: #type: PropertyDataObject
            yield element.info().name()