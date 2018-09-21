import os

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtGui import QPixmap, QIcon, QCursor
from PyQt5.QtWidgets import (
    QWidget,
    QPushButton,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QHBoxLayout,
    QProgressBar,
    QMenu,
    QAction)

from backend.barista.session.session_utils import State
from backend.barista.session.client_session import ClientSession
from backend.barista import caffe_versions
from backend.caffe import loader


class SessionWidget(QWidget):
    """ A instance of this widget represents an entry for a session in the list
    of session within the running jobs dock element.
    """

    #TODO: add an item to select a session as visible/editable i.e. 'active'?
    def __init__(self, session, controller, parent=None):
        super(SessionWidget, self).__init__(parent)
        self.session = session
        self.controller = controller
        mainLayout = QVBoxLayout(self)
        buttonLayout = QHBoxLayout()
        progressLayout = QHBoxLayout()
        remoteLayout = QHBoxLayout()

        # Add a network label if this is a remote session.
        if isinstance(self.session, ClientSession):

            self.buttonClose = QPushButton()
            self.buttonClose.setObjectName("sessionBtn")
            self.buttonClose.setToolTip("Close this session. (Does not remove the session from the server)")
            closeIcon = QPixmap('resources/unlink.png')
            self.buttonClose.setIcon(QIcon(closeIcon))
            self.buttonClose.setFixedSize(30, 20)
            self.buttonClose.clicked.connect(self.onClose)
            remoteLayout.addWidget(self.buttonClose)

            self.networkLabel = QLabel()
            remote = self.session.remote
            if len(remote) > 2:  # if remote host has a name, display this name
                self.networkLabel.setText(remote[2] + ":" + str(remote[1]))
            else:
                self.networkLabel.setText(remote[0] + ":" + str(remote[1]))
            self.networkLabel.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            remoteLayout.addWidget(self.networkLabel)

            mainLayout.addLayout(remoteLayout)


        # Create a label for the session id.
        sessionIdLabel = QLabel(str(session.getSessionId()))
        sessionIdLabel.setObjectName("sessionId")
        sessionIdLabel.setFixedSize(30, 30)
        sessionIdLabel.setAlignment(Qt.AlignCenter)
        buttonLayout.addWidget(sessionIdLabel)

        # Create session status label.
        self.statusLabel = QLabel()
        self.statusLabel.setObjectName("sessionStatus")
        self.statusLabel.setFixedHeight(30)
        self.statusLabel.setMinimumWidth(100)
        self.statusLabel.setAlignment(Qt.AlignCenter)
        buttonLayout.addWidget(self.statusLabel)

        # Create snapshot button.
        self.snapshotBtn = QPushButton()
        self.snapshotBtn.setObjectName("sessionBtn")
        snapshotIcon = QPixmap('resources/snap.png')
        self.snapshotBtn.setIcon(QIcon(snapshotIcon))
        self.snapshotBtn.setToolTip("Take a snapshot")
        self.snapshotBtn.setFixedSize(30, 30)
        self.snapshotBtn.clicked.connect(self.onSnapshot)
        buttonLayout.addWidget(self.snapshotBtn)

        # Create delete button.
        self.deleteBtn = QPushButton()
        self.deleteBtn.setObjectName("sessionBtn")
        deleteIcon = QPixmap('resources/trash.png')
        self.deleteBtn.setIcon(QIcon(deleteIcon))
        self.deleteBtn.setToolTip("Delete Session")
        self.deleteBtn.setFixedSize(30, 30)
        self.deleteBtn.clicked.connect(self.onDelete)
        buttonLayout.addWidget(self.deleteBtn)

        # Create more button.
        self.moreBtn = QPushButton()
        self.moreBtn.setObjectName("sessionBtn")
        moreIcon = QPixmap('resources/more.png')
        self.moreBtn.setIcon(QIcon(moreIcon))
        self.moreBtn.setToolTip("Show more actions")
        self.moreBtn.setFixedSize(30, 30)

        # Add actions to the more button menu.
        moreBtnMenu = QMenu(self.moreBtn)
        self.cloneSessionMenu = moreBtnMenu.addMenu("Clone Session")
        self.moreBtn.setMenu(moreBtnMenu)
        resetAct = QAction("Reset", moreBtnMenu)
        resetAct.triggered.connect(self.onReset)
        moreBtnMenu.addAction(resetAct)
        self.addAllSnapshots()
        buttonLayout.addWidget(self.moreBtn)

        # Add a stretch, so that the horizontal items are left aligned.
        mainLayout.addLayout(buttonLayout)

        # Create start button.
        self.startBtn = QPushButton()
        self.startBtn.setObjectName("sessionBtn")
        startIcon = QPixmap('resources/start.png')
        self.startBtn.setIcon(QIcon(startIcon))
        self.startBtn.setToolTip("Start Training")
        self.startBtn.setFixedSize(30, 30)
        self.startBtn.clicked.connect(self.onStart)
        self.startBtn.setEnabled(False)
        progressLayout.addWidget(self.startBtn)

        # Create pause button.
        self.pauseBtn = QPushButton()
        self.pauseBtn.setObjectName("sessionBtn")
        pauseIcon = QPixmap('resources/pause.png')
        self.pauseBtn.setIcon(QIcon(pauseIcon))
        self.pauseBtn.setToolTip("Pause Training")
        self.pauseBtn.setFixedSize(30, 30)
        self.pauseBtn.clicked.connect(self.onPause)
        self.pauseBtn.setEnabled(False)
        progressLayout.addWidget(self.pauseBtn)

        # Add a progress bar.
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.sessionIterationChanged()
        progressLayout.addWidget(self.progress)

        mainLayout.addLayout(progressLayout)

        #Add text label for invalid sessions
        self.invalidLabel = QLabel()
        self.invalidLabel.setObjectName("invalidMsg")
        self.invalidLabel.setFixedHeight(30)
        self.invalidLabel.setMinimumWidth(80)
        self.invalidLabel.setAlignment(Qt.AlignCenter)
        self.invalidLabel.setEnabled(False)
        progressLayout.addWidget(self.invalidLabel)

        # Update the current session state.
        self.sessionStateChanged(self.session.getState())

    def getSession(self):
        """ Return the session of this widget.
        """
        return self.session

    def getSID(self):
        """ Returns the session ID related to this session item.
        """
        return self.session.getSessionId()

    def showDialog(self, text, info, title, location=None, buttons=None):
        """ Show a message box to the user.

        Return the user decision.
        """
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)

        msg.setText(text)
        msg.setInformativeText(info)
        msg.setWindowTitle(title)
        if buttons is not None:
            try:
                msg.setStandardButtons(buttons)
            except TypeError:
                # if something wrong is passed to the buttons Parameter, show the standard message.
                msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        else:
            msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        if location is None:
            location = QCursor.pos()
        msg.move(location - QPoint(msg.sizeHint().width() / 2,
                                   msg.sizeHint().height() / 2))

        return msg.exec_()

    def sessionIterationChanged(self):
        """ The sessions iteration changed.
        """
        iteration = self.session.getIteration()
        maxIteration = self.session.getMaxIteration()
        try:
            i = float(iteration) * 100.0
            m = float(maxIteration)
            self.progress.setValue(i/m)
        except Exception:
            pass
        text = str(int(iteration))+' / '+str(maxIteration)
        self.progress.setFormat(text)

    def addAllSnapshots(self):
        """ Add all snapshots to the clone session submenu.
        """
        snapshots = self.session.getSnapshots()
        self.cloneSessionMenu.clear()
        for iter_num in sorted(snapshots.keys()):
            self.addSnapshot(snapshots[iter_num])
        snapshots = self.session.getSnapshots()
        snapshotCount = len(snapshots)
        if snapshotCount == 0:
            self.cloneSessionMenu.setEnabled(False)
        else:
            self.cloneSessionMenu.setEnabled(True)

    def addSnapshot(self, snapshot):
        """ Add a snapshot to the snapshot menu.
        """
        snapAct = QAction(os.path.basename(snapshot), self.cloneSessionMenu)
        snapAct.triggered.connect(lambda: self.createFromSnapshot(snapshot))
        self.cloneSessionMenu.addAction(snapAct)

    def createFromSnapshot(self, snapshot=None):
        """ Called when the snapshot tool button was clicked or when a snapshot
        was selected in the snapshot dropdown.
        """
        info = "A new session will be created from the snapshot " + snapshot
        if self.showDialog("Do you want to continue from this snapshot?",
                           info, "") == QMessageBox.Ok:
            self.controller.createNewSessionFromSnapshot(snapshot, self.session)

    def sessionStateChanged(self, state=None):
        """ Called when the session state changed.
        """
        if state is None:
            state = self.session.getState()
        if state is State.WAITING:
            self.__buttons_wait()
            self.__progress_show()
            if self.session.getPretrainedWeights():
                self.setStatus('Pre-trained', '#8000ff')
                self.statusLabel.setToolTip('Ready to start with pre-trained weights!')
            else:
                self.setStatus('Ready', 'blue')
                self.statusLabel.setToolTip('Ready to train!')
        elif state is State.RUNNING:
            self.__buttons_run()
            self.__progress_show()
            self.setStatus('Running', 'green')
            self.statusLabel.setToolTip('Currently training..')
        elif state is State.PAUSED:
            self.__buttons_wait()
            self.__progress_show()
            self.setStatus('Paused', 'orange')
            self.statusLabel.setToolTip('Training paused.')
        elif state is State.FINISHED:
            self.__buttons_disable()
            self.__progress_show()
            self.setStatus('Finished', 'gray')
            self.statusLabel.setToolTip('Finished, training completed.')
        elif state is State.FAILED:
            self.__buttons_disable()
            self.__progress_show()
            self.setStatus('Failed', 'red')
            self.statusLabel.setToolTip('Something went wrong.')
        elif state is State.UNDEFINED:
            self.__buttons_disable()
            self.__progress_show()
            self.setStatus('Undefined', 'gray')
            self.statusLabel.setToolTip('')
        elif state is State.INVALID:
            self.__buttons_disable()
            self.setStatus('Invalid', 'gray')
            self.statusLabel.setToolTip('Session is not ready to train.')
            self.__progress_hide()
            errorList = self.session.getErrorList()
            '''
            ErrorList is a list of all constraints that are broken for this session. Each tuple contains
            a full error message displayed in the tooltip (index 0) and a key word to be shown in the status box.
            '''
            if errorList is not None and len(errorList) > 0:
                self.invalidLabel.setToolTip(errorList[0][0])
                self.setInvalidMsg((errorList[0])[1])

        elif state is State.NOTCONNECTED:
            self.__buttons_disable()
            self.__progress_hide()
            self.setStatus('Invalid', 'gray')
            self.setInvalidMsg('No connection to host found.')
            self.invalidLabel.setToolTip('')
        self.statusLabel.adjustSize()

    def setStatus(self, text, color='gray'):
        """ Set the style of the status label.
        """
        self.statusLabel.setText(text)
        # If we just want to overwrite single properties of the stylesheet, just
        # append them to the current stylesheet.
        self.statusLabel.setStyleSheet(self.statusLabel.styleSheet() + " QLabel { background-color: "+color+"; border-color: "+color+" }" )

    def setInvalidMsg(self, text, color='gray'):
        self.invalidLabel.setText(text)
        self.invalidLabel.setStyleSheet(
            self.invalidLabel.styleSheet() + " QLabel { background-color: " + color + "; border-color: " + color + " }")

    def __buttons_run(self):
        self.startBtn.setEnabled(False)
        self.startBtn.hide()
        self.pauseBtn.setEnabled(True)
        self.pauseBtn.show()
        self.snapshotBtn.setEnabled(True)

    def __buttons_wait(self):
        self.startBtn.setEnabled(True)
        self.startBtn.show()
        self.pauseBtn.setEnabled(False)
        self.pauseBtn.hide()
        self.snapshotBtn.setEnabled(False)

    def __buttons_disable(self):
        self.startBtn.setEnabled(False)
        self.startBtn.show()
        self.pauseBtn.setEnabled(False)
        self.pauseBtn.hide()
        self.snapshotBtn.setEnabled(False)

    def __progress_hide(self):
        self.startBtn.setEnabled(False)
        self.startBtn.show()
        self.progress.setEnabled(False)
        self.progress.hide()
        self.invalidLabel.setEnabled(True)
        self.invalidLabel.show()

    def __progress_show(self):
        self.progress.setEnabled(True)
        self.progress.show()
        self.invalidLabel.setEnabled(False)
        self.invalidLabel.hide()


    def onStart(self):
        """ Start button was clicked.
        """
        if self.session.getState() is State.WAITING:
            self.session.start(caffemodel=self.session.getPretrainedWeights())
        elif self.session.getState() is State.PAUSED:
            self.session.proceed()

    def onPause(self):
        self.session.pause()

    def onSnapshot(self):
        self.session.snapshot()

    def onDelete(self):
        """ Delete button was clicked.
        """
        sid = self.getSID()
        if self.session.getState() == State.RUNNING:
            confirm = self.showDialog("The selected session is still running.\nDo you want to stop it "
                                      "and delete Session {} anyway?".format(sid), "",
                                      "Delete Session") == QMessageBox.Ok
        else:
            confirm = self.showDialog("Do you want to delete Session {}?".format(sid), "",
                                      "Delete Session") == QMessageBox.Ok
        if confirm:
            self.controller.removeSessions((self.session,))

    def onClose(self):
        """ Close button was clicked.
        """
        sid = self.getSID()
        if self.session.getState() == State.RUNNING:
            confirm = self.showDialog("The selected session is still running.\nDo you want to stop it "
                                      "and close the connection anyway?".format(sid), "",
                                      "Close Session") == QMessageBox.Ok
        else:
            confirm = True
        if confirm:
            self.controller.closeSession(self.session)

    def onReset(self):
        """ Reset button was clicked.
        """
        sid = self.getSID()
        if self.session.getState() == State.RUNNING:
            confirm = self.showDialog(
                "The selected session is still running.\nDo you want to stop and reset Session {} anyway?\n"
                "All progress (including logs) will be lost!".format(sid), "", "Reset Session") == QMessageBox.Ok
        elif self.session.getState() == State.PAUSED:
            confirm = self.showDialog(
                "The selected session was trained before.\nDo you want to reset Session {} anyway?\n"
                "All progress (including logs) will be lost!".format(sid), "", "Reset Session") == QMessageBox.Ok
        else:
            confirm = self.showDialog("Do you want to reset Session {}?".format(sid), "",
                                      "Reset Session") == QMessageBox.Ok
        if confirm:
            # Remove all snapshots from the context menu
            for action in self.cloneSessionMenu.actions():
                self.cloneSessionMenu.removeAction(action)
            self.cloneSessionMenu.setDisabled(True)
            self.controller.resetSession(self.session)
