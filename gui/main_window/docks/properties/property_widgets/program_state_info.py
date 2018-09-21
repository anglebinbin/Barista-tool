import backend.caffe.dict_helper as helper
from gui.main_window.docks.properties.property_widgets import network_dict_info
from gui.main_window.docks.properties.property_widgets import solver_info
from gui.main_window.docks.properties.property_widgets.generic_info import GenericInfoBuilder
from gui.main_window.docks.properties.property_widgets.types import *


def defaultState():
    net = helper.bareNet("Unnamed")
    return {
        "network": net,
        "position": {},
        "selection": [],
        "solver": {},
        "hidden_connections": {}
    }

class ProgramStateInfoBuilder(GenericInfoBuilder):
    def __init__(self, statedict):
        self.statedict = statedict
        self.netinfo = network_dict_info.NetworkDictInfoBuilder(lambda: self.statedict["network"])
        self.solverinfo = solver_info.SolverPropertyInfoBuilder()

        infodescription = {
            "type": GroupType,
            "name": "",
            "prototype": defaultState,
            "entries": [
                {
                    "info": self.netinfo.buildRootInfo("network"),
                    "builder": self.netinfo,
                    "urifunc": lambda uri: uri[1:]
                },
                {
                    "name": "position",
                    "type": DictType,
                    "prototype": [],
                    "entry": {
                        "name": "coord",
                        "type": ListType,
                        "prototype": [0,0],
                        "typeEntry": IntType
                    }
                },
                {
                    "name": "selection",
                    "type": ListType,
                    "prototype": [],
                    "typeEntry": StringType
                },
                {
                    "info": self.solverinfo.buildRootInfo("solver"),
                    "builder": self.solverinfo,
                    "urifunc": lambda uri: uri[1:]
                },
                {
                    "name": "hidden_connections",
                    "type": ListType,
                    "prototype": [],
                    "isRequired": False,
                    "entry": {
                        "name": "hidden_connection",
                        "type": GroupType,
                        "prototype": {},
                        "entries": [
                            {
                                "name": "topLayerId",
                                "type": StringType,
                                "prototype": ""
                            },
                            {
                                "name": "topBlobIdx",
                                "type": IntType,
                                "prototype": 0
                            },
                            {
                                "name": "bottomLayerId",
                                "type": StringType,
                                "prototype": ""
                            },
                            {
                                "name": "bottomBlobIdx",
                                "type": IntType,
                                "prototype": 0
                            }
                        ]
                    }
                }
            ]
        }
        
        GenericInfoBuilder.__init__(self,infodescription)
