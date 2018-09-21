from PyQt5.QtWidgets import QLineEdit, QPlainTextEdit
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QTextDocument, QTextCursor, QColor, QFontMetrics


class SearchBar(QLineEdit):
    def __init__(self, editor, parent=None):
        QLineEdit.__init__(self, parent)

        self.editor = editor

        self.setAttribute(Qt.WA_TintedBackground)
        self.setHidden(True)
        self.defaultstyle = self.styleSheet()

        self.textChanged.connect(self.onTextChange)

    def disp(self):
        '''display the searchbar'''
        self.setHidden(False)
        self.setFocus()

    def hide(self):
        '''hide the searchbar'''
        self.setHidden(True)

    def onF3(self):
        '''open or jump to next'''
        if self.isHidden():
            self.disp()
        else:
            self.findText()

    def getText(self):
        return self.text().lower()

    def keyPressEvent(self, event):
        # find the text on enter
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.first = True
            self.findText()
            return
        # clear or hide the searchbar
        if event.key() == Qt.Key_Escape:
            if self.text() == "":
                self.hide()
                self.editor.setFocus()
            else:
                self.clear()
            return
        # jump to next
        if event.key() == Qt.Key_F3:
            self.onF3()
            self.editor.setFocus()
            return
        super(SearchBar, self).keyPressEvent(event)

    def findText(self):
        '''search the prototxt_editor for text'''
        text = self.getText()

        if text != "":
            self.onTextChange()
            doc = self.editor.document()

            # first search from cursor position
            hig = doc.find(text, self.editor.textCursor())
            if not hig.isNull():
                self.editor.setTextCursor(hig)
                return
            # if not found: search from start
            hig = doc.find(text, QTextCursor(doc))
            if not hig.isNull():
                self.editor.setTextCursor(hig)
                return
            # not found, make red
            self.setStyleSheet("background:#FFaaaa;")

    def updatePosition(self):
        '''set position of searchbar'''
        rect = self.editor.rect()
        dx = 0
        if self.editor.verticalScrollBar().isVisible():
            dx = self.editor.verticalScrollBar().width()
        mx = rect.width() - self.width() - dx - 1
        self.move(mx, 2)

    def resizeToFont(self):
        '''set font of searchbar'''
        font = self.font()
        fm = QFontMetrics(font)
        # adjust height to fontsize
        self.setFixedSize(300, fm.height() * 1.2)

    def paintEvent(self, event):
        self.updatePosition()
        super(SearchBar, self).paintEvent(event)

    def onTextChange(self):
        # reset the style back to default
        self.setStyleSheet(self.defaultstyle)
