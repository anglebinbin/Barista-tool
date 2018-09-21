import imp
import backend.barista.caffe_versions as caffeVersions
import os

class Singleton(type):
    """This metaclass is used to provide the singleton pattern in a generic way.

    See http://stackoverflow.com/a/6798042 for source and further explanation.
    TODO outsource this class to use the same pattern in the complete project?
    """
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class PathLoader:

    __metaclass__ = Singleton

    def __init__(self):
        self.path = caffeVersions.getDefaultVersion().getPythonpath()

    def importCaffe(self):
        import importlib
        import sys

        sys.path.insert(0, self.path)  # stellt sicher, dass der angegebene Pfad als erstes durchsucht wird
        try:
            caffe = importlib.import_module("caffe")
            sys.path.pop(0)
            return caffe
        except ImportError as e:
            print(e)
            exit(1)

    def importProto(self):
        import importlib
        import sys

        sys.path.insert(0, self.path)  # stellt sicher, dass der angegebene Pfad als erstes durchsucht wird
        try:
            proto = importlib.import_module("caffe.proto.caffe_pb2")
            sys.path.pop(0)
            return proto
        except ImportError as e:
            print(e)
            exit(1)