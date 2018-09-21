
from PyQt5.QtWidgets import QSizePolicy
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

def handleNonPositives(yValues):
    allNonPositive = []
    for i in range(0,len(yValues)):
        for j in range(0,len(yValues[i])):
            if len(allNonPositive) < j + 1:
                allNonPositive.append(True)
            if yValues[i][j] > 0:
                allNonPositive[j] = False
    for i in range(0,len(yValues)):
        yValues[i] = [yValues[i][j] for j in range(0,len(allNonPositive)) if not allNonPositive[j]]
    return yValues

def allNonNegative(yValues):
    for ys in yValues:
        for y in ys:
            if y > 0:
                return False
    return True

class PlotCanvas(FigureCanvas):
    """
    This plotter canvas draws the actual plots within the plotter widget.
    """

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
       #self.axes.hold(True)  # MatPlotLib hold depricated http://matplotlib.org/api/api_changes.html
        self.axes.grid(True)
        FigureCanvas.__init__(self, self.fig)
        self.setParent(parent)

        FigureCanvas.setSizePolicy(self,
                                   QSizePolicy.Expanding,
                                   QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

    def plotDictList(self, xValues, yValues, logarithmic):
        """
        Plot a multiple charts on the axes.

        Return the Line2D docks.
        """
        self.axes.grid(True)
        if logarithmic and not allNonNegative(yValues):
            try:
                return self.axes.semilogy(xValues, handleNonPositives(yValues))
            except:
                pass
        return self.axes.plot(xValues, yValues)

    def legend(self, lines, labels):
        self.axes.legend(lines, labels, loc = 0, fontsize=10)

    def clear(self):
        self.axes.clear()
        self.axes.grid(True)
