#!/usr/bin/python2
import os
import sys
import signal
import argparse
import logging
from PyQt5.QtCore import QCoreApplication
from backend.networking.barista_server import BaristaServer


if __name__ == "__main__":
    logging.basicConfig(format='[%(asctime)s] %(levelname)s @ %(funcName)s:    %(message)s', datefmt='%d/%m/%Y %H:%M:%S',
                        filename="baristalog.txt", level=logging.INFO)
    # Parse command line arguments.
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', help='local port to receive connections', default=BaristaServer.DEFAULT_PORT, type=int)
    parser.add_argument('-d', '--dir', help='local directory to run all sessions in', type=str, default='.')
    parser.add_argument('-i', '--ip', help='IP reachable from Barista GUI', type=str)
    args = parser.parse_args()
    # Validate port.
    if args.port < BaristaServer.MIN_PORT or args.port > BaristaServer.MAX_PORT:
        logging.error("Port should be between %d and %d." % (BaristaServer.MIN_PORT, BaristaServer.MAX_PORT))
        sys.stderr.write("Port should be between %d and %d.\n" % (BaristaServer.MIN_PORT, BaristaServer.MAX_PORT))
        exit(2)
    # Validate session directory.
    args.dir = os.path.abspath(args.dir)
    if not os.path.isdir(args.dir):
        logging.error("Path '%s' is not valid.", args.dir)
        sys.stderr.write("Path '" + args.dir + "' is not valid.\n")
        exit(3)
    # Verify write access to session directory.
    if not os.access(args.dir, os.W_OK):
        logging.error("Path '%s' is not writeable.", args.dir)
        sys.stderr.write("Path '" + args.dir + "' is not writeable.\n")
        exit(4)
    # Create application and server.
    app = QCoreApplication(sys.argv)
    server = BaristaServer(app, args.ip, args.port, args.dir)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    # Run the application.
    app.exec_()
