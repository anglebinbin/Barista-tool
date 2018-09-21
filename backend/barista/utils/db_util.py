import os
import hashlib

from backend.barista.utils.logger import *

"""
This file contains functions that deal with the path handling and hashing of database files

@author: j_stru18
"""

"""
Logger ID used in functions below.
"""
DBUTIL_LOGGER_ID = Log.getCallerId("dbutil")

"""
returns a hash value by calling a hash function for the opened file of the given path
Warning: This is not meant to be used for HDF5TXT files. You need to use getHdf5List() and call getMultipleHash
with the result.

@author ..., f_prob02, j_stru18, l_hu0002
@param db_path: a path to a database file, for example a data.mdb
@return a hash value for the hashed database as int
@pre dbPath is a valid path
"""
def getHash(dbPath):
    hashObject = hashlib.sha256()
    with open(dbPath, "rb") as openDB:
        for chunk in iter(lambda: openDB.read(2**15), b""):
            hashObject.update(chunk)
    return int(hashObject.hexdigest(), 16)

"""
hashes all files in the given paths

@author j_stru18
@param dbPaths a list of paths
@return a hash value for all files in the given paths as int
"""
def getMultipleHash(dbPaths):
    hashValue = 0
    for path in dbPaths:  # hash all the old .h5 and .hdf5 files in HDF5TXT
        if os.path.exists(path):
            hashValue += getHash(path)
    return hashValue

"""
returns the sha256 hash value of a single string

@author j_stru18
@param inputStr : the string that has to be hashed
@return : the hashValue of the string
"""
def getStringHash(inputStr):
    hashObject = hashlib.sha256()
    hashObject.update(inputStr)
    return int(hashObject.hexdigest(), 16)

"""
returns a list containing the path to a lmdb, if this file exists

@author j_stru18
@param path : a string that is supposed to be a valid path for a lmdb
@return a list that contains the given path
"""
def getLMDBList(path):
    pathList = []
    if os.path.exists(path):
        pathList.append(path)
    return pathList

"""
@author j_stru18
@param path : a string that is supposed to be a valid path for a leveldb (directory path containing a CURRENT file)
@return a list that contains all the .sst and .ldb files in the directory
"""
def getLEVELDBList(directoryPath):
    pathList = []
    if os.path.exists(os.path.join(directoryPath, "CURRENT")):
        for db_file in os.listdir(directoryPath):
            if db_file.endswith(".sst") or db_file.endswith(".ldb"):
                pathList.append(os.path.join(directoryPath, db_file))
    return pathList

"""
returns a list containing the paths to all .h5 or .hdf5 files that are specified in a HDF5TXT file, if this file
exists

@author j_stru18
@ensure: if filePath points to a valid file, it has to a textfile
@param filePath : a string that is supposed to be a valid path for a HDF5TXT file
@return a list that contains all .h5 and .hdf5 files in the HDF5TXT
"""
def getHdf5List(filePath):
    pathList = []
    if os.path.exists(filePath):
        lines = [line.rstrip('\n') for line in open(filePath)]
        for line in lines:
            if line.endswith(".h5") or line.endswith(".hdf5"):
                if os.path.exists(line):  # absolute path in txt
                    pathList.append(line)
                elif os.path.exists(os.path.normpath(os.path.join(filePath, line))):  # path relative to HDF5 location
                    pathList.append(os.path.normpath(os.path.join(filePath, line)))
                else:
                    Log.error("HDF5 textfile contained invalid path {}".format(line), DBUTIL_LOGGER_ID)
    return pathList



"""
returns a list containing all lines of the file that filePath points at


@author: j_stru18
@param filePath : a string that is supposed to be a path for a txt file
@return: a list that contains all lines of that file
"""
def getLinesAsList(filePath):
    pathList = []
    if os.path.exists(filePath):
        pathList = [line for line in open(filePath)]
    return pathList


"""
Given the name of a file, this method returns its type

@author j_stru18
@param filename a string that represents the file's name
@return its type as a string
"""
def getType(filename):
    type = ""
    if filename == "CURRENT":
        type = "LEVELDB"
    else:
        extension = filename[-4:]
        if extension == ".mdb":
            type = "LMDB"
        elif extension == ".ldb":
            type = "LEVELDB"
        elif extension == ".txt":
            type = "HDF5TXT"
        elif filename[-5:] == ".hdf5":
            type = "HDF5"
        elif filename[-3:] == ".h5":
            type = "HDF5"
    return type

"""
Given the path and type of a file, this method returns the paths to all files that this db file uses to store data.

@author: j_stru18
@param filePath : the path to a db file as string
@param type : the db file's type as string
@return : all paths of this db file that are used to store data
"""
def getDBPathsByType(filePath, type):
    dbpaths = []
    if type == 'LMDB':
        filePath = os.path.normpath(os.path.join(filePath, "data.mdb"))
        dbpaths = getLMDBList(filePath)
    elif type == 'LEVELDB':
        directoryPath = os.path.normpath(filePath)
        dbpaths = getLEVELDBList(directoryPath)
    elif type == 'HDF5TXT':
        filePath = os.path.normpath(filePath)
        dbpaths = getHdf5List(filePath)
    elif type == 'HDF5':
        dbpaths.append(filePath)
    else:
        Log.error("File has the wrong type: {}".format(type), DBUTIL_LOGGER_ID)
    return dbpaths



