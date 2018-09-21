# from https://www.eriksmistad.no/visualizing-learned-features-of-a-caffe-neural-network/
# test code, will be changed
from backend.caffe.path_loader import PathLoader
caffe = PathLoader().importCaffe()

from gui.main_window.docks.weight_visualization import visualize_weights

# Load model
net = caffe.Net('/Users/sandtil/Documents/Developer/pyenv/Barista/test/examples/mnist/sessions/20161221_151232_203/net.prototxt',
                '/Users/sandtil/Documents/Developer/pyenv/Barista/test/examples/mnist/sessions/20161221_151232_203/snapshots/lenet_iter_10000.caffemodel',
                caffe.TEST)

visualize_weights(net, 'conv1', filename='conv1')
#visualize_weights(net, 'conv2', filename='conv2.png')
