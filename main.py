#!/usr/bin/python2
import os
import sys
import signal
import argparse
import logging
import backend.barista.caffe_versions as caffe_versions
from backend.barista.project import dirIsProject
from PyQt5.QtCore import QLocale
from backend.barista.utils.settings import applicationQSetting
from backend.caffe import path_loader
from gui.start_dialog import StartDialog
from PyQt5.QtWidgets import QApplication
from gui.caffepath_dialog import CaffepathDialog
from backend.networking.barista_server import BaristaServer
import threading
import subprocess


if __name__ == "__main__":
    logging.basicConfig(format='[%(asctime)s] %(levelname)s @ %(funcName)s:    %(message)s', datefmt='%d/%m/%Y %H:%M:%S',
                        filename="baristalog.txt", level=logging.INFO)
    QLocale.setDefault(QLocale.c())
    # Parse command line arguments.
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--server', help='start a local server and add it to the host manager', default=False, action='store_true')
    parser.add_argument('-d', '--dir', help='local directory to run server sessions in', type=str, default='.')
    parser.add_argument('-o', '--open', help='path to a Barista project to be opened', type=str, default='')
    args = parser.parse_args()
    # Get caffepath out of settings.
    settings = applicationQSetting()
    settings.beginGroup("Path")
    path = settings.value("caffePath")
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    # Start local server on 'localhost:4200' in subprocess.
    if args.server:
        if not os.path.exists(args.dir):
            logging.error("Session folder '%s' does not exist." % (args.dir))
            sys.stderr.write("Session folder '%s' does not exist." % (args.dir))
            exit(2)
        command = './server.py --port {} --dir {}'.format(BaristaServer.DEFAULT_PORT, args.dir)
        pid = subprocess.Popen(command.split()).pid
        # Stop the server when the app is about to quit.
        app.aboutToQuit.connect(lambda: os.kill(pid, signal.SIGTERM))
    # server = BaristaServer(app, ip=None, port=BaristaServer.DEFAULT_PORT, sessionPath='sessions')
    # Set global application stylesheet.
    with open('resources/styles.qss', "r") as stylesFile:
        stylesheet = stylesFile.read()
        app.setStyleSheet(stylesheet)
    # Show caffepath dialog if settings don't contain a valid caffepath.
    caffe_versions.loadVersions()
    if caffe_versions.versionCount() == 0:
        caffedlg = CaffepathDialog("To run Barista you need a valid caffepath.", "Save and start Barista", True)
        caffedlg.show()
        app.exec_()
    # Create start dialog.
    startdlg = StartDialog()
    # If a directory has been passed as an argument, try to open a project from
    # that directory without showing the start dialog.
    if len(args.open) > 0:
        if not dirIsProject(args.open):
            print("The provided path is not a valid Barista project: Please run Barista without flags and create a project first.")
            sys.exit(2)
        args.open = os.path.abspath(args.open)
        #startdlg.setVisible(False)
        startdlg.loadProject(args.open)
    else:
        startdlg.show()
    # Run the application.
    app.exec_()
