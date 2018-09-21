from PyQt5.QtCore import QSettings

def applicationQSetting():
    """ Returns the default QSettings-Object for this application """
    # return QSettings(QSettings.IniFormat,QSettings.UserScope, "wwu", "Barista")
    return QSettings("wwu", "Barista")
