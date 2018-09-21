import os
import re
from abc import abstractmethod

class SessionCommon():
    def __init__(self):
        self.lastSolverState = None
        self.directory = None

    @abstractmethod
    def getLogs(self):
        pass

    @abstractmethod
    def getSnapshotDirectory(self):
        pass

    def getLastSnapshot(self):
        """ Return the last snapshot/solverstate for this session.

        The last snapshot name is searched in the log files.
        """
        if self.last_solverstate:
            if os.path.isfile(os.path.join(self.directory, self.last_solverstate)):
                return self.last_solverstate
        self.last_solverstate = self._getLastSnapshotFromLogFiles()
        if self.last_solverstate:
            if os.path.isfile(os.path.join(self.directory, self.last_solverstate)):
                return self.last_solverstate
        self.last_solverstate = self._getLastSnapshotFromSnapshotDirectory()
        if self.last_solverstate:
            if os.path.isfile(os.path.join(self.directory, self.last_solverstate)):
                return self.last_solverstate
        return None

    def _getLastSnapshotFromLogFiles(self):
        """ Try to find the last snapshot name in the log file.

        Return the name of the solverstate file if it was found.
        """
        # get all log files
        log_files = {}
        regex_filename = re.compile('[\d]+\.([\d]+)\.log$')
        for entry in os.listdir(self.getLogs()):
            filename_match = regex_filename.search(entry)
            if filename_match:
                # key files by run id
                try:
                    run_id = int(filename_match.group(1))
                    log_files[run_id] = entry
                except:
                    pass
        last_solverstate = None
        for run_id in reversed(sorted(log_files.keys())):
            with open(os.path.join(self.getLogs(), log_files[run_id])) as f:
                # find the last snapshot in the file
                regex_snapshot = re.compile(
                    'Snapshotting solver state to (?:binary proto|HDF5) file (.+\.solverstate[\.\w-]*)')
                for line in f:
                    snapshot_match = regex_snapshot.search(line)
                    if snapshot_match:
                        last_solverstate = snapshot_match.group(1)
                if last_solverstate:
                    return last_solverstate

    def _getLastSnapshotFromSnapshotDirectory(self, basename=False):
        """ Try to find the last snapshot in the snapshot directory.

        Return the name of the solverstate file if it was found.
        """
        solver_state = None
        max_iter = -1
        regex_iter = re.compile('iter_([\d]+)\.solverstate[\.\w-]*$')
        for entry in os.listdir(self.getSnapshotDirectory()):
            iter_match = regex_iter.search(entry)
            if iter_match:
                try:
                    iter_id = int(iter_match.group(1))
                    if iter_id > max_iter:
                        max_iter = iter_id
                        solver_state = entry
                except:
                    pass
        if solver_state:
            if basename:
                return solver_state
            return os.path.join(self.getSnapshotDirectory(), solver_state)
