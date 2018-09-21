class HistoryManager():
    def __init__(self, maxSize=100):
        """ Initialize HistoryManager which saved maximal maxSize states.
            The maxSize+1 insertion removes the first
        """
        self.history = []
        # Position is a value contains the index of the state in a continues way.
        # That means even when the first entries get deleted because of maxSize
        # self.position do not get decreased by this.
        self.position = -1
        # the index of the current position in history list
        self.__idx = -1
        # self.listLen contains maxSize
        self.listLen = maxSize
        # If this gets true, no other entry can be make in history
        self.__lockHistory = False

    def canUndo(self):
        return self.__idx >0

    def canRedo(self):
        return self.__idx < len(self.history)-1

    def undo(self):
        if self.canUndo():
            self.__idx -=1
            self.position -= 1

    def redo(self):
        if self.canRedo():
            self.__idx +=1
            self.position += 1

    def currentState(self):
        """ Get latest state saved in history"""
        if len(self.history) > 0:
            return self.history[self.__idx]
        else:
            return None

    def _insert(self,element):
        """ Insert element at the current position """
        # remove newer elements
        del self.history[self.__idx + 1:]
        # Remove the oldest element if there are too many elements
        if self.__idx == self.listLen:
            del self.history[0]
        else:
            self.__idx += 1
        self.history.append(element)
        self.position += 1

    def lockHistory(self, fun):
        """ Lock history for the whole method fun.
            As a result no history can be inserted whil
            fun is executed.
         """
        if self.__lockHistory:
            return
        self.__lockHistory = True
        fun()
        self.__lockHistory = False

    def insertFunc(self, fun):
        """ Insert an element in history using the function fun.
            While fun is working insertFunc is locked, so no other
            element can be added in history.
            As a result recursivly insertion of history is stopped.
            The function fun will be called with in insertion function
            which can be called to insert an element in history.
            E.g.:
               def createNewElement(text):
                  # Nothing happend, because insertFunc is locked
                  historymanager.insertFunc(lambda insertF: insertF(text))
                  return text
               historymananger.insertFunc(lambda insertF: insertF(createNewElement("bla"))
               # Only one string will be insert
           When inserting a new state old state gets removed if the limit of
           entries is reached. 
           Also states newer than the current one (e.g. by using undo()) 
           get removed (so you can't do a redo() anymore)
        """
        if self.__lockHistory:
            return
        self.__lockHistory = True
        fun(self._insert)
        self.__lockHistory = False

    def clear(self):
        self.position = -1
        self.__idx = -1
        self.history = []





