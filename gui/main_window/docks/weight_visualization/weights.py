# from https://www.eriksmistad.no/visualizing-learned-features-of-a-caffe-neural-network/

import numpy as np



def loadNetParameter(caffemodel):
    """ Return a NetParameter protocol buffer loaded from the caffemodel.
    """
    from backend.caffe.path_loader import PathLoader
    proto = PathLoader().importProto()
    net = proto.NetParameter()

    try:
        with open(caffemodel, 'rb') as f:
            net.ParseFromString(f.read())
            return net
    except:
        pass

def loadNetParamFromString(paramstring):
    from backend.caffe.path_loader import PathLoader
    proto = PathLoader().importProto()
    net = proto.NetParameter()
    try:
        net.ParseFromString(paramstring)
        return net
    except:
        pass

def calculateConvWeights(net, layer_name, padding=2):
    """ Return a grayscale image array which displays the weights of the
    convolutional layer in the net.
    """
    for layer in net.layer:
        if layer.name == layer_name:
            for blob in layer.blobs:
                if len(blob.shape.dim) == 4:
                    # The parameters are a list of [weights, biases]
                    data = np.copy(blob.data).reshape(blob.shape.dim)
                    # N is the total number of convolutions
                    N = blob.shape.dim[0]*blob.shape.dim[1]
                    # Ensure the resulting image is square
                    filters_per_row = int(np.ceil(np.sqrt(N)))
                    # Assume the filters are square
                    filter_size = blob.shape.dim[2]
                    # Size of the result image including padding
                    result_size = filters_per_row*(filter_size + padding) - padding
                    # Initialize result image to all zeros
                    result = np.zeros((result_size, result_size))

                    # Tile the filters into the result image
                    filter_x = 0
                    filter_y = 0
                    for n in range(blob.shape.dim[0]):
                        for c in range(blob.shape.dim[1]):
                            if filter_x == filters_per_row:
                                filter_y += 1
                                filter_x = 0
                            for i in range(filter_size):
                                for j in range(filter_size):
                                    x = filter_y*(filter_size + padding) + i
                                    y = filter_x*(filter_size + padding) + j
                                    result[x, y] = data[n, c, i, j]
                            filter_x += 1

                    # Normalize image to 0-1
                    min = result.min()
                    max = result.max()
                    result = (result - min) / (max - min)
                    return result
