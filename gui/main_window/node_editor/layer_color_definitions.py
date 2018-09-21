from PyQt5.QtGui import QColor
from backend.caffe.proto_info import LayerType
from gui.main_window.node_editor.node_editor_constants import Constants


class LayerColorDefinitions:
    __LAYER_CATEGORY_COLORS = {LayerType.CATEGORY_DATA       : QColor(   0, 150,   0),
                               LayerType.CATEGORY_LOSS       : QColor(   0, 100, 255),
                               LayerType.CATEGORY_ACTIVATION : QColor( 200, 200,  50),
                               LayerType.CATEGORY_NONE       : Constants.itemBackgroundColorLight}

    __LAYER_GROUP_INVALID = -1
    __LAYER_GROUP_PYTHON_LAYER = 0
    __LAYER_GROUP_STRUCTURAL_LAYER = 1

    __LAYER_GROUP_COLORS = {__LAYER_GROUP_PYTHON_LAYER : QColor(50, 255, 255),
                            __LAYER_GROUP_STRUCTURAL_LAYER : QColor(255, 100, 0)}

    __LAYER_GROUP_DEFINITIONS = {"Python" : __LAYER_GROUP_PYTHON_LAYER,
                                 "Convolution" : __LAYER_GROUP_STRUCTURAL_LAYER,
                                 "InnerProduct": __LAYER_GROUP_STRUCTURAL_LAYER,
                                 "Deconvolution": __LAYER_GROUP_STRUCTURAL_LAYER,
                                 "LSTM": __LAYER_GROUP_STRUCTURAL_LAYER,
                                 "RNN": __LAYER_GROUP_STRUCTURAL_LAYER,
                                 "BatchNorm": __LAYER_GROUP_STRUCTURAL_LAYER}

    def __init__(self):
        return

    @staticmethod
    def getTypeColor(nodeType):
        """ Returns the color for a given layer type based on the types category and type name """

        # First try to get the group by type name. If the type name is found, try to get the groups color.
        # If the type name has an invalid group, the layers category is used to get the color.
        # If the type name can not be found, use the layer category as well.
        return LayerColorDefinitions.__LAYER_GROUP_COLORS.get(
            LayerColorDefinitions.__LAYER_GROUP_DEFINITIONS.get(nodeType.name(),
                                                                LayerColorDefinitions.__LAYER_GROUP_INVALID),
            LayerColorDefinitions.__LAYER_CATEGORY_COLORS[nodeType.category()])
