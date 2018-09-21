class State:
    """ Pseudo Enumeration for the states a session could be in.
    """
    UNDEFINED = 0
    WAITING = 1
    RUNNING = 2
    PAUSED = 3
    FAILED = 5
    FINISHED = 6
    INVALID = 7
    NOTCONNECTED = 8

def baristaSessionFile(directory):
    import os
    """ Returns the filename of the config-json file in the given directory """
    return os.path.join(directory,  "sessionstate.json")

class Paths:
    # class "constants" defining common file names inside of a session
    FILE_NAME_SOLVER = "solver.prototxt"
    FILE_NAME_NET_ORIGINAL = "net-original.prototxt"
    FILE_NAME_NET_INTERNAL = "net-internal.prototxt"
    FILE_NAME_SESSION_JSON = "sessionstate.json"

class Events:
    import re
    events = {
            # exceptions
            'FileNotFound': re.compile('Check failed: mdb_status == 0 \(([\d]+) vs\. 0\) No such file or directory'),
            'OutOfGPU': re.compile('Check failed: error == cudaSuccess \(([\d]+) vs\. 0\)  out of memory'),
            'NoSnapshotPrefix': re.compile('Check failed: param_\.has_snapshot_prefix\(\) In solver params, snapshot is specified but snapshot_prefix is not'),
            # session finished
            'OptimizationDone': re.compile('Optimization Done'),
            # iterations
            'max_iter': re.compile('max_iter:[\s]+([\d]+)'),
            # snapshots
            'state_snapshot': re.compile('Snapshotting solver state to (?:binary proto|HDF5) file (.+\.solverstate[\.\w-]*)'),
            'model_snapshot': re.compile('Snapshotting to (?:binary proto|HDF5) file (.+\.caffemodel[\.\w-]*)')
        }