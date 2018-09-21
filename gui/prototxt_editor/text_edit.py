from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import QFont, QFontMetrics, QColor, QPainter, QFontDatabase
from PyQt5.QtWidgets import QPlainTextEdit
from gui.prototxt_editor import editor_side_bar, editor_search_bar, editor_syntax_highlight

from gui.prototxt_editor import editor_slider


class Editor(QPlainTextEdit):
    '''based on http://doc.qt.io/qt-5/qtwidgets-widgets-codeeditor-example.html'''

    def __init__(self, parent=None):
        QPlainTextEdit.__init__(self, parent)
        # default settings
        self._fontsize = 12
        self._fmin = 8
        self._fmax = 30

        # setup of prototxt_editor
        self.setLineWrapMode(0)

        # loading of subwidgets
        self.sidebar = editor_side_bar.Sidebar(self)  # line numbers
        self.searchbar = editor_search_bar.SearchBar(self, self)  # search
        self.slider = editor_slider.EditorSlider(self._fmin, self._fontsize, self._fmax, self)  # fontsize slider
        # conntions
        self.slider.valueChanged.connect(self.setFontsize)
        self.blockCountChanged.connect(self._updateSidebarWidth)
        self.updateRequest.connect(self._updateSidebar)
        # show
        self._updateFont()
        self._updateSidebarWidth()
        self.sidebar.show()

    def setFontsize(self, value):
        '''set the fontsize'''
        if self._fmin <= value <= self._fmax:
            self._fontsize = value
            self._updateFont()

    def sidebarWidth(self):
        '''calculate the width of the sidebar'''

        # get the number of digits displayed
        digits = 1
        maxd = max(1, self.blockCount())
        while maxd >= 10:
            maxd /= 10
            digits += 1

        # calc the width
        space = 3 + QFontMetrics(self._font).width(*'9') * digits

        return space

    def _updateSidebarWidth(self, arg=0):
        '''refresh the width of the sidebar'''
        self.setViewportMargins(self.sidebarWidth(), 0, 0, 0)

    def _updateSidebar(self, rect, dy):
        '''realign the sidebar'''
        if dy is not 0:
            self.sidebar.scroll(0, dy)
        else:
            self.sidebar.update(0, rect.y(), self.sidebarWidth(), rect.height())

        if rect.contains(self.viewport().rect()):
            self._updateSidebarWidth()

    def sidebarPaintEvent(self, event):
        '''draw the sidebar'''

        # define the colors
        _c1 = QColor()
        _c1.setNamedColor("lightgrey")
        _c2 = QColor()
        _c2.setNamedColor("darkgrey")
        _c3 = QColor()
        _c3.setNamedColor("black")

        # setup the painter
        painter = QPainter(self.sidebar)
        painter.fillRect(event.rect(), _c1)
        painter.setFont(self._font)

        # calculate the lines
        block = self.firstVisibleBlock()
        blocknumber = block.blockNumber()
        btop = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bbottom = btop + self.blockBoundingRect(block).height()

        # write the line numbers
        while block.isValid() and btop <= event.rect().bottom():
            if block.isVisible() and bbottom >= event.rect().top():
                number = str(blocknumber + 1)

                # change color for "current" line
                if self.textCursor().block().blockNumber() != blocknumber:
                    painter.setPen(_c2)
                else:
                    painter.setPen(_c3)

                painter.drawText(0, btop, self.sidebar.width(), QFontMetrics(self._font).height(), 2, number)

            block = block.next()
            btop = bbottom
            bbottom = btop + self.blockBoundingRect(block).height()
            blocknumber += 1

    def resizeEvent(self, event):
        '''update all subwidgets on resize of the main_window'''
        super(Editor, self).resizeEvent(event)

        self.slider.updatePosition()
        self.searchbar.updatePosition()

        c = self.contentsRect()
        self.sidebar.setGeometry(QRect(c.left(), c.top(), self.sidebarWidth(), c.height()))

    def _updateFont(self):
        '''set the font and fontsize across all widgets'''
        self._font = QFontDatabase.systemFont(QFontDatabase.FixedFont)  # QFont("DejaVu Sans Mono", self._fontsize)
        self._font.setPointSize(self._fontsize) # Change Fontsize if using QFontDatabase
        self.setFont(self._font)
        self.searchbar.setFont(self._font)
        self.searchbar.resizeToFont()
        self.update()

    def keyPressEvent(self, event):
        # search
        if event.key() == Qt.Key_F:
            if event.modifiers() & Qt.ControlModifier:
                self.searchbar.disp()
                return
        if event.key() == Qt.Key_F3:
            self.searchbar.onF3()
            return
        # close
        if event.key() == Qt.Key_Escape:
            if not self.searchbar.isHidden():
                self.searchbar.hide()
                return
        super(Editor, self).keyPressEvent(event)


class EditorSyntax(Editor):
    def __init__(self, parent = None):
        Editor.__init__(self, parent)

        self.highlight = editor_syntax_highlight.EditorSyntaxHighlighter(self.document())  # syntax highlighting
        self.highlight._extractParams()
