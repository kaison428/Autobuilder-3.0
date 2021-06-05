import Model    # contains tower design components
import ProjectSettings  # contains data in project settings
import DisplaySettings  # contains data in display settings
from Definition import *    # file extensions, EnumToString conversion
import pandas as pd  # use data frame to write files

import os   # create new directory

class FileWriter:
    def __init__(self, fileLoc, tower=None, psData=None):
        self.mainFileLoc = fileLoc
        self.folderLoc = fileLoc.replace('.ab', '')

        self.tower = tower
        self.psData = psData

        # Create new directory for data
        try:
            os.mkdir(self.folderLoc)
        except:
            pass

    def writeFiles(self):
        ''' Wrapper function to write all files '''

        self.writeProjectSettings()
        self.writeDisplaySettings()
        self.writeFloorPlans()
        self.writeFloors()
        self.writePanels()
        self.writeBracings()
        self.writeBracingGroups()
        self.writeSectionGroups()
        self.writeBracingAssignments()
        self.writeSectionAssignments()

        self.writeMainFile()

    def writeMainFile(self):
        psettings = ''
        projectSettingsLoc = self.folderLoc + FileExtension.projectSettings
        with open(projectSettingsLoc, 'r') as f:
            psettings = f.read()

        dsettings = ''
        displaySettingsLoc = self.folderLoc + FileExtension.displaySettings
        with open(displaySettingsLoc, 'r') as f:
            dsettings = f.read()

        floorPlan = ''
        floorPlanLoc = self.folderLoc + FileExtension.floorPlan
        with open(floorPlanLoc, 'r') as f:
            floorPlan = f.read()

        floor = ''
        floorLoc = self.folderLoc + FileExtension.floor
        with open(floorLoc, 'r') as f:
            floor = f.read()

        panel = ''
        panelLoc = self.folderLoc + FileExtension.panel
        with open(panelLoc, 'r') as f:
            panel = f.read()

        bracings = ''
        bracingsLoc = self.folderLoc + FileExtension.bracings
        with open(bracingsLoc, 'r') as f:
            bracings = f.read()

        bGroups = ''
        bGroupsLoc = self.folderLoc + FileExtension.bracingGroups
        with open(bGroupsLoc, 'r') as f:
            bGroups = f.read()

        sGroups = ''
        sGroupsLoc = self.folderLoc + FileExtension.sectionGroups
        with open(sGroupsLoc, 'r') as f:
            sGroups = f.read()

        bAssignments = ''
        bAssignmentsLoc = self.folderLoc + FileExtension.bracingAssignments
        with open(bAssignmentsLoc, 'r') as f:
            bAssignments = f.read()
        
        sAssignments = ''
        sAssignmentsLoc = self.folderLoc + FileExtension.sectionAssignments
        with open(sAssignmentsLoc, 'r') as f:
            sAssignments = f.read()

        with open(self.mainFileLoc, 'w') as mainFile:
            mainFile.write(MFHeader.projectSettings)
            mainFile.write('\n')
            mainFile.write(psettings)

            mainFile.write('\n')
            mainFile.write(MFHeader.displaySettings)
            mainFile.write('\n')
            mainFile.write(dsettings)

            mainFile.write('\n')
            mainFile.write(MFHeader.floorPlans)
            mainFile.write('\n')
            mainFile.write(floorPlan)

            mainFile.write('\n')
            mainFile.write(MFHeader.floors)
            mainFile.write('\n')
            mainFile.write(floor)

            mainFile.write('\n')
            mainFile.write(MFHeader.panels)
            mainFile.write('\n')
            mainFile.write(panel)

            mainFile.write('\n')
            mainFile.write(MFHeader.bracings)
            mainFile.write('\n')
            mainFile.write(bracings)
            
            mainFile.write('\n')
            mainFile.write(MFHeader.bracingGroups)
            mainFile.write('\n')
            mainFile.write(bGroups)

            mainFile.write('\n')
            mainFile.write(MFHeader.sectionGroups)
            mainFile.write('\n')
            mainFile.write(sGroups)

            mainFile.write('\n')
            mainFile.write(MFHeader.bracingAssignments)
            mainFile.write('\n')
            mainFile.write(bAssignments)

            mainFile.write('\n')
            mainFile.write(MFHeader.sectionAssignments)
            mainFile.write('\n')
            mainFile.write(sAssignments)

    def writeProjectSettings(self):
        ''' Write project settings data to file '''
        projectSettingsLoc = self.folderLoc + FileExtension.projectSettings
        psData = self.psData

        psData_dict = {
            'setting':[],
            'value':[],
        }

        # Convert to string
        # elevations
        elevs = ' '.join([str(elev) for elev in psData.floorElevs])
        psData_dict['setting'].append('tower_elevs')
        psData_dict['value'].append(elevs)

        # sections
        for key in psData.sections:
            sect = psData.sections[key]
            psData_dict['setting'].append('sect_props')
            val = str(sect.name) + ' ' + str(sect.rank)
            psData_dict['value'].append(val)

        # Other settings
        psKeys = [
            'gm',
            'analysis',
            'modelLoc',
            'modelName',
            'renderX',
            'renderY',
            'renderZ',
        ]
        
        values = [
            psData.groundMotion,
            EnumToString.ATYPE[psData.analysisType],
            psData.SAPModelLoc,
            psData.modelName,
            psData.renderX,
            psData.renderY,
            psData.renderZ,
        ]

        for i, psKey in enumerate(psKeys):
            psData_dict['setting'].append(psKey)
            psData_dict['value'].append(values[i])

        df = pd.DataFrame(psData_dict)
        df.to_csv(projectSettingsLoc, index=False)

    def writeDisplaySettings(self):
        ''' Write display settings to file '''
        displaySettingsLoc = self.folderLoc + FileExtension.displaySettings
        dSettings = self.tower.displaySettings

        dSettings_dict = {
            'setting':[],
            'value':[],
        }

        dsKeys = [
            '2D_pName',
            '2D_pLength',
        ]

        values = [
            dSettings.pName,
            dSettings.pLength,
        ]

        for i, dsKey in enumerate(dsKeys):
            dSettings_dict['setting'].append(dsKey)
            dSettings_dict['value'].append(values[i])

        df = pd.DataFrame(dSettings_dict)
        df.to_csv(displaySettingsLoc, index=False)

    def writeFloorPlans(self):
        ''' Write floor plans to file '''
        floorPlanLoc = self.folderLoc + FileExtension.floorPlan
        tower = self.tower
        floorPlans = tower.floorPlans

        floorPlanData = {
            'floorPlanName':[],
            'x':[],
            'y':[],
            'bot':[],
            'top':[],
        }

        for fpName in floorPlans:
            floorPlan = floorPlans[fpName]

            botConnections = [0 for i in range(len(floorPlan.nodes))]
            for botLabel in floorPlan.bottomConnections:
                for index in floorPlan.bottomConnections[botLabel]:
                    botConnections[index] = botLabel

            topConnections = [0 for i in range(len(floorPlan.nodes))]
            for topLabel in floorPlan.topConnections:
                for index in floorPlan.topConnections[topLabel]:
                    topConnections[index] = topLabel

            for i, node in enumerate(floorPlan.nodes):
                floorPlanData['floorPlanName'].append(str(fpName))
                floorPlanData['x'].append(str(node.x))
                floorPlanData['y'].append(str(node.y))
                floorPlanData['bot'].append(str(botConnections[i]))
                floorPlanData['top'].append(str(topConnections[i]))

        df = pd.DataFrame(floorPlanData)
        df.to_csv(floorPlanLoc, index=False)

    def writeFloors(self):
        ''' Write floors to file '''
        floorLoc = self.folderLoc + FileExtension.floor
        floors = self.tower.floors

        floorData = {
            'elevation':[],
            'floorPlans':[],
        }

        for elev in floors:
            floor = floors[elev]
            fpNames = ' '.join([str(fp.name) for fp in floor.floorPlans])

            floorData['elevation'].append(str(elev))
            floorData['floorPlans'].append(fpNames)

        df = pd.DataFrame(floorData)
        df.to_csv(floorLoc, index=False)

    def writePanels(self):
        ''' Write panels to file '''
        panelLoc = self.folderLoc + FileExtension.panel
        tower = self.tower
        panels = tower.panels

        panelData = {
            'panelName':[],
            'nodeLocation':[],
            'x':[],
            'y':[],
            'z':[],
        }

        for pName in panels:
            panel = panels[pName]

            panelData['panelName'].append(str(pName))
            panelData['nodeLocation'].append('lowerLeft')
            panelData['x'].append(str(panel.lowerLeft.x))
            panelData['y'].append(str(panel.lowerLeft.y))
            panelData['z'].append(str(panel.lowerLeft.z))
            
            panelData['panelName'].append(str(pName))
            panelData['nodeLocation'].append('upperLeft')
            panelData['x'].append(str(panel.upperLeft.x))
            panelData['y'].append(str(panel.upperLeft.y))
            panelData['z'].append(str(panel.upperLeft.z))
            
            panelData['panelName'].append(str(pName))
            panelData['nodeLocation'].append('upperRight')
            panelData['x'].append(str(panel.upperRight.x))
            panelData['y'].append(str(panel.upperRight.y))
            panelData['z'].append(str(panel.upperRight.z))
            
            panelData['panelName'].append(str(pName))
            panelData['nodeLocation'].append('lowerRight')
            panelData['x'].append(str(panel.lowerRight.x))
            panelData['y'].append(str(panel.lowerRight.y))
            panelData['z'].append(str(panel.lowerRight.z))

        df = pd.DataFrame(panelData)
        df.to_csv(panelLoc, index=False)

    def writeBracings(self):
        ''' Write Bracings to file '''
        bracingsLoc = self.folderLoc + FileExtension.bracings
        tower = self.tower
        bracings = tower.bracings

        bracingsData = {
            'bracingName':[],
            'x1':[],
            'y1':[],
            'x2':[],
            'y2':[],
            'material':[],
        }

        for bName in bracings:
            bracing = bracings[bName]

            for member in bracing.members:
                x1 = member.start_node.x
                y1 = member.start_node.y
                x2 = member.end_node.x
                y2 = member.end_node.y

                mat = member.material

                bracingsData['bracingName'].append(bName)
                bracingsData['x1'].append(str(x1))
                bracingsData['y1'].append(str(y1))
                bracingsData['x2'].append(str(x2))
                bracingsData['y2'].append(str(y2))
                bracingsData['material'].append(mat)

        df = pd.DataFrame(bracingsData)
        df.to_csv(bracingsLoc, index=False)

    def writeBracingGroups(self):
        ''' Write Bracing Groups to file '''
        bGroupsLoc = self.folderLoc + FileExtension.bracingGroups
        tower = self.tower
        bGroups = tower.bracingGroups

        bGroupsData = {
            'bracingGroup':[],
            'bracing':[],
        }

        for bGroupName in bGroups:
            bGroup = bGroups[bGroupName]

            for bName in bGroup.bracings:
                bGroupsData['bracingGroup'].append(bGroupName)
                bGroupsData['bracing'].append(bName)

        df = pd.DataFrame(bGroupsData)
        df.to_csv(bGroupsLoc, index=False)

    def writeSectionGroups(self):
        ''' Write Section Groups to file '''
        sGroupsLoc = self.folderLoc + FileExtension.sectionGroups
        tower = self.tower
        sGroups = tower.sectionGroups

        sGroupsData = {
            'sectionGroup':[],
            'section':[],
        }

        for sGroupName in sGroups:
            sGroup = sGroups[sGroupName]

            for sName in sGroup.sections:
                sGroupsData['sectionGroup'].append(sGroupName)
                sGroupsData['section'].append(sName)

        df = pd.DataFrame(sGroupsData)
        df.to_csv(sGroupsLoc, index=False)

    def writeBracingAssignments(self):
        ''' Write Bracing Assignments to file '''
        bAssignmentsLoc = self.folderLoc + FileExtension.bracingAssignments
        tower = self.tower
        panels = tower.panels

        bAssignmentsData = {
            'panelName':[],
            'bracingGroup':[],
        }

        for pName in panels:
            panel = panels[pName]
            bGroup = panel.bracingGroup

            if bGroup:
                bAssignmentsData['panelName'].append(pName)
                bAssignmentsData['bracingGroup'].append(bGroup)

        df = pd.DataFrame(bAssignmentsData)
        df.to_csv(bAssignmentsLoc, index=False)

    def writeSectionAssignments(self):
        ''' Write Section Assignments to file '''
        sAssignmentsLoc = self.folderLoc + FileExtension.sectionAssignments
        tower = self.tower
        member_ids = tower.member_ids

        sAssignmentsData = {
            'memberid':[],
            'sectionGroup':[],
        }

        for member_id in member_ids:
            sGroup = member_ids[member_id]

            sAssignmentsData['memberid'].append(member_id)
            sAssignmentsData['sectionGroup'].append(sGroup)

        df = pd.DataFrame(sAssignmentsData)
        df.to_csv(sAssignmentsLoc, index=False)

    def writeInputTable(self, inputTable):
        ''' Write Input Table to file '''
        inputTableLoc = self.folderLoc + FileExtension.inputTable

        df = pd.DataFrame(inputTable)
        df.to_csv(inputTableLoc, index=False)