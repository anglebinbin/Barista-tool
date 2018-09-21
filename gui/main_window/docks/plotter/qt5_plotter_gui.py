import os
from PyQt5 import QtGui, QtCore, QtWidgets
from collections import OrderedDict

from PyQt5.QtCore import Qt, pyqtSignal, QVariant
from PyQt5.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QPushButton,
    QCheckBox,
    QListWidget,
    QFileDialog,
    QStackedWidget,
    QWidget,
    QLabel,
    QToolButton,
    QMenu,
    QWidgetAction,
    QStyle,
    QApplication,
    QMessageBox,
    QListWidgetItem)

from backend.barista.utils.logger import Log
from backend.parser.parser import Parser
from gui.main_window.docks.dock import DockElement
from gui.main_window.docks.plotter.qt5_plotter import Qt5Plotter


class DockElementPlotter(DockElement):

    selected = None
    registerKeySignal = pyqtSignal(str, str, str)

    __settings = {}

    def __init__(self, mainWindow, title):
        DockElement.__init__(self, mainWindow, 'Plotter')
        self.name = title
        self.setWindowTitle(title)
        self.setupUi()

    def setupUi(self):
        self.resize(500, 300)
        self.settingsWidget = QWidget()
        self.settingsWidget.setMinimumSize(900,150)
        # Create the main widget as a container widget.
        self.mainWidget = QWidget(self)
        self.setWidget(self.mainWidget)
        mainLayout = QVBoxLayout(self.mainWidget)
        # Create 'Settings' dropdown button.
        self.settingsButton = QToolButton(self)
        self.settingsButton.setText("Settings")
        # Remove the menu indicator by applying a global style.
        self.settingsButton.setObjectName("noIndicator")
        # And replace it with a down arrow icon instead (which looks better).
        self.settingsButton.setArrowType(QtCore.Qt.DownArrow)
        self.settingsButton.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        # Set the popup that opens on button click.
        self.settingsButton.setPopupMode(QToolButton.InstantPopup)
        action = QWidgetAction(self.settingsButton)
        action.setDefaultWidget(self.settingsWidget)
        self.settingsButton.addAction(action)
        # Create a horizontal layout for the settings button.
        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(self.settingsButton)
        buttonLayout.addStretch()
        mainLayout.addLayout(buttonLayout)
        # Create the plotter widget.
        self.plotter = Qt5Plotter()
        self.plotter.setPlotterGUI(self)
        self.plotter.setMinimumSize(300,200)
        self.plotter.plotLinear()
        mainLayout.addWidget(self.plotter)
        # Create the settings dialog.
        self.setupSettingsDialogUi()
        # Set keys that are plotted by default
        self.defaultKeys = {"TEST": ["loss"], "TRAIN": ["loss"]}

    def setupSettingsDialogUi(self):
        self.settingsDialogLayout = QGridLayout()
        # DropDown for plotAgainstTime or Iterations
        self.dbTimeIter = QComboBox()
        self.dbTimeIter.addItem("Iterations")
        self.dbTimeIter.addItem("Time")
        self.dbTimeIter.setFixedWidth(130)
        self.dbTimeIter.currentIndexChanged.connect(self.plotAgainstTimeIter)
        self.settingsDialogLayout.addWidget(self.dbTimeIter, 1, 3)
        # DropDown for plotting scale linear or logarithmic
        self.dbLinLoga = QComboBox()
        self.dbLinLoga.addItem("Linear")
        self.dbLinLoga.addItem("Logarithmic")
        self.dbLinLoga.setFixedWidth(130)
        self.dbLinLoga.currentIndexChanged.connect(self.plotLinLoga)
        self.settingsDialogLayout.addWidget(self.dbLinLoga, 3,3)
        # Dynamic checkboxes
        # Key lists from parser that define the table rows for train and test
        self.test_dict_list = []
        self.train_dict_list = []
        # Lists for checkboxes for train and test
        self.test_cb = []
        self.train_cb = []
        # Text labels for better display
        testLabel = QLabel("Test keys:")
        trainLabel = QLabel("Train keys:")
        timeIterLabel = QLabel("Plot against:")
        LinLogaLabel = QLabel("Plot scale:")
        self.settingsDialogLayout.addWidget(testLabel,0,4)
        self.settingsDialogLayout.addWidget(trainLabel,2,4)
        self.settingsDialogLayout.addWidget(timeIterLabel,0,3)
        self.settingsDialogLayout.addWidget(LinLogaLabel,2,3)
        # create default Checkboxes
        self.createCheckboxes(self.test_dict_list, self.train_dict_list)
        # Button select Logfiles
        self.btn1 = QPushButton(QtGui.QIcon(QApplication.style().standardIcon(QStyle.SP_DialogOpenButton)), "")
        self.btn1.setFixedWidth(40)
        self.btn1.clicked.connect(self.getFiles)
        self.settingsDialogLayout.addWidget(self.btn1,3,0)
        # Button remove item
        self.btn2 = QPushButton(QtGui.QIcon(QApplication.style().standardIcon(QStyle.SP_TrashIcon)), "")
        self.btn2.setFixedWidth(40)
        self.btn2.clicked.connect(self.removeItem)
        self.settingsDialogLayout.addWidget(self.btn2,3,1)
        # Button CSV export
        self.btn3 = QPushButton("Export as CSV")
        self.btn3.setFixedWidth(110)
        self.btn3.clicked.connect(self.exportCSV)
        self.settingsDialogLayout.addWidget(self.btn3,3,2)
        # Create Logfile list
        self.leftlist = QListWidget()
        self.leftlist.setFixedSize(200,100)
        self.Stack = QStackedWidget(self)
        self.settingsDialogLayout.addWidget(self.Stack,0,0,3,3)
        self.settingsDialogLayout.addWidget(self.leftlist,0,0,3,3)
        self.leftlist.currentRowChanged.connect(self.display)
        self.leftlist.currentItemChanged.connect(self.selectedLogItem)
        self.settingsWidget.setLayout(self.settingsDialogLayout)
        # Signal handling
        self.registerKeySignal.connect(self.registerKey)

    def btnstatetest(self, checkbox):
        """
        Plot the selected checkbox for Test-Data
        """
        if self.selected:
            self.plotter.showMetricTest(self.selected, checkbox.text(), checkbox.isChecked())
            self.displayPlot()
            self.__settings["checkBoxes"][self.selected]["TEST"][checkbox.text()] = checkbox.isChecked()


    def btnstatetrain(self, checkbox):
        """
        Plot the selected checkbox for Train-Data
        """
        if self.selected:
            self.plotter.showMetricTrain(self.selected, checkbox.text(), checkbox.isChecked())
            self.displayPlot()
            self.__settings["checkBoxes"][self.selected]["TRAIN"][checkbox.text()] = checkbox.isChecked()

    def displayPlot(self):
        """
        Update the plotter.
        """
        if self.selected:
            self.plotter.plot()
            self.plotter.show()
            self.createNecessaryDocks()

    def createNecessaryDocks(self):
        """
        Create the necessary docks if they don't exist.
        """
        if self.__settings is None:
            self.__settings = {}
        if "checkBoxes" not in self.__settings:
            self.__settings["checkBoxes"] = {}
        if self.selected not in self.__settings["checkBoxes"] or \
                isinstance(self.__settings["checkBoxes"][self.selected], list):
            self.__settings["checkBoxes"][self.selected] = {"TEST": {}, "TRAIN": {}}

    def existsKeySelection(self):
        """
        Returns true if there is a selection by the user of keys to be plotted
        """
        if self.__settings is None:
            self.__settings = {}
        if "checkBoxes" not in self.__settings:
            self.__settings["checkBoxes"] = {}
        if self.selected not in self.__settings["checkBoxes"]:
            return False
        return True

    def createCheckboxes(self, test_list, train_list):
        """
        Dynamically creates checkboxes, which are in the lists: test_list and train_list
        """
        self.test_dict_list = test_list
        self.train_dict_list = train_list
        # As long as there are elements in TEST list: create Checkboxes
        if self.test_dict_list is not None:
            for i in range(len(self.test_dict_list)):
                self.test_cb.append(QCheckBox(self.test_dict_list[i], self))
                self.settingsDialogLayout.addWidget(self.test_cb[i], 1, 4+i)
                self.test_cb[i].stateChanged.connect(lambda checked, i=i: self.btnstatetest(self.test_cb[i]))
                if self.existsKeySelection() and self.test_cb[i].text() in \
                        self.__settings["checkBoxes"][self.selected]["TEST"]:
                    # Compatibility for older projects
                    try:
                        self.test_cb[i].setChecked(
                            self.__settings["checkBoxes"][self.selected]["TEST"].get(self.test_cb[i].text(), True))
                    except AttributeError:
                        self.test_cb[i].setChecked(True)
                else:
                    self.test_cb[i].setChecked(self.test_cb[i].text() in self.defaultKeys["TEST"])
                self.btnstatetest(self.test_cb[i])


        # As long as there are elements in TRAIN list: create Checkboxes
        if self.train_dict_list is not None:
            for i in range(len(self.train_dict_list)):
                self.train_cb.append(QCheckBox(self.train_dict_list[i], self))
                self.settingsDialogLayout.addWidget(self.train_cb[i], 3, 4+i)
                self.train_cb[i].stateChanged.connect(lambda checked, i=i: self.btnstatetrain(self.train_cb[i]))
                if self.existsKeySelection() and self.train_cb[i].text() in \
                        self.__settings["checkBoxes"][self.selected]["TRAIN"]:
                    # Compatibility for older projects
                    try:
                        self.train_cb[i].setChecked(
                            self.__settings["checkBoxes"][self.selected]["TRAIN"].get(self.train_cb[i].text(), True))
                    except AttributeError:
                        self.train_cb[i].setChecked(True)

                else:
                    self.train_cb[i].setChecked(self.train_cb[i].text() in self.defaultKeys["TRAIN"])
                self.btnstatetrain(self.train_cb[i])
        self.settingsWidget.setLayout(self.settingsDialogLayout)

    def display(self, i):
        self.Stack.setCurrentIndex(i)

    def loadFiles(self, filenames):
        """
        Loads every log file in the list of filenames and adds them to the list of logs.
        """
        for i in range(len(filenames)):
            f = filenames[i]
            if not os.path.exists(f):
                Log.error("External log not found: " + f, Log.getCallerId("plotter"))
            else:
                parser = Parser(open(f, 'r'), OrderedDict(), Log.getCallerId(str(f)))
                head, tail = os.path.split(str(f))
                logId = "external_" + tail
                logName = "[ext] " + tail
                self.putLog(logId, parser, logName=logName)
                parser.parseLog()

                # This is for saving the loaded logs in the project file
                # (create the necessary docks if they don't exist)
                if self.__settings is None:
                    self.__settings = {"logFiles": {logId: f}}
                elif "logFiles" not in self.__settings:
                    self.__settings["logFiles"] = {logId: f}
                else:
                    self.__settings["logFiles"][logId] = f

    def getFiles(self):
        """
        Dialog for adding different data files to list for plotting
        """
        dlg = QFileDialog()
        dlg.setFileMode(QFileDialog.ExistingFiles)
        if dlg.exec_():
            self.loadFiles(dlg.selectedFiles())
        self.selectLast()

    def plotAgainstTimeIter(self):
        if self.dbTimeIter.currentText() == "Time":
            self.plotter.plotAgainstTime()
            self.__settings["againstTime"] = "Time"
            self.plotter.plot()
        else:
            if self.dbTimeIter.currentText() == "Iterations":
                self.plotter.plotAgainstIterations()
                self.__settings["againstTime"] = "Iterations"
                self.plotter.plot()

    def plotLinLoga(self):
        if self.dbLinLoga.currentText() == "Linear":
            self.plotter.plotLinear()
            self.__settings["logarithmic"] = "Linear"
            self.plotter.plot()
        else:
            if self.dbLinLoga.currentText() == "Logarithmic":
                self.plotter.plotLogarithmic()
                self.__settings["logarithmic"] = "Logarithmic"
                self.plotter.plot()

    def putLog(self, logId, parser, plotOnUpdate=False, logName=None):
        """
        Add a log (i.e. parser) to the list of shown logs. If a log with the
        log name already exists primes are added to the name until it is unique.
        """
        for i in range(self.leftlist.count()):
            if logId == self.leftlist.item(i).data(Qt.UserRole):
                return
        if not logName:
            logName = logId
        self.test_dict_list = []
        self.train_dict_list = []
        while self.leftlist.findItems(logName, Qt.MatchExactly):
            logName += "'"
        self.plotter.putLog(logId, logName, parser, plotOnUpdate)
        logItem = QListWidgetItem(logName)
        v = QVariant(logId)
        logItem.setData(Qt.UserRole, v)
        self.leftlist.insertItem(self.leftlist.count(), logItem)
        self.selectLast()

    def removeLog(self, logId, logName):
        try:
            self.__settings["checkBoxes"].pop(logId)
        except KeyError:
            pass
        self.plotter.removeLog(logId)
        item = self.leftlist.findItems(logName, Qt.MatchExactly)
        if item:
            row = self.leftlist.row(item[0])
            self.leftlist.takeItem(row)
            self.test_dict_list = []
            self.train_dict_list = []
            self.selectLast()
            self.plotter.plot()
            self.plotter.show()

    def registerKey(self, logId, phase, key):
        """
        Registers the key given by the signal. This is only of interest if the key belongs
        to the selected log file. A new checkbox is then created for that key.
        """
        if self.leftlist.currentItem():
            if str(self.leftlist.currentItem().data(Qt.UserRole)) == logId:
                if phase == "TEST":
                    self.test_dict_list.append(key)
                if phase == "TRAIN":
                    self.train_dict_list.append(key)
                self.updateCheckboxes(self.test_dict_list, self.train_dict_list)

    def removeItem(self):
        """
        Removes the selected item from the list and also from plot.
        """
        item = self.leftlist.takeItem(self.leftlist.currentRow())
        if item is not None:
            self.removeLog(item.data(Qt.UserRole), item.text())
            self.displayPlot()
            self.selectLast()
            if (self.__settings is not None
                    and "logFiles" in self.__settings
                    and str(item.data(Qt.UserRole)) in self.__settings["logFiles"]):
                del self.__settings["logFiles"][str(item.data(Qt.UserRole))]

    def selectLast(self):
        if len(self.leftlist) > 0:
            self.leftlist.setCurrentItem(self.leftlist.item(len(self.leftlist) - 1))
            self.selectedLogItem(self.leftlist.item(len(self.leftlist) - 1))
        else:
            self.test_dict_list = []
            self.train_dict_list = []
            self.updateCheckboxes(self.test_dict_list,self.train_dict_list)

    def selectedLogItem(self, item, update=True):
        """
        Memorize which logfile is selected, block signals, and asks plotter if the checkbox is
        selected or not.
        """
        if item:
            if update:
                self.updateCheckboxes(
                                 list(self.plotter.getParser(str(item.data(Qt.UserRole))).getKeys('TEST')),
                                 list(self.plotter.getParser(str(item.data(Qt.UserRole))).getKeys('TRAIN')))
            self.selected = str(str(item.data(Qt.UserRole)))
            self.tickBoxes()
            self.__settings["selectedIndex"] = self.leftlist.row(item)

    def updateCheckboxes(self, test_list, train_list):
        """
        Clear all checkboxes and clear the layer and create new checkboxes and
        add them to the layer again
        """
        for i in range(len(self.test_cb)):
            self.settingsDialogLayout.removeWidget(self.test_cb[i])
            self.test_cb[i].deleteLater()
            self.test_cb[i] = None

        for i in range(len(self.train_cb)):
            self.settingsDialogLayout.removeWidget(self.train_cb[i])
            self.train_cb[i].deleteLater()
            self.train_cb[i] = None

        self.test_cb = []
        self.train_cb = []
        # create new Checkboxes with new Keys
        self.createCheckboxes(test_list, train_list)
        self.tickBoxes()

    def tickBoxes(self):
        """
        Whether a plot is shown is stored in the plotter object. This method
        ticks the checkboxes of the keys whose plot is shown in the plotter.
        """
        for i in range(len(self.test_cb)):
            self.test_cb[i].blockSignals(True)
            self.test_cb[i].setChecked(self.plotter.isMetricTestShown(self.selected, self.test_cb[i].text()))
            self.test_cb[i].blockSignals(False)
        for i in range(len(self.train_cb)):
            self.train_cb[i].blockSignals(True)
            self.train_cb[i].setChecked(self.plotter.isMetricTrainShown(self.selected, self.train_cb[i].text()))
            self.train_cb[i].blockSignals(False)

    def setProject(self, project):
        """
        This sets the project object. The plotter settings have the following structure:

        "plotter": {
                   "checkBoxes": {
                       "logName1": {
                           "TEST": {
                                "accuracy": true,
                                "loss": false
                            },
                            "TRAIN": {
                                "LearningRate": true,
                                "loss": false
                            }
                       },
                       "logName2": {
                           ...
                       },
                       ...
                   },
                   "selectedIndex": 0,
                   "againstTime": "Iterations",
                   "logarithmic": "Logarithmic"
               }

        """

        if "plotter" not in project.getSettings():
            project.getSettings()["plotter"] = self.__settings
        else:
            self.__settings = project.getSettings()["plotter"]
        selectedIndex = -1
        if "selectedIndex" in self.__settings:
            selectedIndex = self.__settings["selectedIndex"]
        if "logFiles" in self.__settings:
            self.loadFiles(list(self.__settings["logFiles"].values()))
        if "checkBoxes" in self.__settings:
            for name in self.__settings["checkBoxes"]:
                for key in self.__settings["checkBoxes"][name]["TEST"]:
                    # Compatibility for older projects
                    try:
                        self.plotter.showMetricTest(name, key, self.__settings["checkBoxes"][name]["TEST"].get(key))
                    except AttributeError:
                        self.plotter.showMetricTest(name, key, True)
                for key in self.__settings["checkBoxes"][name]["TRAIN"]:
                    # Compatibility for older projects
                    try:
                        self.plotter.showMetricTrain(name, key, self.__settings["checkBoxes"][name]["TRAIN"].get(key))
                    except AttributeError:
                        self.plotter.showMetricTrain(name, key, True)
        if "againstTime" in self.__settings:
            index = self.dbTimeIter.findText(self.__settings["againstTime"], Qt.MatchFixedString)
            if index >= 0:  
                self.dbTimeIter.setCurrentIndex(index)
        if "logarithmic" in self.__settings:
            index = self.dbLinLoga.findText(self.__settings["logarithmic"], Qt.MatchFixedString)
            if index >= 0:
                self.dbLinLoga.setCurrentIndex(index)
        #for sid in project.getSessions():
        #    session = project.getSession(sid)
        #    self.putLog(str(session.getLogId()), session.getParser(), True, str(session.getLogFileName(True)))
        self.plotter.plot()
        if selectedIndex >= 0:
            self.leftlist.setCurrentItem(self.leftlist.item(selectedIndex))
            self.selectedLogItem(self.leftlist.item(selectedIndex), False)
        else:
            self.selectLast()
        # Delete plot if session is deleted
        project.deleteSession.connect(lambda sid: self.removeLog(str(project.getSession(sid).getLogId()),
                                                                 str(project.getSession(sid).getLogFileName(True))))
        project.deleteSession.connect(lambda sid: project.deletePlotterSettings(str(project.getSession(sid).getLogId())))
        project.resetSession.connect(lambda sid: self.removeLog(str(project.getSession(sid).getLogId()),
                                                                 str(project.getSession(sid).getLogFileName(True))))
        project.resetSession.connect(lambda sid: project.deletePlotterSettings(str(project.getSession(sid).getLogId())))

    def exportCSV(self):
        """
        Opens a file dialog and the plotter saves the shown plots to the selected file.
        The file dialog only appears if there is at least one plot.
        """
        if self.plotter.numGraphs() == 0:
            QMessageBox.question(self, 'PyQt5 message', "Nothing selected!", QMessageBox.Ok, QMessageBox.Ok)
        else:
            path = str(QFileDialog.getSaveFileName(filter="CSV table (*.csv) ;; Text file (*.txt)")[0])
            if path:
                if not (path.endswith(".csv") or path.endswith(".txt")):
                    path = path + ".csv"
                self.plotter.exportCSVToFile(path)
