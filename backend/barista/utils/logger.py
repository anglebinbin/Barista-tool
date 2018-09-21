from PyQt5.QtCore import Qt
from PyQt5.Qt import QObject

import PyQt5.QtCore as QtCore
import inspect

import datetime
import time as tim

'''
Model/Helper-Classes
'''


class MessageType:

    def __init__(self, id, description):
        self.typeId = id
        if(id == -1):   # DockElementConsole.ALL
            self.color = Logger.COLORS[Logger.TEXT.typeId]  # not existiing now
        else:
            self.color = Logger.COLORS[id]
        self.description = description


class LogLine:

    def __init__(self, line, caller, msgType, time):
        self.line = line
        self.caller = caller
        self.msgType = msgType
        self.time = time


class Caller:

    def __init__(self, id, description, customColor):
        # if no id is given, default to 0
        if not id:
            id = 0

        self.callerId = id

        id += 2  # color offset for reserved colors black and red

        if id >= len(Logger.COLORS) or not customColor:
            self.color = Logger.COLORS[
                Logger.TEXT.typeId]
        else:
            self.color = Logger.COLORS[id]
        self.description = description
        self.used = False
        
    def setUsed(self):
        self.used = True


class LogCaller:
    """ A interface for users of the Logger class.

    If a class implements this interface, it can use the Logger methods log and
    error without delivering the callerId
    """

    def getCallerId(self):
        pass


class Logger(QObject):
    """
    TODO: Selection is removed on insertion, fix needed?
    TODO: Logfile schreiben
    """

    newLine = QtCore.pyqtSignal(object)
    sigRefreshGui = QtCore.pyqtSignal(object)
    sigRefreshCallers = QtCore.pyqtSignal(object)

    # Color Constants
    COLORS = [Qt.red, Qt.black, Qt.blue, Qt.green, Qt.yellow]

    # Type Constants, used for color and combobox index
    # initalized at the bottom of this module
    ERROR = None
    TEXT = None
    ALL = None

    def __init__(self):
        super(Logger, self).__init__()
        self.__loglines = []
        self.__callerIdCount = 0
        self.__removedCallers = []
        self.__callers = {}
        self.__guiConsole = None
        self.__filePath = None
        self.__defaultCaller = Caller(-1, "Caller could not be identified", False)

    def getCallerFromIdWithFallback(self, callerId):
        if callerId is None or callerId not in self.__callers:
            return self.__defaultCaller
        else:
            return self.__callers[callerId]

    def log(self, line, callerId=None):
        '''
        use to log simple text
        '''
        # inspired by http://stackoverflow.com/a/7272464/2129327
        if callerId is None:
            try:
                caller = inspect.currentframe().f_back.f_locals['self']
                if caller:
                    log_id = getattr(caller, "getCallerId()", None)
                    if callable(log_id):
                        callerId = caller.getCallerId()()
            except Exception:
                # TODO: Warn properly that something went wrong
                print('From unknown callerID: ' + line)
                pass

        self.appendLine(line, callerId)

    def error(self, line, callerId=None):
        '''
        use to log errors
        '''
        # inspired by http://stackoverflow.com/a/7272464/2129327
        if callerId is None:
            try:
                caller = inspect.currentframe().f_back.f_locals['self']
                if caller:
                    log_id = getattr(caller, "getCallerId()", None)
                    if callable(log_id):
                        callerId = caller.getCallerId()()
            except Exception:
                pass
        self.appendLine(line, callerId, Logger.ERROR)

    def appendLine(self, line, callerId, msgType=None):
        '''
        appends a sing line to the logger and if existing to console
        and file
        line: String , the string to append
        callerId: Int, the id created by getCallerId
        msgType: MessageType, An Object indicating which Type this logline is
        '''
        if(msgType is None):
            msgType = Logger.TEXT

        ts = tim.time()
        st = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")
        caller = self.getCallerFromIdWithFallback(callerId)
        caller.setUsed()
        logline = LogLine(line, caller, msgType, st)
        self.__loglines.append(logline)

        # notify all consoles etc about new line
        self.newLine.emit(logline)

        if self.__filePath is not None:
            self.__guiConsole.appendLineToConsole(logline)

    def appendLines(self, lines, callerId):
        '''
        TODO: Possible optimization for big amount of data, like logfiles
        '''
        for line in lines:
            self.appendLine(line, callerId)

    def getCallerId(self, description, customColor=False):
        '''
        creates a new Caller id which identifies the
        using object to group their log messages
        '''
        if(self.__removedCallers): # list not empty
            callerId = self.__removedCallers.pop()
        else:
            callerId = self.__callerIdCount
            self.__callerIdCount += 1
        caller = Caller(callerId, description, customColor)
        self.__callers[callerId] = caller
        self.refreshCallers()
        return callerId

    def removeCallerId(self, callerId, keepLines=True):
        if(callerId in self.__removedCallers):
            return
        self.__removedCallers.append(callerId)

        self.__callers.pop(callerId, None)
        if(keepLines == False):
            filterLines = lambda logline: logline.caller.callerId != callerId
            self.__loglines = list(filter(filterLines, self.__loglines))
            self.refreshGui()
        else:
            self.refreshCallers()

    def setFile(self, filePath):
        self.__filePath = filePath

    def refreshGui(self):
        '''
        refreshs/validates the whole console and filter values
        '''
        self.refreshConsole()
        self.refreshCallers()

    def refreshConsole(self):
        '''
        refreshs/validates the whole console
        '''
        self.sigRefreshGui.emit(self.__loglines)

    def refreshCallers(self):
        '''
        refreshs/validates the filter values/callers
        '''
        self.sigRefreshCallers.emit(self.__callers)

    def __getPrefix(self, caller, time):
        '''
        the prefix that have to be added
        '''
        prefix = ""
        prefix = "[" + time + ", " + caller.description + "]"
        return prefix



# Add Constant Values to Logger
Logger.ERROR = MessageType(0, "ERROR")
Logger.TEXT = MessageType(1, "TEXT")
Logger.ALL = MessageType(-1, "ALL")

# "Singelton" instance
Log = Logger()
