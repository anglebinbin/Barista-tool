import os.path

import lmdb  # pip install lmdb

from backend.barista.utils.logger import Log


class LmdbInput:
    def __init__(self):
        self._env = None
        self._path = None
        self._cursor = None
        self._txn = None
        self.logid = Log.getCallerId("LMDB Input")

    def __del__(self):
        self.close()

    def setPath(self, path):
        '''set the path of the database.'''
        self._path = path

    def open(self):
        '''open the database from the set path.'''
        if self._env:
            self.close()
        if self._path:
            if os.path.exists(self._path + "data.mdb") or os.path.exists(self._path + "/data.mdb"):
                self._env = lmdb.open(self._path, max_dbs=2)
            else:
                Log.error("Dir is not valid LMDB: " + self._path, self.logid)

    def close(self):
        '''close and clean up the database.'''
        if self._env:
            self._env.close()
        self._env = None
        self._txn = None
        self._cursor = None

    def getDataCount(self):
        '''get the number of entries in the database'''
        if self._env:
            return {"data": self._env.stat()['entries']}

    def getDimensions(self):
        '''get the dimensions of the first entry'''
        if self._env:
            datum = self._getFirstDatum()
            if datum:
                dim = (datum.channels, datum.height, datum.width)
                return {"label": (), "data": dim}  # TODO dim of label

    def verifyConsistency(self):
        '''check if all entries have the same channel number and size.
        This may take a lot of time since every entrie has to be checked.'''
        if self._env:
            if self.getDataCount() < 2:
                return True
            first = self._getFirstDatum()
            if first:
                channels = first.channels
                width = first.width
                height = first.height

                while self._cursor.next():
                    if channels is not self._getCurrentDatum().channels \
                            or width is not self._getCurrentDatum().width \
                            or height is not self._getCurrentDatum().height:
                        return False

                return True

    def isOpen(self):
        '''check if db is open:'''
        if self._env:
            return True
        return False

    def _openTransaction(self):
        if self._env:
            if self._txn is None:
                self._txn = self._env.begin()

    def _openCursor(self):
        if self._env:
            if self._txn:
                if self._cursor is None:
                    self._cursor = self._txn.cursor()

    def _getFirstDatum(self):
        self._openTransaction()
        self._openCursor()
        if self._cursor:
            self._cursor.first()
            return self._getCurrentDatum()

    def _getCurrentDatum(self):
        from backend.caffe.path_loader import PathLoader
        caffe = PathLoader().importCaffe()
        if self._cursor:
            raw_datum = self._cursor.value()
            datum = caffe.proto.caffe_pb2.Datum()

            try:
                datum.ParseFromString(raw_datum)
            except:
                Log.error("LMDB does not contain valid data: " + self._path, self.logid)
                return None
            return datum
