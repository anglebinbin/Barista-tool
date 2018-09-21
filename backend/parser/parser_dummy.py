from backend.parser.parser_common import ParserCommon

class ParserDummy(ParserCommon):
    def __init__(self):
        super(ParserDummy, self).__init__()

    def sendParserFinished(self):
        for lis in self.listener:
            lis.parsingFinished()

    def sendParserUpdate(self, phase, row):
        for lis in self.listener:
            lis.update(phase, row)

    def sendParserHandle(self, event, line, groups):
        for lis in self.listener:
            lis.handle(event, line, groups)

    def sendParserRegisterKeys(self, phase, key):
        keyRegistry = self.getKeys(phase)
        if key not in keyRegistry:
            keyRegistry.append(key)
        for lis in self.listener:
            lis.registerKey(phase, key)
