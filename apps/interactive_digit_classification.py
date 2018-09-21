#! /usr/bin/env python

"""
This is a small self-contained application that demonstrates usage of networks deployed from Barista
in other applications. If net definition and weight's files obtained by training the caffe mnist example
are supplied via command line parameters, the user can draw digits [0-9] in the window, use the net
to classify the result and print the result to stdout.
- Drawing works by pressing the left mouse button and moving the mouse
- The "Return"-Button grabs the image and starts the classification
- The "Backspace"-Button clears the image.
"""
#
#
# Python package dependencies:
#   pygame
#   caffe
#   numpy

import pygame
import caffe
import numpy as np
import argparse

# Argument parsing
parser = argparse.ArgumentParser(description='Interactively classify handwritten digits using neural nets.', epilog=__doc__, formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument('-m', '--model', help='Model (.prototxt) file', type=str, required=True)
parser.add_argument('-w', '--weights', help='Weights (.caffemodel) file', type=str, required=True)
args = parser.parse_args()


#######################################################
# Setup caffe for classification
#######################################################

#load the model
net = caffe.Net(args.model, args.weights, caffe.TEST)

# load input and configure preprocessing
transformer = caffe.io.Transformer({'data': net.blobs['data'].data.shape})
transformer.set_transpose('data', (2,0,1))
transformer.set_raw_scale('data', 1.0)

# Change the batch size to a single image
net.blobs['data'].reshape(1,1,28,28)

#######################################################
# Proprecessing helper functions
#######################################################

# Find the required offset (i.e. difference between center of weight and center of the image)
def find_offset(grid):
    x_acc = 0;
    y_acc = 0;
    h = grid.shape[0]
    w = grid.shape[1]
    num_points = 0;
    for y in np.arange(h):
        for x in np.arange(w):
            val = (grid[y,x] > 0)
            x_acc += (x-w/2.0) * val
            y_acc += (y-h/2.0) * val
            if val:
                num_points += 1
    if num_points == 0:
        return (0,0)
    x_acc /= num_points
    y_acc /= num_points
    return (y_acc, x_acc)

# Shift and resample values in grid and thus centering the center of weight in the center of the image
def shift(grid):
    offset = find_offset(grid)

    h = grid.shape[0]
    w = grid.shape[1]
    image = np.zeros((h, w, 1))
    for y in np.arange(h):
        for x in np.arange(w):
            x_n = int(np.round(x+offset[1]))
            y_n = int(np.round(y+offset[0]))
            if x_n < 0 or x_n >= w:
                val = 0
            elif y_n < 0 or y_n >= h:
                val = 0
            else:
                val = grid[y_n,x_n]
            image[y,x] = val
    return image

# Classify a given image and output the index of the class with the highest probability according to the net and caffe
def classify(pixels):
    image = np.zeros((pixels.shape[0], pixels.shape[1], 1))
    image[:,:,0] = pixels[:,:]
    image = np.transpose(image, (1,0,2))
    image = shift(image)
    data = np.asarray([transformer.preprocess('data', image)])

    out = net.forward_all(data = data)

    prob = out['probabilities']
    cls = prob.argmax()
    return cls


#######################################################
# Pygame application stuff
#######################################################

# Create screen of specified size
screen_size = (112,112)
screen = pygame.display.set_mode(screen_size)

# Global variables/constants used for drawing
currently_drawing = False
last_pos = (0, 0)
draw_color = (255, 255, 255)
clear_color = (0, 0, 0)
brush_radius = 3

# draw a line of circles from start to finish
def roundline(srf, color, start, end, radius):
    dx = end[0]-start[0]
    dy = end[1]-start[1]
    distance = max(abs(dx), abs(dy))
    for i in range(distance):
        x = int( start[0]+float(i)/distance*dx)
        y = int( start[1]+float(i)/distance*dy)
        pygame.draw.circle(srf, color, (x, y), radius)

try:
    while True:
        e = pygame.event.wait()
        if e.type == pygame.QUIT:
            raise StopIteration
        if e.type == pygame.MOUSEBUTTONDOWN:
            pygame.draw.circle(screen, draw_color, e.pos, brush_radius)
            currently_drawing = True
        if e.type == pygame.MOUSEBUTTONUP:
            currently_drawing = False
        if e.type == pygame.MOUSEMOTION:
            if currently_drawing:
                pygame.draw.circle(screen, draw_color, e.pos, brush_radius)
                roundline(screen, draw_color, e.pos, last_pos,  brush_radius)
            last_pos = e.pos
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_RETURN:
                array = pygame.PixelArray(screen)
                cls = classify(array)
                print("The net says says: {}".format(cls))
            if e.key == pygame.K_BACKSPACE:
                screen.fill(clear_color)
        pygame.display.flip()

except StopIteration:
    pass

pygame.quit()
