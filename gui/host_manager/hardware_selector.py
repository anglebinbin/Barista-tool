from PyQt5.QtWidgets import QDialog, QHBoxLayout,QVBoxLayout, QPushButton, QListWidget, QLabel, QListView, QScrollArea
from PyQt5.QtCore import QAbstractListModel, Qt
from PyQt5.QtGui import QFontDatabase

from backend.networking.net_util import sendMsgToHost, buildTransaction
from backend.networking.protocol import Protocol

class HardwareSelector(QDialog):
    def __init__(self, host, port, parent = None):
        QDialog.__init__(self, parent)
        self.host = host
        self.port = port

        self._layout = QVBoxLayout(self)
        self.setWindowTitle("Hardware on " + self.host + ":" + str(self.port))
        self.setMinimumSize(800, 600)

        self.hardware = None
        self.selectedHW = None
        self._model = None

        self._lbl_status = QLabel()
        self._layout.addWidget(self._lbl_status)

        self._layoutH = QHBoxLayout()
        self._layout.addLayout(self._layoutH)

        self._hwlist = QListView()
        self._layoutH.addWidget(self._hwlist)

        self._lbl_hw = QLabel()
        self._lbl_hw.setMinimumWidth(400)
        self._lbl_hw.setMargin(10)
        self._lbl_hw.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        #self._layoutH.addWidget(self._hwlabel)
        self._hwscroll = QScrollArea()
        self._hwscroll.setWidget(self._lbl_hw)
        self._layoutH.addWidget(self._hwscroll)

        self._layoutB = QHBoxLayout()
        self._layout.addLayout(self._layoutB)

        self._btn_select = QPushButton("Select")
        self._layoutB.addWidget(self._btn_select)
        self._btn_rescan = QPushButton("Rescan")
        self._layoutB.addWidget(self._btn_rescan)
        self._btn_cancel = QPushButton("Cancel")
        self._layoutB.addWidget(self._btn_cancel)

        self._btn_select.clicked.connect(self._select)
        self._btn_cancel.clicked.connect(lambda: (self._quitScan(), self.close()))
        self._btn_rescan.clicked.connect(self._prepareScan)

        self._disable()
        self._start()



    def _start(self, ret=None):
        if not ret:
            self._prepareScan()
            ret = self._getHardware()
        if ret:
            self.hardware = ret[0]
            if len(self.hardware) == 0:
                self._lbl_status.setText("No Hardware detected. Is Caffepath set?")
            elif ret[1] == 0:
                self._lbl_status.setText("Currently selected CPU: " + ret[0][0]["name"])
            else:
                self._lbl_status.setText("Currently selected GPU " + str(ret[1]) + ": " + ret[0][ret[1]]["name"])
            self._model = self.HardwareListModel(self.hardware)
            self._hwlist.setModel(self._model)
            self._hwlist.selectionModel().currentChanged.connect(self._onSelection)
            self._enable()

    def _enable(self):
        self._hwlist.setEnabled(True)
        self._btn_rescan.setEnabled(True)

    def _disable(self):
        self._hwlist.setEnabled(False)
        self._btn_select.setEnabled(False)
        self._btn_rescan.setEnabled(False)
        self._lbl_hw.setText("")
        if self._hwlist.selectionModel():
            self._hwlist.selectionModel().currentChanged.disconnect()
            self._hwlist.setModel(None)

    def _select(self):
        self.selectedHW = self._hwlist.currentIndex().row()
        self.close()

    def _onSelection(self):
        row = self._hwlist.currentIndex().row()
        if row != -1:
            self._lbl_hw.setText(self._getText(row))
            self._lbl_hw.adjustSize()
            self._btn_select.setEnabled(True)
        else:
            self._lbl_hw.setText("")

    def _getText(self, row):
        log = self.hardware[row]["log"]
        text = ""
        for l in log:
            text += l + "\n"
        return text

    def _prepareScan(self):
        self._disable()
        ct = buildTransaction(self.host, self.port)
        if ct:
            self.ct = ct
            msg = {"key": Protocol.SCANHARDWARE}
            self.ct.send(msg)
            self.ct.bufferReady.connect(self._processScan)
            self.ct.socketClosed.connect(self._socketClosed)
            self._lbl_status.setText("Start scanning...")
        else:
            self._lbl_status.setText("Failed to start Scan.")

    def _processScan(self):
        msg = self.ct.asyncRead()
        if msg["status"]:
            if "finished" in msg.keys():
                if msg["finished"]:
                    self._quitScan()
                    self._lbl_status.setText("Scan finished.")
                    self._start([msg["hardware"], msg["current"]])
                else:
                    if "id" in msg.keys():
                        self._lbl_status.setText("Found GPU " + str(msg["id"]) + ": " + msg["name"])
                    else:
                        self._lbl_status.setText("Found CPU: " + msg["name"])
        else:
            self._lbl_status.setText("Scan failed: " + msg["error"])

    def _socketClosed(self):
        self._quitScan()
        self._enable()
        self._lbl_status.setText("Connection lost!")

    def _quitScan(self):
        if hasattr(self, "ct"):
            self.ct.bufferReady.disconnect()
            self.ct.socketClosed.disconnect()
            self.ct.close()
            del self.ct

    def _getHardware(self):
        msg = {"key": Protocol.GETHARDWARE}
        ret = sendMsgToHost(self.host, self.port, msg)
        if ret and "hardware" in ret:
            return [ret["hardware"], ret["current"]]

    class HardwareListModel(QAbstractListModel):
        def __init__(self, data):
            QAbstractListModel.__init__(self)
            self.data = data

        def rowCount(self, parent=None, *args, **kwargs):
            return len(self.data)

        def data(self, index, role=None):
            row = index.row()
            if role == Qt.DisplayRole:
                if row==0:
                    return "CPU: " + self.data[row]["name"]
                return "GPU " + str(self.data[row]["id"]) + ": " + self.data[row]["name"]
