'''
Created on 18.11.2016

@author: k.Hartz
'''

import itertools
import os
import re

from backend.parser.parser_listener import ParserListener

from backend.barista.utils.logger import Log
from backend.parser.parser import Parser


class Concatenator:
    '''
    Concatenates multiple logfiles (with same snapshot-file) to one iterator
    '''

    def __init__(self, listOfLogfiles):
        '''
        Initializes the concatinator with a list of Logfiles
        to get a list of iterators concerning to the merged logs
        call concate()
        '''

        self.__listeners = []
        events = {
            Concatenator.finish: re.compile('Optimization Done.'),
            Concatenator.interrupt: re.compile(
                "((?:Snapshotting solver state to (?:binary proto|HDF5) file ).*)"),
            Concatenator.resume: re.compile("((?<= Resuming from ).*)"),
            }

        for logFile in listOfLogfiles:
            log_iter = self.__createIterFromFile(logFile)
            parser = Parser(log_iter, events)
            listener = Concatenator.SnapshotListener(logFile)
            parser.addListener(listener)
            try:
                parser.parseLog()
                self.__listeners.append(listener)
            except:
                callerId = Log.getCallerId("Error Parsing Log File:" + str(logFile))
                Log.error("", callerId)

    def createSingleLogfile(self, filePath, logfileName, stream=None):
        '''
        creates one logfile for each Training
        returns amount of created files or -1 for none
        '''
        if(stream is not None):
            fullIter = [self.concateWithStream(stream)]
        else:
            fullIter = self.concate()

        i = -1
        for itera in fullIter:
            i += 1
            with open(filePath + logfileName + str(i) + '.log', 'w') as f:
                for line in itera:
                    f.write(str(line))
        return i+1

    # TODO: Test
    def concateWithStream(self, stream):
        '''
        concatenates (only!) the first (concatenated) logfile
        with the given stream to an iterator, first the logfiles
        than the stream
        '''
        return itertools.chain(iter(self.concate()[0]), stream)

    def concate(self):
        '''
        concatenate the logfiles into one iterator
        returns an array of concatenated iterators
        every iterator represents one training
        '''
        if(len(self.__listeners) == 1):
            return [self.__listeners[0].filePath]

        listenerRange = range(0, len(self.__listeners))
        for i in listenerRange:
            for j in listenerRange:  # TODO can start from i ... length
                if(i != j and (self.__listeners[i].groupId == -1 or self.__listeners[j].groupId == -1 ) and
                   self.__fromSameTraining(i, j)):
                    self.__setGroupId(i, j)
        for i in listenerRange:
            if(self.__listeners[i].groupId == -1):
                self.__setGroupId(i, i)

        listenerGroups = self.__groupListeners()
        return self.__createAndConcateIters(listenerGroups)

    # Training Interrupted, snapshot is made
    __groupIdCounter = 0

    # ------EVENT CONSTANTS-----
    # Training Completet (Caffe exited)
    finish = 'Finished'
    # Training Resumed from snapshot
    resume = 'Resume'
    # Training Interrupted, snapshot is made
    interrupt = 'Interrupted'

    class SnapshotListener(ParserListener):
        '''
        Listener for Logfile-Parser, looks for properties
        that are needed to determine which logs should
        concate
        '''

        def __init__(self, logfilePath):
            # id to put listeners together
            self.groupId = -1
            # to be able to create an iter from this listener
            self.filePath = logfilePath
            # to identify the listeners ancestor
            self.logname = self.__getFileName(logfilePath)
            # has finished parsing
            self.finish = False

            # has been resumed from another session
            self.resume = False
            # hasSnapshot
            self.hasSnapshot = False
            self.snapshotName = ""
            # the name of the resumed snapshot file
            self.snapshotResumeName = ""

            # start iteration count
            self.iterationMin = -1
            # finished iteration count
            self.iterationMax = -1

        def update(self, phase, row):
            if phase == "TRAIN":
                iterations = row.get('NumIters')
                if iterations > self.iterationMax:
                    self.iterationMax = int(iterations)
                if self.iterationMin == -1:
                    self.iterationMin = int(iterations)

        def handle(self, event, message, groups):
            '''
            handles events: finish,interrupt,resume
            '''
            if(event == Concatenator.finish):
                self.finish = True
            elif(event == Concatenator.interrupt):
                self.hasSnapshot = True
                self.snapshotName = groups[0].strip()
            elif(event == Concatenator.resume):
                self.hasSnapshot = True
                self.snapshotResumeName = groups[0].strip()

        def __getFileName(self, filePath):
            '''
            extracts the filename from a filepath
            '''
            _, tail = os.path.split(str(filePath))
            return tail

    # ----------Private Methods-------------

    def __fromSameTraining(self, i, j):
        '''
        returns boolean indicating whether index i and j
        are from the same training
        '''
        iListener = self.__listeners[i]
        jListener = self.__listeners[j]

        # Merge every log
        if(False):
            return True

        # have snapshots?
        if not(iListener.hasSnapshot and
               jListener.hasSnapshot):
            return False

        # Same snapshotname?
        if(iListener.snapshotName != jListener.snapshotResumeName and
           jListener.snapshotName != iListener.snapshotResumeName):
            return False

        range1 = range(iListener.iterationMin,
                       iListener.iterationMax)
        range2 = range(jListener.iterationMin,
                       jListener.iterationMax)

        # Iterations doesnt have intersect
        if(len(set(range1).intersection(range2)) > 1):
            return False

        return True

    def __setGroupId(self, i, j):
        '''
        Sets the same group id for index i,j in
        self.__listeners
        '''
        if self.__listeners[i].groupId != -1:
            self.__listeners[j].groupId = self.__listeners[i].groupId
            return

        if self.__listeners[i].groupId != -1:
            self.__listeners[j].groupId = self.__listeners[i].groupId
            return

        Concatenator.__groupIdCounter += 1
        self.__listeners[j].groupId = Concatenator.__groupIdCounter
        self.__listeners[j].groupId = Concatenator.__groupIdCounter

    def __groupListeners(self):
        '''
        groups the listeners by id and sorts them
        by the startiterations
        '''

        self.__listeners.sort(key=lambda listener:
                              (listener.groupId, listener.iterationMin))
        listenerGroups = itertools.groupby(self.__listeners,
                                           lambda listener: (listener.groupId))
        sortedList = []
        for _, group in listenerGroups:
            group = list(group)
            sortedList.append(group)

        return sortedList

    def __createAndConcateIters(self, listenerGroups):
        '''
        creates an iterator for every
        '''
        iterators = []
        for group in listenerGroups:
            for listener in group:
                itera = listener.filePath
                iterators.append(itera)

        # for i in range(0, len(iterators)):
        #     iterators[i] = fileinput.input(iterators[i])

        return iterators

    def __createIterFromFile(self, filePath):
        '''
        creates an iterator for a logfile
        for a given path
        '''
        return (open(filePath))
