from PyQt5.QtGui import QFont, QFontMetricsF, QColor


class Constants:
    """ This class stores constant values used by the node prototxt_editor """

    # grid size and pattern
    sceneGridSize = 20
    sceneLargeGridCells = 5

    # scene size
    sceneInitialWidth = 32000
    sceneInitialHeight = 32000

    # used for zoom in/out using the mouse wheel
    viewScaleFactor = 1.1
    viewMaxScale = 0.2
    viewMinScale = 5.0

    # use default font
    font = QFont()

    # font used for the layer name
    nodeItemFontName = QFont(font)
    nodeItemFontName.setPointSize(10)
    nodeItemFontName.setBold(True)
    nodeItemFontNameMetrics = QFontMetricsF(nodeItemFontName)

    # font used for the layer type
    nodeItemFontType = QFont(font)
    nodeItemFontType.setPointSize(8)
    nodeItemFontTypeMetrics = QFontMetricsF(nodeItemFontType)

    # font used for the blob names
    nodeItemFontBlob = QFont(font)
    nodeItemFontBlob.setPointSize(8)
    nodeItemFontBlobMetrics = QFontMetricsF(nodeItemFontBlob)

    # constants used to add free spaces in the node item rendering
    nodeItemMinBlobAreaHeight = 10
    nodeItemHeadPadding = 20
    nodeItemSelectionSize = 3
    nodeItemBorderSize = 3
    nodeItemTextMargin = 4
    nodeItemConnectorPaddding = 6

    # connector size
    connectorItemOuterSize = 12
    connectorItemInnerSize = 6

    # opacity for items in phase and normal items
    itemOpacityInPhase = 200
    itemOpacityNotInPhase = 100

    # node item background colors
    itemBackgroundColorDark = QColor(100, 100, 100)
    itemBackgroundColorLight = QColor(200, 200, 200)
    itemBorderColor = QColor(0, 0, 0)

    # color of items working in-place
    itemInPlaceColor = QColor(30, 30, 200)

    # connection item constants
    connectionItemColor = QColor(100, 100, 100)
    connectionItemSelectionSize = 9
    connectionItemSize = 5
    connectionItemHiddenDashCount = 4
    connectionItemHiddenDashSize = 10
    connectionItemHiddenDashSpace = 10

    # color for selected items (node item, connection)
    selectedColor = QColor(150, 150, 0)

    def __init__(self):
        return

    @staticmethod
    def setPaintDevice(device):
        """ Used to setup font metrics correctly """
        Constants.nodeItemFontNameMetrics = QFontMetricsF(Constants.nodeItemFontName, device)
        Constants.nodeItemFontTypeMetrics = QFontMetricsF(Constants.nodeItemFontType, device)
        Constants.nodeItemFontBlobMetrics = QFontMetricsF(Constants.nodeItemFontBlob, device)
