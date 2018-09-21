from google.protobuf import text_format
import backend.caffe.proto_info as info

def saveSolver(solverdict):
    solver= _import_solver(solverdict)

    solverproto = text_format.MessageToString(solver)
    return solverproto


def _import_solver(solverdict):
    from backend.caffe.path_loader import PathLoader
    proto = PathLoader().importProto()
    solver = proto.SolverParameter()

    for entry in solverdict:

        # special case: inline-net definition in solver
        # (required to handle layers and layerOrder the same way it is handled for a standalone net definition)
        if entry == "net_param":
            net = _import_dictionary(solverdict["net_param"])
            solver.net_param.MergeFrom(net)
        else:
            _insert(entry, solverdict[entry], solver)

    return solver

def saveNet(netdict):

    """ Save the dictionary into a prototxt string.
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

    net = _import_dictionary(netdict)

    netproto = text_format.MessageToString(net)
    return netproto

def _import_dictionary(netdict):
    """fill the ProtoTxt-Net with data from the dictionary"""
    from backend.caffe.path_loader import PathLoader
    proto = PathLoader().importProto()
    net = proto.NetParameter()

    for entry in netdict:
        if entry == "layerOrder":
            continue
        if entry == "layers":
            _extract_layer(netdict["layers"],netdict["layerOrder"],net)
            continue
        _insert(entry,netdict[entry],net)
    return  net

def _extract_layer(layers, layerorder,net):
    for order in layerorder:
        index = len(net.layer)
        net.layer.add()
        currlayer = layers[order]

        for param in currlayer["parameters"]:
            _insert(param,currlayer["parameters"][param],net.layer[index])
    return

def _insert(key, value, insert):
    descr = info.ParameterGroupDescriptor(insert)
    param = descr.parameter()[key]
    if param.isParameterGroup():
        if param.isRepeated():
            for l in range(0, len(value)):
                index = len(getattr(insert,key))
                getattr(insert,key).add()
                for v in value[l]:
                    _insert(v,value[l][v],getattr(insert,key)[index])
        else:
            for v in value:
                _insert(v,value[v],getattr(insert,key))
        return
    if param.isRepeated():
        for v in value:
            w = v
            if param.isEnum():
                w = param.availableValues().index(v)
            getattr(insert,key).append(w)

        return
    if param.isEnum():
        value = param.availableValues().index(value)
    setattr(insert, key, value)
