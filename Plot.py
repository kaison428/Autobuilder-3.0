import matplotlib.pyplot as plt
import numpy

class Plotter:
    def __init__(self, xlabel='X', ylabel='Y', title='Tower Performances', lineType='ro'):
        self.xlabel = xlabel
        self.ylabel = ylabel
        self.title = title
        self.lineType = lineType

        self.fig = plt.figure()
        self.ax = plt.subplot(1,1,1)

        self.xdata = []
        self.ydata = []

    def show(self):
        plt.ion()

        self.ax.set_xlabel(self.xlabel)
        self.ax.set_ylabel(self.ylabel)
        
        plt.title(self.title)

        self.ax.plot(self.xdata, self.ydata, self.lineType, markersize=6)
        plt.grid(True)
        plt.show(block=False)

    def save(self, loc):
        plt.savefig(loc)

    def updatePlot(self):
        self.ax.lines[0].set_data(self.xdata,self.ydata)
        self.ax.relim()
        self.ax.autoscale_view()
        plt.xticks(numpy.arange(min(self.xdata), max(self.xdata)+1, 1.0))
        self.fig.canvas.flush_events()

    def addxData(self,x):
        self.xdata.append(x)

    def addyData(self,y):
        self.ydata.append(y)
    