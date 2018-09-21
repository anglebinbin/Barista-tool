from PyQt5.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QListWidget,
    QMessageBox,
    QListWidgetItem,
    QGridLayout,
    QStyle,
    qApp,
    QAbstractItemView
)
from gui.caffepath_dialog import CaffepathDialog
import backend.barista.caffe_versions as caffeVersions
import os
import json

class CaffeVersionDialog(QDialog):

    def __init__(self, exception, dir, default_actions, parent = None):
        super(CaffeVersionDialog, self).__init__(parent)
        self.exception = exception
        self.parent = parent
        self.dir = dir
        self.actions = default_actions
        self.projectVersion = self.getProjectVersion()

        self.setWindowTitle("Warning!")

        self.layout = QGridLayout(self)

        self.lblWarning = QLabel("Failed to load Project with caffe-version: '" + self.projectVersion + "'\n{} \nPlease select another caffe-version for the project".format(str(self.exception)))
        self.layout.addWidget(self.lblWarning, 0, 0, 1, 1)
        
        self.pbAddCaffeVersion = QPushButton("Add Version")
        self.layout.addWidget(self.pbAddCaffeVersion, 1, 0, 1, 1)    

        self.lstVersions = QListWidget(self)
        self.lstVersions.setSelectionMode(QAbstractItemView.SingleSelection)
        self.layout.addWidget(self.lstVersions, 2, 0, 1, 1)  

        self.pbChangeCaffeVersion = QPushButton("Select")
        self.layout.addWidget(self.pbChangeCaffeVersion, 3, 0, 1, 1)    

        self.pbAddCaffeVersion.clicked.connect(self._onAddVersion)
        self.pbChangeCaffeVersion.clicked.connect(self._onSetProjectDefault)
        self.lstVersions.itemSelectionChanged.connect(self._onSelectionChanged)
        self.updateList()

    def _onAddVersion(self):
        """Opens the dialog to add new caffe versions"""
        caffedlg = CaffepathDialog("Add a new caffe version to Barista", "Add version")
        caffedlg.exec_()
        self.updateList()

    def updateList(self):
        """updates the list containing all available caffe versions"""
        self.lstVersions.clear()
        versions = caffeVersions.getAvailableVersions()
        for version in versions:
            name = version.getName()
            lblVersion = QLabel(name)

            item = QListWidgetItem()
            self.lstVersions.addItem(item)
            self.lstVersions.setItemWidget(item, lblVersion)

    def _onSelectionChanged(self):
        if len(self.lstVersions.selectedItems()) < 1:
            self.pbChangeCaffeVersion.setEnabled(False)
        else:
            self.pbChangeCaffeVersion.setEnabled(True)

    def getProjectVersion(self):
        configfile = os.path.join(self.dir,  "barista_project.json")
        with open(configfile, "r") as file:
            res = json.load(file)
        file.close()
        if "caffeVersion" in res:
            return res["caffeVersion"]
        else:
            return None
         
    def _onSetProjectDefault(self, name):
        """Sets the default caffe version of the current project"""
        caffeVersions.loadVersions()
        configfile = os.path.join(self.dir,  "barista_project.json")
        with open(configfile, "r") as file:
            res = json.load(file)
        file.close()
        if "caffeVersion" in res:
            caffeVersion = self.lstVersions.itemWidget(self.lstVersions.currentItem()).text()
            res["caffeVersion"] = caffeVersion 
            with open(configfile, "w") as file:
                json.dump(res, file, sort_keys=True, indent=4)
            file.close()
            msgBox = QMessageBox(QMessageBox.Warning, "Warning", "Please restart Barista client for changes to apply, otherwise Barista may be unstable!")
            msgBox.addButton("Ok", QMessageBox.NoRole)
            msgBox.addButton("Restart now", QMessageBox.YesRole)
            ret = msgBox.exec_()
            if ret == 1:
                self.actions.restart(self.dir)
            self.close()

    def closeEvent(self, event):
        if not self.parent.isVisible():
            exit()



