from PyQt5.QtWidgets import QWidget, QSlider, QHBoxLayout
from PyQt5.QtCore import QMargins
from PyQt5.QtCore import QObject, pyqtSignal


class EditorSlider(QWidget):
    # widget containig the slider
    # direct subclassing of QSlider leads to errors

    valueChanged = pyqtSignal(int)

    def __init__(self, vmin, vcur, vmax, parent):
        QWidget.__init__(self, parent)

        self.editor = parent
        self.setFocusPolicy(0)

        #layouts
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        #add the slider
        self.slider = QSlider()
        self.slider.setRange(vmin, vmax)
        self.slider.setValue(vcur)
        self.slider.setOrientation(1)
        self.slider.setFocusPolicy(0)
        self.layout.addWidget(self.slider)

        self.slider.valueChanged.connect(self._passThrough)

    def updatePosition(self):
        '''set the position of the slider'''
        rect = self.editor.rect()
        dy = 0
        dx = 0
        #check for scrollbars
        if self.editor.verticalScrollBar().isVisible():
            dx = self.editor.verticalScrollBar().width()
        if self.editor.horizontalScrollBar().isVisible():
            dy = self.editor.horizontalScrollBar().height()
        mx = rect.width() - self.width() - dx - 5
        my = rect.height() - self.height() - dy - 5
        self.move(mx, my)

    def paintEvent(self, event):
        self.updatePosition()
        super(EditorSlider, self).paintEvent(event)

    def _passThrough(self, value):
        '''pass through the valueChanged signal of the QSlider'''
        self.valueChanged.emit(value)
