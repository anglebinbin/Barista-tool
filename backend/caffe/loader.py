import uuid

import h5py as h5
from google.protobuf import text_format
from google.protobuf.text_format import ParseError

import backend.caffe.proto_info as info
from backend.barista.utils.logger import Log


class ParseException(Exception):
    def __init__(self, msg):
        self._msg = msg

    def __str__(self):
        return self._msg

def loadSolver(solverstring):
    """ Return a dictionary which represent the caffe-solver-prototxt solverstring """
    from backend.caffe.path_loader import PathLoader
    proto = PathLoader().importProto()
    solver = proto.SolverParameter()

    # Get DESCRIPTION for meta infos
    descr = info.ParameterGroupDescriptor(solver)
    # "Parse" the solver-definition in prototxt-format
    try:
        text_format.Merge(solverstring,solver)
    except ParseError as ex:
        raise ParseException(str(ex))
    params = descr.parameter().copy() # All Parameters of the solver
    return copy.deepcopy(_extract_param(solver,params))

import copy
def loadNet(netstring):
    """ Load the prototxt string "netstring" into a dictionary.
        The dictionary has the following form


        {
            "name": "Somenetwork",
            "input_dim": [1,2,1,1],
            "state": {
                   "phase": "TRAIN"
           },
             ...
            "layers":
            {
                "somerandomid1": {
                    "type": LayerType Instance of Pooling-Layer,
                    "parameters": {
                        "pooling_param": [
                            "kernel_size": 23,
                            "engine": "DEFAULT"
                        ]
                        ....
                        "input_param": [
                            {"shape": {"dim": [...], ....  },
                            {"shape": {"dim": [...], ....  },
                        ]
                    }
                },
              "somerandomid2": {"type": ..., "parameters": ....}
            },
           "layerOrder": ["somerandomid1", "somerandomid2", ....]
        }

    """
    from backend.caffe.path_loader import PathLoader
    proto = PathLoader().importProto()
    # Load Protoclass for parsing
    net = proto.NetParameter()

    # Get DESCRIPTION for meta infos
    descr = info.ParameterGroupDescriptor(net)
    # "Parse" the netdefinition in prototxt-format
    try:
        text_format.Merge(netstring,net)
    except ParseError as ex:
        raise ParseException(str(ex))
    params = descr.parameter().copy() # All Parameters of the network

    # add logger output if deprecated layers have been found, to inform the user that those can't be parsed yet
    if len(net.layers) > 0:
        callerId = Log.getCallerId('protoxt-parser')
        Log.log("The given network contains deprecated layer definitions which are not supported and will be dropped.",
                callerId)

    # Layers is deprecated, Layer will be handled seperatly and linked to "Layers" key
    del params["layers"]
    del params["layer"]
    if params.has_key("layerOrder"):
        raise ValueError('Key layerOrder not expected!')

    # Extract every other parameters
    res = _extract_param(net,params)

    res["layers"], res["layerOrder"] = _load_layers(net.layer)

    res = copy.deepcopy(res)
    return res

def _load_layers(layerlist):
    """ Build the dictionary of all layers in layerlist. The dictionary has the form loadNet needs.
    """
    allLayers = info.CaffeMetaInformation().availableLayerTypes()
    order = []
    res = {}
    dicLayerTypeCounter = {}
    for layer in allLayers:
        dicLayerTypeCounter[layer] = 1

    for layer in layerlist:
        typename = layer.type
        layerinfo = info.CaffeMetaInformation().getLayerType(typename)
        id = str(uuid.uuid4())
        res[id]={
            "type": layerinfo,
            "parameters": _extract_param(layer,layerinfo.parameters())
        }
        order.append(id)

    for id in order:
        if "name" not in res[id]["parameters"]:
            typeName = res[id]["parameters"]["type"]
            newName = typeName + " #" + str(dicLayerTypeCounter[typeName])
            changed = True
            while changed == True:
                newName = typeName + " #" + str(dicLayerTypeCounter[typeName])
                changed = False
                for id2 in order:
                    if "name" in res[id2]["parameters"] and res[id2]["parameters"]["name"] == newName:
                        dicLayerTypeCounter[typeName] += 1
                        changed = True
            res[id]["parameters"]["name"] = newName

    return res, order

def _extract_param(value,parameters):
    """ Build the dictionary of all paramters, e.g. for layer. The parameters will be constructed recursivly.
        "value" is the loaded class from caffe.proto.caffe_pb2 and "parameters" the dictionary of
        parameter-descriptions (wrapped with protoinfo.py-Classes).
    """
    res = {}
    for paramname in parameters:
        val = getattr(value, paramname)
        parameter = parameters[paramname]
        if parameter.isRepeated():
            if len(val) == 0: # probably not set
                continue
            if parameter.isParameterGroup():
                res[paramname] = [_extract_param(subval, parameter.parameter()) for subval in val]
            elif parameter.isEnum():
                res[paramname] = [copy.deepcopy(parameter.availableValues()[x]) for x in val]
            else:
                res[paramname] = list(val)
        else:
            if not value.HasField(paramname):
                #Not explicit set -> ignore
                continue
            if parameter.isParameterGroup():
                res[paramname] = _extract_param(val, parameter.parameter())
            elif parameter.isEnum():
                res[paramname] = copy.deepcopy(parameter.availableValues()[val])
            else:
                res[paramname] = val
    return res

def extractNetFromSolver(solverstring):
    """Read a protoxt string(!) of a solver and return the network protoxt string(!).

    This works only, if the solver specifies a network using the "net_param" parameter. A reference to a file using the
    "net" parameter can not be handled by this method.
    """
    from backend.caffe.path_loader import PathLoader
    proto = PathLoader().importProto()
    # create empty solver message
    solver = proto.SolverParameter()

    # "Parse" the solver-definition in prototxt-format
    try:
        text_format.Merge(solverstring, solver)

        # extract net as a message and convert it into a string
        netString = text_format.MessageToString(solver.net_param)

        return netString
    except ParseError as ex:
        raise ParseException(str(ex))


def getCaffemodelFromSolverstate(solverstate):
    """ Parse the filename of the caffemodel file from the solverstate file.
    """
    from backend.caffe.path_loader import PathLoader
    proto = PathLoader().importProto()
    try:
        state = proto.SolverState()

        with open(solverstate, 'rb') as f:
            state.ParseFromString(f.read())
            return state.learned_net
    except Exception as e:
        print(str(e))


def getCaffemodelFromSolverstateHdf5(filename):
    """ Extract the filename of the caffemodel file from the solverstate hdf5 file. """
    try:
        file = h5.File(filename, 'r')
        if "learned_net" in file.keys():
            return str(file["learned_net"].value)
        return None
    except:
        return None

def getIterFromSolverstate(solverstate):
    """ Parse the iterations from the solverstate file.
    """
    from backend.caffe.path_loader import PathLoader
    proto = PathLoader().importProto()
    try:
        state = proto.SolverState()

        with open(solverstate, 'rb') as f:
            state.ParseFromString(f.read())
            return state.iter
    except Exception as e:
        print(str(e))
