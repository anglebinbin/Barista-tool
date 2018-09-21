"""
COPYRIGHT

All contributions by the University of California:
Copyright (c) 2014, 2015, The Regents of the University of California (Regents)
All rights reserved.

All other contributions:
Copyright (c) 2014, 2015, the respective contributors
All rights reserved.

Caffe uses a shared copyright model: each contributor holds copyright over
their contributions to Caffe. The project versioning records all such
contribution and copyright details. If a contributor wants to further mark
their specific copyright on a particular contribution, they should indicate
their copyright solely in the commit message of the change when it is
committed.

LICENSE

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

CONTRIBUTION AGREEMENT

By contributing to the BVLC/caffe repository through pull-request, comment,
or otherwise, the contributor releases their content to the
license and copyright terms herein.
"""

import re
import sys
if sys.version_info[0] == 2:
    from Queue import Queue
else:
    from queue import Queue
from collections import OrderedDict
from threading import Lock

from backend.parser import extract_seconds as exs
from backend.barista.utils.logger import Log
from backend.parser.parser_common import ParserCommon

from PyQt5.QtCore import pyqtSignal
from PyQt5.Qt import QObject


class Parser(QObject, ParserCommon):
    """ Log File Parser.

    This class takes a stream of log messages and parses them on parseLog().
    A listener could be registered for parsing events like log records,
    exceptions and new keys.
    """

    printLogSignl = pyqtSignal(str, bool)

    def __init__(self, log_stream, events, log_id=None):
        super(Parser, self).__init__()
        self.train_dict_list = []
        self.test_dict_list = []
        self.log_stream = log_stream
        self.thread_id = None
        self.start_time = None
        self.log_id = log_id
        self.logging = False
        self.streams = Queue()
        self.lock = Lock()
        if self.log_stream:
            self.streams.put(self.log_stream)
        self.events = events
        if self.events is None:
            self.events = {}

    def printLog(self, log, error=False):
        if self.log_id is not None:
            if not error:
                Log.log(log, self.log_id)
            else:
                Log.error(log, self.log_id)
        else:
            self.printLogSignl.emit(log, error)

    def getTestEvents(self):
        """Return the list of parsed test records."""
        return self.test_dict_list

    def getTrainEvents(self):
        """Return the list of parsed training records."""
        return self.train_dict_list

    def getThreadID(self):
        """ Return the thread id of the caffe process.
        """
        return self.thread_id

    def addLogStream(self, log_stream):
        """ Add a log stream to to queue of parsing tasks.
        """
        if log_stream:
            self.streams.put(log_stream)

    def setLogging(self, log):
        self.logging = log

    def parseLog(self):
        """Parse log file.

        Returns (train_dict_list, test_dict_list)
        train_dict_list and test_dict_list are lists of dicts that define the
        table rows
        """
        locked = self.lock.acquire()
        if locked is False:
            return self.train_dict_list, self.test_dict_list

        regex_iteration = re.compile('Iteration (\d+)')
        regex_train_output = re.compile(
            'Train net output #(\d+): (\S+) = ([\.\deE+-]+)')
        regex_test_output = re.compile(
            'Test net output #(\d+): (\S+) = ([\.\deE+-]+)')
        regex_learning_rate = re.compile(
            'lr = ([-+]?[0-9]*\.?[0-9]+([eE]?[-+]?[0-9]+)?)')

        # Pick out lines of interest
        iteration = -1
        learning_rate = float('NaN')
        train_dict_list = self.train_dict_list
        test_dict_list = self.test_dict_list
        train_row = None
        test_row = None
        try:
            while self.streams.empty() is False:
                head = self.streams.get()
                log_file = None
                ht = type(head)
                if ht is unicode or ht is str:
                    # open file
                    log_file = open(head, 'r')
                    log_stream = log_file.readlines()
                else:
                    log_stream = head
                try:
                    logfile_year = exs.getLogCreatedYear(log_stream)
                    for line in log_stream:
                        line = line.strip()
                        if self.logging:
                            self.printLog(line)
                        if self.thread_id is None:
                            self.extractThreadID(line)
                        if self.start_time is None:
                            self.start_time = exs.getStartTime(line,
                                                               logfile_year)
                        self.parseEvent(line)


                        iteration_match = regex_iteration.search(line)
                        if iteration_match:
                            iteration = float(iteration_match.group(1))
                        if iteration == -1:
                            # Only start parsing for other stuff if we've
                            # found the first iteration
                            continue
                        if exs.isLogFormat(line) is False:
                            continue

                        if self.start_time is None:
                            self.start_time = exs.extractDatetimeFromLine(line,
                                                          logfile_year)
                        time = exs.extractDatetimeFromLine(line,
                                                          logfile_year)
                        seconds = (time - self.start_time).total_seconds()

                        lr_match = regex_learning_rate.search(line)
                        if lr_match:
                            self.checkKey(Parser.TRAIN, 'LearningRate')
                            learning_rate = float(lr_match.group(1))

                        train_dict_list, train_row = self.parseLine(
                            regex_train_output, train_row, train_dict_list,
                            line, iteration, seconds, learning_rate, time,
                            Parser.TRAIN
                        )
                        test_dict_list, test_row = self.parseLine(
                            regex_test_output, test_row, test_dict_list,
                            line, iteration, seconds, learning_rate, time,
                            Parser.TEST
                        )
                except Exception as e:
                    self.printLog('Parser error: '+str(e))
                finally:
                    if log_file:
                        log_file.close()
        except Exception as e:
            if self.log_id:
                self.printLog('Failed to parse log '+str(e), True)
            else:
                print('Failed to parse log '+str(e))
        finally:
            if locked:
                self.lock.release()
        for lis in self.listener:
            lis.parsingFinished()
        return train_dict_list, test_dict_list

    def parseLine(self, regex_obj, row, row_dict_list, line, iteration,
                  seconds, learning_rate, time, phase):
        """Parse a single line for training or test output.

        Returns a a tuple with (row_dict_list, row)
        row: may be either a new row or an augmented version of the current row
        row_dict_list: may be either the current row_dict_list or an augmented
        version of the current row_dict_list
        """

        output_match = regex_obj.search(line)
        if output_match:
            if not row or row['NumIters'] != iteration:
                # Push the last row and start a new one
                if row:
                    # If we're on a new iteration, push the last row
                    # This will probably only happen for the first row;
                    # otherwisethe full row checking logic below will push and
                    # clear full rows
                    row_dict_list.append(row)

                row = OrderedDict([
                    ('NumIters', iteration),
                    ('Seconds', seconds),
                    ('LearningRate', learning_rate),
                    ('DateTime', time)
                ])

            # output_num is not used; may be used in the future
            # output_num = output_match.group(1)
            output_name = output_match.group(2)
            output_val = output_match.group(3)
            row[output_name] = float(output_val)
            self.checkKey(phase, output_name)
        # append a new row to the dict
        if (row and
                len(row_dict_list) >= 1 and
                len(row) == len(row_dict_list[0])):
            # fix the learning rate of the first row
            if len(row_dict_list) == 1:
                row_dict_list[0]['LearningRate'] = row['LearningRate']
                for lis in self.listener:
                    lis.update(phase, row_dict_list[0])
            # The row is full, based on the fact that it has the same number of
            # columns as the first row; append it to the list
            row_dict_list.append(row)
            # notify the listener about the new row
            for lis in self.listener:
                lis.update(phase, row)
            row = None

        return row_dict_list, row

    def parseEvent(self, line):
        """Parse the line for events.

        Notifies the listener about every event found.
        """
        for event, regex in self.events.iteritems():
            event_match = regex.search(line)
            if event_match:
                size = len(event_match.groups())
                groups = []
                for i in range(0, size):
                    groups.append(event_match.group(i+1))
                for lis in self.listener:
                    lis.handle(event, line, groups)

    def extractThreadID(self, line):
        """ Extract the thread id from the file.
        """
        regex_thread_id = re.compile(
            '[IWEF][\d]{4} [\d]{2}:[\d]{2}:[\d]{2}\.[\d]{6}[\s]+([\d]+)')
        line = line.strip()
        thread_id_match = regex_thread_id.search(line)
        if thread_id_match:
            self.thread_id = thread_id_match.group(1)

    def checkKey(self, phase, key):
        """ Check wheter the key is new and notify the listener in this case.
        """
        if key == "lr":
            key = "LearningRate"
        key_registry = self.getKeys(phase)
        if key not in key_registry:
            key_registry.append(key)
            for lis in self.listener:
                lis.registerKey(phase, key)

    def hasKey(self, phase, key):
        """ Return true if the key was registered for the phase.
        """
        return key in self.getKeys(phase)
