from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QDialog, QPushButton, QMessageBox, QAction, QGridLayout

from gui.prototxt_editor import text_edit

class EditorWidget(QDialog):
    '''This Editor enables text-based changes of Prototxt files. Connect to the sinal sgSave to get the savedata'''

    def __init__(self, syntax = True, parent=None):
        # main_window settings
        QDialog.__init__(self, parent)
        self.setModal(True)
        self.resize(600, 600)
        self.setMinimumWidth(500)
        self.layout = QGridLayout(self)
        # buttons
        self.pbSave = QPushButton("Save")
        self.layout.addWidget(self.pbSave, 0, 0)
        self.pbSaveClose = QPushButton("Save && Close")
        self.layout.addWidget(self.pbSaveClose, 0, 1)
        self.pbClose = QPushButton("Close")
        self.layout.addWidget(self.pbClose, 0, 2)
        # the prototxt_editor itself
        if syntax:
            self.textwidget = text_edit.EditorSyntax()
        else:
            self.textwidget = text_edit.Editor()

        self.layout.addWidget(self.textwidget, 1, 0, 1, 3)
        self.containsChanges = False
        # connections
        self.pbSave.clicked.connect(self._onSave)
        self.pbSaveClose.clicked.connect(self._onSaveClose)
        self.pbClose.clicked.connect(self._onClose)
        self.textwidget.textChanged.connect(self._onChange)

        # actions
        self.saveaction = QAction(self)
        self.saveaction.setShortcut('Ctrl+S')
        self.addAction(self.saveaction)
        self.saveaction.triggered.connect(self._onSave)

        self.quitaction = QAction(self)
        self.quitaction.setShortcut('Ctrl+Q')
        self.addAction(self.quitaction)
        self.quitaction.triggered.connect(self._onClose)


    sgSave = pyqtSignal(['QString'])
    sgClose = pyqtSignal()

    def closeEvent(self, event):
        '''if closing with changes ask if changes should be discarded'''
        if self.containsChanges:
            if self._showWarning():
                self.sgClose.emit()
                event.accept()
            else:
                event.ignore()
        else:
            self.sgClose.emit()
            event.accept()

    def getText(self):
        '''convert prototxt_editor to text'''
        return self.textwidget.toPlainText()

    def setText(self, insertText):
        '''replace the current content of the prototxt_editor with the new one'''
        self.textwidget.setPlainText(insertText)
        self.containsChanges = False

    def clear(self):
        '''clear the prototxt_editor'''
        self.textwidget.clear()
        self.textwidget.setFocus()
        self.containsChanges = False

    def _onSave(self):
        '''emit save sinal'''
        self.sgSave.emit(self.getText())
        self.containsChanges = False

    def _onSaveClose(self):
        '''save and close'''
        self._onSave()
        self.close()

    def _onClose(self):
        self.close()

    def _onChange(self):
        '''set echange flag'''
        self.containsChanges = True

    def _showWarning(self):
        '''show message box if changes are discarded'''
        if QMessageBox.warning(
                self, "Warning", "Close without saving?",
                QMessageBox.Yes, QMessageBox.No) \
                == QMessageBox.Yes:
            return True
        else:
            return False

    # workaround
    # previously pressing the ESC key would close the main_window and always discard changes
    # therefor catch the key and close the main_window manualy
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super(EditorWidget, self).keyPressEvent(event)

    def disableEditing(self, disable):
        ''' Set textwidget in read-only mode '''
        self.textwidget.setReadOnly(disable)
