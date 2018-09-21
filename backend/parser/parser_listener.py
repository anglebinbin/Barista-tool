

class ParserListener:

    def update(self, phase, row):
        """ Called when the parser has parsed a new record.
        """
        pass

    def handle(self, event, message, groups):
        """ Called when the parser has parsed a registered event.
        """
        pass

    def registerKey(self, phase, key):
        """ Called when a new key was found in the log data.
        """
        pass

    def parsingFinished(self):
        """ Called when the parser has processed all available streams.
        """
        pass
