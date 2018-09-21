from backend.barista.utils.logger import *
from backend.networking.client_transaction import ClientTransaction


def sendMsgToHost(host, port, msg):
    ct = ClientTransaction()
    ct.connect(host, port)
    ct.waitForConnection()
    if ct.isConnected():
        ct.send(msg)
        ret = ct.asyncRead()
        ct.close()
        if ret:
            return ret
        else:
            Log.error("No answer from " + host + ":" + str(port), Log.getCallerId("Network Connection"))
    else:
        Log.error("Failed to connect to " + host + ":" + str(port), Log.getCallerId("Network Connection"))


def buildTransaction(host, port):
    ct = ClientTransaction()
    ct.connect(host, port)
    ct.waitForConnection()
    if ct.isConnected():
        return ct
