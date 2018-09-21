from os import path

from backend.barista.utils.logger import Log
from backend.input_db.hdf5_input import *


class Hdf5TxtInput:
    def __init__(self):
        self._db = []
        self._path = None
        self._logid = Log.getCallerId("HDF5TXT Input")
        self._projectPath = None

    def __del__(self):
        self.close()

    def setPath(self, path):
        self._path = os.path.normpath(path)

    def open(self):
        if self._db:
            self.close()
        if self._path is not None:
            if os.path.exists(self._path):
                lines = [line.rstrip('\n') for line in open(self._path)]
                hdf5Count = 0
                for line in lines:
                    if line is not "":
                        if line[:1] == '.':
                            line = self._makepath(line)
                        i = len(self._db)
                        self._db.append(Hdf5Input(pathOfHdf5Txt=True))
                        self._db[i].setPath(line)
                        self._db[i].open()
                        if self._db[i].isOpen():
                            hdf5Count += 1
                if hdf5Count == 0:
                    self._db = None
                    Log.error("File contained no valid paths to HDF5 files: {}".format(self._path), self._logid)


    def close(self):
        if self._db:
            for db in self._db:
                db.close()
        self._db = []

    def getDataCount(self):
        if self._db:
            sum = {}
            for db in self._db:
                sum = self._sumDataCount(sum, db.getDataCount())
            return sum

    def getDimensions(self):
        if self._db:
            d = {}
            for db in self._db:
                d = self._combineDim(d, db.getDimensions())
            return d

    def verifyConsistency(self):
        if self._db:
            d = self._db[0].getDimensions()
            for db in self._db:
                if not db.verifyConsistency():
                    return False
                if not self._compareDim(d, db.getDimensions()):
                    return False
            return True

    def isOpen(self):
        if self._db:
            return True
        return False

    def setProjectPath(self, path):
        self._projectPath = path

    def _sumDataCount(self, d1, d2):
        dataCountDict = {}
        if d1 or d2:
            dataCountDict =  {k: d1.get(k, 0) + d2.get(k, 0) for k in set(d1) | set(d2)}
        return dataCountDict


    def _combineDim(self, d1, d2):
        return {k: max(d1.get(k, 0), d2.get(k, 0)) for k in set(d1) | set(d2)}

    def _compareDim(self, d1, d2):
        l = [d1.get(k) == d2.get(k) for k in set(d1) | set(d2)]
        if False in l:
            return False
        return True

    """
    Converts a path that is considered to be relative to the project path into an absolute path.

    @author: ..., j_stru18
    @param relpath a path that should be relative to the project path
    """
    def _makepath(self, relpath):
        if self._projectPath:
            p = path.abspath(path.join(self._projectPath, relpath))
            return p
        return relpath
