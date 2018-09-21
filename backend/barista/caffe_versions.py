import os
from backend.barista.utils.logger import LogCaller

versions = []
restart = False

def saveVersions(path=""):
    """Saves the versions to file."""
    import pickle
    try:
        with open(os.path.join(path, "caffeVersions"), "w") as outfile:
            global versions
            pickle.dump(versions, outfile)
        return True
    except IOError as e:
        return False

def loadVersions(path=""):
    """Reloads the versions from file."""
    import pickle
    try:
        with open(os.path.join(path, "caffeVersions"), "r") as infile:
            global versions
            versions = pickle.load(infile)
        return True
    except IOError as e:
        return False

def getAvailableVersions():
    """Returns all to barista available caffe versions."""
    global versions
    return versions

def addVersion(version, path=""):
    """Adds a caffe version to barista.
        Returns True if the version was successfully added
        Returns False if version could not be added"""
    try:
        global versions
        versions.index(version)
        return False
    except Exception as e:
        versions.append(version)
        return saveVersions(path)

def removeVersion(version, path=""):
    """Removes a caffe version from barista.
        Returns True if the version was successfully removed
        Returns False if version could not be removed"""
    try:
        global versions
        versions.remove(version)

        return saveVersions(path)
    except Exception as e:
        return False

def versionCount():
    """Returns the number of stored caffe versions"""
    global versions
    return len(versions)

def getVersionByName(name):
    """Returns the version object depending on the given name"""
    global versions
    for version in versions:
        if version.getName() == name:
            return version
    return None

def getDefaultVersion():
    """Returns the default version object"""
    if versionCount() > 0:
        global versions
        return versions[0]
    else:
        return None

def setDefaultVersion(name, path=""):
    """Sets the default caffe version of barista,
        implemented as beeing the first element of the list
        Returns True if the default version was successfully set
        Returns False if not"""
    version = getVersionByName(name)
    if version != None:
        global versions
        index = versions.index(version)
        temp = versions[0]
        versions[0] = versions[index]
        versions[index] = temp
        return saveVersions(path)
    else:
        return False

class caffeVersion():
    """This class represents a specific caffe version."""

    def __init__(self, name, root, binary, python, proto):
        self.name = name
        self.root = root
        self.binary = binary
        self.python = python
        self.proto = proto

    def getName(self):
        return self.name

    def getRootpath(self):
        return self.root

    def getBinarypath(self):
        return self.binary

    def getPythonpath(self):
        return self.python

    def getProtopath(self):
        return self.proto

    def setName(self, name):
        self.name = name

    def setName(self, root):
        self.root = root

    def setBinarypath(self, binary):
        self.binary = binary

    def setPythonpath(self, python):
        self.python = python

    def setProtopath(self, proto):
        self.proto = proto