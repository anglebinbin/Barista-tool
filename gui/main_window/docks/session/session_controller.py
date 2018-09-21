from collections import OrderedDict

from PyQt5.Qt import QObject
from PyQt5.QtCore import pyqtSignal, Qt
from backend.barista.constraints.session_run.training import checkMinimumTrainingRequirements
from backend.barista.session.client_session import ClientSession
from backend.barista.session.session import State

from backend.barista.session.session_pool import SessionPool
from backend.barista.utils.logger import Log
from backend.barista.utils.logger import LogCaller


class SessionController(QObject, LogCaller):
    """ View Controller for DockElementSessions.

    This controller handles events from the sessions widget and dispatches
    sessions when a user requests to train his configured net.
    """

    poolSignal = pyqtSignal(object)
    sessionSelectionChanged = pyqtSignal(object)
    sessionStateRefreshed = pyqtSignal(object)

    def __init__(self):
        super(SessionController, self).__init__()
        self.project = None
        self.caller_id = None
        self.plotter = None
        self.sessionGui = None
        self.wPlotter = None
        # self.activeSession = None  # stores the session that is currently worked on

    def setProject(self, project):
        self.project = project
        if project:
            for sid, session in project.getSessions().iteritems():
                self.sessionConnects(session)
                session.snapshotAdded.connect(lambda: self.wPlotter.updatePlotter(self.project.getSessions()))
            self.filterState()
            pool = SessionPool()
            self.poolSignal.connect(lambda: self.wPlotter.updatePlotter(self.project.getSessions()))
            pool.activate(lambda: self.poolSignal.emit('hey'))
            self.updateWeightPlotter()
            project.activeSessionChanged.connect(self.refreshAccordingToActiveSession)

    def sessionConnects(self, session):
        """ Connects different signals to the given session. """
        # Without the QueuedConnection a running remote session can't communicate with the server
        session.stateChanged.connect(
            lambda state=None, session=session: self.sessionStateChanged(session, state), Qt.QueuedConnection)
        session.iterationChanged.connect(
            lambda session=session: self.sessionIterationChanged(session), Qt.QueuedConnection)
        session.snapshotAdded.connect(
            lambda _, session=session: self.sessionSnapshotAdded(session), Qt.QueuedConnection)

    def sessionStateChanged(self, session, state=None):
        """ Handle state-change of the given session. """
        if not session.isRemote():
            session.updateMaxIterFromStateDict()
        self.sessionIterationChanged(session)

        self.sessionGui.sessionStateChanged(session, state)
        self.refreshAccordingToActiveSession()
        if session.getState() == State.RUNNING:
            self.displaySession(session.getSessionId())

    def refreshAccordingToActiveSession(self):
        """ Refresh docks, text editor and node editor according to the active session. """
        session = self.project.getActiveSession()
        state = session.getState()
        # emit signal to handle state change in view_manager
        self.sessionStateRefreshed.emit(state)

    def sessionIterationChanged(self, session):
        """ Handle iteration-change of the given session. """
        self.sessionGui.sessionIterationChanged(session)

    def sessionSnapshotAdded(self, session):
        """ Handle new snapshot for a given session. """
        self.sessionGui.sessionSnapshotAdded(session)

    def setPlotterGui(self, plotter):
        self.plotter = plotter

    def setSessionGui(self, sessionGui):
        self.sessionGui = sessionGui

    def setActiveSID(self, sessionID):
        """Sets the active sessionID.

        If a valid sessionID is provided, this method sets the session active
        and updates all GUI elements accordingly. A sessionID is valid if a
        session item does exist. Session states and connectivity are not
        checked."""
        if sessionID in self.project.getValidSIDs():
            self.filterState()
            self.sessionSelectionChanged.emit(sessionID)
            self.sessionGui.setSelectedSID(sessionID)  # update session list
            self.updateWeightPlotter()


    def setWeightPlotter(self, wPlotter):
        self.wPlotter = wPlotter

    def justCreateNewSession(self, remote=None):
        """ Creates a new session and returns its session id.
        """
        if remote is not None:
            sessionID = self.project.createRemoteSession(remote,
                            state_dictionary=self.sessionGui.mainWindow.networkManager.getStateDictionary())
        else:
            sessionID = self.project.createSession(
                state_dictionary=self.sessionGui.mainWindow.networkManager.getStateDictionary())

        self.filterState()
        if sessionID is not None:
            session = self.project.getSession(sessionID)
            self.sessionConnects(session)
            self.sessionIterationChanged(session)
            self.sessionGui.mainWindow.actions.checkSessionState(session, showWarnings=False)
            self.setActiveSID(sessionID)
        return sessionID

    def loadRemoteSession(self, remote, sessionUID):
        sessionID = self.project.loadRemoteSession(remote, sessionUID)
        self.filterState()
        if sessionID is not None:
            session = self.project.getSession(sessionID)
            session.fetchParserData()
            self.sessionConnects(session)
            self.setActiveSID(sessionID)

    def createNewSession(self, caffemodel=None):
        """ Create a new session and start the training.

        Create a new session, add new parser to plotter and create a new
        session widget for the session
        """
        if checkMinimumTrainingRequirements(self.project, self.sessionGui):
            sessionID = self.project.createSession(
                state_dictionary=self.sessionGui.mainWindow.networkManager.getStateDictionary())
            if sessionID:
                session = self.project.getSessions[sessionID]
                session.snapshotAdded.connect(lambda: self.wPlotter.updatePlotter(self.project.getSessions()))
                self.updateWeightPlotter()
                # Since this is not set at startup, the parsing has already been done, thus the session should send signals
                session.setParserInitialized()
                session.start(caffemodel=caffemodel)
                self.filterState()
            else:
                Log.error('Failed to create session!', self.getCallerId())

    def displaySession(self, sessionID):
        """ Displays a session in the plotter.
        """
        session = self.project.getSession(sessionID)
        if self.plotter and session is not None:
            parser = session.getParser()
            if parser:
                # add plot (True -> plotOnUpdate = realtime)
                self.plotter.putLog(str(session.getLogId()), parser, True, str(session.getLogFileName(True)))

    def updateWeightPlotter(self, input=None):
        """ Updates Plotter"""
        self.wPlotter.updatePlotter(self.project.getSessions())

    def createNewSessionFromSnapshot(self, solverstate, old_session):
        """ Create a new session as a clone of the given session, start with the
        snapshot state.
        """
        if old_session.isRemote():
            sessionID = self.project.cloneRemoteSession(solverstate, old_session)
        else:
            sessionID = self.project.cloneSession(solverstate, old_session)
        session = self.project.getSession(sessionID)
        if session:
            session.setState(State.PAUSED)
            self.sessionConnects(session)
            session.snapshotAdded.connect(lambda: self.wPlotter.updatePlotter(self.project.getSessions()))
            self.setActiveSID(sessionID)
        else:
            cid = None
            if old_session:
                cid = old_session.getCallerId()
            else:
                cid = self.getCallerId()
            Log.error('Failed to clone session!', cid)

    def closeSession(self, remoteSession):
        """ Closes the given remote session and makes sure that a new valid session will
            be selected. If the last session is deleted, a new one will be created
            For further in-method documentation see removeSessions() below
        """
        if not isinstance(remoteSession, ClientSession):
            return
        remoteSession.pause()

        sessionID = remoteSession.getSessionId()
        validSIDs = [s for s in self.project.getValidSIDs() if not s == sessionID]
        if len(validSIDs) == 0:
            sid = self.justCreateNewSession()
        else:
            sid = validSIDs[-1]
        self.project.setActiveSID(sid)

        self.plotter.removeLog(str(remoteSession.getLogId()),
                               str(remoteSession.getLogFileName(True)))
        self.project.closeSession(remoteSession)
        self.wPlotter.updatePlotter(self.project.getSessions())

        self.filterState()
        self.sessionGui.mainWindow.actions.loadSessionState(sid)
        self.sessionGui.setSelectedSID(sid)



    def removeSessions(self, sessions):
        """ Delete the given sessions and make sure that a new valid session will
        be selected. If the last session is deleted, we create a new one, to keep
        a sane project state.
        """
        sessionIDs = [s.getSessionId() for s in sessions]
        # Get all session ids that remain valid after the sessions have been deleted.
        validSIDs = [s for s in self.project.getValidSIDs() if s not in sessionIDs]
        # If we delete all valid sessions, we create a new one, because the project
        # shouldn't exist without a valid session.
        if len(validSIDs) == 0:
            sid = self.justCreateNewSession()
        else:
            sid = validSIDs[-1]
        # Now we select a new session from the remaining valid sessions, to prevent
        # a conflict when deleting.
        self.project.setActiveSID(sid)
        # Remove the session.
        for session in sessions:
            self.plotter.removeLog(str(session.getLogId()),
                                   str(session.getLogFileName(True)))
        self.project.removeSessions(sessions)
        # Update the weight plotter.
        self.wPlotter.updatePlotter(self.project.getSessions())
        # Update the session list widget, to show the remaining session items.
        self.filterState()
        # And finally we call the default action to load the newly selected session.
        # TODO: this should eventually be called from sessionGui.setSelectedSID()
        # anyway, however without this line it doesn't seem to work.
        self.sessionGui.mainWindow.actions.loadSessionState(sid)
        # And select the newly selected session from the list widgets.
        self.sessionGui.setSelectedSID(sid)
        # TODO: Are the deleted sessions garbage collected at this point or do we
        # have a memory leak?

    def filterState(self):
        """ Filter the sessions for the state that has been selected in the GUI.
        """
        filtered = OrderedDict()
        state = self.sessionGui.getFilterState()
        if state == 'ALL':
            filtered = self.project.getSessions()
        else:
            for sid, session in self.project.getSessions().iteritems():
                sesstate = session.getState()
                if ((state == 'RUNNING' and sesstate is State.RUNNING) or
                        (state == 'FAILED' and sesstate is State.FAILED) or
                        (state == 'FINISHED' and sesstate is State.FINISHED) or
                        (state == 'PAUSED' and sesstate is State.PAUSED) or
                        (state == 'INVALID' and sesstate is State.INVALID) or
                        (state == 'WAITING' and sesstate is State.WAITING)):
                    filtered[sid] = session
        self.sessionGui.showSessions(filtered)

    # LogCaller

    def getCallerId(self):
        """ Return the unique caller id for this session
        """
        if self.caller_id is None:
            self.caller_id = Log.getCallerId('SessionController')
        return self.caller_id

    def resetSession(self, session):
        session.reset()
        self.sessionStateChanged(session)
