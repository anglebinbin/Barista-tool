import multiprocessing
import sys
if sys.version_info[0] == 2:
    from Queue import PriorityQueue, Empty
else:
    from queue import PriorityQueue, Empty
from threading import Thread


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


class SessionPool:
    """ A simple thread pool implementation for parsing log files of sessions.

    A job is added by adding a session.
    Jobs are ordered by the session_id(priority), so new sessions have a higher
    priority.
    The pool allocates and starts threads on demand. It allocates no more then
    CPU_COUNT - 2 threads, but at least 1.
    """

    __metaclass__ = Singleton

    def __init__(self):
        self.sessions = PriorityQueue()
        self.pool = []
        self.__start_jobs = False
        self.MAX_THREADS = multiprocessing.cpu_count() - 2
        if self.MAX_THREADS <= 0:
            self.MAX_THREADS = 1

    def addSession(self, session):
        """ Add a session to to queue and start a thread.
        """
        self.sessions.put(session)
        if self.__start_jobs:
            self.__startJob()

    def activate(self, emptyJob):
        """ Activates this pool by starting threads.
        """
        self.__start_jobs = True
        self.emptyJob = emptyJob
        qs = self.sessions.qsize()
        starts = min(qs, self.MAX_THREADS)
        for i in range(0, starts):
            self.__startJob()

    # private methods

    def __startJob(self):
        """ Remove inactive threads from the pool and create a new for the new
        job.
        """
        if self.__start_jobs is False:
            return
        # clean thread pool
        jc = len(self.pool)
        for ri in range(jc, 0, -1):
            i = ri - 1
            thread = self.pool[i]
            if thread is not None:
                if thread.is_alive() is False:
                    self.pool.pop(i)
        # create a new thread
        jc = len(self.pool)
        if jc < self.MAX_THREADS:
            t = Thread(target=self.__executeJob)
            t.start()
            self.pool.append(t)

    def __executeJob(self):
        """ The target method of a thread.

        Poll for sessions and execute their parser.
        """
        try:
            while True:
                session = self.sessions.get(True, 1)
                if session:
                    session.parseOldLogs()
                    parser = session.getParser()
                    parser.parseLog()
                    self.sessions.task_done()
                else:
                    break
        except Empty:
            if self.emptyJob:
                self.emptyJob()
            return
        except Exception as e:
            print(str(e))
