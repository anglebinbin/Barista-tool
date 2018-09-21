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

from datetime import datetime


def extractDatetimeFromLine(line, year):
    """Extract the datetime from the line.

    Returns the parsed datetime with the added year.
    """
    # Expected format:
    # I0210 13:39:22.381027 2521 solver.cpp:204]
    line = line.strip().split()
    month = int(line[0][1:3])
    day = int(line[0][3:])
    timestamp = line[1]
    pos = timestamp.rfind('.')
    ts = [int(x) for x in timestamp[:pos].split(':')]
    hour = ts[0]
    minute = ts[1]
    second = ts[2]
    microsecond = int(timestamp[pos + 1:])
    dt = datetime(year, month, day, hour, minute, second, microsecond)
    return dt


def getLogCreatedYear(input_file):
    """Get year from log file start time.

    Search for 'Log file created at:'
    Use current year if the string can not be found.
    """

    regex_year = re.compile('Log file created at: ([\d]{4})')
    for line in input_file:
        year_match = regex_year.search(line)
        if year_match:
            return int(year_match.group(1))
        if isLogFormat(line):
            now = datetime.now()
            return now.year


def getStartTime(line, year):
    """Find start time in the line.
    """

    if line.find('Solving') != -1:
        return extractDatetimeFromLine(line, year)

regex_log_msg = re.compile(
    '[IWEF][\d]{4} [\d]{2}:[\d]{2}:[\d]{2}\.[\d]{6}[\s]+[\d]+[\s]+[\w\.]+:[\d]+\]')


def isLogFormat(line):
    """ Return True if the line has the log format.
    """
    log_match = regex_log_msg.search(line)
    if log_match:
        return True
    else:
        return False
