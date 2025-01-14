from Definition import *    # for constants
import math as m
from DisplaySettings import DisplaySettings
from typing import List
import copy

# Module description: 
# - Stores classes that define the geometry of the tower and its components

# -------------------------------------------------------------------------
# Wrapper class for all data
class Tower:

    def __init__(self, elevations = []):
        # Display Settings
        self.displaySettings = DisplaySettings()

        # Geometry
        self.elevations = elevations
        self.floors = {}
        self.columns = {}
        self.floorPlans = {}
        self.panels = {}
        self.bracings = {}
        self.faces = []

        # Section properties
        self.sections = {}
        self.areaSections = {}

        # Groups and assignments
        self.bracingGroups = {}
        self.sectionGroups = {}
        self.areaSectionGroups = {}
        self.assignments = {}
        
        # Input table
        self.member_ids = {} # Member id from SAP2000 model (key: member_id; value: sectionGroup)
        self.inputTable = {}

        # analysis results for performance analysis
        self.towerPerformances = {}

    def setElevations(self, elevs):
        self.elevations = elevs

    def setSections(self, sects):
        self.sections = sects

    def setAreaSections(self, areaSects):
        self.areaSections = areaSects

    def reset(self):
        ''' clear all data '''
        self.elevations.clear()
        self.floors.clear()
        self.columns.clear()
        self.floorPlans.clear()
        self.panels.clear()
        self.sections.clear()
        self.areaSections.clear()
        self.bracings.clear()
        self.bracingGroups.clear()
        self.sectionGroups.clear()
        self.areaSectionGroups.clear()
        self.assignments.clear()
        self.faces.clear()
        self.member_ids.clear()
        self.inputTable.clear()

    def build(self):
        ''' build tower (assume all tower components are saved in tower)'''
        self.addPanelsToFloors()
        self.generateFaces()
        #for name in self.floorPlans:
            #self.generateFacesByFloorPlan(self.floorPlans[name])
        self.generateColumnsByFace()     

    def defineFloors(self):
        ''' Add Floor objects to the member variables based on the elevations '''
        for elev in self.elevations:
            # Create new floor if needed
            if not (elev in self.floors):
                self.floors[elev] = Floor(elev)

        # Delete redundant floors
        for elev in self.floors:
            if not (elev in self.elevations):
                del self.floors[elev]

    def addFace(self, face):
        ''' Add face object to faces '''
        self.faces.append(face)

    def addFloorPlan(self, floorPlan):
        ''' Add floor plan object to floorPlans '''
        self.floorPlans[floorPlan.name] = floorPlan

    def addPanel(self, panel):
        ''' Add panel object to panels '''
        self.panels[panel.name] = panel

    def addBracing(self, bracing):
        ''' Add bracing object to bracings '''
        self.bracings[bracing.name] = bracing

    def addBracingGroup(self, group):
        ''' Add bracing group object to bracing groups '''
        self.bracingGroups[group.name] = group

    def addSectionGroup(self, group):
        ''' Add section group object to section groups '''
        self.sectionGroups[group.name] = group

    def addAreaSectionGroup(self, group):
        ''' Add area section group object to area section groups '''
        self.areaSectionGroups[group.name] = group

    def addAssignment(self, assignment):
        ''' Add bracing assignment objects to bracing assignments '''
        self.assignments[assignment.name] = assignment

    def addFloorPlansToFloors(self):
        ''' Add floor plans to floors based on the elevation '''
        for floorPlan in self.floorPlans.values():
            for elev in floorPlan.elevations:
                if elev in self.floors:
                    self.floors[elev].addFloorPlan(floorPlan)

    def clearFloor(self):
        '''Clears the floor plan prior to updating them'''
        for elev in self.elevations:
            if elev in self.floors:
                self.floors[elev].floorPlans.clear()
                self.floors[elev].panels.clear()

    def addPanelsToFloors(self):
        ''' Add panels to floors based on the elevation '''
        for panel_id in self.panels:
            panel = self.panels[panel_id]
            panelElevation = panel.lowerLeft.z
            
            if panelElevation in self.elevations: # avoid error due to wrong panel creation
                floor = self.floors[panelElevation]
                floor.addPanel(panel)

    def generatePanels_addToFloors(self):
        self.generatePanelsByFace()
        self.addPanelsToFloors()

    def generateFaces(self):
        ''' Generate face objects '''
        for i in range(len(self.elevations)-1):
            currentElev = self.elevations[i]
            nextElev = self.elevations[i+1]

            currentFloor = self.floors[currentElev]
            nextFloor = self.floors[nextElev]

            numCurrentFloorPlans = len(currentFloor.floorPlans)
            numNextFloorPlans = len(nextFloor.floorPlans)

            if numCurrentFloorPlans > 0 and numNextFloorPlans > 0: # check if floor plan is assigned to floor

                currentFloorPlan = currentFloor.floorPlans[-1]
                nextFloorPlan = nextFloor.floorPlans[0]

                # 1: Convert top connections to list (in order)
                dict_currentTopConnections = currentFloorPlan.topConnections
                list_currentTopConnections = ['' for i in range(len(currentFloorPlan.nodes))] # index: node index; value: label

                for label in dict_currentTopConnections:
                    indices = dict_currentTopConnections[label]
                    for index in indices:
                        list_currentTopConnections[index] = label

                # 2: Construct Face object
                currentMembers = currentFloorPlan.members 
                nextNodes = nextFloorPlan.nodes
                currentNodePairs = currentFloorPlan.nodePairs

                if len(currentMembers) > 1:
                    for j in range(len(currentMembers)):

                        # 2a) Add bottom member
                        currentMember = currentMembers[j]
                        bottomMember = copy.deepcopy(currentMember)

                        bottomMember.start_node.z = currentElev
                        bottomMember.end_node.z = currentElev

                        # 2b) Add top member
                        i_start, i_end = currentNodePairs[j]

                        topStartLabel = list_currentTopConnections[i_start]
                        topEndLabel = list_currentTopConnections[i_end]

                        topStartIndices = [0]
                        if topStartLabel in nextFloorPlan.bottomConnections:
                            topStartIndices = nextFloorPlan.bottomConnections[topStartLabel]

                        topEndIndices = [0]
                        if topEndLabel in nextFloorPlan.bottomConnections:
                            topEndIndices = nextFloorPlan.bottomConnections[topEndLabel]

                        # Generate all permutations
                        for topStartIndex in topStartIndices:
                            for topEndIndex in topEndIndices:
                                topMember = Member()

                                topStart = nextNodes[topStartIndex]
                                topStart = Node(topStart.x, topStart.y, nextElev)
                                topEnd = nextNodes[topEndIndex]
                                topEnd = Node(topEnd.x, topEnd.y, nextElev)

                                topMember.setNodes(topStart, topEnd)

                                face = Face()
                                face.addMember(currentElev, bottomMember)
                                face.addMember(nextElev, topMember)

                                self.faces.append(face)

    def generateFacesByFloorPlan(self, floorPlan):
        ''' Generate face objects by floor plan '''

        for member in floorPlan.members:
            face = Face()
            for elev in floorPlan.elevations:

                memberStart = member.start_node
                memberEnd = member.end_node

                # Add elevation to member
                start = Node()
                start.setLocation(memberStart.x, memberStart.y, elev)
                end = Node()
                end.setLocation(memberEnd.x, memberEnd.y, elev)

                member = Member()
                member.setNodes(start, end)

                face.addMember(elev, member)

            self.faces.append(face)

    def generateFacesByFloorPlans(self, floorPlans):
        ''' Generate face objects by floor plans '''

        # 1. Loop through each floor
        # 2. Retrieve all floor plans
        # 3. Convert to list?

        # Create dictionary for floor plan (value) at every elevation (key)
        allPlans = {}
        for floorPlan in floorPlans:
            for elevation in floorPlan.elevations:
                    allPlans[elevation] = floorPlan

        elevs = list(allPlans.keys())
        elevs.sort()
        
        for i in range (len(elevs)-1):
            # assume all plans have same number of members
            for j in range (len(allPlans[elevs[i]].members)):
                face = Face()

                topMemberStart = allPlans[elevs[i+1]].members[j].start_node
                topMemberEnd = allPlans[elevs[i+1]].members[j].end_node

                botMemberStart = allPlans[elevs[i]].members[j].start_node
                botMemberEnd = allPlans[elevs[i]].members[j].end_node

                topStart = Node()
                topStart.setLocation(topMemberStart.x, topMemberStart.y, elevs[i+1])
                topEnd = Node()
                topEnd.setLocation(topMemberEnd.x, topMemberEnd.y, elevs[i+1])

                botStart = Node()
                botStart.setLocation(botMemberStart.x, botMemberStart.y, elevs[i])
                botEnd = Node()
                botEnd.setLocation(botMemberEnd.x, botMemberEnd.y, elevs[i])

                topMember = Member()
                topMember.setNodes(topStart, topEnd)
                bottomMember = Member()
                bottomMember.setNodes(botStart, botEnd)

                face.addMember(elevs[i], bottomMember)
                face.addMember(elevs[i+1], topMember)

                self.faces.append(face)

    def generatePanelsByFace(self):
        ''' Generate panel objects by faces '''
        for face in self.faces:
            # Step 1: sort the keys out (elevation)
            elevations = list(face.members.keys())
            elevations.sort()
            # Step 2: use members to form panels
            for i in range (len(elevations)-1):
                bottomMember = face.members[elevations[i]]
                topMember = face.members[elevations[i+1]]
                # Step 3: form panel
                panel = Panel()
                panel.definePanelWithMembers(topMember, bottomMember)
                # Step 4: add panel to panels
                self.panels[panel.name] = panel

    def generateColumnsByFace(self):
        ''' Add column objects by face '''
        for face in self.faces:
            # Step 1: sort the keys out (elevation)
            elevations = list(face.members.keys())
            elevations.sort()
            # Step 2: use members to generate columns
            for i in range (len(elevations)-1):
                bottomMember = face.members[elevations[i]]
                topMember = face.members[elevations[i+1]]

                leftColumn = Member()
                leftColumn.setNodes(bottomMember.start_node, topMember.start_node)

                rightColumn = Member()
                rightColumn.setNodes(bottomMember.end_node, topMember.end_node)

                self.columns[leftColumn.name] = leftColumn
                self.columns[rightColumn.name] = rightColumn

# -------------------------------------------------------------------------
class Floor:
    def __init__(self, elevation):
        self.elevation = elevation
        self.nodes = []
        self.floorPlans = []
        self.panels = []
        self.comX = 0.0 # centre of mass in X direction
        self.comY = 0.0 # centre of mass in Y direction
    
    def addPanel(self, panel):
        self.panels.append(panel)

    def addNode(self, node):
        self.nodes.append(node)

    def addFloorPlan(self, floorPlan):
        self.floorPlans.append(floorPlan)

    def __str__(self):
        return 'Floor elevation {}'.format(self.elevation)

# -------------------------------------------------------------------------
class FloorPlan:

    # static variable for id
    id = 1

    def __init__(self, name=None):
        self.name = name    # name is in string form
        if not name:
            self.name = str(FloorPlan.id)
            FloorPlan.id += 1

        self.nodes = []

        self.members = []
        self.elevations = []

        # Top and Bottom connections
        # keys (str): connection label
        # values (list(int)): index of self.nodes
        self.topConnections = {}
        self.bottomConnections = {}

        # node pairs: [[int, int]]
        # indicates the index of nodes in self.nodes
        # starts from 0
        self.nodePairs = []

    def addNode(self, node):
        self.nodes.append(node)

    def addMember(self, member):
        self.members.append(member)

    def generateMembersfromNodes(self):
        self.members.clear()
        for i_start, i_end in self.nodePairs:
            member = Member(self.nodes[i_start], self.nodes[i_end])
            self.addMember(member)

    def generateMemberFromNodePair(self, i_nodePair):
        ''' indice of node pairs list: int '''
        i_start, i_end = self.nodePairs[i_nodePair]
        member = Member(self.nodes[i_start], self.nodes[i_end])
        self.addMember(member)

    def generateNodePairs(self):
        ''' Generate node pairs in sequence of nodes; only for testing purposes '''
        numNodes = len(self.nodes)
        self.nodePairs =  [[i, i+1] for i in range(numNodes-1)] + [[numNodes-1, 0]]

    def addElevation(self, elevation: float):
        self.elevations.append(elevation)

    def addTopConnection(self, label: str, index: List[int]):
        if label in self.topConnections:
            self.topConnections[label].append(index)
        else:
            self.topConnections[label] = [index]

    def addBottomConnection(self, label: str, index: List[int]):
        if label in self.bottomConnections:
            self.bottomConnections[label].append(index)
        else:
            self.bottomConnections[label] = [index]

    def __str__(self):
        return 'Floor Plan {}'.format(self.name)

# -------------------------------------------------------------------------
class Face:

    # static variable for id
    id = 1

    def __init__(self, name=None):

        # Use id as name if name is not provided
        self.name = name
        if not name:
            self.name = str(Face.id)
            Face.id += 1

        # contains horizontal members/beams on the face
        # key: elevation; element: member
        self.members = {}

    def addMember(self, elevation, member):
        self.members[elevation] = member

# -------------------------------------------------------------------------
class Panel:

    # static variable for id
    id = 1

    def __init__(self, name=None):

        # Use id as name if name is not provided
        self.name = name
        if not name:
            self.name = str(Panel.id)
            Panel.id += 1

        # Nodes that define a panel object
        self.lowerLeft = Node()
        self.upperLeft = Node()
        self.upperRight = Node()
        self.lowerRight = Node()

        # Member IDs contained in Panel
        self.memberIDs = ['UNKNOWN']

        # Area Object IDs contained in Panel
        self.areaID= 'UNKNOWN'

        # Bracing that is assigned to a panel object
        self.bracingGroup = ''

        # Area section that is assigned to a panel object
        self.areaSectionGroup = ''

    def definePanelWithNodes(self, lowerLeft, upperLeft, upperRight, lowerRight):
        ''' Define panel with nodes '''
        self.lowerLeft = lowerLeft
        self.upperLeft = upperLeft
        self.upperRight = upperRight
        self.lowerRight = lowerRight

    def definePanelWithMembers(self, topMember, bottomMember):
        ''' Define panel with top and bottom members in the same orientation '''
        self.lowerLeft = bottomMember.start_node
        self.lowerRight = bottomMember.end_node
        self.upperLeft = topMember.start_node
        self.upperRight = topMember.end_node

    def addBracingAssignment(self, bGroup):
        self.bracingGroup = bGroup

    def addAreaSectionAssignment(self, asGroup):
        self.areaSectionGroup = asGroup

    def averageSideLength(self):
        ''' Calculate the average side length of panel'''
        leftMember = Member(self.lowerLeft, self.upperLeft)
        rightMember = Member(self.lowerRight, self.upperRight)
        return (leftMember.length() + rightMember.length())/2

    def __str__(self):
        return "Panel {}".format(self.name)

# -------------------------------------------------------------------------
class Node:

    # static variable for id
    id = 1

    def __init__(self, x = 0, y = 0, z = 0, name = None):

        # Use id if name is not provided
        self.name = name
        if not name:
            self.name = str(Node.id)
            Node.id +=  1

        self.x = x
        self.y = y
        self.z = z

    def setLocation(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z
            
    def __str__(self):
        return '{} ({},{},{})'.format(self.name, self.x, self.y, self.z)

# -------------------------------------------------------------------------
class Member:

    # static variable for id
    id = 1

    def __init__(self, start_node=Node(), end_node=Node(), name=None):

        # Use id if name is not provided
        self.name = name
        if not name:
            self.name = str(Member.id)
            Member.id +=  1

        self.start_node = start_node
        self.end_node = end_node

        self.material = None

    def addMaterial(self, mat):
        self.material = mat

    def setNodes(self, start, end):
        ''' set start and end nodes '''
        self.start_node = start
        self.end_node = end

    # TODO: make this function more generic --> use dot product and numpy
    def angle(self):
        ''' Find angle between the member and the x axis --> in radians '''
        start = self.start_node
        end = self.end_node

        slope = (end.y - start.y) / (end.x - start.x + Algebra.EPSILON) # tolerance to avoid divison by zero
        
        orientationX = end.x - start.x
        orientationY = end.y - start.y

        angle = abs(m.atan(slope))
        
        # First quadrant
        if orientationX >= 0 and orientationY >= 0:
            angle = angle
        # Second quadrant
        elif orientationX < 0 and orientationY > 0:
            angle = m.pi - angle
        # Third quadrant
        elif orientationX <= 0 and orientationY <= 0:
            angle += m.pi
        # Fourth quardant
        elif orientationX > 0 and orientationY < 0:
            angle = m.pi*2 - angle

        return angle
    
    def length(self):
        ''' Euclidean distance from start node to end node '''
        dX = self.end_node.x - self.start_node.x
        dY = self.end_node.y - self.start_node.y
        dZ = self.end_node.z - self.start_node.z

        return m.sqrt(dX**2 + dY**2 + dZ**2)
# --------------------------------------------------------------------------
class Bracing:

    # static variable for id
    id = 1

    def __init__(self, name=None):
        self.name = name    # name is in string form
        if not name:
            self.name = str(Bracing.id)
            Bracing.id += 1

        self.nodePairs = []
        self.members = []
        self.materials = []

    def addNodes(self, node1, node2):
        self.nodePairs.append([node1,node2])

    def addMember(self, member):
        self.members.append(member)

    def addMat(self, mat):
        self.materials.append(mat)

    def generateMembersfromNodes(self):
        numNodePairs = len(self.nodePairs)
        for i in range(numNodePairs):
            member = Member(self.nodePairs[i][0], self.nodePairs[i][1])
            member.addMaterial(self.materials[i])
            self.addMember(member)

    def __str__(self):
        return "Bracing {}".format(self.name)

# --------------------------------------------------------------------------
class Group:
    variables: List[str]
    assignments: List[str]

    # static variable for id
    id = 1

    def __init__(self, name=None):
        self.name = name    # name is in string form
        if not name:
            self.name = str(Group.id)
            Group.id += 1

        self.variables = []
        self.assignments = []
    
    def addVariable(self, var):
        self.variables.append(var)

    def addAssignment(self, assignment):
        self.assignments.append(assignment)

class BracingGroup(Group):
    variables: List[str] # str -> key to bracing objects
    assignments: List[str] # str -> key to panel objects

    def __init__(self, name=None):
        super().__init__(name)

class SectionGroup(Group):
    variables: List[str] # str -> key to section objects
    assignments: List[str] # str -> member ids

    def __init__(self, name=None):
        super().__init__(name)

class AreaSectionGroup(Group):
    variables: List[str] # str -> key to area section objects
    assignments: List[str] # str -> key to panel objects

    def __init__(self, name=None):
        super().__init__(name)

# --------------------------------------------------------------------------
# TODO: remove this class?
class Assignment:

     # static variable for id
    id = 1

    def __init__(self, name=None):
        self.name = name    # name is in string form
        if not name:
            self.name = str(Assignment.id)
            Assignment.id += 1

        self.bracingGroup = None

    def addBracingGroup(self, group):
        self.bracingGroup = group

    def __str__(self):
        return "Assignment {}".format(self.name)

# ---------------------------------
class Section:

    def __init__(self, name, rank):
        self.name = name
        self.rank = rank

    def setName(self, name):
        self.name = name

    def setRank(self, rank):
        self.rank = rank