

class ParserCommon(object):

    # keys for train/test phase
    TRAIN = 'TRAIN'
    TEST = 'TEST'

    def __init__(self):
        super(ParserCommon, self).__init__()
        self.listener = []
        self.train_keys = []
        self.test_keys = []


    def addListener(self, listener):
        """Add the listener to the list of listener.

        Every listener is notified about every parsing event.
        """
        if listener not in self.listener:
            self.listener.append(listener)

    def removeListener(self, listener):
        """ Remove the listener from the list of listener.
        """
        self.listener.remove(listener)

    def getKeys(self, phase):
        """ Return all registered keys for the given phase.
        """
        if phase == ParserCommon.TEST:
            return self.test_keys
        elif phase == ParserCommon.TRAIN:
            return self.train_keys
