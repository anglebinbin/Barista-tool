
StringType = "string"
IntType = "int"
FloatType = "float"
EnumType = "enum"
GroupType = "group"
ListType = "list"
BoolType = "bool"
DictType = "dict"
UnknownType = "unknown"

def checkIsType(instance, typestring):
    """ Checks if instance match the type expected from typestring.
        E.g. checkIsType(22, IntType) == True
             checkIsType(true, StringType) == False
    """
    if typestring in [StringType, EnumType]:
        return type(instance) in [str, unicode]
    if typestring == IntType:
        return type(instance) in [int, long]
    if typestring == FloatType:
        return type(instance) in [int, long, float]
    if typestring in [GroupType, DictType]:
        return type(instance) == dict
    if typestring  == BoolType:
        return type(instance) == bool
    if typestring in [ListType]:
        return type(instance) == list
    if typestring == UnknownType:
        return True
    raise ValueError("Unhandable typestring {}".format(typestring))
    
