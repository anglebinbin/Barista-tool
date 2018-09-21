import os


class LayerHelper:
    def __init__(self):
        return

    PHASE_TRAIN = u'TRAIN'
    PHASE_TEST = u'TEST'


    @staticmethod
    def getLayerPhase(layer):
        # TODO implement further rules to decide the phase of a layer (see issue #201)
        # -> not only "include", but also "exclude"
        # -> (include|exclude).min_level
        # -> (include|exclude).max_level
        # -> (include|exclude).stage
        # -> (include|exclude).not_stage
        # -> combination of multiple rules. e.g. include.phase == TRAIN and include.phase == TEST equals no value
        # -> unclear: what does LayerParameter.phase (instead of LayerParameter.[include|exclude].phase) do?
        if "include" in layer["parameters"]:
            for item in layer["parameters"]["include"]:
                if "phase" in item:
                    return item["phase"]
        return ""

    @staticmethod
    def isLayerIncludedInTrainingPhase(layer):
        """Check whether this layer is included in the training phase."""
        # TODO see TODO in LayerHelper.getLayerPhase().
        return LayerHelper.getLayerPhase(layer) != LayerHelper.PHASE_TEST

    @staticmethod
    def isLayerInPlace(layer):
        if "top" in layer["parameters"] and "bottom" in layer["parameters"]:
            for bottomBlob in layer["parameters"]["bottom"]:
                for topBlob in layer["parameters"]["top"]:
                    if bottomBlob == topBlob:
                        return True
        return False

    @staticmethod
    def isLayerInPlaceForBlob(layer, blobName):
        if "top" in layer["parameters"] and "bottom" in layer["parameters"]:
             if not blobName in layer["parameters"]["top"]:
                 return False
             if not blobName in layer["parameters"]["bottom"]:
                 return False
             return True
        else:
            return False

    @staticmethod
    def getTopBlobIndex(layer, blobName):
        if "top" in layer["parameters"]:
            for index in range(0, len(layer["parameters"]["top"])):
                if blobName == layer["parameters"]["top"][index]:
                    return index
        return -1


    @staticmethod
    def buildConnectionList(network):
        layerDict = network["layers"]
        layerOrder = network["layerOrder"]

        orderedLayersByBlob = OrderedLayersByBlob(layerDict, layerOrder)
        blobOrder = orderedLayersByBlob.blobLayerDict

        connections = list()

        for layerID in layerOrder:
            layer = layerDict[layerID]
            LayerHelper.__addConnectionsForLayer(layer, layerID, blobOrder, connections, layerDict)

        return connections

    @staticmethod
    def getLayersInfo(layertypes, network, dbpath):
        """ Go over all layers in the network, search for layers of given types and return their id, name and a boolean
            indicating if the layer's path matches the given dbpath.
        """
        mylayer = []
        for nid in network["layerOrder"]:
            type = network["layers"][nid]["type"].name()
            if type in layertypes:
                params = network["layers"][nid]["parameters"]
                layername = params["name"]
                # since names can be ambiguous append the phase
                if unicode("include") in params:
                    for incl in params["include"]:
                        if unicode("phase") in incl:
                            layername += " (" + incl["phase"] + ")"
                same = False
                dataParamType = "hdf5_data_param" if type == "HDF5Data" else "data_param"
                if unicode(dataParamType) in params and unicode("source") in params[dataParamType]:
                    layerpath = params[dataParamType]["source"]
                    same = (os.path.realpath(dbpath) == os.path.realpath(layerpath))
                mylayer.append([nid, layername, same])
        return mylayer

    @staticmethod
    def setPathforType(id, path, type, network):
        '''set the path and db type to layer basend on the ID'''
        params = network["layers"][id]["parameters"]
        if type in ["LMDB", "LEVELDB"]:
            if "data_param" not in params:
                params.giveProperty("data_param",{})
            params["data_param"]["source"] = path
            if type == "LMDB":
                params["data_param"]["backend"] = u'LMDB'
            if type == "LEVELDB":
                params["data_param"]["backend"] = u'LEVELDB'
        if type == "HDF5TXT":
            if "hdf5_data_param" not in params:
                params.giveProperty("hdf5_data_param",{})
            params["hdf5_data_param"]["source"] = path



    @staticmethod
    def __addConnectionsForLayer(layer, layerID, blobOrder, connections, layerDict):
        if "bottom" in layer["parameters"]:
            bottoms = layer["parameters"]["bottom"]
            for bottomIndex in range(0, len(bottoms)):
                bottom = bottoms[bottomIndex]
                if bottom in blobOrder:
                    topBlobList = blobOrder[bottom]
                    phaseDict = topBlobList[0]
                    if "" in phaseDict:
                        LayerHelper.__addConnection(phaseDict[""], layerID, bottomIndex, bottom, connections, layerDict)
                        LayerHelper.__removeBlobPhaseFromDict("", bottom, blobOrder)
                    elif LayerHelper.getLayerPhase(layer) == "":
                        for topPhase, topLayerID in phaseDict.iteritems():
                            LayerHelper.__addConnection(topLayerID, layerID, bottomIndex, bottom, connections, layerDict)
                            LayerHelper.__removeBlobPhaseFromDict(topPhase, bottom, blobOrder)
                    else:
                        phase = LayerHelper.getLayerPhase(layer)
                        for topPhase, topLayerID in phaseDict.iteritems():
                            if phase == topPhase:
                                LayerHelper.__addConnection(topLayerID, layerID, bottomIndex, bottom, connections, layerDict)
                                LayerHelper.__removeBlobPhaseFromDict(topPhase, bottom, blobOrder)



    @staticmethod
    def __addConnection(topLayerID, bottomLayerID, bottomBlobIndex, blobName, connections, layerDict):
        topBlobIndex = LayerHelper.getTopBlobIndex(layerDict[topLayerID], blobName)
        connections.append((topLayerID, topBlobIndex, bottomLayerID, bottomBlobIndex))
        return

    @staticmethod
    def __removeBlobPhaseFromDict(phase, top, blobOrder):
        blobList = blobOrder[top]
        if len(blobList) > 1:
            phaseDict = blobList[0]
            if "" in phaseDict:
                del phaseDict[""]
            elif phase in blobList[1]:
                del phaseDict[phase]
                
            if len(phaseDict) == 0:
                del blobList[0]

class OrderedLayersByBlob:
    def __init__(self, layerDict, layerOrder):
        self.blobLayerDict = dict()
        self.__createOrderedLayerListPerBlob(layerDict, layerOrder)

    def __createOrderedLayerListPerBlob(self, layerDict, layerOrder):
        for layerID in layerOrder:
            layer = layerDict[layerID]
            self.__addLayerToDict(layer, layerID)

    def __addLayerToDict(self, layer, layerID):
        if "top" in layer["parameters"]:
            for top in layer["parameters"]["top"]:
                self.__addTopBlobLayer(top, layer, layerID)

    def __addTopBlobLayer(self, top, layer, layerID):
        if top in self.blobLayerDict:
            if LayerHelper.isLayerInPlaceForBlob(layer, top):
                if len(self.blobLayerDict[top]) > 1:
                    currentLevelDict = self.blobLayerDict[top][-1]
                    if "" in currentLevelDict or LayerHelper.getLayerPhase(layer) in currentLevelDict:
                        self.__createDictForTop(top, layer, layerID)
                    else:
                        currentLevelDict[LayerHelper.getLayerPhase(layer)] = layerID
                else:
                    self.__createDictForTop(top, layer, layerID)
            else:
                self.blobLayerDict[top][0][LayerHelper.getLayerPhase(layer)] = layerID
        else:
            self.blobLayerDict[top] = list()
            self.__createDictForTop(top, layer, layerID)

    def __createDictForTop(self, top, layer, layerID):
        tempDict = dict()
        tempDict[LayerHelper.getLayerPhase(layer)] = layerID
        self.blobLayerDict[top].append(tempDict)
