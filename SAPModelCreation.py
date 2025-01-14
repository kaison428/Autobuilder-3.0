from PyQt5.QtCore import *  # core Qt functionality
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *  # extends QtCore with GUI functionality
from PyQt5 import uic

from Model import * # tower and other design components
from ProjectSettings import *   # project settings data, data enumeration
from TowerVariation import * # dict of combinations
from Performance import * # results
from FileWriter import *
from Plot import * # For graphs and plots
from Definition import InputFileKeyword

from Definition import *    # file extensions, EnumToString conversion

import os
import sys
import comtypes.client
import comtypes.gen

import random
import re
import time
import scipy
import copy
import numpy
from scipy.stats import norm
import datetime
import matplotlib.pyplot as plt
import shapely.geometry
from skimage.transform import ProjectiveTransform


class RunTower(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.mainFileLoc = args[0].fileLoc
        self.folderLoc= self.mainFileLoc.replace('.ab', '')
        self.SAPFolderLoc = self.folderLoc + FileExtension.SAPModels

        # Create new directory for data
        try:
            os.mkdir(self.SAPFolderLoc)
        except:
            pass
  
        # Load the UI Page
        fileh = QFile(':/UI/autobuilder_buildtower.ui')
        fileh.open(QFile.ReadOnly)
        uic.loadUi(fileh, self)
        fileh.close()
        
        # Project Settings Data
        self.psData = args[0].projectSettingsData
        self.runGMs = self.psData.groundMotion
        self.analysisType = self.psData.analysisType

        # Reference to existing tower
        self.tower = args[0].tower

        # Members to be divided at intersections
        self.membersToDivide = []

        # Tower performances
        self.towerPerformances = {}

        # Elasped Time
        self.timeElapsed = 0 # in seconds
        self.estTimeRemaining = 0 # in seconds
        self.timer = QTimer(self)
        self.timer.setInterval(1000) # period in miliseconds
        self.timer.timeout.connect(self.updateElapsedTime)

        # Start scatter plot of tower performance
        xlabel = 'Tower Number'
        if self.runGMs:
            ylabel = 'Total Cost'
        else:
            ylabel = 'Period'
        self.plotter = Plotter(xlabel, ylabel)
        self.plotter.show()

        self.setCloseButton()

        # Establish alternate thread to run SAP2000 ----------------------------------------
        sapRunnable = SAPRunnable(self)
        QThreadPool.globalInstance().start(sapRunnable) # no need to create a new thread here

        # Signals to connect SAP2000 thread and GUI thread
        sapRunnable.signals.log.connect(self.logText.append)
        sapRunnable.signals.startTime.connect(self.timer.start)
        sapRunnable.signals.endTime.connect(self.timer.stop)
        sapRunnable.signals.resetProgress.connect(self.resetProgress)
        sapRunnable.signals.plotData.connect(self.updatePlot)
        sapRunnable.signals.updateProgress.connect(self.updateProgress)

    def setCloseButton(self):
        self.closeButton = self.buttonBox.button(QDialogButtonBox.Close)
        self.closeButton.clicked.connect(self.close)

    def updateProgress(self, current, numTowers):
        self.progressBar.setValue(current + 1)
        self.numTowersLabel.setText('{} out of {}'.format(str(current + 1), str(numTowers)))

        avgTime = self.timeElapsed/(current + 1)
        self.estTimeRemaining = round(avgTime * (numTowers - (current+1)))

    def resetProgress(self, max):
        self.progressBar.setValue(0)
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(max)
        self.numTowersLabel.setText('0 out of {}'.format(str(max)))

    def updateElapsedTime(self):
        self.timeElapsed += 1
        self.timeElapsedLabel.setText(str(datetime.timedelta(seconds=self.timeElapsed)))

        if self.estTimeRemaining > 1:
            self.estTimeRemaining -= 1
        self.estTimeLabel.setText(str(datetime.timedelta(seconds=self.estTimeRemaining)))

    def updatePlot(self, x, y):
        self.plotter.addxData(x)
        self.plotter.addyData(y)

        self.plotter.updatePlot()

class SAPSignals(QObject):
    '''
    This is a Struct
    Defines the signals available from a running worker thread.
    '''

    log = pyqtSignal(str)
    resetProgress = pyqtSignal(int)
    plotData = pyqtSignal(int, float)
    updateProgress = pyqtSignal(int, int)
    startTime = pyqtSignal()
    endTime = pyqtSignal()

class SAPRunnable(QRunnable):
    ''' Worker thread; to avoid freezing GUI '''

    def __init__(self, runTower):
        super().__init__()

        self.mainFileLoc = runTower.mainFileLoc
        self.folderLoc = runTower.folderLoc
        self.SAPFolderLoc = runTower.SAPFolderLoc

        # Project Settings Data
        self.psData = runTower.psData
        self.runGMs = self.psData.groundMotion
        self.analysisType = self.psData.analysisType

        # Reference to existing tower
        self.tower = runTower.tower

        # Tower performances
        self.towerPerformances = {}

        self.membersToDivide = []

        self.signals = SAPSignals()

    def run(self):
        # try:
        self.buildTowers()
        # except:
        #     self.signals.log.emit('ERROR while building towers')

    def buildTowers(self):
        self.signals.log.emit('Starting SAP2000...')

        SapModel = self.startSap2000()
        if SapModel == False:
            self.signals.log.emit('Fail to start SAP2000 - Check if SAP2000 model is correctly selected or if SAP2000 v22 is available')
            return

        # Delete all members within the plans and build correct bracing scheme
        SapModel.SetPresentUnits(SAP2000Constants.Units['kip_in_F'])

        inputTable = self.tower.inputTable
        print(inputTable)
        numTowers = len(inputTable['towerNumber'])
        self.signals.resetProgress.emit(numTowers)

        # Update time -----------------------------
        self.signals.startTime.emit()

        for i, towerNum in enumerate(inputTable['towerNumber']):

            self.signals.log.emit('Building Tower {}...'.format(str(towerNum)))

            SapModel.SetModelIsLocked(False)
            SapModel.SetPresentUnits(SAP2000Constants.Units['kip_in_F'])

            # Define tower performance object to store results
            towerPerformance = TowerPerformance(str(towerNum))

            for key in inputTable:
                if InputFileKeyword.bracing in key:
                    bracing = self.tower.bracings[inputTable[key][i]]
                    panel = self.tower.panels[key.strip('Panel ').rstrip('-Bracing')]
                    self.clearMembersinPanel(SapModel, panel)
                    self.buildBracing(SapModel, panel, bracing)

                if InputFileKeyword.shearWall in key:
                    areaSectionName = inputTable[key][i]
                    panel = self.tower.panels[key.lstrip('Panel ').rstrip('-ShearWall')]
                    self.removeShearWallinPanel(SapModel, panel)
                    if areaSectionName != str(None):
                        self.buildShearWall(SapModel, panel, areaSectionName)

                # TODO: update member later
                if InputFileKeyword.member in key:
                    memberID = key.strip('Member ')
                    sectionName = inputTable[key][i]
                    # build members
                    self.changeMemberSection(SapModel, memberID, sectionName)

                if InputFileKeyword.variable in key:
                    variableName = key.strip('Variable-')
                    assignedValue = inputTable[key][i]
  
                    towerPerformance.addVariable(variableName, assignedValue)
            
            self.signals.log.emit('Rounding coordinates...')
            self.roundingModelCoordinates(SapModel)
            #self.divideMembersAtIntersection(SapModel)

            # Set to multi-thread solver
            SapModel.Analyze.SetSolverOption_2(SolverType=2, SolverProcessType=0, NumberParallelRuns=0)

            # Save the file
            SAPFileLoc = r'{}\Tower{}.sdb'.format(self.SAPFolderLoc, str(towerNum))
            SapModel.File.Save(SAPFileLoc)

            # Analyse tower and print results to spreadsheet
            self.signals.log.emit('\nAnalyzing tower number ' + str(towerNum))
            self.signals.log.emit('-------------------------')

            # try:
            self.runAnalysis(SapModel, towerPerformance, towerNum)
            # except:
            # self.signals.log.emit('ERROR running analysis')
                
            self.towerPerformances[str(towerNum)] = towerPerformance
            
            if self.runGMs:
                avgBuildingCost = towerPerformance.avgBuildingCost()
                avgSeismicCost = towerPerformance.avgSeismicCost()

                self.signals.plotData.emit(towerNum, avgBuildingCost + avgSeismicCost)
            else:
                self.signals.plotData.emit(towerNum, towerPerformance.period)

            # Save the file
            SapModel.File.Save(SAPFileLoc)

            self.signals.updateProgress.emit(i, numTowers)

        self.signals.endTime.emit()

        # Create output table
        filewriter = FileWriter(self.mainFileLoc)
        filewriter.writeOutputTable(self.towerPerformances, self.signals.log)

        # Create member stresses table
        filewriter.writeStressOut(self.towerPerformances, self.signals.log)

        # Save tower performances
        self.tower.towerPerformances.clear()
        self.tower.towerPerformances.update(self.towerPerformances)

        # reset
        for panel in self.tower.panels.values():
            panel.memberIDs = ["UNKNOWN"]
            panel.areaID = "UNKNOWN"

    def startSap2000(self):
        #set the following flag to True to attach to an existing instance of the program
        #otherwise a new instance of the program will be started
        AttachToInstance = False

        #set the following flag to True to manually specify the path to SAP2000.exe
        #this allows for a connection to a version of SAP2000 other than the latest installation
        #otherwise the latest installed version of SAP2000 will be launched
        SpecifyPath = True

        #if the above flag is set to True, specify the path to SAP2000 below
        ProgramPath = self.psData.SAPPath

        if AttachToInstance:
            # attach to a running instance of SAP2000
            try:
                # get the active SapObject
                mySapObject = comtypes.client.GetActiveObject("CSI.SAP2000.API.SapObject")
            except (OSError, comtypes.COMError):
                self.signals.log.emit("No running instance of the program found or failed to attach.")
                sys.exit(-1)
        else:
            # create API helper object
            helper = comtypes.client.CreateObject('SAP2000v1.Helper')
            helper = helper.QueryInterface(comtypes.gen.SAP2000v1.cHelper)
            if SpecifyPath:
                try:
                    # 'create an instance of the SAPObject from the specified path
                    mySapObject = helper.CreateObject(ProgramPath)
                except (OSError, comtypes.COMError):
                    self.signals.log.emit("Cannot start a new instance of the program from " + ProgramPath)
                    sys.exit(-1)
            else:
                try:
                    # create an instance of the SAPObject from the latest installed SAP2000
                    mySapObject = helper.CreateObjectProgID("CSI.SAP2000.API.SapObject")
                except (OSError, comtypes.COMError):
                    self.signals.log.emit("Cannot start a new instance of the program.")
                    sys.exit(-1)
            # start SAP2000 application
            mySapObject.ApplicationStart()
            # create SapModel Object
            SapModel = mySapObject.SapModel
            # initialize model
            SapModel.InitializeNewModel()

            # open model at specified file path in project settings
            ret = SapModel.File.OpenFile(self.psData.SAPModelLoc)
            if ret != 0:
                self.signals.log.emit('ERROR cannot open SAP2000 model file')
                return False

        return SapModel

    def roundingModelCoordinates(self, SapModel):
        SapModel.SetModelIsLocked(False)
        [NumberPoints, AllPointNames, ret] = SapModel.PointObj.GetNameList()

        for PointName in AllPointNames:
            [x, y, z, ret] = SapModel.PointObj.GetCoordCartesian(PointName, 0, 0, 0)
            x = round(x, SAP2000Constants.MaxDecimalPlaces)
            y = round(y, SAP2000Constants.MaxDecimalPlaces)
            z = round(z, SAP2000Constants.MaxDecimalPlaces)
            ret = SapModel.EditPoint.ChangeCoordinates_1(PointName, x, y, z, True)
            if ret != 0:
                self.signals.log.emit('ERROR rounding coordinates of point ' + PointName)

    def clearMembersinPanel(self, SapModel, panel):
        # Deletes all members that are in the panel
        if panel.memberIDs == ["UNKNOWN"] and (not self.psData.keepExistingMembers):
            self.clearExistingMembersinPanel(SapModel, panel)
        else:
            # Delete members that are contained in the panel
            for memberID in panel.memberIDs:
                ret = SapModel.FrameObj.Delete(memberID)
                if ret != 0:
                    self.signals.log.emit('ERROR deleting member ' + memberID)
        panel.memberIDs.clear()

    def removeShearWallinPanel(self, SapModel, panel):
        # if panel.areaIDs == ["UNKNOWN"] and (not self.psData.keepExistingMembers):
        #     self.clearExistingMembersinPanel(SapModel, panel)
        # else:
        # Delete area objects that exist in the panel
        if panel.areaID == "UNKNOWN":
            pass
        else: 
            ret = SapModel.AreaObj.Delete(panel.areaID)
            if ret != 0:
                self.signals.log.emit('ERROR deleting area ' + panel.areaID)
        panel.areaID = ''

    def clearExistingMembersinPanel(self, SapModel, panel):
        vec1_x = panel.lowerLeft.x - panel.upperLeft.x
        vec1_y = panel.lowerLeft.y - panel.upperLeft.y
        vec1_z = panel.lowerLeft.z - panel.upperLeft.z
        vec2_x = panel.lowerLeft.x - panel.upperRight.x
        vec2_y = panel.lowerLeft.y - panel.upperRight.y
        vec2_z = panel.lowerLeft.z - panel.upperRight.z

        # Two vectors defining the panel
        vec1 = [vec1_x, vec1_y, vec1_z]
        vec2 = [vec2_x, vec2_y, vec2_z]
        
        # Normal vector of panel
        norm_vec = numpy.cross(numpy.array(vec1), numpy.array(vec2))

        [number_members, all_member_names, ret] = SapModel.FrameObj.GetNameList()
        # Loop through all members in model
        for member_name in all_member_names:
            # Get member coordinates
            [member_pt1_name, member_pt2_name, ret] = SapModel.FrameObj.GetPoints(member_name)
            if ret != 0:
                self.signals.log.emit('ERROR checking member ' + member_name)
            [member_pt1_x, member_pt1_y, member_pt1_z, ret] = SapModel.PointObj.GetCoordCartesian(member_pt1_name)
            if ret != 0:
                self.signals.log.emit('ERROR getting coordinate of point ' + member_pt1_name)
            [member_pt2_x, member_pt2_y, member_pt2_z, ret] = SapModel.PointObj.GetCoordCartesian(member_pt2_name)
            if ret != 0:
                self.signals.log.emit('ERROR getting coordinate of point ' + member_pt2_name)

            # Check if the member is within the elevation of the panel
            panel_max_z = max(panel.lowerLeft.z, panel.upperLeft.z, panel.upperRight.z, panel.lowerRight.z)
            panel_min_z = min(panel.lowerLeft.z, panel.upperLeft.z, panel.upperRight.z, panel.lowerRight.z)
            
            if min(member_pt1_z, member_pt2_z) >= panel_min_z and max(member_pt1_z, member_pt2_z) <= panel_max_z:
                member_vec_x = member_pt2_x - member_pt1_x
                member_vec_y = member_pt2_y - member_pt1_y
                member_vec_z = member_pt2_z - member_pt1_z
                member_vec = [member_vec_x, member_vec_y, member_vec_z]

                # Check if member is in the same plane as the panel
                if numpy.dot(member_vec, norm_vec) == 0:
                    # To do this, check if the vector between a member point and a plane point is parallel to plane
                    test_vec = [member_pt1_x - panel.lowerLeft.x, member_pt1_y - panel.lowerLeft.y,
                                member_pt1_z - panel.lowerLeft.z]
                    if numpy.dot(test_vec, norm_vec) == 0:
                        # Check if the member lies within the limits of the panel
                        # First, transform the frame of reference since Shapely only works in 2D
                        # Create unit vectors
                        ref_vec_1 = vec1
                        ref_vec_2 = numpy.cross(ref_vec_1, norm_vec)
                        # Project each point defining the panel onto each reference vector
                        panelPoints = [
                            [panel.lowerLeft.x, panel.lowerLeft.y, panel.lowerLeft.z],
                            [panel.upperLeft.x, panel.upperLeft.y, panel.upperLeft.z],
                            [panel.upperRight.x, panel.upperRight.y, panel.upperRight.z],
                            [panel.lowerRight.x, panel.lowerRight.y, panel.lowerRight.z]
                        ]

                        panelPointsTrans = []

                        for panelPoint in panelPoints:
                            panelPointTrans1 = numpy.dot(panelPoint, ref_vec_1) / numpy.linalg.norm(ref_vec_1)
                            panelPointTrans2 = numpy.dot(panelPoint, ref_vec_2) / numpy.linalg.norm(ref_vec_2)

                            panelPointsTrans.append([panelPointTrans1, panelPointTrans2])

                        # Project each point defining the member onto the reference vector
                        member_pt1 = [member_pt1_x, member_pt1_y, member_pt1_z]
                        member_pt2 = [member_pt2_x, member_pt2_y, member_pt2_z]
                        member_pt1_trans_1 = numpy.dot(member_pt1, ref_vec_1) / numpy.linalg.norm(ref_vec_1)
                        member_pt1_trans_2 = numpy.dot(member_pt1, ref_vec_2) / numpy.linalg.norm(ref_vec_2)
                        member_pt2_trans_1 = numpy.dot(member_pt2, ref_vec_1) / numpy.linalg.norm(ref_vec_1)
                        member_pt2_trans_2 = numpy.dot(member_pt2, ref_vec_2) / numpy.linalg.norm(ref_vec_2)

                        # Create shapely geometries to check if member is in the panel
                        poly_coords = panelPointsTrans
                        member_coords = [[member_pt1_trans_1, member_pt1_trans_2],
                                            [member_pt2_trans_1, member_pt2_trans_2]]

                        # round coordinates
                        for i in range(len(poly_coords)):
                            poly_coords[i][0] = round(poly_coords[i][0], SAP2000Constants.MaxDecimalPlaces)
                            poly_coords[i][1] = round(poly_coords[i][1], SAP2000Constants.MaxDecimalPlaces)

                        for i in range(len(member_coords)):
                            member_coords[i][0] = round(member_coords[i][0], SAP2000Constants.MaxDecimalPlaces)
                            member_coords[i][1] = round(member_coords[i][1], SAP2000Constants.MaxDecimalPlaces)

                        panel_shapely = shapely.geometry.Polygon(poly_coords)
                        member_shapely = shapely.geometry.LineString(member_coords)

                        # Delete member if it is inside the panel
                        if member_shapely.intersects(panel_shapely):
                            if not member_shapely.touches(panel_shapely):
                                ret = SapModel.FrameObj.Delete(member_name, 0)
                                
                            # Get members needed to be divided at intersections
                            else:
                                self.membersToDivide.append(member_name)

    def buildBracing(self, SapModel, panel, bracing):
        # Scale the member start and end points to fit the panel location and dimensions
        # Get unit vectors to define the panel
        panel_vec_horiz_x = panel.lowerRight.x - panel.lowerLeft.x
        panel_vec_horiz_y = panel.lowerRight.y - panel.lowerLeft.y
        panel_vec_horiz_z = panel.lowerRight.z - panel.lowerLeft.z
        panel_vec_vert_x = panel.upperLeft.x - panel.lowerLeft.x
        panel_vec_vert_y = panel.upperLeft.y - panel.lowerLeft.y
        panel_vec_vert_z = panel.upperLeft.z - panel.lowerLeft.z

        panel_vec_horiz = [panel_vec_horiz_x, panel_vec_horiz_y, panel_vec_horiz_z]
        panel_vec_vert = [panel_vec_vert_x, panel_vec_vert_y, panel_vec_vert_z]

        panel_norm_vec = numpy.cross(numpy.array(panel_vec_horiz), numpy.array(panel_vec_vert))

        # Convert panel coordinates to the local coordinate system of panel (defined by vec_horiz and vec_vert)
        panel_points = [
            [panel.lowerLeft.x, panel.lowerLeft.y, panel.lowerLeft.z],
            [panel.upperLeft.x, panel.upperLeft.y, panel.upperLeft.z],
            [panel.upperRight.x, panel.upperRight.y, panel.upperRight.z],
            [panel.lowerRight.x, panel.lowerRight.y, panel.lowerRight.z],
        ]

        # Reference vectors for the local coordinate system of the panel
        ref_vec_1 = panel_vec_horiz
        ref_vec_2 = numpy.cross(panel_vec_horiz, panel_norm_vec)

        panel_points_trans = [[numpy.dot(point,ref_vec_1) / numpy.linalg.norm(ref_vec_1),
                                numpy.dot(point,ref_vec_2) / numpy.linalg.norm(ref_vec_2)] 
                                for point in panel_points]

        # Generate a matrix which projects the "bracing scheme space" to the "panel space"
        t = ProjectiveTransform()
        src = numpy.asarray([[0, 0], [0, 1], [1, 1], [1, 0]])
        dst = numpy.asarray(panel_points_trans)

        if not t.estimate(src, dst): raise Exception("estimate failed")

        for member in bracing.members:
            node1 = member.start_node
            node2 = member.end_node
            section = member.material

            memberData = numpy.array([
                [node1.x, node1.y],
                [node2.x, node2.y],
            ])

            # Project member's coordinate onto the panel
            memberData_local = t(memberData)

            panel_vec_horiz_hat = numpy.array(ref_vec_1) / numpy.linalg.norm(ref_vec_1)
            panel_vec_vert_hat = numpy.array(ref_vec_2) / numpy.linalg.norm(ref_vec_2)

            # Convert member coordinates from the local 2D coordinate system of panel to the global 3D coordinate system
            start_node_x = panel.lowerLeft.x + (memberData_local[0][0] - panel_points_trans[0][0]) * panel_vec_horiz_hat[0] + (memberData_local[0][1] - panel_points_trans[0][1]) * panel_vec_vert_hat[0]
            start_node_y = panel.lowerLeft.y + (memberData_local[0][0] - panel_points_trans[0][0]) * panel_vec_horiz_hat[1] + (memberData_local[0][1] - panel_points_trans[0][1]) * panel_vec_vert_hat[1]
            start_node_z = panel.lowerLeft.z + (memberData_local[0][0] - panel_points_trans[0][0]) * panel_vec_horiz_hat[2] + (memberData_local[0][1] - panel_points_trans[0][1]) * panel_vec_vert_hat[2]
            end_node_x = panel.lowerLeft.x + (memberData_local[1][0] - panel_points_trans[0][0]) * panel_vec_horiz_hat[0] + (memberData_local[1][1] - panel_points_trans[0][1]) * panel_vec_vert_hat[0]
            end_node_y = panel.lowerLeft.y + (memberData_local[1][0] - panel_points_trans[0][0]) * panel_vec_horiz_hat[1] + (memberData_local[1][1] - panel_points_trans[0][1]) * panel_vec_vert_hat[1]
            end_node_z = panel.lowerLeft.z + (memberData_local[1][0] - panel_points_trans[0][0]) * panel_vec_horiz_hat[2] + (memberData_local[1][1] - panel_points_trans[0][1]) * panel_vec_vert_hat[2]

            # Create the member
            [member_name, ret] = SapModel.FrameObj.AddByCoord(start_node_x, start_node_y, start_node_z, end_node_x,
                                                              end_node_y, end_node_z, PropName=section)

            # Get points of member
            [point_1, point_2, ret] = SapModel.FrameObj.GetPoints(member_name)
            points = (point_1, point_2)
            
            # Set point to fixed support if at ground level
            for point in points:
                [x, y, z, ret] = SapModel.PointObj.GetCoordCartesian(point)
                if z <= 0:
                    values = [True for i in range(6)] # Set restraint in all 6 degree of freedom
                    ret = SapModel.PointObj.setRestraint(point, values)

            if ret != 0:
                self.signals.log.emit('ERROR building member in panel '+ panel.name)

            if member_name is not None:
                print('member name:', member_name)
                panel.memberIDs.append(member_name)

    def buildShearWall(self, SapModel, panel, areaSectionName):

        numPoints = 4
        points = {
            'x': [panel.lowerLeft.x, panel.upperLeft.x, panel.upperRight.x, panel.lowerRight.x],
            'y': [panel.lowerLeft.y, panel.upperLeft.y, panel.upperRight.y, panel.lowerRight.y],
            'z': [panel.lowerLeft.z, panel.upperLeft.z, panel.upperRight.z, panel.lowerRight.z],
        }
        
        [x_coords, y_coords, z_coord, areaName, ret] = SapModel.AreaObj.AddByCoord(numPoints, points['x'], points['y'], points['z'], PropName=areaSectionName)

        if ret != 0:
            self.signals.log.emit('ERROR building area object in panel '+ panel.name)

        # Get points of area
        [num, points, ret] = SapModel.AreaObj.GetPoints(areaName)
        
        # Set point to fixed support if at ground level
        for point in points:
            [x, y, z, ret] = SapModel.PointObj.GetCoordCartesian(point)
            if z <= 0:
                values = [True for i in range(6)] # Set restraint in all 6 degree of freedom
                ret = SapModel.PointObj.setRestraint(point, values)

        if areaName is not None:
            print('areaName:', areaName)
            panel.areaID = areaName

    def divideMembersAtIntersection(self, SapModel):
        '''  May not be necessary '''
        # Make sure no duplicates
        self.membersToDivide = list(dict.fromkeys(self.membersToDivide))

        for memberName in self.membersToDivide:

            ret = SapModel.SelectObj.All(False)
            if ret != 0:
                self.signals.log.emit('ERROR selecting all members')

            num = 0
            newNames = []
            [num, newNames, ret] = SapModel.EditFrame.DivideAtIntersections(memberName, num, newNames)
            if ret != 0:
                self.signals.log.emit('ERROR dividing member ' + memberName)

            else:
                for newName in newNames:
                    self.membersToDivide.append(newName)

        ret = SapModel.SelectObj.All(True)

    def changeMemberSection(self, SapModel, memberID, sectionName):
        # Change the section properties of specified members
        ret = SapModel.FrameObj.SetSection(str(memberID), sectionName, 0)
        if ret != 0 :
            self.signals.log.emit('ERROR changing section of member ' + str(memberID))

    def runAnalysis(self, SapModel, towerPerformance, towerNum):
        SapModel.SetPresentUnits(SAP2000Constants.Units['kip_in_F'])

        # TODO: get load cases for respective load case types
        NumberCases = 0
        DeadCaseNames, ModalCaseNames, THCaseNames, RSCaseNames = [], [], [], []

        [NumberCases, DeadCaseNames, ret] = SapModel.LoadCases.GetNameList(NumberCases, DeadCaseNames,SAP2000Constants.CaseTypes['LinearStatic'])
        [NumberCases, ModalCaseNames, ret] = SapModel.LoadCases.GetNameList(NumberCases, ModalCaseNames,SAP2000Constants.CaseTypes['Modal'])
        [NumberCases, THCaseNames, ret] = SapModel.LoadCases.GetNameList(NumberCases, THCaseNames,SAP2000Constants.CaseTypes['LinearHistory'])
        [NumberCases, RSCaseNames, ret] = SapModel.LoadCases.GetNameList(NumberCases, RSCaseNames,SAP2000Constants.CaseTypes['ResponseSpectrum'])

        SapModel.Analyze.SetRunCaseFlag('', False, True)    # reset load cases flags

        # TEST: print all load cases run flags
        print('BEFORE')
        [NumberItems, CaseName, Run, ret] = SapModel.Analyze.GetRunCaseFlag()
        for name, run in zip(CaseName, Run):
            if run:
                print(name)

        # 1. run dead load and modal cases (required by default)
        for caseName in DeadCaseNames:
            SapModel.Analyze.SetRunCaseFlag(caseName, True, False)
        for caseName in ModalCaseNames:
            SapModel.Analyze.SetRunCaseFlag(caseName, True, False)

        # 2. run time history or response spectrum analysis to obtain seismic performance
        if self.runGMs: 
            if self.analysisType == ATYPE.TIME_HISTORY:
                for caseName in THCaseNames:
                    SapModel.Analyze.SetRunCaseFlag(caseName, True, False)
            elif self.analysisType == ATYPE.RSA:
                for caseName in RSCaseNames:
                    SapModel.Analyze.SetRunCaseFlag(caseName, True, False)

        # TEST: print all load cases run flags
        print('AFTER')
        [NumberItems, CaseName, Run, ret] = SapModel.Analyze.GetRunCaseFlag()
        runningCases = [name for name, run in zip(CaseName, Run) if run]
        print('runningCases', runningCases)

        print('runGMs', self.runGMs)
        print('analysisType', self.analysisType)
        print('THCaseNames', THCaseNames)
        print('DeadCaseNames', DeadCaseNames)
        print('RSCaseNames', RSCaseNames)

        #Run Analysis
        self.signals.log.emit('Running model in SAP2000...')
        SapModel.Analyze.RunAnalysis()
        self.signals.log.emit('Finished running.')

        self.signals.log.emit('Getting results...')

        analyzer = PerformanceAnalyzer(SapModel)

        # Find Roof nodes ---------------------------------------------
        roofNodeNames = self.psData.nodesList
        # Check if nodes exist in model
        [NumberPoints, AllPointNames, ret] = SapModel.PointObj.GetNameList()
        tempRoofNodeNames = copy.deepcopy(roofNodeNames)
        # remove non-existent nodes
        counter = 0
        for i, name in enumerate(roofNodeNames):
            if not (name in AllPointNames):
                self.signals.log.emit('ERROR {} does not exist in model provided.'.format(name))
                tempRoofNodeNames.pop(i-counter)
                counter += 1
        roofNodeNames = tempRoofNodeNames

        # Get WEIGHT in lbs ---------------------------------
        totalWeight = analyzer.getWeight()
        
        # Get PERIOD ---------------------------------
        period = analyzer.getPeriod()

        # try:
        [NumberCombo, AllCombos, ret] = SapModel.RespCombo.GetNameList()
        print('old all combos', AllCombos)

        # Check case list of each combo in AllCombos to see if the entire case list is in runningCases
        # If not, remove from AllCombos
        try:
            tempAllCombos = list(copy.deepcopy(AllCombos))
            for combo in AllCombos:
                [NumberItems, comboTypeList, comboCaseList, scaleFactorList, ret] = SapModel.RespCombo.GetCaseList(combo)
                if not set(comboCaseList).issubset(set(runningCases)):
                    self.signals.log.emit('NOTE {} not run in SAP2000'.format(combo))
                    tempAllCombos.remove(combo)
            AllCombos = tempAllCombos
            print('new all combos', AllCombos)

        except:
            self.signals.log.emit('ERROR no load combinations found')
            AllCombos = []
        
        # Get MEMBER STRESS ---------------------------------
        if self.runGMs:
            memberUtilizationId = self.psData.memberUtilizationId
            maxTs_df, maxCs_df, maxMs_df, maxVs_df, maxTwBs, maxCwBs = analyzer.getMemberStress(maxStressIdentifier=memberUtilizationId, allCombos=AllCombos)

            forceReductionFactor = self.psData.forceReductionFactor
            maxT_DCR = max(maxTwBs)*forceReductionFactor / (self.psData.tensileStrength + Algebra.EPSILON)
            maxC_DCR = max(maxCwBs)*forceReductionFactor / (self.psData.compressiveStrength + Algebra.EPSILON)
            maxV_DCR = maxVs_df['Stress'].max()*forceReductionFactor / (self.psData.shearStrength + Algebra.EPSILON)

            # Temporary output
            self.signals.log.emit('maxT_DCR: {}'.format(round(maxT_DCR,2)))
            self.signals.log.emit('maxC_DCR: {}'.format(round(maxC_DCR,2)))
            self.signals.log.emit('maxV_DCR: {}'.format(round(maxV_DCR,2)))

        else:
            maxT_DCR = 'max tension not calculated'
            maxC_DCR = 'max compression not calculated'
            maxV_DCR = 'max shear not calculated'

            dictTemplate = {
                'Stress': [0],
                'Type': [0], # 'F': Frame; 'W': Wall
                'LC': [0],
                'Name': [0],
            }

            maxTs_df = pd.DataFrame(data=dictTemplate)
            maxCs_df = pd.DataFrame(data=dictTemplate)
            maxMs_df = pd.DataFrame(data=dictTemplate)
            maxVs_df = pd.DataFrame(data=dictTemplate)
            maxTwBs = [0]
            maxCwBs = [0]

        towerPerformance.max_T = maxTs_df
        towerPerformance.max_C = maxCs_df
        towerPerformance.max_M = maxMs_df
        towerPerformance.max_V = maxVs_df
        towerPerformance.max_CombT = max(maxTwBs)
        towerPerformance.max_CombC = max(maxCwBs)

        for combo in AllCombos:
            self.signals.log.emit(str(self.runGMs))
            if self.runGMs:
                # Only run combo with ground motions
                # self.signals.log.emit('GM id '+ self.psData.gmIdentifier)
                # self.signals.log.emit('combo '+combo)
                if not(self.psData.gmIdentifier in combo):
                    continue

                SapModel.Results.Setup.DeselectAllCasesAndCombosForOutput()
                SapModel.Results.Setup.SetComboSelectedForOutput(combo)
                # set type to envelope
                SapModel.Results.Setup.SetOptionModalHist(1)

                # get max ACCELERATION ---------------------------------------
                maxAcc = analyzer.getMaxAcceleration(roofNodeNames)

                # get joint DISPLACEMENT ---------------------------------------
                maxDisp = analyzer.getMaxDisplacement(roofNodeNames)

                # Get BASE SHEAR  ---------------------------------------
                basesh = analyzer.getBaseShear()
                
                buildingCost, seismicCost = analyzer.getCosts(maxAcc, maxDisp, self.psData.footprint, totalWeight, self.psData.totalMass, self.psData.totalHeight)
                towerPerformance.buildingCost[combo] = buildingCost
                towerPerformance.seismicCost[combo] = seismicCost

            else:
                maxAcc = 'max acc not calculated'
                maxDisp = 'max disp not calculated'
                basesh = 'base shear not calculated'

            # Store performance data to struct
            towerPerformance.maxAcc[combo] = maxAcc
            towerPerformance.maxDisp[combo] = maxDisp
            towerPerformance.basesh[combo] = basesh

        towerPerformance.totalWeight = totalWeight
        towerPerformance.period = period
        towerPerformance.tensionDCR = maxT_DCR
        towerPerformance.compDCR = maxC_DCR
        towerPerformance.shearDCR = maxV_DCR
        
        # Get Centre of Rigidity ---------------------------------
        if self.psData.centreOfRigidity == CRTYPE.SINGLE_FLOOR:
            towerPerformance.CR = analyzer.getCR(self.tower.elevations)
            print(towerPerformance.CR)
        elif self.psData.centreOfRigidity == CRTYPE.ALL_FLOOR:
            towerPerformance.CR = analyzer.getCR(self.tower.elevations)
        elif self.psData.centreOfRigidity == CRTYPE.DO_NOT_RUN:
            towerPerformance.CR = analyzer.getCR(self.tower.elevations)
        else:
            pass

        # Get Eccentricity ---------------------------------
        towerPerformance.maxEcc, towerPerformance.avgEcc = analyzer.getEccentricity(towerPerformance.CR, self.tower)


