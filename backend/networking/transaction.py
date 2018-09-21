import pickle
import sys
from abc import abstractmethod
from threading import Lock
import logging
import zlib

from PyQt5.QtCore import QByteArray, QDataStream, QIODevice, QObject, pyqtSignal
from PyQt5.QtNetwork import QTcpSocket, QAbstractSocket
from PyQt5.QtTest import QSignalSpy
from PyQt5.QtWidgets import qApp

COMPRESS = True

class Transaction(QObject):
    """Use parent class for server and client transactions. Abstracts TCPSocket-Access"""
    # empirical benchmarks using the echo command (send + recieve) shows following performance characteristics:
    # - a server can handle thousands of messages on one open socket per second, more CPU performance --> faster server
    # - as long as you don't saturate your network connection by increasing the message size there
    #   should be no problems at all
    # - increasing the message size beyond the saturation of the network connection may lead to message drops
    #   and crash the server
    #
    #   some examples:
    #   - a server on a laptop connected over a 2-3 mb/s wifi would crash if the message size is greater then aprox 6mb
    #   - the same laptop with an ethernet cable can handle up to aprox 20 mb per message
    #   - a server over localhost and the loopback interface could handle up to aprox 100mb
    # TODO longer testing
    # TODO close and reopen the socket after each / after n messages
    # TODO investigate message drops and server crashed
    # TODO maybe rewrite the class to split messages over certain size
    #       splitting messages refers to writing at most n bytes to the QDataStream and flushing regulary
    #       alternatively split the message altogether
    #       this depends if the QTcpSocket or the QDataStream is the bottleneck

    bufferReady = pyqtSignal()
    socketClosed = pyqtSignal()
    _stopWaiting = pyqtSignal()
    _staging = pyqtSignal()

    def __init__(self):
        # QObject.__init__(self)
        super(Transaction, self).__init__()
        self.tcpsocket = None  # type: QTcpSocket
        self.messageBuffer = QByteArray()
        self.recieveBuffer = QByteArray()
        self.messageOutput = list()
        self.messageSize = 0
        self.isRecieving = False
        self.bufferReady.connect(self.processMessage)
        self._isConnected = False
        self._hasError = False
        self.lock = Lock()

    def connect(self, host, port):
        """connect to host on port"""
        logging.debug("Connecting to %s:%i", host, port)
        self._hasError = False
        self.tcpsocket = QTcpSocket()
        self.tcpsocket.error.connect(self.processError)
        self.tcpsocket.connected.connect(self._connected)
        self.tcpsocket.connected.connect(lambda: self._stopWaiting.emit())
        self.tcpsocket.readyRead.connect(self.receive)

        self.tcpsocket.connectToHost(host, port)
        self.waitForConnection()

    def processError(self, error):
        """
        Process the errors on the tcpsocket
        See: http://doc.qt.io/qt-5/qabstractsocket.html#SocketError-enum
        """
        logging.debug("Error %i", error)
        if error == 0:
            # Remote Host can't be resolved
            self.close()
        elif error == 1:
            # Remote Host closed the connection.
            self.close()
        else:
            # TODO: somehow handle errors
            # Code 7 is detected far too late, it waits till the socket itself times out
            errortxt = ""
            for k in dir(QAbstractSocket):
                v = getattr(QAbstractSocket, k)
                if type(v) is type(error) and str(v) is str(error):
                    errortxt = k

            sys.stderr.write("QTcpSocket@Transaction Error Code: " + str(error) + " " + errortxt + "\n")

            self.close()
        self._isConnected = False
        self._hasError = True
        self._stopWaiting.emit()

    def _connected(self):
        """On Connect mark this transactions as connected"""
        logging.debug("Socket connected.")
        self._isConnected = True
        self._hasError = False

    def acceptClient(self, socket):
        """set external socket"""
        logging.debug("Client socket connected.")
        self.tcpsocket = socket
        self._isConnected = True
        self._hasError = False
        self.tcpsocket.error.connect(self.processError)
        self.tcpsocket.readyRead.connect(self.receive)

    def receive(self):
        """On recieve packet load message into buffer. But first get message length"""
        logging.debug("Receiving message")
        while self.tcpsocket.bytesAvailable() > 0:
            # while some unread bytes available
            stream = QDataStream(self.tcpsocket)
            stream.setVersion(QDataStream.Qt_5_3)

            if not self.isRecieving:  # For a new Message get the Message Size
                if self.tcpsocket.bytesAvailable >= 4:  # since reading UInt32
                    self.messageSize = stream.readUInt32()
                    logging.debug("Start of new message of size %i", self.messageSize)
                    self.isRecieving = True
                else:
                    break

            else:  # For a continued message keep reding until whole message is in buffer
                s = min(self.tcpsocket.bytesAvailable(), self.messageSize - len(self.messageBuffer))
                self.messageBuffer.append(stream.readRawData(s))
                if len(self.messageBuffer) == self.messageSize:
                    logging.debug("Finished receiving message of size %i", self.messageSize)
                    self._processBuffer()

    def send(self, msg):
        """Send first the message size, then the message in Pickle"""
        if self.isConnected():
            pmsg = pickle.dumps(msg)
            if COMPRESS:
                pmsg = zlib.compress(pmsg)
            buffer = QByteArray()
            stream = QDataStream(buffer, QIODevice.WriteOnly)
            stream.setVersion(QDataStream.Qt_5_3)
            stream.writeUInt32(len(pmsg))
            stream.writeRawData(pmsg)
            bytesWritten = self.tcpsocket.write(buffer)
            self.tcpsocket.flush()
            self.tcpsocket.waitForBytesWritten()
            # qApp.processEvents()  # send data immediately and don't wait for next mainloop
            logging.debug("Bytes written: %i", bytesWritten)
            if bytesWritten > 0:
                return True
        else:
            logging.debug("Message not send. Not connected")
        return False

    def isConnected(self):
        """return the connected state"""
        return self._isConnected

    def close(self):
        """close this socket and fire signal socketClosed to notify slots to delete this obj"""
        if self.tcpsocket:
            logging.debug("socket closing")
            self._isConnected = False
            self.tcpsocket.close()
            # self.tcpsocket = None
            self.socketClosed.emit()

    def _processBuffer(self):
        """If message is complete: read Pickle and move to output buffer"""
        pmsg = str(self.messageBuffer)
        if COMPRESS:
            pmsg = zlib.decompress(pmsg)
        msg = pickle.loads(pmsg)
        logging.debug("Message received: %s", str(msg))

        self.lock.acquire()
        self.messageOutput.append(msg)
        self.lock.release()
        # reset state
        self.isRecieving = False
        self.messageBuffer.clear()
        self._stopWaiting.emit()
        self.bufferReady.emit()

    @abstractmethod
    def processMessage(self):
        """implement in server/client"""
        pass

    def asyncRead(self, timeout=5000, staging=False, attr=None):
        """For direct reading access, pop the first message in buffer
        Explanation:

        timeout: stop after waiting for 5s and return NONE object.
            this is usefull if the server does not answer (e.g. crash)
            or the networkconnection breaks

        staging: If True the asynchronous wait will wait for a the staging signal instead of the messageOutput signal.
            the staging signal should be used if you have a class which uses both: a signal/slot based processMessage
            methode and asyncRead calls. This gives the processMessage calls priority.

            !!!Don't forget to call the stage() method if your processMessage ignores the message!!!

        attr: In some cases you have multiple asyncRead calls on the same transaction Item.
            This may lead to preemtive behaviour resulting in reading the wrong messages and key errors.
            (e.g. READ#1 reads messages destined for READ#2)
            By providing a tupel (attr, value) the message is parsed and only poped if the value matches.
            Not matching messages are appended back into the buffer and other waiting asyncReads are notified
        """
        if self.isConnected():
            turns = 0
            while True:
                turns += 1
                if turns > 100:
                    logging.debug("Timeout on read after 100 iterations")
                    return None

                result = True
                logging.debug("MessageOutput size: %i", len(self.messageOutput))
                if len(self.messageOutput) == 0 and not self.containsAttr(attr):
                    logging.debug("Waiting for new message.")
                    if not staging:
                        # spy = QSignalSpy(self._stopWaiting)
                        spy = QSignalSpy(self.bufferReady)
                    else:
                        spy = QSignalSpy(self._staging)
                    result = spy.wait(timeout)  # Asynchronous wait, Timeout 5s

                if result and not self._hasError:
                    self.lock.acquire()
                    if len(self.messageOutput) == 0:
                        self.lock.release()
                        logging.debug("Race condition triggered. Wait for next message.")
                        continue
                    found = False
                    result = self.messageOutput[0]
                    if attr is not None:
                        for msg in self.messageOutput:
                            if attr[0] in msg:
                                if attr[1] == msg[attr[0]]:
                                    found = True
                                    result = msg
                                    break
                    if found or attr is None:
                        del self.messageOutput[self.messageOutput.index(result)]
                        logging.debug("MessageOutput size: %i", len(self.messageOutput))
                        self.lock.release()

                        if "error" not in result:
                            result["error"] = []
                        if "status" not in result:
                            result["status"] = True

                        return result
                    else:
                        logging.debug("Message not found. Release of lock.")
                        if attr is not None:
                            logging.debug("Miss '%s' with value '%s'", str(attr[0]), str(attr[1]))
                        self.lock.release()
                        self.bufferReady.emit()
                        qApp.processEvents()
                else:
                    logging.debug("Nothing to read.")
                    break
        else:
            logging.debug("Not connected. Did not read.")
        return None

    def stage(self):
        logging.debug("Stage!")
        self._staging.emit()

    def waitForConnection(self):
        """sometimes it takes some time to establish the connection. wait half a second"""
        logging.debug("Establishing connection")
        if self.tcpsocket is not None:
            result = True
            if not self.isConnected() and not self._hasError:
                # spy = QSignalSpy(self.tcpsocket.connected)
                spy = QSignalSpy(self._stopWaiting)
                result = spy.wait(5000)  # Asynchronous wait, Timeout 5 s
                if not result:
                    #  it is bad if the socket needs longer than the timeout and connects
                    #  after the connection is deemed dead
                    self.close()
                    logging.debug("Connection not established, manually closing socket.")
            return result and not self._hasError
        return False

    def getAttrOfFirst(self, attrlist):
        """check the attributes of the first item in the output buffer"""
        self.lock.acquire()
        result = []
        for attr in attrlist:
            if attr in self.messageOutput[0]:
                result.append(self.messageOutput[0][attr])
            else:
                result.append(None)
        self.lock.release()
        return result

    def containsAttr(self, attr):
        """check if any message in the output buffer contains the desired attribute"""
        if attr is None:
            return False
        self.lock.acquire()
        found = False
        for msg in self.messageOutput:
            if attr[0] in msg:
                if msg[attr[0]] is attr[1]:
                    found = True
                    break
        self.lock.release()
        return found
