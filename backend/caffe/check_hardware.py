from subprocess import Popen, PIPE, STDOUT
from sys import stdout
from os import path
import logging
from backend.networking.protocol import Protocol

def checkHardware(binary, silent=False, transaction=None):
    """
    probe caffe continuously for incrementing until missing id
    structure:
    [
        { "id": 0,
          "name": "..", 
          "log": ["..", "..", "..", ... ]
        },
        { "id": 1,
          "name": "..", 
          "log": ["..", "..", "..", ... ]
        },
        ...
    ]
    """
    gid = 0
    hw = []
    if not silent:
        stdout.write("Checking Hardware...\n")
        logging.info("Checking Hardware...")
    cpu = _getCPU()
    name = _getCPUName(cpu)
    hw.append({"name": name, "log": cpu})
    if not silent:
        stdout.write("CPU found: " + name + "\n")
        logging.info("CPU found: %s", name)
    if transaction:
        msg = {"key": Protocol.SCANHARDWARE, "finished": False, "name": name}
        transaction.send(msg)
    while True:
        log = _getId(gid, binary)
        if not _isValid(log) or _isCpuOnly(log):
            if not silent and gid is 0:
                stdout.write("No GPU found, CPU mode\n")
                logging.info("No GPU found, CPU mode")
            break
        name = _getName(log)
        if not silent:
            stdout.write("GPU " + str(gid) + " found: " + name + "\n")
        if transaction:
            msg = {"key": Protocol.SCANHARDWARE, "finished": False, "name": name, "id": gid}
            transaction.send(msg)
        hw.append({"id": gid, "name": name, "log": _parseLog(log)})
        gid += 1
    return hw


def _getId(gid, binary):
    """probe caffe for gpu id"""
    proc = Popen([binary, "device_query", "-gpu", str(gid)], stdout=PIPE, stderr=STDOUT)
    it = iter(proc.stdout.readline, '')
    log = []
    for i in it:
        log.append(i[:-1])
    return log

def _getCPU():
    proc = Popen(["cat", "/proc/cpuinfo"], stdout=PIPE)
    it = iter(proc.stdout.readline, '')
    log = []
    for i in it:
        log.append(i[:-1])
    return log

def _isValid(log):
    """check if no error has occurred"""
    for l in log:
        if "error" in l.lower():
            return False
    return True


def _isCpuOnly(log):
    """check for CPU-Only mode"""
    for l in log:
        if "cpu" in l.lower():
            return True
    return False


def _getName(log):
    """extract the Name"""
    for l in log:
        if "name:" in l.lower():
            return l[l.index("Name:") + 5:].strip()
    return ""

def _getCPUName(log):
    """extract the CPU name"""
    for l in log:
        if "model name" in l.lower():
            return l.split(":")[1].strip()


def _parseLog(log):
    """clean up logs to show to user"""
    return [l[l.index("]")+2:] for l in log[1:]]
