# -*- coding: utf-8 -*-
import copy
import os
from PyQt5 import QtWidgets

from backend.barista.utils.logger import Log
from backend.caffe import saver


class ExportSolverDialog(QtWidgets.QDialog):

    COMBO_INDEX_INLINE = 0
    COMBO_INDEX_SEPARATE_FILE = 1

    def __init__(self, solver, network, parent = None, defaultActions=None):
        super(ExportSolverDialog, self).__init__(parent)

        # create a deep copy of the solver, as we will need to manipulate it a little bit
        self._solver = copy.deepcopy(solver.valuedict)
        self._network = network

        # this will be used to add paths to the recent file list
        self._defaultActions = defaultActions

        self.PROTOTXT_FILTER = self.tr("Prototxt Files (*.prototxt);;All files (*)")

        self.setWindowTitle(self.tr("Export Solver - Options"))
        mainLayout = QtWidgets.QVBoxLayout(self)

        # browse solver file
        mainLayout.addWidget(QtWidgets.QLabel(self.tr("Export solver definition to"), self))
        self._textPathSolver = QtWidgets.QLineEdit()
        btnBrowseSolver = QtWidgets.QPushButton(self.tr("Browse"))
        btnBrowseSolver.clicked.connect(lambda: self.selectFileSolver())
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self._textPathSolver)
        layout.addWidget(btnBrowseSolver)
        mainLayout.addLayout(layout)

        # options to include the net
        # pay attention to the order in which the combo items are added.
        # they must fit to COMBO_INDEX_SEPARATE_FILE and COMBO_INDEX_INLINE
        mainLayout.addWidget(QtWidgets.QLabel(self.tr("Include net definition"), self))
        self._comboNet = QtWidgets.QComboBox()
        self._comboNet.addItem(self.tr("inline (parameter: net_param)"))
        self._comboNet.addItem(self.tr("by pointing to the following file (parameter: net)"))
        self._comboNet.currentIndexChanged.connect(self.selectionChange)
        mainLayout.addWidget(self._comboNet)

        # browse net file
        self._textPathNet = QtWidgets.QLineEdit()
        self._textPathNet.setDisabled(True)
        self._btnBrowseNet = QtWidgets.QPushButton(self.tr("Browse"))
        self._btnBrowseNet.clicked.connect(lambda: self.selectFileNet())
        self._btnBrowseNet.setDisabled(True)
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self._textPathNet)
        layout.addWidget(self._btnBrowseNet)
        mainLayout.addLayout(layout)

        # bottom button bar
        layout = QtWidgets.QHBoxLayout()
        btnSave = QtWidgets.QPushButton(self.tr("Save"))
        btnSave.clicked.connect(lambda: self.save())
        btnCancel = QtWidgets.QPushButton(self.tr("Cancel"))
        btnCancel.clicked.connect(lambda: self.cancel())
        layout.addWidget(btnCancel)
        layout.addWidget(btnSave)
        mainLayout.addLayout(layout)

        # use fixed size
        self.layout().setSizeConstraint(QtWidgets.QLayout.SetFixedSize)

    def selectFileNet(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            parent=self,
            filter=self.PROTOTXT_FILTER
        )
        self._textPathNet.setText(filename)

    def selectFileSolver(self):
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            parent=self,
            filter=self.PROTOTXT_FILTER
        )

        # if the file does not yet exist and no file extension has been specified,
        # set it to the default .prototxt
        if len(filename) > 0 and not os.path.exists(filename) and os.path.splitext(filename)[1] == "":
            filename += ".prototxt"

        self._textPathSolver.setText(filename)

    def selectionChange(self, selectedIndex):
        disableNetFileSelection = (selectedIndex != self.COMBO_INDEX_SEPARATE_FILE)
        self._textPathNet.setDisabled(disableNetFileSelection)
        self._btnBrowseNet.setDisabled(disableNetFileSelection)

    def cancel(self):
        self.close()

    def save(self):
        try:
            # get user input
            netFullPath = self._textPathNet.text()
            solverFullPath = self._textPathSolver.text()
            solverDirPath = os.path.dirname(solverFullPath)
            netInSeparateFile = (self._comboNet.currentIndex() == self.COMBO_INDEX_SEPARATE_FILE)
            netPathIsValid = len(netFullPath) > 0 and os.path.exists(netFullPath) \
                             and os.path.isfile(netFullPath)

            # ensure that the input isn't empty
            if len(solverFullPath) > 0:

                # ensure that the path (except the base name) does already exist
                folderExists = os.path.isdir(solverDirPath)

                # if it doesn't exist yet, let the user decide whether to create all missing folders
                if not folderExists:
                    reply = QtWidgets.QMessageBox.question(self,
                                                           self.tr("Destination doesn't exist yet."),
                                                           self.tr("Do you want to create all non-existing folders "
                                                                   "in the given path?"),
                                                           QtWidgets.QMessageBox.Yes,
                                                           QtWidgets.QMessageBox.No)
                    if reply == QtWidgets.QMessageBox.Yes:
                        folderExists = True
                        os.makedirs(solverDirPath)

                if folderExists:
                    # ensure that the full path does point to a file and not a folder
                    fileIsNoFolder = not os.path.exists(solverFullPath) or not os.path.isdir(solverFullPath)

                    # input is valid, go ahead and start the actual export
                    if fileIsNoFolder:

                        if netInSeparateFile:

                            # network path does not need to be valid, as we are not doing anything with the referenced file
                            # anyway: let the user decide whether an invalid path is used on purpose
                            if not netPathIsValid:
                                reply = QtWidgets.QMessageBox.question(self,
                                                                       self.tr("Network path seems to be invalid."),
                                                                       "Do you want to continue anyway?",
                                                                       QtWidgets.QMessageBox.Yes,
                                                                       QtWidgets.QMessageBox.No)
                                if reply == QtWidgets.QMessageBox.Yes:
                                    netPathIsValid = True

                            if netPathIsValid:
                                # point to selected network file
                                self._solver["net"] = netFullPath

                                # remove any other references to a network definition
                                if "net_param" in self._solver:
                                    del self._solver["net_param"]
                        else:
                            # include inline definition of the network
                            self._solver["net_param"] = self._network

                            # remove any other references to a network file
                            if "net" in self._solver:
                                del self._solver["net"]

                        # finally, save solver prototxt
                        if not netInSeparateFile or netPathIsValid:
                            with open(solverFullPath, 'w') as file:
                                file.write(saver.saveSolver(self._solver))

                            callerId = Log.getCallerId('export_solver')
                            Log.log(
                                "The solver has been exported successfully to {}.".format(
                                    solverFullPath
                                ), callerId)

                            # add used file paths to the recent file list
                            if self._defaultActions is not None:
                                self._defaultActions.recentSolverData.addRecently(solverFullPath, solverFullPath)

                                if netInSeparateFile and netPathIsValid:
                                    self._defaultActions.recentNetData.addRecently(netFullPath, netFullPath)

                            self.close()
                    else:
                        QtWidgets.QMessageBox.critical(self, self.tr("Can't save solver"),
                                                       self.tr("The given path points to an existing folder instead of "
                                                               "a file."))
            else:
                QtWidgets.QMessageBox.critical(self,
                                               self.tr("Can't save solver"),
                                               self.tr("Please select a valid destination for the solver file."))
        except:
            QtWidgets.QMessageBox.critical(self,
                                           self.tr("Can't save solver"),
                                           self.tr("Unknown error."))
            self.close()
