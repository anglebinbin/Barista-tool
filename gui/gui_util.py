from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QRegExp
from backend.barista.project import dirIsProject
import os

def askFromList(parent, layerlist, title, text, defaultSelection=True):
    '''given a list of layernames, select one'''

    # create a QDialog
    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle(title)
    # set some layouts
    layout = QtWidgets.QVBoxLayout(dialog)
    sublayout = QtWidgets.QHBoxLayout()
    # set Widgets
    label = QtWidgets.QLabel(text)
    layout.addWidget(label)
    list = QtWidgets.QListWidget(dialog)
    layout.addWidget(list)
    # add the listitems
    for id, name in layerlist:
        item = QtWidgets.QListWidgetItem(list)
        item.setData(Qt.UserRole, id)
        item.setData(0, name)
        list.addItem(item)
    # add the buttons
    pb_ok = QtWidgets.QPushButton("Ok")
    pb_can = QtWidgets.QPushButton("Cancel")
    sublayout.addWidget(pb_ok)
    sublayout.addWidget(pb_can)
    layout.addLayout(sublayout)
    # connect the buttons
    list.doubleClicked.connect(dialog.accept)
    pb_ok.clicked.connect(dialog.accept)
    pb_can.clicked.connect(lambda: (list.clearSelection(), dialog.close()))

    # select the first item of the list by default
    if defaultSelection:
        list.setCurrentRow(0)

    # exec the dialog and check if return value is 1 or 0
    if dialog.exec_() == 0:
        return None

    # process the selection
    selection = list.selectedItems()
    if len(selection) == 0:
        return None
    # return the ID of the selected layer
    return selection[0].data(Qt.UserRole)


def getRecentProjectsFolder(defAct):
    """ Get the folder containing (!) the most recent project.
        defAct: DefaultActions to use
        returns: folder path or None
    """
    # Find starting directory to start new project dialog
    recentProjectTuple = defAct.recentProjectsData.getMostRecent()
    if recentProjectTuple is None:
        return
    else:
        [_, mostRecentProjectPath] = recentProjectTuple
        return os.path.dirname(mostRecentProjectPath)

def getOpenProjectDir(defAct, parent):
    """ Interactively select an existing project directory
        defAct: DefaultActions to use
        parent: a Qt parent object
        returns: folder path (may be empty if selection fails)
    """
    directory = QtWidgets.QFileDialog.getExistingDirectory(parent = parent, caption = defAct.tr("Directoy of the project"), directory = getRecentProjectsFolder(defAct))
    if len(directory) == 0:
        return ""
    if not dirIsProject(directory):
        answer = QtWidgets.QMessageBox.question(parent, defAct.tr("No Project"), defAct.tr("The selected folder does not seem to be a valid project. Load this dir anyway?"))
        if answer == QtWidgets.QMessageBox.No:
            return ""
    return directory

def getNewProjectDir(defAct, parent):
    """ Interactively select a potential new project directory
        defAct: DefaultActions to use
        parent: a Qt parent object
        returns: folder path (may be empty if selection fails)
    """

    # Select new project dir path
    newProjectDir, _ = QtWidgets.QFileDialog.getSaveFileName(parent = parent, caption = defAct.tr("New Project Directory"), directory = getRecentProjectsFolder(defAct))
    if len(newProjectDir) == 0:
        return ""

    name = os.path.basename(newProjectDir)

    # If name contains special characters
    regExpName = QRegExp("[A-Za-z0-9_()-][A-Za-z0-9_ #()-]*")
    if not regExpName.exactMatch(name):
        QtWidgets.QMessageBox.warning(parent, defAct.tr("Invalid character"),
                                      defAct.tr("Project name is invalid. You may only use letters, digits, whitespace and the following special characters: _ # ( ) -"))
        return ""

    # if the path already exists
    if os.path.exists(newProjectDir):
        QtWidgets.QMessageBox.warning(parent, defAct.tr("Already exists"),
                                      defAct.tr("Project with this name already exists"))
        return ""
    # if everything is alright
    return newProjectDir
