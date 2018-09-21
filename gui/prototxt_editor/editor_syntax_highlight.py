from PyQt5.QtGui import QSyntaxHighlighter, QColor, QTextCharFormat, QFont
from PyQt5.QtCore import QRegExp
import backend.caffe.proto_info as info


class EditorSyntaxHighlighter(QSyntaxHighlighter):
    '''
    Based on
    http://doc.qt.io/qt-5/qtwidgets-richtext-syntaxhighlighter-example.html
    https://wiki.python.org/moin/PyQt/Python%20syntax%20highlighting
    '''

    def __init__(self, document):
        QSyntaxHighlighter.__init__(self, document)
        self.rules = []
        self.enums = []
        self.params = []
        self.paramgroups = []
        self._setupRules()

    def _setupRules(self):
        # strings
        self.tri_single = self._createRule('"', "darkorange", "", 1)
        self.tri_double = self._createRule("'", "darkorange", "", 2)

        # numbers
        self.rules.append(self._createRule('\\b\\d+(\\.\\d+)?(e(\\-|\\+?)\\d+)?\\b', "darkmagenta"))

        # get the parameters from caffe
        self._extractParams()

        # enums
        for e in self.enums:
            self.rules.append(self._createRule("\\b" + e + "\\b", "cornflowerblue", "bold"))

        # parameter
        for p in self.params:
            self.rules.append(self._createRule("\\b" + p + "\\b", "darkcyan", ""))

        # parameter groups
        for g in self.paramgroups:
            self.rules.append(self._createRule("\\b" + g + "\\b", "indigo", "italic"))

    def highlightBlock(self, p_str):
        '''apply rules to block'''

        # for each rule
        for exp, n, form in self.rules:
            # find in text
            index = exp.indexIn(p_str, 0)
            while index >= 0:
                index = exp.pos(n)
                l = len(exp.cap(n))
                # change format till end of string
                self.setFormat(index, l, form)
                # search for next
                index = exp.indexIn(p_str, index + l)
        self.setCurrentBlockState(0)

        # multiline handling for strings
        multiline = self.match_multiline(p_str, *self.tri_single)
        if not multiline:
            self.match_multiline(p_str, *self.tri_double)

    def match_multiline(self, text, exp, n, style):
        '''handling of multiline matches'''
        # start from beginning
        start = 0
        add = 0
        # if not previously found search anew
        if self.previousBlockState() != n:
            start = exp.indexIn(text)
            add = exp.matchedLength()

        while start >= 0:
            # find the end
            end = exp.indexIn(text, start + add)

            if end >= add:
                length = end - start + add + exp.matchedLength()
                self.setCurrentBlockState(0)
            else:
                self.setCurrentBlockState(n)
                length = len(text) - start + add
            # set style
            self.setFormat(start, length, style)
            # find next
            start = exp.indexIn(text, start + length)

        if self.currentBlockState() == n:
            return True
        else:
            return False

    def _createRule(self, regex, color="black", style="", index=0):
        return QRegExp(regex), index, self._format(color, style)

    def _format(self, color, style):
        # refer to https://www.w3.org/TR/SVG/types.html#ColorKeywords for colors

        # create color
        _c = QColor()
        _c.setNamedColor(color)

        # create font
        _f = QTextCharFormat()
        _f.setForeground(_c)

        # set font style
        if 'bold' in style:
            _f.setFontWeight(QFont.Bold)
        if 'italic' in style:
            _f.setFontItalic(True)

        return _f

    def _extractParams(self):
        '''open caffe meta information'''
        info.resetCaffeProtoModulesvar()
        info.CaffeMetaInformation().updateCaffeMetaInformation()
        allSolver = info.CaffeMetaInformation().availableSolverTypes()
        for solver in allSolver:
            self._iterParams(allSolver[solver].parameters())
        allLayer = info.CaffeMetaInformation().availableLayerTypes()
        for layer in allLayer:
            self._iterParams(allLayer[layer].parameters())

    def _iterParams(self, dict):
        '''recursive param search'''
        for param in dict:
            obj = dict[param]
            # sort
            if obj.isParameterGroup():
                if param not in self.paramgroups:
                    self.paramgroups.append(param)
                self._iterParams(obj.parameter())
            elif obj.isEnum():
                if param not in self.params:
                    self.params.append(param)
                values = obj.availableValues()
                for v in values:
                    if v not in self.enums:
                        self.enums.append(v)
            else:
                if param not in self.params:
                    self.params.append(param)
