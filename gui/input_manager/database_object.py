from backend.input_db.lmdb_input import *
from backend.input_db.leveldb_input import *
from backend.input_db.hdf5_txt_input import *


class DatabaseObject:
    '''abstraction to make accessing databases easy and consistent across types'''

    def __init__(self):
        self._legalTypes = ["LMDB", "LEVELDB", "HDF5TXT"]
        self._db = None
        self._path = None
        self._dbType = None
        self._openPath = None
        self._openDBType = None
        self._projectPath = None

    def __del__(self):
        '''on delete: close'''
        if self._db is not None:
            self._db.close()

    def setDB(self, path, type):
        '''set the path and type of a database.'''
        if self.isLegalType(type):
            self._path = unicode(path)
            self._dbType = unicode(type)

    def open(self):
        '''open a database.'''
        if self._db is not None:
            self.close()
        if self._path is not None and self.isLegalType(self._dbType):
            if self._dbType == 'LMDB':
                self._db = LmdbInput()
            if self._dbType == 'LEVELDB':
                self._db = LeveldbInput()
            if self._dbType == 'HDF5TXT':
                self._db = Hdf5TxtInput()
                if self._projectPath:
                    self._db.setProjectPath(self._projectPath)

            self._db.setPath(self._path)
            self._db.open()
            self._openPath = self._path
            self._openDBType = self._dbType

    def openFromPath(self, path, type):
        '''directly open db from path.'''
        if self.isLegalType(type):
            self._path = unicode(path)
            self._dbType = unicode(type)
            self.open()

    def close(self):
        '''close the db.'''
        if self._db is not None:
            self._db.close()
        self._db = None
        self._openPath = None
        self._openDBType = None

    def getDataCount(self):
        '''get the number of entries in the database.'''
        if self._db is not None:
            return self._db.getDataCount()

    def getDimensions(self):
        '''get the dimensions.'''
        if self._db is not None:
            return self._db.getDimensions()

    def verifyConsistency(self):
        '''check if all entries have the same channel number and size.
        This may take a lot of time since every entry has to be checked.'''
        if self._db is not None:
            return self._db.verifyConsistency()

    def getPath(self):
        '''get the path of the current open db.
         if no db is open get the path of the to be opened db.'''
        if self._db is not None:
            return self._openPath
        return self._path

    def getDBType(self):
        '''get the type of the current open db.
         if no db is open get the type of the to be opened db.'''
        if self._db is not None:
            return self._openDBType
        return self._dbType

    def isOpen(self):
        '''check if a db is open.'''
        if self._db is not None:
            return self._db.isOpen()
        return False

    def isLegalType(self, type):
        '''check if the passed type is legal.'''
        if type in self._legalTypes:
            return True
        return False

    def setProjectPath(self, path):
        '''set the project path for the HDF5TXT format'''
        if self._dbType == "HDF5TXT":
            self._projectPath = path