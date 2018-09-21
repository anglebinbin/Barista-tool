import os.path

import h5py as h5
import numpy as np

from backend.barista.utils.logger import Log


class Hdf5Input:
    def __init__(self, pathOfHdf5Txt=False):
        self._db = None
        self._path = None
        self._pathOfHdf5Txt = pathOfHdf5Txt  # HDF5TXT files can contain commentary lines that are no paths
        self._logid = Log.getCallerId('HDF5 Input')

    def __del__(self):
        self.close()

    def setPath(self, path):
        '''set the path of the database.'''
        self._path = path

    def getPath(self):
        '''get the path of this HDF5Input object'''
        return self._path

    def open(self):
        '''open the database from the set path.'''
        if self._db:
            self.close()
        if self._path:
            if os.path.exists(self._path):
                try:
                    self._db = h5.File(self._path, 'r')
                except:
                    Log.error("File not valid HDF5: " + self._path, self._logid)
                    self._db = None
            elif not self._pathOfHdf5Txt:
                Log.error("File does not exist: " + self._path, self._logid)

    def close(self):
        if self._db:
            self._db.close()
        self._db = None

    def getDataCount(self):
        if self._db:
            d = {}
            for i in range(0, len(self._db.keys())):
                d[self._db.keys()[i]] = len(self._db.values()[i])
            return d

    def getDimensions(self):
        if self._db:
            d = {}
            for i in range(0, len(self._db.keys())):
                ar = np.array(self._db.values()[i][0])
                d[self._db.keys()[i]] = ar.shape
            return d

    def verifyConsistency(self):
        if self._db:
            for i in range(0, len(self._db.keys())):
                ar = np.array(self._db.values()[i][0])
                for j in range(0, len(self._db.values()[i])):
                    ar2 = np.array(self._db.values()[i][j])
                    if not self._dimCompare(ar.shape, ar2.shape):
                        return False
            return True

    def isOpen(self):
        if self._db:
            return True
        return False

    def _dimCompare(self, d1, d2):
        if not d1 and not d2:  # both empty
            return True
        if d2 and not d1:  # d1 empty
            return False
        if d1 and not d2:  # d2 empty
            return False
        if len(d1) != len(d2):  # different dim count
            return False
        for i in range(0, len(d1)):  # dims not matching
            if d1[i] != d2[i]:
                return False
        return True
