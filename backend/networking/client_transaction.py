from PyQt5.QtCore import pyqtSignal

from backend.networking.transaction import Transaction
from backend.networking.protocol import Protocol


class ClientTransaction(Transaction):
    showDirSig = pyqtSignal(list, bool)

    def __init__(self):
        Transaction.__init__(self)
        # self.options = {Protocol.ECHO: self.msgEcho}

    def processMessage(self):
        """process the received message and call further processing"""
        pass
        # msg = self.messageOutput[0]
        # if msg["key"] in self.options:
        #     self.options[msg["key"]]()

    # def msgEcho(self):
    #     msg = self.asyncRead()
    #     print(msg)
