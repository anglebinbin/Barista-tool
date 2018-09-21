import os
import uuid

from PyQt5 import QtWidgets
from functools import partial

from PyQt5.QtCore import QUrl, QMetaObject, QDir, QSize
from PyQt5.QtCore import pyqtSlot as Slot
from PyQt5.QtGui import QDesktopServices

from gui.host_manager.remote_file_dialog import *
from gui.input_manager.database_object import *
from gui.manager_dialog import ManagerDialog
from gui.network_manager.layer_helper import *

from backend.barista.utils.logger import *
import backend.barista.utils.db_util as db_util
from backend.networking.net_util import sendMsgToHost
from backend.networking.protocol import Protocol
from gui.prototxt_editor.editor_widget import EditorWidget

from gui.gui_util import askFromList
from input_manager_dialogs import DatabaseCheckBoxDialog, AssignLayerCheckBoxDialog, TableEditor
from operator import itemgetter
from threading import Thread
from threading import Event

class InputManager(ManagerDialog):
    # DB Dict
    # databases = {id1 = {path = "..", "name="...", type=".."}, id2 =...}
    # dborder = [id1,id2,id3]

    def __init__(self, parent=None):
        ManagerDialog.__init__(self, parent)

        self.logid = Log.getCallerId("InputManager")

        # main_window title
        self.setWindowTitle("Input Manager")

        # add db button
        self._pb_add = QtWidgets.QPushButton("Add new Database")
        self._buttonlayout.addWidget(self._pb_add)

        # search and add button
        self._pb_searchadd = QtWidgets.QPushButton("Search and add new Databases")
        self._buttonlayout.addWidget(self._pb_searchadd)

        # hdf5txt file button
        self._pb_createtxt = QtWidgets.QPushButton("New HDF5TXT File")
        self._buttonlayout.addWidget(self._pb_createtxt)

        self._buttonlayout.addStretch()

        # type label
        self._type_label = QtWidgets.QLabel("Type:")
        self._buttonlayout.addWidget(self._type_label)

        # combobox for filters
        self._filterCombo = QtWidgets.QComboBox()
        types = ["ALL", "LMDB", "LEVELDB", "HDF5TXT"]
        self._filterCombo.addItems(types)
        self._filterCombo.currentIndexChanged.connect(self.onFilter)
        self._buttonlayout.addWidget(self._filterCombo)

        # listwidget with all dbs
        self._itemscroll = self.ScrollList()
        self._itemscroll.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        # layout settings

        self._itemscroll.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._layout.addWidget(self._itemscroll)
        self._itemscroll.dropped.connect(self.fileDropEvent)

        self.dbs = []
        self.disable = False

        self._pb_add.clicked.connect(self.opendb)
        self._pb_searchadd.clicked.connect(self.searchAddDB)
        self._pb_createtxt.clicked.connect(self.createTxt)

        self.currentWalkDirectory = ""
        # get all files with their type that lie under the top directory
        self.fileList = []

    def keyReleaseEvent(self, QKeyEvent):
        if QKeyEvent.key() == QtCore.Qt.Key_Delete:
            self.onKeyDelete()
        super(InputManager, self).keyReleaseEvent(QKeyEvent)

    """
    creates a new db entry for a selected database. this is handled differently depending on whether or not the db
    source is local or remote by calling 'opendbLocal' or 'opendbRemote'

    @author ..., j_stru18
    """
    def opendb(self):
        list = self.parent.hostManager.getActiveHostList()  # type: list
        if len(list) == 0:
            self.opendbLocal()
        else:
            list.insert(0, ["local", "Local Host"])
            ret = askFromList(self, list, "Select DB Source",
                          "You have configured remote Hosts.\nPlease select the Source of the Database.")
            if ret:
                if ret == "local":
                    self.opendbLocal()
                else:
                    self.opendbRemote(ret)

    """
    open a file dialog and create a new db entry with the resulting absolute path
    if the selected file is *.hd5 or *.hdf5 a new *.txt file will be created, which contains the path of the selected
    database file, because caffe expects a txt file

    @author ..., f_prob02, j_stru18, l_hu0002
    """
    def opendbLocal(self):
        projectPath = self.parent.actions.getProjectPath()
        if projectPath:
            ret = QtWidgets.QFileDialog.getOpenFileName(self, "Select a Database", QDir.homePath(),
                                                        "ALL (*.mdb CURRENT *.ldb *.txt *.h5 *.hdf5);;" + "LMDB (*.mdb);;" +
                                                        "LEVELDB (CURRENT *.ldb);;" +
                                                        "HDF5 (*.h5 *.hdf5);;" +
                                                        "HDF5TXT (*.txt)")
            # ret = [PATH, TYPE]
            if len(ret[0]) != 0:
                success = self.addDBbyPathLocal(ret[0], ret[1])
                if success:
                    self.updateListWidget()

    """
    does the same as opendbLocal but instead of the GUI File Dialog a RemoteFileDialog is used for the remote source
    additionally the db dict that is added contains information about the host and port of the remote source


    @author ..., f_prob02, j_stru18, l_hu0002
    @param id the id of the remote source that was selected
    """
    def opendbRemote(self, id):
        data = self.parent.hostManager.getHostDataById(id)
        if data:
            filter = "ALL (*.mdb CURRENT *.ldb *.hdf5 *.h5 *.txt);;LMDB (*.mdb);;LEVELDB (CURRENT *.ldb);;" \
                     "HDF5 (*.h5 *.hdf5);;HDF5TXT (*.txt)"
            rfd = RemoteFileDialog(data[0], data[1], "Select a Database", filter, parent=self)
            rfd.exec_()
            path = rfd.returnvalue
            if rfd.returnvalue is not "":
                if path and path != "":
                    success = self.addDBbyPathRemote(path, data[0], data[1])
                    if success:  # a new db was added
                        self.updateListWidget()

    def fileDropEvent(self, list):
        """called when an item is dragged and dropped onto the Input Manager List"""
        for path in list:
            if os.path.isdir(path):
                self.searchAddDB(path)
            elif os.path.isfile(path):
                path, ext = os.path.splitext(path)
                # make sure extension is valid, .ldb files need a CURRENT file
                if not ext in [".mdb", ".txt", ""]:
                    continue
                # make sure .mdb files are named data
                if ext == ".mdb" and os.path.basename(path) != "data":
                    continue
                # make sure if extension is empty the filename is CURRENT
                if ext == "" and os.path.basename(path) != "CURRENT":
                    continue
                # stick path and ext back together
                path = path+ext
                self.addDBbyPathLocal(path)
                self.updateListWidget()

    """
    Adds a db to the input manager's dict.
    Parses for the file's type. In case of a .h5 or .hdf5 file a new HDF5TXT is created.
    The db's files (in case of lmdb a single one and in case of leveldb and hdf5 multiple files) are hashed and used as
    ID to prevent duplicates.

    @author j_stru18
    @param path : the path to the db file
    @param typeString : if this method is called from openDBLocal, a typeString can be added as second parameter that
                        implies the dbs datatype
    @return : whether or not the adding to the db dict was successful
    """
    def addDBbyPathLocal(self, path, typeString=None):
        filename = os.path.basename(path)
        type = ""
        # parse for type
        if typeString is None or "ALL" in typeString:
            type = db_util.getType(filename)
        elif "LMDB" in typeString:
            type = 'LMDB'
        elif "LEVELDB" in typeString:
            type = "LEVELDB"
        elif "HDF5TXT" in typeString:
            type = "HDF5TXT"
        elif "HDF5" in typeString:
            type = "HDF5"

        newFileCreated = False
        if type == "HDF5":
            h5path = path
            index = filename.rfind(".", 0, len(filename))
            defaultName = filename[:index]
            filename = self._showLineDialog("Create new HDF5TXT", "Enter a name for the HDF5TXT file:",
                                            defaultName)
            if filename is "":  # Dialog was closed
                return False

            path = os.path.join(os.path.dirname(path), filename) + ".txt"
            if os.path.exists(path):
                Log.error("File already exists: " + path + ", can't create new HDF5TXT ", self.logid)
                QtWidgets.QMessageBox.critical(self, "Can't create new HDF5TXT",
                                               "File already exists:\n" + path)
                return False
            with open(path, 'w') as file:
                # add a new line to be sure
                file.write(h5path)
            type = "HDF5TXT"
            newFileCreated = True
        # trim path for folder based dbs
        if type == "LMDB" or type == "LEVELDB":
            path = os.path.dirname(path) + os.path.sep
        # create entry in db dict
        db = dict()
        db["name"] = type + " Database"
        db["path"] = path
        db["type"] = type
        addingSuccessful = self._addDB(db)
        if not addingSuccessful and newFileCreated:  # adding the hdf5txt wasn't successful: remove newly created file
            os.remove(path)
        self.parent.networkManager.setModifiedFlag()
        return addingSuccessful

    """
    Adds a db to the input manager's dict.
    Parses for the file's type. In case of a .h5 or .hdf5 file a new HDF5TXT is created.

    @author j_stru18
    @param path : the path to the db file
    @param host : the hostname of the remote db file
    @param port : the host's port
    @return : whether or not the adding to the db dict was successful
    """
    def addDBbyPathRemote(self, path, host, port):
        filename = os.path.basename(path)
        type = db_util.getType(filename)
        hdf5ID = None
        typeWasHDF5 = False
        if type == "HDF5":
            typeWasHDF5 = True
            type = "HDF5TXT"
            h5path = path
            index = filename.rfind(".", 0, len(filename))
            filename = filename[:index]
            filename = self._showLineDialog("Create new HDF5TXT", "Enter a name for the HDF5TXT file:",
                                            filename)
            if filename is "":  # Dialog was closed
                return False

            path = os.path.join(os.path.dirname(path), filename) + ".txt"
            # we hash the hdf5 file: if it already exists in the input manager, we don't have to create a new HDF5TXT
            msg = {"key": Protocol.GETHASH, "path": h5path, "type": "HDF5"}
            ret = sendMsgToHost(host, port, msg)
            if ret and ret["status"]:
                hashValue = ret["hashValue"]
                portHash = db_util.getStringHash(str(port))
                hdf5ID = str(hashValue ^ portHash)
                if not self.dbcontains(hdf5ID):
                    msg = {"key": Protocol.MAKEHDF5TXT, "path": path, "hdf5": h5path}
                    ret = sendMsgToHost(host, port, msg)
                    if not ret and not ret["status"]:
                        QtWidgets.QMessageBox.critical(self, "Can't create new HDF5TXT",
                                                        "Creation of File failed:\n"
                                                        + path)
                        Log.error("Creation of HDF5TXT " + path + " failed", self.logid)
                        return False
            else:
                Log.error("Remote host sent no message.", self.logid)

        if type == "LMDB" or type == "LEVELDB":
            path = os.path.dirname(path) + os.path.sep
        # create entry in db dict
        db = dict()
        db["name"] = type + " Database"
        db["path"] = path
        db["type"] = type
        db["isRemote"] = True
        db["host"] = host
        db["port"] = port
        if typeWasHDF5:
            addingSuccessful = self._addDBbyID(db, hdf5ID)
        else:
            addingSuccessful = self._addDB(db)
        self.parent.networkManager.setModifiedFlag()
        return addingSuccessful


    def searchAddDB(self, topdir=None):
        """ searches a given Folder """
        # if topdir is empty, the user has to select one, else topdir will be already given (e.g. drag and drop)
        if not topdir:
            # get Top directory and project path
            topdir = QtWidgets.QFileDialog.getExistingDirectory(self, "Select a Database Folder", QDir.homePath())
            if topdir == "": return  # user canceled

        #start database search in thread
        e = Event()
        cancel = Event()
        thread = Thread(target=self.searchDB, args=(e, cancel, topdir, ))

        #Messagebox contains information about current search and a cancel Button
        cancelButton = QtWidgets.QPushButton("Cancel", self)
        cancelButton.setText("Cancel")
        cancelButton.clicked.connect(partial(self.walkCanceled, cancel))

        msg = QtWidgets.QMessageBox(self)
        msg.setText("Current Directory:")
        msg.setInformativeText(self.currentWalkDirectory)
        msg.setWindowTitle("Searching for databases...")
        #add the cancel-Button with RejectRole = 1
        msg.addButton(cancelButton, 1)
        msg.setStyleSheet("QLabel{min-width: 700px; min-height: 50px}");
        QtCore.QCoreApplication.processEvents()
        msg.show()
        thread.start()

        #update the current os.walk directory in the messagebox
        while(thread.is_alive()):
            QtCore.QCoreApplication.processEvents()
            e.wait()
            msg.setInformativeText(self.currentWalkDirectory)
            e.clear()
        msg.close()
        self.addDBtoInputManager(topdir)
        #reset fileList to avoid multiple results of the same folders
        self.fileList = []

    def walkCanceled(self, cancel):
        """Set the Event to leave the current search for databases"""
        cancel.set()

    def searchDB(self, e, cancel, topdir=None):
        """Search for databases in given top directory. Execution as additional Thread"""
        for root, dirs, files in os.walk(topdir):
            for name in reversed(files):
                #if the search is not canceled, search for databases with os.walk
                if not cancel.isSet():
                    # parse for type
                    type = ""
                    # determine the type by analysing file Extensions
                    filePath, extension = os.path.splitext(os.path.join(root, name))
                    if extension == ".mdb":
                        type = "LMDB"
                    elif extension == ".txt":
                        type = "HDF5TXT"
                    elif extension == "":
                        if filePath[-7:] == "CURRENT":
                            type = "LEVELDB"

                    self.currentWalkDirectory = os.path.dirname(os.path.join(root, name))
                    e.set()

                    # if file has a valid type add it to the fileList
                    if len(type) > 0:
                        if type == "LMDB" and filePath[-4:] != "data":
                            pass  # if db is from type lmdb but not named "data"
                        else:
                            self.fileList.append({"filepath": filePath+extension, "type": type})

                #kill the current thread by leaving the function
                else:
                    cancel.clear()
                    return

    def addDBtoInputManager(self, topdir=None):
        if not self.fileList:
            QtWidgets.QMessageBox.warning(
                    self,
                    self.tr("Error: No database found"),
                    self.tr("Neither \"{}\" nor any subfolders contain valid Barista databases!".format(topdir))
                    )
            return

        # if there is just 1 item in the list (or the first item is a txt), skip the dialog
        if len(self.fileList) > 1 or self.fileList[0]["type"] == "HDF5TXT":
            # sort list by type
            self.fileList = sorted(self.fileList, key=itemgetter("type"), reverse=True)
            # call dialog
            dialog = DatabaseCheckBoxDialog(self.fileList, topdir)
            if dialog.exec_():  # checks if dialog was accepted ("ok pressed") or aborted ("cancel" pressed)
                self.fileList = dialog.getFileList()
            else:
                return  # if dialog was aborted, nothing needs to be imported

        # add files to input manager
        for file in self.fileList:
            if file["type"] == "LMDB" or file["type"] == "LEVELDB":
                file["filepath"] = os.path.dirname(file["filepath"]) + os.path.sep
            elif file["type"] == "HDF5TXT":
                file["filepath"] = file["filepath"]
            db = dict()
            db["name"] = file["type"] + " Database" if file["type"] != "HDF5TXT" else "HDF5 Database"
            db["path"] = file["filepath"]
            db["type"] = file["type"]
            self._addDB(db)
        self.updateListWidget()
        self.parent.networkManager.setModifiedFlag()

    """
    Create a new HDF5TXT file with the paths of one or more HDF5 files.

    Opens a TableEditor where you can add, remove and edit lines and also select HDF5 files with a file dialog. This new
    file can be saved, when you enter a name for it. When a file was created and its path exists, it is added to the
    input manager, which will also be updated.

    @author: j_schi48, j_stru18
    """
    def createTxt(self):
        self.editor = TableEditor()
        newPath = self.editor.path
        if newPath:
            addingSuccessful = self.addDBbyPathLocal(self.editor.path)  # create TXT is only implemented for local dbs
            if addingSuccessful:
                QtWidgets.QMessageBox.information(self, self.tr("File Saved"), self.tr("File saved at \"{}\"".format(newPath)))
                self.updateListWidget()

    def importdb(self, dict):
        '''receive a new db dict, clear the old and open all'''
        self.dict = None
        self._initDict()
        if len(dict) > 0:
            k = dict.keys()
            # for every entry
            # check consistency
            if "dborder" in k and "dblist" in k:
                for dbid in dict["dborder"]:
                    if dbid in dict["dblist"]:
                        self._addDBbyID(dict["dblist"][dbid], dbid)
                self.updateListWidget()
            else:
                Log.error("Invalid Data on Import", self.logid)

    def deletebyID(self, id):
        '''given an ID remove the entry from the db dict'''
        if id:
            if self.dbcontains(id):
                self.dict["dborder"].remove(id)  # this removes it from the order list
                del self.dict["dblist"][id]  # this removes it from the dict
                self.parent.networkManager.setModifiedFlag()  # notify change
            assert not self.dbcontains(id)

    def clearInputManager(self):
        '''clear the inputmanager on changing the project'''
        if self.dict is not None:
            self.dict = None
            self._initDict()
            self.updateListWidget()

    """
    add a new database to the dict. only for databases WITHOUT IDs
    in case of a local db the relevant files are hashed and the hash is used as ID, in case of remote dbs a unique id
    is generated

    @author j_stru18
    @param db a dictionary that holds the attributes of a database object
    @return whether or not the adding of the db was successful
    """
    def _addDB(self, db):
        if not self._locationIsImported(db):
            if "isRemote" in db and db["isRemote"]:
                return self._addDBRemote(db)
            else:
                return self._addDBLocal(db)
        else:
            if "isRemote" in db and db["isRemote"]:
                QtWidgets.QMessageBox.information(self, self.tr("Importing Failed"),
                                                self.tr("There is already a file imported from \n\"{0}\"\n"
                                                    " at the host: \n{1}".format(db["path"], db["host"])))
            else:
                QtWidgets.QMessageBox.information(self, self.tr("Importing Failed"),
                                                  self.tr("There is already a file imported from \n\"{}\"".format(db["path"])))
            return False

    """
    add this new database to the dict. only for databases WITHOUT IDs
    generates an ID of the database by hashing the file to ensure no database is added twice, unless it is a HDF5TXT
    without any valid paths. In this case, a new unique ID is generated. This prevents unwanted hash conflicts for these
    files.

    @author ..., f_prob02, j_stru18, l_hu0002
    @param db a dictionary that holds the attributes of a database object
    @return True if the adding was correct, False if the same database was already loaded or if the type, name or path
            was invalid
    """
    def _addDBLocal(self, db):
        isValidDB = False
        if db["path"] is not None:
            dbPaths = db_util.getDBPathsByType(db["path"], db["type"])
            hashValue = db_util.getMultipleHash(dbPaths)
            if hashValue == 0:
                hashValue = uuid.uuid4()
            id = str(hashValue)
            isValidDB = self._addDBbyID(db, id)
        return isValidDB

    """
    Generates an ID by hashing a remote database and the remote host's port, which is used to add the database to the
    input manager, unless it is a HDF5TXT without any valid paths. In this case, a new unique ID is generated and
    modified with the hash of the port. This prevents hash unwanted conflicts for these files.

    WARNING: until #401 is implemented, we have to hash the port of the remote host as well, to ensure that duplicate
    files on different hosts can be added. This has to be changed afterwards.

    @author: j_stru18
    @param db a dictionary that holds the attributes of a remote database object
    @return True if the adding was correct, False if the type, name or path was invalid
    @pre ensure that db is a db from remote host
    @pre ensure that db["path"] is absolute
    """
    def _addDBRemote(self, db):
        isValidDB = False
        if db["path"] is not None:
            msg = {"key": Protocol.GETHASH, "path": db["path"], "type": db["type"]}
            ret = sendMsgToHost(db["host"], db["port"], msg)
            if ret and ret["status"]:
                hashValue = ret["hashValue"]
                if hashValue == 0:
                    hashValue = uuid.uuid4().int
                portHash = db_util.getStringHash(str(db["port"]))
                id = str(hashValue ^ portHash)
                isValidDB = self._addDBbyID(db, id)
            else:
                Log.error("Remote host sent no message.", self.logid)
        return isValidDB



    """
    Adds a new database to the input manager's dict for a given ID. When the DB is already loaded, the user is warned.
    When the db dict isn't constructed in the right way and doesn't contain the right keys and doesn't have the right
    type or is already imported, this method returns false. Else, if the adding was successful, it returns false.

    @author : j_stru18
    @param db : a dict containing the information of a database file
    @id : the id of a database file as string
    @return : whether or not the adding to the db dict was successful or not
    """
    def _addDBbyID(self, db, id):
        self._initDict()
        addingSuccessful = False
        if self._dbCheck(db):
            if not self.dbcontains(id):
                if "isRemote" not in db:
                    db["isRemote"] = False
                self.dict["dborder"].append(id)
                self.dict["dblist"].update({id: db})
                addingSuccessful = True
            else:
                duplicatePath = self.getPathByID(id)
                QtWidgets.QMessageBox.critical(self, "Duplicate Error on Import!", "The selected file {0} was already "
                                                                    "imported:\n{1}".format(db["path"], duplicatePath))
                Log.error("Duplicate error on import.", self.logid)
            assert self.dbcontains(id)
        return addingSuccessful

    """
    returns the path of the saved db that is associated with the given ID

    @author j_stru18
    @param id a db's unique ID
    @return the file path of the database that is associated with this ID
    """
    def getPathByID(self, id):
        path = None
        self._initDict()
        if id in self.dict["dborder"]:
            path = self.dict["dblist"][id]["path"]
            type = self.dict["dblist"][id]["type"]
            if type == 'LMDB':
                path = os.path.join(path, "data.mdb")
            elif type == 'LEVELDB':
                path = os.path.join(path, "CURRENT")
            elif type == 'HDF5TXT':  # in case of HDF5TXT the path already contains the filename
                pass
        return path

    def dbcontains(self, id):
        '''check if an ID is already in the dict'''
        self._initDict()
        if id in self.dict["dborder"]:
            return True
        return False

    def _initDict(self):
        '''this creates an empty dict if there is none'''
        if self.dict is None:
            self.dict = dict()
            self.dict["dblist"] = dict()
            self.dict["dborder"] = list()

    """
    checks if a db dict is constructed in a valid way (contains keys for type, name and path and type is one of the
    three expected types

    @param db a dict containing the attributes of a database
    """
    def _dbCheck(self, db):
        validDB = True
        if "type" not in db.keys():
            Log.error("'type' not in Database key", self.logid)
            validDB = False
        elif "name" not in db.keys():
            Log.error("'name' not in Database key", self.logid)
            validDB = False
        elif "path" not in db.keys():
            Log.error("'path' not in Database key", self.logid)
            validDB = False
        elif db["type"] not in ["LMDB", "LEVELDB", "HDF5TXT"]:
            Log.error("Database of wrong type: " + db["type"], self.logid)
            validDB = False

        return validDB


    """
    Checks if there is already a db with the same location as the inout in the input managers dict of databases.

    For local dbs the path is compared only; for remote dbs the host and port are taken into consideration as well.
    @author: j_stru18
    @param: dbToCheck: a dict containing the attributes of a database
    @return: whether or not a database with the same location already exists in the input managers dict of databases
    """
    def _locationIsImported(self, dbToCheck):
        locationIsImported = False
        for id, dict in self.dict["dblist"].iteritems():
            if dict["path"] == dbToCheck["path"]:
                if "isRemote" in dbToCheck and dbToCheck["isRemote"]:
                    if dict["isRemote"]:
                        # both are remote and share the same path and host/port
                        if (dict["host"] == dbToCheck["host"]) and (dict["port"] == dbToCheck["port"]):
                           locationIsImported = True
                else:
                    if not dict["isRemote"]:  # both are local and share the same path
                        locationIsImported = True
        return locationIsImported

    def getDBDict(self):
        '''export the dict'''
        self._initDict()
        return self.dict

    def getLogID(self):
        '''return log id of input manager'''
        return self.logid

    def updateListWidget(self):
        '''remove all the widgets from the listwidget and create new. easiest way of updating the list widget'''
        self._itemscroll.clear()

        # for every db in dict
        for id in self.dict["dborder"]:
            db = self.dict["dblist"][id]
            # create a new widget and give it all necessary info
            dbwidget = self.DatabaseWidget(db["type"], self)
            dbwidget.setId(id)
            dbwidget.setPath(db["path"])
            dbwidget.setName(db["name"])
            dbwidget.showUsage(self.parent.networkManager.network)
            dbwidget.disableEditing(self.disable)
            if db["isRemote"]:
                dbwidget.setRemote(db["host"], db["port"])
            dbwidget.open()

            # create a new listwidget item and give it all necessary info
            item = QtWidgets.QListWidgetItem(self._itemscroll)
            item.setData(Qt.UserRole, id)
            item.setData(255, db["type"])
            item.setSizeHint(dbwidget.sizeHint())

            # add the item and set the widget
            self._itemscroll.addItem(item)
            self._itemscroll.setItemWidget(item, dbwidget)
            self.onFilter()

    def onFilter(self):
        '''apply the filter to all items by hiding and unhiding'''
        type = self._filterCombo.currentText()
        for index in range(0, self._itemscroll.count()):
            item = self._itemscroll.item(index)
            if item.data(255) == type or type == "ALL":
                item.setHidden(False)
            else:
                item.setHidden(True)

    def onButtonDelete(self, id = None):
        '''delete db by id and update ListWidget'''
        ret = QtWidgets.QMessageBox.question(self, "Remove selected Database",
                                             "Do you really want to remove this database?",
                                             QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.No)
        if ret == QtWidgets.QMessageBox.Ok:
            if not id is None:
                self.deletebyID(id)
                self.updateListWidget()

    def onKeyDelete(self):
        selection = self._itemscroll.selectedItems()
        count = len(selection)
        if count > 0:
            gramNum = ""
            thisThese = "this"
            if len(selection) > 1:
                gramNum = "s"
                thisThese = "these"
            ret = QtWidgets.QMessageBox.question(self, "Remove {0} selected Database{1}".format(str(count), gramNum),
                                            "Do you really want to remove {0} database{1}?".format(thisThese, gramNum),
                                            QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.No)
            if ret == QtWidgets.QMessageBox.Ok:
                for item in selection:
                    self.deletebyID(item.data(Qt.UserRole))
                self.updateListWidget()


    def setName(self, id, name):
        '''change the name to a db'''
        self.dict["dblist"][id]["name"] = name
        self.parent.networkManager.setModifiedFlag()
        self._updateSizeHint()

    @Slot()
    def _updateSizeHint(self):
        '''update the size of a widget inside the listwidget'''
        for index in range(0, self._itemscroll.count()):
            item = self._itemscroll.item(index)
            widget = self._itemscroll.itemWidget(item)
            item.setSizeHint(widget.sizeHint())
        self._itemscroll.update()

    def _getIndexinList(self, id):
        '''given an id what is the index of the item in the listwidget'''
        for index in range(0, self._itemscroll.count()):
            item = self._itemscroll.item(index)
            if item.data(Qt.UserRole) == id:
                return index
        return -1

    def createWidget(self, id):
        # ... but you can't move the widget. you need to create the widget anew
        dbwidget = self.DatabaseWidget(self.dict["dblist"][id]["type"], self)
        dbwidget.setId(id)
        dbwidget.setPath(self.dict["dblist"][id]["path"])
        dbwidget.setName(self.dict["dblist"][id]["name"])
        if self.dict["dblist"][id]["isRemote"]:
            dbwidget.setRemote(self.dict["dblist"][id]["host"], self.dict["dblist"][id]["port"])
        dbwidget.open()
        return dbwidget

    def updateAfterMovement(self):
        self.parent.networkManager.setModifiedFlag()
        # update list widget
        self.updateListWidget()

    def assignToLayer(self, id):
        '''assign and unassign selected layers to the db given by id'''
        # TODO: instead of setting the abs-path modify this in the future to allow:
        # - use relative paths for the dbs in the dict
        # - assign a reference to the layer to get the path at runtime from the input manager

        # get type and path
        type = self.dict["dblist"][id]["type"]
        path = self.dict["dblist"][id]["path"]

        # define corresponding layertypes
        layertypes = []
        if type == "LMDB" or type == "LEVELDB":
            layertypes = ["Data"]
        if type == "HDF5TXT":
            layertypes = ["HDF5Data"]

        # get the layers
        network = self.parent.networkManager.network
        mylayer = LayerHelper.getLayersInfo(layertypes, network, path)

        if len(mylayer) == 0:
            # no layer of this type
            QtWidgets.QMessageBox.warning(self, type, "There is no layer of this type.")
            return

        # get the selected layers
        dialog = AssignLayerCheckBoxDialog(mylayer)
        if dialog.exec_():
            sel = dialog.getSelectedLayersList()
        else:
            return

        # set/remove the path
        for layerid, layername, assigned in sel:
            if assigned:
                LayerHelper.setPathforType(layerid, path, type, network)
            elif not [layerid, layername, assigned] in mylayer:
                LayerHelper.setPathforType(layerid, "", type, network)

        # update list widget
        self.updateListWidget()


    def _showLineDialog(self, title, text, default=""):
        '''display a simple dialog asking for a line input'''
        # create a dialog
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(title)
        # layouts and widgets
        layout = QtWidgets.QVBoxLayout(dialog)
        label = QtWidgets.QLabel(text)
        layout.addWidget(label)
        line = QtWidgets.QLineEdit(default)
        layout.addWidget(line)
        button = QtWidgets.QPushButton("Ok")
        layout.addWidget(button)
        button.clicked.connect(lambda: dialog.accept())
        # exec and get the line content
        isAccepted = dialog.exec_()
        if isAccepted == QDialog.Accepted:
            return line.text()
        else:
            return ""

    def disableEditing(self, disable):
        """ Set attribute disable """
        self.disable = disable

    class DatabaseWidget(QtWidgets.QWidget):
        '''a widget to display a db in the listwidget'''

        def __init__(self, type, manager, parent=None):
            QtWidgets.QWidget.__init__(self, parent)

            self.db = None
            self.id = None
            self.isRemote = False
            self.remoteHost = None
            # remember the manager
            self.manager = manager
            # add layouts
            self.layout = QtWidgets.QVBoxLayout(self)
            self.hbox1 = QtWidgets.QHBoxLayout()
            self.hbox1.setAlignment(Qt.AlignLeft)
            self.hbox2 = QtWidgets.QHBoxLayout()
            self.hbox2.setAlignment(Qt.AlignLeft)
            self.hbox3 = QtWidgets.QHBoxLayout()
            self.hbox3.setAlignment(Qt.AlignLeft)
            self.hbox4 = QtWidgets.QHBoxLayout()
            self.hbox4.setAlignment(Qt.AlignLeft)
            # add labels
            self.lbl_remote = QtWidgets.QLabel()
            self.lbl_path = QtWidgets.QLabel("path")
            self.hbox3.addWidget(self.lbl_remote)
            self.hbox3.addWidget(self.lbl_path)
            self.layout.addLayout(self.hbox1)
            self.layout.addLayout(self.hbox2)
            self.layout.addLayout(self.hbox3)
            self.layout.addLayout(self.hbox4)

            # type label
            self.lbl_type = QtWidgets.QLabel(type)
            self.lbl_type.setObjectName("databaseType")
            # Overwrite the type color by appending them to the current stylesheet.
            self.lbl_type.setStyleSheet(
                self.lbl_type.styleSheet() + " QLabel { background-color: "+self._typeColor(type)+" }")
            self.lbl_type.setFixedWidth(100)
            self.hbox1.addWidget(self.lbl_type)

            # status label
            self.lbl_status = QtWidgets.QLabel("stat")
            self.lbl_status.setObjectName("databaseStatus")
            self.lbl_status.setFixedWidth(45)
            self.hbox1.addWidget(self.lbl_status)
            self._updateStatus(False)

            # name label
            self.lbl_name = QtWidgets.QLabel("name")
            font = self.lbl_name.font()
            font.setBold(True)
            self.lbl_name.setFont(font)
            self.hbox1.addWidget(self.lbl_name)

            # create all resources
            ico_rename = QIcon("resources/pencil.png")

            pix_loc = QtWidgets.qApp.style().standardPixmap(QtWidgets.QStyle.SP_DialogOpenButton)
            ico_loc = QIcon(pix_loc)

            pix_reload = QtWidgets.qApp.style().standardPixmap(QtWidgets.QStyle.SP_BrowserReload)
            ico_reload = QIcon(pix_reload)

            pix_up = QtWidgets.qApp.style().standardPixmap(QtWidgets.QStyle.SP_ArrowUp)
            ico_up = QIcon(pix_up)

            pix_down = QtWidgets.qApp.style().standardPixmap(QtWidgets.QStyle.SP_ArrowDown)
            ico_down = QIcon(pix_down)

            pix_assign = QtWidgets.qApp.style().standardPixmap(QtWidgets.QStyle.SP_CommandLink)
            ico_assign = QIcon(pix_assign)

            ico_remove = QIcon('resources/trash.png')

            # make all buttons
            self.pb_rename = QtWidgets.QPushButton(ico_rename, "")
            self.pb_rename.setFixedSize(30, 30)
            self.pb_rename.setToolTip("Rename")
            self.hbox2.addWidget(self.pb_rename)

            self.pb_remove = QtWidgets.QPushButton(ico_remove, "")
            self.pb_remove.setFixedSize(30, 30)
            self.pb_remove.setToolTip("Remove")
            self.hbox2.addWidget(self.pb_remove)

            self.pb_loc = QtWidgets.QPushButton(ico_loc, "")
            self.pb_loc.setFixedSize(30, 30)
            self.pb_loc.setToolTip("Change Location")
            self.hbox2.addWidget(self.pb_loc)

            self.pb_reload = QtWidgets.QPushButton(ico_reload, "")
            self.pb_reload.setFixedSize(30, 30)
            self.pb_reload.setToolTip("Reload")
            self.hbox2.addWidget(self.pb_reload)

            self.pb_up = QtWidgets.QPushButton(ico_up, "")
            self.pb_up.setFixedSize(30, 30)
            self.pb_up.setToolTip("Move Up")
            self.hbox2.addWidget(self.pb_up)

            self.pb_down = QtWidgets.QPushButton(ico_down, "")
            self.pb_down.setFixedSize(30, 30)
            self.pb_down.setToolTip("Move Down")
            self.hbox2.addWidget(self.pb_down)

            # some special buttons for HDF5TXT
            if type == "HDF5TXT":
                pix_edit = QtWidgets.qApp.style().standardPixmap(QtWidgets.QStyle.SP_FileDialogContentsView)
                ico_edit = QIcon(pix_edit)

                self.pb_edit = QtWidgets.QPushButton(ico_edit, "")
                self.pb_edit.setFixedSize(30, 30)
                self.pb_edit.setToolTip("Edit Textfile")
                self.hbox2.addWidget(self.pb_edit)

                # self.pb_open.clicked.connect(lambda: self._openFile(), Qt.QueuedConnection)
                self.pb_edit.clicked.connect(lambda: (self.onEditPressed(), Qt.QueuedConnection))

                pix_add = QtWidgets.qApp.style().standardPixmap(QtWidgets.QStyle.SP_FileDialogNewFolder)
                ico_add = QIcon(pix_add)

                self.pb_add = QtWidgets.QPushButton(ico_add, "")
                self.pb_add.setFixedSize(30, 30)
                self.pb_add.setToolTip("Add single Hdf5 File")
                self.hbox2.addWidget(self.pb_add)

                self.pb_add.clicked.connect(lambda: self._addHdf5(), Qt.QueuedConnection)

            self.pb_assign = QtWidgets.QPushButton(ico_assign, "")
            self.pb_assign.setFixedSize(30, 30)
            self.pb_assign.setToolTip("Assign to Layer")
            self.hbox2.addWidget(self.pb_assign)

            # usage label
            self.lbl_usage = QtWidgets.QLabel("no layer assigned")
            font = self.lbl_usage.font()
            font.setItalic(True)
            self.lbl_usage.setFont(font)
            self.hbox2.addWidget(self.lbl_usage)

            # number of elements in the db
            self.lbl_count = QtWidgets.QLabel("None")
            self.lbl_count.setObjectName("databaseLabel")
            self.hbox4.addWidget(self.lbl_count)
            self.lbl_count.setMinimumWidth(200)
            self.lbl_count.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
            self.lbl_count.setAlignment(Qt.AlignTop)

            # dimensions of elements in the db
            self.lbl_dim = QtWidgets.QLabel("None")
            self.lbl_dim.setObjectName("databaseLabel")
            self.hbox4.addWidget(self.lbl_dim)
            self.lbl_dim.setMinimumWidth(200)
            self.lbl_dim.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
            self.lbl_dim.setAlignment(Qt.AlignTop)

            # connect the buttons
            self.pb_rename.clicked.connect(self.onRename, Qt.QueuedConnection)
            self.pb_loc.clicked.connect(self.changeLocation, Qt.QueuedConnection)
            self.pb_reload.clicked.connect(self.reload, Qt.QueuedConnection)
            self.pb_up.clicked.connect(lambda: self.manager.moveUp("dborder", self.id), Qt.QueuedConnection)
            self.pb_down.clicked.connect(lambda: self.manager.moveDown("dborder", self.id), Qt.QueuedConnection)
            self.pb_assign.clicked.connect(lambda: self.manager.assignToLayer(self.id), Qt.QueuedConnection)
            self.pb_remove.clicked.connect(lambda: self.manager.onButtonDelete(self.id), Qt.QueuedConnection)

        def getPath(self):
            '''return the path of this db'''
            return self.lbl_path.text()

        def setPath(self, path):
            '''set the path of this db'''
            self.lbl_path.setText(path)

        def getType(self):
            '''get the type of this db'''
            return self.lbl_type.text()

        def setName(self, name):
            '''set the name of this db'''
            self.lbl_name.setText(name)

        def setUsage(self, usage):
            '''set the usage of this db'''
            self.lbl_usage.setText(usage)

        def setId(self, id):
            '''set the id of this db'''
            self.id = id

        def setRemote(self, host, port):
            '''set this as remote'''
            self.isRemote = True
            self.remoteHost = [host, port]
            self.lbl_remote.setText(host + ":" + str(port))

        def showUsage(self, network):
            """ Display assignment of db to layers
            """
            # define corresponding layertypes
            layertypes = []
            if self.getType() == "LMDB" or self.getType() == "LEVELDB":
                layertypes = ["Data"]
            if self.getType() == "HDF5TXT":
                layertypes = ["HDF5Data"]

            # get the layers
            mylayer = LayerHelper.getLayersInfo(layertypes, network, self.getPath())

            usedBy = ""
            for _, layername, assigned in mylayer:
                if assigned:
                    usedBy += layername + ", "
            if usedBy is "":
                self.setUsage("no layer assigned")
            else:
                self.setUsage(usedBy[:-2])


        def changeLocation(self):
            type = self.getType()
            if type == "LMDB":
                filter = "LMDB (*.mdb)"
            elif type == "LEVELDB":
                filter = "LEVELDB (CURRENT *.ldb)"
            elif type == "HDF5TXT":
                filter = "HDF5TXT (*.txt)"
            else:
                filter = "ALL"

            path = QtWidgets.QFileDialog.getOpenFileName(self, "Select the new location", QDir.homePath(), filter)[0]
            if len(path) == 0:
                return
            if type == "LMDB" or type == "LEVELDB":
                path = os.path.dirname(path) + os.path.sep
            self.manager.dict["dblist"][self.id]["path"] = path
            self.dbo.setDB(path, type)
            self.manager.updateListWidget()

        """
        Reload this database widget by opening it again and in case of a HDF5TXT rehashing it. If the file was
        changed outside of Barista, a warning is shown.

        @author: j_stru18
        """
        def reload(self):
            self.open()
            type = self.getType()
            path = self.getPath()
            if type == "HDF5TXT":
                if not self.isRemote:
                    dbpaths = db_util.getHdf5List(path)
                    hashValue = db_util.getMultipleHash(dbpaths)
                    hashedID = str(hashValue)
                else:
                    hostName = self.remoteHost[0]
                    port = self.remoteHost[1]
                    hashMsg = {"key": Protocol.GETHASH, "path": self.getPath(), "type": "HDF5TXT"}
                    hashRet = sendMsgToHost(hostName, port, hashMsg)
                    if hashRet["status"]:
                        hashValue = hashRet["hashValue"]
                        portHash = db_util.getStringHash(str(port))
                        if hashValue != 0:  # file contained paths to HDF5 files
                            hashedID = str(hashValue ^ portHash)
                        else:
                            return
                    else:
                        Log.log("Reloading of database {} on remote host failed.".format(self.id),
                                self.manager.getLogID)
                        QtWidgets.QMessageBox.warning(self, "Reloading Failed", "Reloading of database on remote host"
                                                                                " failed.")
                        return

                if hashedID != self.id:  # file was changed outside of Barista
                    QtWidgets.QMessageBox.warning(self, "File was Changed", "This HDF5TXT file's paths were changed "
                                                                            "outside of Barista - check for duplicate "
                                                                            "files may fail.")

        def open(self):
            '''try to open this db and fill all the label based on whether or not it is local or remote'''
            if not self.isRemote:
                self.openLocal()
            else:
                self.openRemote()

        def openLocal(self):
            '''try to open this db and fill all the labels with information'''

            projectPath = self.manager.parent.actions.getProjectPath()
            if projectPath:
                # create a DatabaseObject and open it from path
                self.dbo = DatabaseObject()
                path = os.path.join(projectPath, self.getPath())
                self.dbo.setDB(path, self.getType())
                if self.getType() == "HDF5TXT":
                    self.dbo.setProjectPath(projectPath)
                self.dbo.open()
                # if DBO is open:
                status = self.dbo.isOpen()
                self._updateStatus(status)
                if status:
                    # get the element count
                    count = self.dbo.getDataCount()
                    self.lbl_count.setText(self._convertDatacount(count))

                    # get the element dim
                    dim = self.dbo.getDimensions()
                    self.lbl_dim.setText(self._convertDimensions(dim))
                else:
                    self.lbl_count.setText("None")
                    self.lbl_dim.setText("None")

                # close the DBO
                self.dbo.close()

                # call the manager to update the size hints
                # use this threadsave methode to enable updates of the GUI
                QMetaObject.invokeMethod(self.manager, "_updateSizeHint", Qt.QueuedConnection)

            else:
                Log.error("No project set, can't build rel. paths", self.manager.getLogID())

        def openRemote(self):
            ''' try to open this db on a remote host and fill all the label with information'''
            msg = {"key": Protocol.GETDBSTATUS, "type": self.getType(), "path": self.getPath()}
            ret = sendMsgToHost(self.remoteHost[0], self.remoteHost[1], msg)
            if ret and ret["status"]:   # getting db status was successful
                self._updateStatus(True)
                # get the element count
                count = ret["dataCount"]
                self.lbl_count.setText(self._convertDatacount(count))
                # get the element dim
                dim = ret["dimensions"]
                self.lbl_dim.setText(self._convertDimensions(dim))
            else:                       # getting db status was not successful
                self._updateStatus(False)
                self.lbl_count.setText("None")
                self.lbl_dim.setText("None")
            QMetaObject.invokeMethod(self.manager, "_updateSizeHint", Qt.QueuedConnection)

        """
        Opens a view of the current HDF5TXT that can be edited.

        In case of a local database, a TableEditor is shown where all lines are marked as either dead or alive paths and
        where these lines can be added, removed or altered.
        In case of a remote database, the text file is simply opened in a file dialog and can be changed and saved.

        @TODO: implement the behavior with the TableEditor for remote files as well (Task #2 of #449)

        @author: j_schi48, j_stru18
        @ensure: the type is HDF5TXT
        """
        def onEditPressed(self):
            if not self.isRemote:
                self._editLocal()
            else:
                self._editRemote()
            self.open()

        """
        Method for editing local HDF5TXT files.

        The user can edit the file using a TableEditor. If the file was changed and is no duplicate of a file, that is
        already imported, the entry with the old hashed ID is deleted and it is added with the new ID. If changes were
        made and the modified file is a duplicate, then the user has the choice of either discarding all changes or
        replacing the old duplicate with the modified file.

        @author: j_stru18
        @ensure: the database of this DatabaseWidget is remote
        """
        def _editLocal(self):
            path = self.getPath()
            allLines = db_util.getLinesAsList(path)
            h5paths = db_util.getHdf5List(path)
            if len(h5paths) != 0:
                oldHash = db_util.getMultipleHash(h5paths)
                oldID = str(oldHash)
            else:
                oldID = self.id
            self.editor = TableEditor(self.getPath())  # actual editing is done here
            newh5paths = db_util.getHdf5List(path)
            if len(newh5paths) != 0:  # modified file is not empty
                newHash = db_util.getMultipleHash(newh5paths)
                newID = str(newHash)
            else:
                if len(h5paths) != 0:  # file wasn't empty, but it is now
                    newID = str(uuid.uuid4())
                else:
                    newID = self.id
            isFileDuplicate = self.manager.dbcontains(newID)  # does a db with the same id exist?
            if newID != oldID:
                if isFileDuplicate:  # new file is identical to another imported file
                    duplicatePath = self.manager.getPathByID(newID)
                    ret = QtWidgets.QMessageBox.question(self, "HDF5TXT with same Files Found",
                        "Another file with the same ID was found: \n{}\n Do you want to keep the changed "
                        "HDF5TXT and remove the old duplicate from Barista?".format(duplicatePath),
                    QtWidgets.QMessageBox.Apply, QtWidgets.QMessageBox.Discard)
                    if ret == QtWidgets.QMessageBox.Apply:  # remove both old databases and add modified new one
                        self.manager.deletebyID(newID)
                        self.manager.deletebyID(oldID)
                        self.manager.addDBbyPathLocal(path)
                        assert self.manager.dbcontains(newID)
                        Log.log("Old HDF5TXT was removed and current file was modified.",
                            self.manager.getLogID())
                        self.manager.updateListWidget()
                    else:  # discard changes, old status is restored
                        with open(path, 'w') as file:
                            for line in allLines:
                                file.write(line)
                        Log.log("No changes to HDF5TXT files were made.", self.manager.getLogID())
                else:  # file changed, but is unique
                    self.manager.deletebyID(oldID)
                    self.manager.addDBbyPathLocal(path)

        """
        Method for editing files on remote hosts.

        The user can edit the file using a file dialog. If the file was changed and is no duplicate of a file, that is
        already imported, the entry with the old hashed ID is deleted and it is added with the new ID. If changes were
        made and the modified file is a duplicate, then the user has the choice of either discarding all changes or
        replacing the old duplicate with the modified file.

        WARNING: until #401 is implemented, we have to hash the port of the remote host as well, to ensure that
        duplicate files on different hosts can be added. This has to be changed afterwards.

        TODO: when #449 was fully implemented with a TableEditor for remote files, this method has to be updated.

        @author: j_stru18
        @ensure: the database of this DatabaseWidget is remote
        """
        def _editRemote(self):
            hostName = self.remoteHost[0]
            port = self.remoteHost[1]
            path = self.getPath()
            hashMsg = {"key": Protocol.GETHASH, "path": path, "type": "HDF5TXT"}
            oldHashRet = sendMsgToHost(hostName, port, hashMsg)
            fileContentMsg = {"key": Protocol.GETFILECONTENT, "path": path}
            fileContent = sendMsgToHost(hostName, port, fileContentMsg)

            if not oldHashRet["status"]:
                Log.error("Hashing of old HDF5TXT not successful.", self.manager.getLogID())
                return

            if not fileContent["status"]:
                Log.error("Getting file content from host was not successful.", self.manager.getLogID())
                return

            oldHashValue = oldHashRet["hashValue"]
            portHash = db_util.getStringHash(str(port))
            if oldHashValue == 0:  # file contained no paths to HDF5 files
                oldID = self.id
            else:
                oldID = str(oldHashValue ^ portHash)

            self._openFileRemote()  # actual file editing
            newHashRet = sendMsgToHost(hostName, port, hashMsg)   # hash file again for new ID
            newHashValue = newHashRet["hashValue"]
            if newHashValue != 0:  # modified file is not empty
                newID = str(newHashValue ^ portHash)
            else:
                if oldHashValue != 0:  # file wasn't empty, but is now
                    newID = str(uuid.uuid4())
                else:
                    newID = self.id
            isFileDuplicate = self.manager.dbcontains(newID)  # does a db with the same id exist?
            if newID != oldID:
                if isFileDuplicate:  # new file is identical to another imported file
                    duplicatePath = self.manager.getPathByID(newID)
                    ret = QtWidgets.QMessageBox.question(self, "HDF5TXT with same Files Found",
                        "Another file with the same ID was found: \n{}\n Do you want to keep the changed "
                        "HDF5TXT and remove the old duplicate from Barista?".format(duplicatePath),
                    QtWidgets.QMessageBox.Apply, QtWidgets.QMessageBox.Discard)
                    if ret == QtWidgets.QMessageBox.Apply:  # remove both old databases and add modified new one
                        self.manager.deletebyID(newID)
                        self.manager.deletebyID(oldID)
                        self.manager.addDBbyPathRemote(path, hostName, port)
                        assert self.manager.dbcontains(newID)
                        Log.log("Old HDF5TXT was removed and current file was modified.",
                            self.manager.getLogID())
                        self.manager.updateListWidget()
                    else:  # discard changes, old status is restored
                        self._editorSave(fileContent["file"])
                        Log.log("No changes to HDF5TXT files were made.", self.manager.getLogID())
                else:  # file changed, but is unique
                    self.manager.deletebyID(oldID)
                    self.manager.addDBbyPathRemote(path, hostName, port)


        def onRename(self):
            '''ask for a new name and set it'''
            name = self.manager._showLineDialog("Rename", "Enter a new name:", self.lbl_name.text())
            self.setName(name)
            self.manager.setName(self.id, name)

        def _convertDatacount(self, count):
            strcount = "Number of Elements:"
            if count:
                for key in sorted(count.keys()):
                    strcount += "\n" + key + ":"
                    strcount += "\n\t" + str(count[key])
            else:
                strcount += "\nNone"
            return strcount

        def _convertDimensions(self, dim):
            strdim = "Dimensions:"
            if dim:
                for key in sorted(dim.keys()):
                    strdim += "\n" + key + ":"
                    l = dim[key]
                    if len(l) == 0:
                        strdim += "\n\tscalar"
                    else:
                        # reformat
                        strdim += "\n" + str(len(l)) + ":\t"
                        for i in range(0, len(l)):
                            strdim += str(l[i])
                            if i < len(l) - 1:
                                strdim += " x "
            else:
                strdim += "\nNone"
            return strdim

        def _updateStatus(self, status):
            '''update the status label'''
            if status:
                self.lbl_status.setText("alive")
            else:
                self.lbl_status.setText("dead")

            # Overwrite the status colors by appending them to the current stylesheet.
            self.lbl_status.setStyleSheet(
                self.lbl_status.styleSheet() + "QLabel {"+self._statusColor(status)+"}"
            )

        def _typeColor(self, type):
            '''define the colors for every type as strings'''
            if type == "LMDB":
                return "#FFBF00"
            if type == "LEVELDB":
                return "#FF8000"
            if type == "HDF5TXT":
                return "#2EFEF7"
            return "#eeeeee"

        def _statusColor(self, status):
            '''set the color for the status'''
            if status:
                return """background-color: #00EE00;color:#000000;"""
            return """background-color:#EE0000;color:#EEEEEE;"""

        def _openFile(self):
            if self.isRemote:
                self._openFileRemote()
            else:
                self._openFileLocal()

        def _openFileLocal(self):
            '''open the file of HDF5TXT in a system prototxt_editor'''
            if self.getType() == "HDF5TXT":
                projectPath = self.manager.parent.actions.getProjectPath()
                if projectPath:
                    path = os.path.join(projectPath, self.getPath())
                    if os.path.exists(path):
                        url = QUrl(path, QUrl.TolerantMode)
                        QDesktopServices.openUrl(url)
                    else:
                        Log.error("File not found: " + path, self.manager.getLogID())
                        QtWidgets.QMessageBox.critical(self, "File not Found!", "File not Found at:\n" + path)
                        self.open()

        def _openFileRemote(self):
            msg = {"key": Protocol.GETFILECONTENT, "path": self.getPath()}
            ret = sendMsgToHost(self.remoteHost[0], self.remoteHost[1], msg)

            if ret["status"]:
                self.editor = EditorWidget(False, self.manager)
                self.editor.setText(ret["file"])
                self.editor.setWindowTitle(self.getPath())
                self.editor.sgSave.connect(self._editorSave)
                self.editor.sgClose.connect(self._editorClose)
                self.editor.exec_()
            else:
                QtWidgets.QMessageBox.critical(self, "Open File", "Failed to open remote file:\n" + self.getPath())

        def _editorClose(self):
            self.editor.sgSave.disconnect(self._editorSave)
            self.editor.sgClose.disconnect(self._editorClose)
            self.editor.deleteLater()
            self.editor = None

        def _editorSave(self, text):
            msg = {"key": Protocol.WRITEFILECONTENT, "path": self.getPath(), "file": text}
            ret = sendMsgToHost(self.remoteHost[0], self.remoteHost[1], msg)
            if ret["status"]:
                return
            QtWidgets.QMessageBox.critical(self, "Write File", "Failed to write remote file:\n" + self.getPath())

        """
        adds a new .h5 or .hdf5 file to an existing HDF5TXT file
        in case of a local db, the file or files are hashed and it is checked if the resulting HDF5TXT already exists

        TODO: remove this method, when #449 was fully implemented with a TableEditor for remote files

        @author j_stru18
        """
        def _addHdf5(self):
            if self.isRemote:
                self._addHdf5Remote()
            else:
                self._addHdf5Local()


        """
        Adds a new HDF5 File to the local HDF5TXT file:
        After selecting one or more files , it checks whether or not there is another imported db that contains paths
        to the same file as the selected HDF5TXT with the newly selected paths would. If the modified file would be no
        duplicate, it is deleted under its old ID and added again with its new one.
        If it is a duplicate, the user is asked whether to keep the changes and remove the old file or discard them and
        modify none of them. When changes were made to either one of the files, the Widgets of the input manager are
        reloaded.

        TODO: remove this method, when #449 is fully implemented with a TableEditor for remote files

        @author j_stru18
        """
        def _addHdf5Local(self):
            if self.getType() != "HDF5TXT":  # guard statement for wrong db type
                Log.error("No HDF5TXT file was selected.", self.manager.getLogID())
                return

            ret = QtWidgets.QFileDialog.getOpenFileNames(self, "Select a HDF5 Database", QDir.homePath(),
                                                         "HDF5 (*.hdf5 *.h5)")
            path = self.getPath()
            newh5paths = ret[0]

            if len(newh5paths) == 0:  # guard statement for empty selection
                Log.error("File not found: " + path, self.manager.getLogID())
                QtWidgets.QMessageBox.critical(self, "File not Found!", "File not Found at:\n" + path)
                return

            if os.path.exists(path):  # there are selected files and the HDF5TXT exists
                h5paths = db_util.getHdf5List(path)
                newHash = db_util.getMultipleHash(newh5paths)
                if not h5paths:  # file contains no valid paths
                    oldID = self.id
                else:
                    oldHash = db_util.getMultipleHash(h5paths)
                    newHash += oldHash
                    oldID = str(oldHash)
                newID = str(newHash)
                isFileDuplicate = self.manager.dbcontains(newID)  # does a db with the same id exist?
                updateNeeded = False
                if not isFileDuplicate:
                    with open(path, 'a+') as file:
                        for newh5path in newh5paths:  # add paths to HDF5TXT
                            file.write("\n" + newh5path)
                    self.manager.deletebyID(oldID)
                    self.manager.addDBbyPathLocal(path)
                    assert self.manager.dbcontains(newID)
                    updateNeeded = True  # db entries were changed and the inputs need to be updated
                else:
                    duplicatePath = self.manager.getPathByID(newID)
                    ret = QtWidgets.QMessageBox.question(self, "HDF5TXT with same Files Found",
                        "Another file with the same ID was found: \n{}\n Do you want to keep the changed "
                        "HDF5TXT and remove the old duplicate from Barista?".format(duplicatePath),
                        QtWidgets.QMessageBox.Apply, QtWidgets.QMessageBox.Discard)
                    if ret == QtWidgets.QMessageBox.Apply:  # remove both old databases and add modified new one
                        with open(path, 'a+') as file:
                            for newh5path in newh5paths:  # add paths to HDF5TXT
                                file.write("\n" + newh5path)
                        self.manager.deletebyID(newID)
                        self.manager.deletebyID(oldID)
                        self.manager.addDBbyPathLocal(path)
                        assert self.manager.dbcontains(newID)
                        updateNeeded = True  # db entries were changed and the inputs need to be updated
                        Log.log("Old HDF5TXT was removed and current file was modified.",
                                self.manager.getLogID())
                    else:  # discard changes
                        Log.log("No changes to HDF5TXT files were made.", self.manager.getLogID())
                if updateNeeded:
                    self.manager.updateListWidget()

        """
        Adds a new HDF5 File to the local HDF5TXT file:
        After selecting a .h5 or .hdf5 file , it checks whether or not there is another imported db that contains paths
        to the same file as the selected HDF5TXT with the newly selected path would. If the modified file would be no
        duplicate, it is deleted under its old ID and added again with its new one.
        If it is a duplicate, the user is asked whether to keep the changes and remove the old file or discard them and
        modify none of them. When changes were made to either one of the files, the Widgets of the input manager are
        reloaded.


        WARNING: until #401 is implemented, we have to hash the port of the remote host as well, to ensure that
        duplicate files on different hosts can be added. This has to be changed afterwards.

        TODO: remove this method, when #449 was fully implemented with a TableEditor for remote files

        @author j_stru18
        """
        def _addHdf5Remote(self):
            hostName = self.remoteHost[0]
            port = self.remoteHost[1]
            path = self.getPath()
            rfd = RemoteFileDialog(hostName, port, "Select a HDF5 Database", "HDF5 (*.hdf5 *.h5)")
            rfd.exec_()
            newPath = rfd.returnvalue

            if newPath == "":  # guard  statement for empty path
                Log.error("No HDF5TXT file was selected.", self.manager.getLogID())
                return

            oldHashMsg = {"key": Protocol.GETHASH, "path": path, "type": "HDF5TXT"}
            oldHashRet = sendMsgToHost(hostName, port, oldHashMsg)
            newHashMsg = {"key": Protocol.GETHASH, "path": newPath, "type": "HDF5"}
            newHashRet = sendMsgToHost(hostName, port, newHashMsg)

            if not oldHashRet["status"]:  # guard statement for invalid return status #1
                Log.error("Hashing of old HDF5TXT not successful.", self.manager.getLogID())
                return

            if not newHashRet["status"]:  # guard statement for invalid return status #2
                Log.error("Hashing of selected HDF5 was not successful", self.manager.getLogID())
                return

            oldHashValue = oldHashRet["hashValue"]
            portHash = db_util.getStringHash(str(port))
            if oldHashValue == 0:  # file contained no paths to HDF5 files
                oldID = self.id
            else:
                oldID = str(oldHashValue ^ portHash)
            updateNeeded = False
            newHashValue = oldHashValue + newHashRet["hashValue"]
            newID = str(newHashValue ^ portHash)
            isFileDuplicate = self.manager.dbcontains(newID)  # does a db with the same id exist?
            if not isFileDuplicate:
                addPathMsg = {"key": Protocol.ADDHDF5, "path": path, "hdf5": newPath}
                addPathRet = sendMsgToHost(hostName, port, addPathMsg)
                if addPathRet["status"]:
                    self.manager.deletebyID(oldID)
                    self.manager.addDBbyPathRemote(path, hostName, port)
                    assert self.manager.dbcontains(newID)
                    updateNeeded = True  # db entries were changed and the inputs need to be updated
                else:
                    Log.error("Failed to add HDF5 Path: " + newPath, self.manager.getLogID())
            else:  # file with identical hashed ID exists
                duplicatePath = self.manager.getPathByID(newID)
                ret = QtWidgets.QMessageBox.question(self, "HDF5TXT with same Files Found",
                    "Another file with the same ID was found: \n{}\n Do you want to keep the changed "
                    "HDF5TXT and remove the old duplicate from Barista?".format(duplicatePath),
                    QtWidgets.QMessageBox.Apply, QtWidgets.QMessageBox.Discard)
                if ret == QtWidgets.QMessageBox.Apply:  # remove both old databases and add modified new one
                    addPathMsg = {"key": Protocol.ADDHDF5, "path": path, "hdf5": newPath}
                    addPathRet = sendMsgToHost(hostName, port, addPathMsg)
                    if addPathRet["status"]:
                        self.manager.deletebyID(oldID)
                        self.manager.deletebyID(newID)
                        self.manager.addDBbyPathRemote(path, hostName, port)
                        assert self.manager.dbcontains(newID)
                        updateNeeded = True  # db entries were changed and the inputs need to be updated
                        Log.log("Old HDF5TXT was removed and current file was modified.",
                            self.manager.getLogID())
                    else:
                        Log.error("Failed to add HDF5 Path: " + newPath, self.manager.getLogID())
                else:  # discard changes
                    Log.log("No changes to HDF5TXT files were made.", self.manager.getLogID())
            if updateNeeded:
                self.manager.updateListWidget()

        def disableEditing(self, disable):
            """ Disable the button to assign a new layer """
            self.pb_assign.setDisabled(disable)

    # class to make the Database List accept Drag and Drop inputs
    class ScrollList(QtWidgets.QListWidget):

        dropped = pyqtSignal(list)

        def __init__(self, parent=None):
            QtWidgets.QWidget.__init__(self, parent)
            self.setAcceptDrops(True)

        def dragEnterEvent(self, event):
            if event.mimeData().hasUrls:
                event.accept()
            else:
                event.ignore()

        def dragMoveEvent(self, event):
            if event.mimeData().hasUrls:
                event.accept()
            else:
                event.ignore()

        def dropEvent(self, event):
            if event.mimeData().hasUrls:
                event.setDropAction(QtCore.Qt.CopyAction)
                event.accept()

                links = []
                for url in event.mimeData().urls():
                    links.append(str(url.toLocalFile()))

                self.dropped.emit(links)
            else:
                event.ignore()
