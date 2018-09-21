# -*- coding: utf-8 -*-
import os
import ntpath
from PyQt5 import QtWidgets

from backend.barista.utils.logger import Log
from backend.barista.deployed_net import DeployedNet
from backend.barista.project import Project

from backend.barista.session.session_utils import Paths

class DeploymentDialog(QtWidgets.QDialog):

    COMBO_INDEX_INLINE = 0
    COMBO_INDEX_SEPARATE_FILE = 1

    def __init__(self, sessions, parent = None):
        super(DeploymentDialog, self).__init__(parent)
        # Save given params.
        self._sessions = sessions
        self._setupUi()
        self.caller_id = None

    def _setupUi(self):
        self.setWindowTitle(self.tr("Deployment - Options"))
        mainLayout = QtWidgets.QVBoxLayout(self)

        # browse destination folder
        mainLayout.addWidget(QtWidgets.QLabel(self.tr("Export deployment files to"), self))
        self._textDestination = QtWidgets.QLineEdit()
        btnBrowseDestination = QtWidgets.QPushButton(self.tr("Browse"))
        btnBrowseDestination.clicked.connect(lambda: self.selectFolder())
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self._textDestination)
        layout.addWidget(btnBrowseDestination)
        mainLayout.addLayout(layout)

        # snapshot selection
        self._snapshotInfoByComboIndex = []
        mainLayout.addWidget(QtWidgets.QLabel(self.tr("Snapshot (determines caffemodel file and "
                                                      " network version)."), self))
        self._comboNet = QtWidgets.QComboBox()
        for sessionKey in sorted(self._sessions, reverse=True):
            session = self._sessions[sessionKey]
            snapshots = session.getSnapshots()
            for snapshotKey in sorted(snapshots, reverse=True):
                snapshot = snapshots[snapshotKey]
                self._comboNet.addItem(self.tr("Session " + str(session.getSessionId()) + " - " +
                                               os.path.basename(snapshot)))
                self._snapshotInfoByComboIndex.append({"session": session,
                                                       "snapshot": snapshot})
        mainLayout.addWidget(self._comboNet)

        # bottom button bar
        layout = QtWidgets.QHBoxLayout()
        btnDeployAndExport = QtWidgets.QPushButton(self.tr("Deploy and Export"))
        btnDeployAndExport.clicked.connect(lambda: self.deployAndExport())
        btnCancel = QtWidgets.QPushButton(self.tr("Cancel"))
        btnCancel.clicked.connect(lambda: self.cancel())
        layout.addWidget(btnCancel)
        layout.addWidget(btnDeployAndExport)
        mainLayout.addLayout(layout)
        # Fix width and height.
        self.layout().setSizeConstraint(QtWidgets.QLayout.SetFixedSize)

    def getCallerId(self):
        """ Return the unique caller id for this session
        """
        if self.caller_id is None:
            self.caller_id = Log.getCallerId('Deployment')
        return self.caller_id

    def selectFolder(self):
        """
        Opens a directory selection dialog and sets the line edit's value to the
        selected path. This will be triggered when the user clicks the browse button.
        """
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(
            parent=self
        )
        self._textDestination.setText(dir_path)

    def cancel(self):
        """
        Closes the dialog. This will be triggered when the user clicks the
        cancel button.
        """
        self.close()

    def _replaceLast(self, source_string, replace_what, replace_with):
        """
        Replace the very last occurrence of replace_what with replace_with in source_string.

        Code taken from: http://stackoverflow.com/a/3675423
        """
        head, sep, tail = source_string.rpartition(replace_what)
        return head + replace_with + tail

    def deployAndExport(self):
        """
        Wrapper around _deployAndExportUnsafe that catches exceptions and shows
        them to the user in an error dialog.
        """
        try:
            self._deployAndExportUnsafe()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self,
                                           self.tr("Can't use specified destination"),
                                           self.tr("Error: " + str(e)))
            self.close()

    def _deployAndExportUnsafe(self):
        """
        This will be triggered when the user clicks the deploy button. It validates
        the user input and displays messages and errors if additional input is
        required. If everything is validated successfully, the session is exported
        to the destination directory.
        """
        # If no snapshot exists, we show an error message and close the dialog.
        if not self._hasSnapshotsOrDisplayError():
            self.close()
            return
        # Get the destination folder from the current user input. If the input
        # is empty, we show an error message and cancel.
        destinationFolder = self._getDestinationOrDisplayError()
        if not destinationFolder:
            return
        # Check if the path already exsists. If it doesn't exist yet, let the user
        # decide whether to create all missing folders and abort otherwise.
        folderExists = os.path.isdir(destinationFolder)
        if not folderExists and not self._askDirectoryCreatePermission():
            return
        # Ensure that the full path points to a folder and not a file.
        if not self._ensurePathIsFolderOrDisplayError(destinationFolder):
            return
        # Determine the destination file paths for
        destinationPrototxtFile, caffemodelDestination = self._getDestinationFilePaths(destinationFolder)
        # Check if any of the destination files already exsist and ask the user
        # if they should be replaced. Abort if the user decides not to replace one
        # of the files.
        if not self._checkFilesDontExistOrAskReplacePermission([destinationPrototxtFile, caffemodelDestination]):
            return
        # Export files.
        session = self._selectedSession()
        snapshot = self._selectedSnapshot()
        caffemodelContents = session.readCaffemodelFile(self._replaceLast(snapshot,
                                                                          'solverstate',
                                                                          'caffemodel'))
        # Start deployment.
        deployedNet = session.readDeployedNetAsString()

        # Write prototxt file.
        with open(destinationPrototxtFile, 'w') as file:
            file.write(deployedNet)
        # Write caffemodel file.
        with open(caffemodelDestination, 'w') as caffemodelFile:
            caffemodelFile.write(caffemodelContents)

        Log.log("Deployment files have been saved successfully to {}.".format(destinationPrototxtFile), self.getCallerId())

        # Close the current dialog.
        self.close()

    def _selectedSession(self):
        """ Returns the session that belongs to the currently selected snapshot. """
        return self._snapshotInfoByComboIndex[self._comboNet.currentIndex()]["session"]

    def _selectedSnapshot(self):
        """ Returns the currently selected snapshot name. """
        return self._snapshotInfoByComboIndex[self._comboNet.currentIndex()]["snapshot"]

    def _hasSnapshotsOrDisplayError(self):
        """
        Displays an error QMessageBox and returns False if no snapshots exist.
        Returns True otherwise.
        """
        if len(self._snapshotInfoByComboIndex) <= 0:
            QtWidgets.QMessageBox.critical(self,
                                           self.tr("Deployment not available"),
                                           self.tr("There needs to be at least one saved snapshot to allow deployment."))
            return False
        return True

    def _getDestinationOrDisplayError(self):
        """
        If the user has not input a destination directory, this shows an error
        QMessageBox and returns False. Returns the destination path otherwise.
        """
        destinationFolder = self._textDestination.text()
        if len(destinationFolder) <= 0:
            QtWidgets.QMessageBox.critical(self,
                                           self.tr("Can't use specified destination"),
                                           self.tr("Please select a valid destination to export deployment files."))
            return False
        return destinationFolder

    def _ensurePathIsFolderOrDisplayError(self, path):
        """
        Checks if the given path is a folder and not a file. Displays an error
        QMessageBox if it is not a folder and returns False. Returns True otherwise.
        """
        # Ensure that the full path points to a folder and not a file.
        destinationIsFolder = not os.path.exists(path) or os.path.isdir(path)
        # If it does point to a file, we show an error and return False.
        if not destinationIsFolder:
            QtWidgets.QMessageBox.critical(self, self.tr("Can't use specified destination"),
                                           self.tr("The given path points to an existing file instead of "
                                                   "a folder."))
            return False
        return True

    def _checkFilesDontExistOrAskReplacePermission(self, files):
        """
        Takes a list of filepaths as an input and for each of those paths checks
        if the file already exists. If it does, it asks the user if it should be
        replaced. If the user clicks 'No' on any of the dialogs it returns False.
        Returns True otherwise.
        """
        for f in files:
            fileAlreadyExists = os.path.exists(f)
            basename = ntpath.basename(f)
            if fileAlreadyExists and not self._askFileReplacePermission(basename):
                return False
        return True

    def _askFileReplacePermission(self, filename):
        """,
        Shows a QMessageBox that asks the user if the file with name filename should
        be replaced. Returns True if the user clicks 'Yes' and False otherwise.
        """
        reply = QtWidgets.QMessageBox.question(self,
                                                      self.tr("File does already exist."),
                                                      self.tr(
                                                          "Do you want to replace the existing "
                                                          "%s file?" % (filename)),
                                                      QtWidgets.QMessageBox.Yes,
                                                      QtWidgets.QMessageBox.No)
        return reply == QtWidgets.QMessageBox.Yes

    def _askDirectoryCreatePermission(self):
        """
        Shows a QMessageBox that asks the user if the destination directories should
        be created. If the users clicks 'Yes', the directories will be created.
        Returns True if the user clicked 'Yes', False otherwise.
        """
        reply = QtWidgets.QMessageBox.question(self,
                                               self.tr("Destination does not exist."),
                                               self.tr("Do you want to create all non-existing folders in the given path?"),
                                               QtWidgets.QMessageBox.Yes,
                                               QtWidgets.QMessageBox.No)
        # If the user agrees, we create the directory.
        if reply == QtWidgets.QMessageBox.Yes:
            os.makedirs(destinationFolder)
        return reply == QtWidgets.QMessageBox.Yes

    def _getDestinationFilePaths(self, directory):
        """
        Returns a tuple where the first element is the filepath for the destination
        prototxt file and the second element is the filepath for the destination
        caffemodel file.
        """
        # Determine the destination file paths for
        destinationPrototxtFile = os.path.join(directory, "deployed_net.prototxt")
        caffemodelFilename = self._replaceLast(self._selectedSnapshot(),
                                               "solverstate", "caffemodel")
        caffemodelDestination = os.path.join(os.path.dirname(destinationPrototxtFile),
                                             caffemodelFilename)
        return destinationPrototxtFile, caffemodelDestination
