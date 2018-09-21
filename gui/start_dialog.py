# -*- coding: utf-8 -*-
from PyQt5 import QtWidgets, QtCore

from PyQt5.QtGui import QIcon

from backend.barista.utils.settings import applicationQSetting
from gui.main_window import main_window
from backend.caffe.proto_info import resetCaffeProtoModulesvar, UnknownLayerTypeException
from gui.main_window.default_actions import DefaultActions, dirIsProject
from backend.barista.project import Project
from backend.barista.session.session import State
from gui_util import getNewProjectDir, getOpenProjectDir
import backend.barista.caffe_versions as caffe_versions
from gui.change_caffe_version_dialog import CaffeVersionDialog

# True => Enable Development Feature like skip project loading
DEVELOP_MODE = False

class StartDialog(QtWidgets.QDialog):

    def __init__(self, parent = None):
        super(StartDialog, self).__init__(parent)
        #reload the caffe und proto Modules from the program settings to get a working version
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setWindowTitle("Barista")
        self.setWindowIcon(QIcon('./resources/icon.png'))
        self._defAct = DefaultActions(self)
        # self._win = main_window.UiMainWindow()
        # self._defAct.projectChanged.connect(self.__switchMainWindow)
        lay = QtWidgets.QVBoxLayout(self)


        welcomeText="Barista is a graphical user interface for caffe, a deep neural  network framework. <br/><br/> \n\
        Additional information about caffe and barista can be found under:<br/> \n\
         Caffe: <a href=\"http://caffe.berkeleyvision.org\">http://caffe.berkeleyvision.org</a><br/>  \n\
         Barista: <a href=\"http://barista.uni-muenster.de\">http://barista.uni-muenster.de</a><br/><br/> \n\
         We sincerely appreciate your interest and contributions!<br/> \n\
         Just follow the link above, if you like to contribute or want to send feedback.<br/><br/>"
        welcomeLabel=QtWidgets.QLabel(self)
        welcomeLabel.setText(welcomeText)
        welcomeLabel.setOpenExternalLinks(True)

        lay.addWidget(welcomeLabel)
        lay.addLayout(self.__buildButton(self.tr("New Project"), self.newProject))
        lay.addLayout(self.__buildButton(self.tr("Open Project"), self.openProject,
                                         menu=self._defAct.buildRecentProjectMenu(callback=self.loadProject)))
        if DEVELOP_MODE:
            lay.addLayout(self.__buildButton("Skip",
                                             descr="I'm professional! Just want to develop without some strange "
                                                   "loading (Development Feature)",
                                             fun=self.skip))
        lay.addLayout(self.__buildButton(self.tr("Exit"), fun=self.close))


        self.setFixedSize(self.sizeHint())
            #Development-Feature
        if DEVELOP_MODE:
            skipping = self._read_skip_setting()
            skipBox = QtWidgets.QCheckBox("Fast skipping on start (development-feature)")
            skipBox.setToolTip("Skip automatically on next start within 1 second")

            skipBox.setChecked(skipping)

            skipBox.stateChanged.connect(lambda: self._write_skip_setting(skipBox.isChecked()))
            lay.addWidget(skipBox)
            if skipping:
                QtCore.QTimer.singleShot(1000, self.skip)
        else:
            self._write_skip_setting(False)

    # method called when pushing "new project" button in Start window
    def newProject(self):
        dir = getNewProjectDir(defAct=self._defAct, parent=self)
        if len(dir) == 0:
            return
        else:
            win = main_window.UiMainWindow(self._defAct)
            # self._defAct.setProject(proj)
            win.availableActions().newProjectDialog(dir, parent=self)
            self.__switchMainWindow(win)    

    def openProject(self):
        proj = getOpenProjectDir(defAct=self._defAct, parent=self)
        if len(proj) == 0:
            return
        resetCaffeProtoModulesvar()
        self.loadProject(proj)

    def loadProject(self, dir):
        resetCaffeProtoModulesvar()
        try:
            proj = Project(dir)
        except UnknownLayerTypeException as e:
            caffeVersionDialog = CaffeVersionDialog(e, dir, self._defAct, self)
            caffeVersionDialog.exec_()
            return
        
        win = main_window.UiMainWindow(self._defAct)
        self._defAct.setProject(proj)
        self.__switchMainWindow(win)

    def skip(self):
        win = main_window.UiMainWindow(self._defAct)
        self.__switchMainWindow(win)

    def __buildButton(self, text, fun, descr="", menu=None):
        """ Build Button with given text and description.
            Connect click event to fun.
            Add an extra Button for Menu if menu is not None
        """
        lay = QtWidgets.QHBoxLayout()
        wdg = QtWidgets.QCommandLinkButton(text, self)
        lay.addWidget(wdg)
        wdg.setDescription(descr)
        if menu:
            menuButton = QtWidgets.QCommandLinkButton("Open Recent")
            menuButton.setIcon(QIcon(None))
            #menuButton.setFlat(True)
            menuButton.setMenu(menu)
            lay.addWidget(menuButton)
        pol = QtWidgets.QSizePolicy()
        pol.setHorizontalPolicy(QtWidgets.QSizePolicy.Expanding)
        wdg.setSizePolicy(pol)
        wdg.clicked.connect(fun)
        return lay

    def __switchMainWindow(self, win):
        # Resize and show the main main_window
        win.showMaximized()
        win.show()
        win.setFocus()
        self.close()

    def _read_skip_setting(self):
        setting = applicationQSetting()
        setting.beginGroup("StartDialog")
        res = setting.value("skip_always", "false")
        setting.endGroup()
        return res == "true"

    def _write_skip_setting(self, shouldSkip ):
        setting = applicationQSetting()
        setting.beginGroup("StartDialog")
        setting.setValue("skip_always", "true" if shouldSkip else "false")
        setting.endGroup()
