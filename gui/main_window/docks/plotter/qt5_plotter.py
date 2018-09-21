import csv
import time
import seaborn
from collections import OrderedDict

from PyQt5 import QtCore
from PyQt5.QtWidgets import QVBoxLayout, QWidget, QFrame
from backend.parser.parser_listener import ParserListener

from backend.parser.parser import Parser
from backend.parser.parser_dummy import ParserDummy
from gui.main_window.docks.plotter.plot_canvas import PlotCanvas


# Own class for plotter
# Select Train/Test
# Select one or more value types: training rate, acc0, acc1, loss
# Plot against time or iteration
# Label the coordinates
# More features? Multiple Plots...


class Qt5Plotter(QFrame):
    """
    This plotter takes a list of dictionaries as input and plottes
    selected data
    """

    # available metrics
    global TIME, ITERATION, LEARNING_RATE
    TIME = "Seconds"
    ITERATION = "NumIters"
    LEARNING_RATE = "LearningRate"

    # How will be plottet? Time <-> Iterations, Linear <-> Logarithmic
    __againstTime = False
    __logarithmic = False

    # Each parser (i.e. log) has a list of metrics of train and test values
    # that the user wants to be plotted
    # Each list entry is a set of the metric that will be plotted
    # logId -> {metric}
    __testMetrics = OrderedDict()
    __trainMetrics = OrderedDict()

    # Each parser (i.e. log) has a list of train and test data
    # Each list entry is again a dictionary of the parsed key-value-pairs
    # logId -> [key -> value]
    __trainData = OrderedDict()
    __testData = OrderedDict()

    # Logs can be plotted with an offset in time/iterations
    # This is a usefull parameter for concatenating logs
    __timeOffsets = OrderedDict()
    __iterationOffsets = OrderedDict()

    # The list of parsers corresponds to the list of logs that are observed.
    # Each log (file or stream) must be added using a parser
    # logId -> parser
    __parsers = OrderedDict()
    __listener = OrderedDict()

    __plotterGUI = None

    class ParserConnection(ParserListener):
        """
        Implements the required methods for the ParserListener so that the
        parsed data can be added to the data that will be plotted.
        """

        def __init__(self, logId, testData, trainData, plotter, plotOnUpdate=False):
            """
            Register the test and train data lists of the plotter. Optionaly
            set plotOnUpdate to True to replot the data every time the parser
            reads a new row and triggers an update.
            """
            self.logId = logId
            self.plotter = plotter
            self.testData = testData
            self.trainData = trainData
            self.plotOnUpdate = plotOnUpdate

        def update(self, phase, row):
            """
            Pass the update signal to the plotter. Replot if that is wanted.
            """
            if phase == "TEST":
                self.testData.append(row)
            if phase == "TRAIN":
                self.trainData.append(row)
            if self.plotOnUpdate:
                self.plotter.plot(False, [self.logId])

        def handle(self, event, message, groups):
            # Ignore event.
            # Not the plotters business.
            pass

        def registerKey(self, phase, key):
            """
            Pass the signal to the gui so that it can create a new checkbox for the key.
            """
            gui = self.plotter.getPlotterGUI()
            if gui:
                gui.registerKeySignal.emit(self.logId, phase, key)

    # end ParserConnection



    def __init__(self, parent=None):
        super(Qt5Plotter, self).__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)

        # this is the Canvas Widget that displays the `figure`
        self.canvas = PlotCanvas(self)

        # this is the Navigation widget
        # it takes the Canvas widget and a parent
#        self.toolbar = NavigationToolbar(self.canvas, self)

        # set the layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
#        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    def resizeEvent(self, event):
        # This keeps the plot area as large as possible even after resizing the widget
        try:
            self.canvas.fig.tight_layout()
        except:
            pass

    def setPlotterGUI(self, plotterGUI):
        self.__plotterGUI = plotterGUI

    def getPlotterGUI(self):
        return self.__plotterGUI

    def getParser(self, logId):
        """
        Get the parser that corresponds to the given log name.
        """
        return self.__parsers[logId][1]

    def putLog(self, logId, logName, parser, plotOnUpdate=False, timeOffset=0, iterationOffset=0):
        """
        Add a new log to be plotted. A log is added by adding a parser that
        reads the log file/stream. A logId is used to identify the
        logs/parsers

        It is possible to add offset values for time and iteration numbers
        This is usually only interesting for the time, e.g. if a training is
        interruped and resumed (usually the iteration number in the log-file
        is still constistent.
        """
        if (isinstance(parser, Parser) | isinstance(parser, ParserDummy)) & isinstance(logId, str):
            self.__testData[logId] = []
            self.__trainData[logId] = []
            self.__testMetrics[logId] = []
            self.__trainMetrics[logId] = []
            self.__timeOffsets[logId] = timeOffset
            self.__iterationOffsets[logId] = iterationOffset
            self.__listener[logId] = self.ParserConnection(
                               logId,
                               self.__testData[logId],
                               self.__trainData[logId],
                               self,
                               plotOnUpdate)
            parser.addListener(self.__listener[logId])
            self.__parsers[logId] = [logName, parser]

    def removeLog(self, logId):
        """
        Remove the given log from the plot.
        """
        if logId:
            if logId in self.__parsers:
                if logId in self.__listener:
                    self.__parsers[logId][1].removeListener(self.__listener[logId])
                self.__parsers.pop(logId)

    def showMetricTest(self, logId, metric, show=True):
        """
        Add a metric to the test plot if show is true, otherwise remove
        the metric. logId is the name of the logfile which is plotted.
        """
        if logId not in self.__testMetrics:
            return
        if show and metric not in self.__testMetrics[logId]:
            self.__testMetrics[logId].append(metric)
        elif not show and metric in self.__testMetrics[logId]:
            self.__testMetrics[logId].remove(metric)

    def isMetricTestShown(self, logId, metric):
        return metric in self.__testMetrics[logId]

    def showMetricTrain(self, logId, metric, show=True):
        """
        Add a metric to the train plot if show is true, otherwise remove
        the metric. logId is the name of the logfile which is plotted.
        """
        if logId not in self.__testMetrics:
            return
        if show and metric not in self.__trainMetrics[logId]:
            self.__trainMetrics[logId].append(metric)
        elif not show and metric in self.__trainMetrics[logId]:
            self.__trainMetrics[logId].remove(metric)

    def isMetricTrainShown(self, logId, metric):
        return metric in self.__trainMetrics[logId]

    def plotAgainstTime(self):
        self.__againstTime = True

    def plotAgainstIterations(self):
        self.__againstTime = False

    def plotLogarithmic(self):
        self.__logarithmic = True

    def plotLinear(self):
        self.__logarithmic = False

    #
    # Some helping methodes for the plotting # # # # # # # # # # # #
    #

    def __xLabel(self):
        if self.__againstTime:
            return "Time (in s)"
        else:
            return "Iterations"

    def __xValues(self, dictList, logId, againstTime):
        xValues = []
        if againstTime:
            for dict in dictList:
                xValues.append(dict.get(TIME) + self.__timeOffsets[logId])
        else:
            for dict in dictList:
                xValues.append(dict.get(ITERATION) +
                               self.__iterationOffsets[logId])
        return xValues

    def __yValues(self, dictList, showMetrics):
        yValues = []
        for record in dictList:
            values = []
            for metric in showMetrics:
                values.append(record.get(metric))
            yValues.append(values)
        return yValues


    # Count the metrics the user wants to plot
    def numGraphs(self):
        numGraphs = 0
        for logId in self.__parsers:
            numGraphs = numGraphs + len(self.__trainMetrics[logId]) + len(self.__testMetrics[logId])
        return numGraphs

    def plot(self, evenIfThereIsNothingToPlot = True, updateOnly = None):
        """
        Plot the data. This method will don't call the final plot function of the actual
        plotting library if there is no data selected for plotting. Otherwise there could
        result an unpretty visual flickering in the widget.
        One can plot anyway by setting the first parameter to False. In addition one can
        further specify which logs should be checked in order to avoid unnecessary replotting.
        """
        # Count the metrics the user wants to plot
        # Only plot it if the number is greater than 0 or if the user wants to plot the empty plot
        numGraphs = 0
        relevantParsers = self.__parsers
        if updateOnly is not None:
            relevantParsers = updateOnly
        for logId in relevantParsers:
            numGraphs = numGraphs + len(self.__trainMetrics[logId]) + len(self.__testMetrics[logId])
        if numGraphs == 0 and not evenIfThereIsNothingToPlot:
            return

        # Begin plotting
        self.canvas.clear()
        lines = []
        labels = []
        for logId in self.__parsers:
            if len(self.__trainMetrics[logId]) != 0:
                xValues = self.__xValues(self.__trainData[logId], logId, self.__againstTime)
                yValues = self.__yValues(self.__trainData[logId],
                                         self.__trainMetrics[logId])
                lines.extend(self.canvas.plotDictList(xValues, yValues, self.__logarithmic))
                train = lambda s: self.__parsers[logId][0] + ".train." + s
                labels.extend(map(train, self.__trainMetrics[logId]))
            if len(self.__testMetrics[logId]) != 0:
                xValues = self.__xValues(self.__testData[logId], logId, self.__againstTime)
                yValues = self.__yValues(self.__testData[logId],
                                         self.__testMetrics[logId])
                lines.extend(self.canvas.plotDictList(xValues, yValues, self.__logarithmic))
                test = lambda s: self.__parsers[logId][0] + ".test." + s
                labels.extend(map(test, self.__testMetrics[logId]))
        self.canvas.legend(lines, labels)
        try:
            self.canvas.draw()
        except:
            pass

    def getLastTimeValue(self, logId, ofTestData=False):
        if ofTestData:
            return self.__testData[logId][-1][TIME]
        else:
            return self.__trainData[logId][-1][TIME]

    def getLastIterationValue(self, logId, ofTestData=False):
        if ofTestData:
            return self.__testData[logId][-1][ITERATION]
        else:
            return self.__trainData[logId][-1][ITERATION]

    # Methods for CSV export # # # # # # # # # # # # # # # # # # # # # # #

    def __arrayToString(self, array, delimiter):
        if array is None or len(array) == 0:
            return ""
        else:
            string = array[0]
            for i in range(1, len(array)):
                string = string + delimiter + " " + array[i]
            return string

    def exportCSVToFile(self, path):
        if not path:
            return
        with open(path, 'wb') as csvfile:
            spamwriter = csv.writer(csvfile, delimiter=';',
                            quotechar='|', quoting=csv.QUOTE_MINIMAL)
            spamwriter.writerow(["# Barista CSV-Export (" + time.ctime() + ")"])

            for logId in self.__parsers:
                names = []
                if len(self.__trainMetrics[logId]) != 0:
                    xIterValues = self.__xValues(self.__trainData[logId], logId, False)
                    xTimeValues = self.__xValues(self.__trainData[logId], logId, True)
                    yValues = self.__yValues(self.__trainData[logId],
                                         self.__trainMetrics[logId])
                    train = lambda s: self.__parsers[logId][0] + ".train." + s
                    names = map(train, self.__trainMetrics[logId])
                    spamwriter.writerow([])
                    spamwriter.writerow([])
                    spamwriter.writerow(["# " + self.__parsers[logId][0] + " TRAIN"])
                    row = ["Iterations", "Time"]
                    row.extend(names)
                    spamwriter.writerow(row)
                    for i in range(0, len(xIterValues)):
                        row = [xIterValues[i], xTimeValues[i]]
                        row.extend(yValues[i])
                        spamwriter.writerow(row)
                if len(self.__testMetrics[logId]) != 0:
                    xIterValues = self.__xValues(self.__testData[logId], logId, False)
                    xTimeValues = self.__xValues(self.__testData[logId], logId, True)
                    yValues = self.__yValues(self.__testData[logId],
                                         self.__testMetrics[logId])
                    test = lambda s: self.__parsers[logId][0] + ".test." + s
                    spamwriter.writerow([])
                    spamwriter.writerow([])
                    spamwriter.writerow(["# " + self.__parsers[logId][0] + " TEST"])
                    names = map(test, self.__testMetrics[logId])
                    row = ["Iterations", "Time"]
                    row.extend(names)
                    spamwriter.writerow(row)
                    for i in range(0, len(xIterValues)):
                        row = [int(xIterValues[i]), xTimeValues[i]]
                        row.extend(yValues[i])
                        spamwriter.writerow(row)
