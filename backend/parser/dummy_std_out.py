'''
Created on 08.11.2016

@author: k.hartz
'''
import os

import time
import sys


# Logfile to pass through stdout
logFile = "test/logfiles/test_log_1.log"
# delay per line in sec, 1=1sec
delayPerLine = 0.01

# Seperator to seperate the logfile output from print
seperator = "------------------"
# directory where this file is contained
dir_path = os.path.dirname(os.path.realpath(__file__))
# working directory
cwd = os.getcwd()

print("Start Output:\n\n")
print("working directory:", cwd)
print("directory where this file is contained:", dir_path)
print(seperator)

f = open(logFile)

for line in f:
    sys.stdout.write(line)
    sys.stdout.flush()
    time.sleep(delayPerLine)

print(seperator)

print("Finished log")
