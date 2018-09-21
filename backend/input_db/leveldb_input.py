import leveldb  # pip install leveldb
import os.path

from backend.barista.utils.logger import Log


class LeveldbInput:
    def __init__(self):
        self._db = None
        self._path = None
        self.logid = Log.getCallerId("LEVELDB Input")

    def __del__(self):
        self.close()

    def setPath(self, path):
        '''set the path of the database.'''
        self._path = path

    def open(self):
        '''open the database from the set path.'''
        if self._db:
            self.close()
        if self._path:
            if os.path.exists(self._path + "CURRENT") or os.path.exists(self._path + "/CURRENT"):
                self._db = leveldb.LevelDB(self._path)
            else:
                Log.error("Dir is not valid LEVELDB: " + self._path, self.logid)

    def close(self):
        '''close and clean up the database.'''
        self._db = None

    def getDataCount(self):
        '''get the number of entries in the database'''
        if self._db:
            iter = self._getIter()
            if iter:
                number = 0
                for elem in iter:
                    number = number + 1
                return {"data": number}

    def getDimensions(self):
        '''get the dimensions of the first entry'''
        datum = self._getFirstDatum()
        if datum:
            dim = (datum.channels, datum.height, datum.width)
            return {"label": (), "data": dim}  # TODO dim of label

    def verifyConsistency(self):
        '''check if all entries have the same channel number and size.
        This may take a lot of time since every entry has to be checked.'''
        from backend.caffe.path_loader import PathLoader
        caffe = PathLoader().importCaffe()
        if self.getDataCount() < 2:
            return True
        first = self._getFirstDatum()
        if first:
            channels = first.channels
            width = first.width
            height = first.height

            iter = self._getIter()
            if iter:
                for key, value in iter:
                    raw_datum = value
                    datum = caffe.proto.caffe_pb2.Datum()

                    datum.ParseFromString(raw_datum)

                    if channels is not datum.channels \
                            or width is not datum.width \
                            or height is not datum.height:
                        return False
                return True

    def isOpen(self):
        '''check if db is open.'''
        if self._db:
            return True
        return False

    def _getIter(self):
        if self._db:
            return self._db.RangeIter()

    def _getFirstDatum(self):
        from backend.caffe.path_loader import PathLoader
        caffe = PathLoader().importCaffe()
        iter = self._getIter()
        if iter:
            for key, value in iter:
                raw_datum = value
                datum = caffe.proto.caffe_pb2.Datum()

                try:
                    datum.ParseFromString(raw_datum)
                except:
                    Log.error("LEVELDB does not contain valid data: " + self._path, self.logid)
                    return None
                return datum
