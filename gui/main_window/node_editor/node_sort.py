from backend.barista.utils.logger import Log
from gui.main_window.node_editor.items.node_item import NodeItem

# TODO:
# -try avoiding intersecting connections (arrange ordered by connectors)

callerId = Log.getCallerId('GraphLayouter')


class NodeSort():

    class Node:
        OFFSET = 50
        CENTER_X = 0
        CENTER_Y = 0

        def __init__(self, guiNode, listOfConnectedNodes):
            self.guiNode = guiNode

            # contains only output nodes of type Node
            self.listOfConnectedNodes = listOfConnectedNodes

            self.height = self.guiNode.boundingRect().height()
            self.width = self.guiNode.boundingRect().width()
            self.x = -1  # mark pos not set yet
            self.y = -1  # mark pos not set yet
            self.visited = False

        def setPosition(self, columnWidths, rowHeights):

            xpos = -NodeSort.Node.CENTER_X
            for x in range(0, self.x):
                xpos += columnWidths[x]+self.OFFSET
            ypos = -NodeSort.Node.CENTER_Y
            for y in range(0, self.y):
                ypos += rowHeights[y]+self.OFFSET

            self.guiNode.setPos(xpos, ypos)

        # Special methods, not really needed noticed to late,
        # handles only if there is a connection between topand bottom

        def getIndexWhereTopEqualsBottom(self):
            '''
            Needed for special cases where the top is
            equal to the bottom (where input is equal to output)
            '''
            if (len(self.listOfConnectedNodes) > 0 and
                    self in self.listOfConnectedNodes):
                    return self.listOfConnectedNodes.index(self)
            return -1

        def getOutputNodesWithoutSelf(self):
            nodes = self.listOfConnectedNodes
            index = self.getIndexWhereTopEqualsBottom()
            if(index != -1):
                # remove index from list
                return nodes[:index] + nodes[index+1:]
            return nodes

    def __init__(self, layers, view, vertical=False):
        self.vertical = vertical
        if(vertical):
            NodeSort.Node.OFFSET = 70
        else:
            NodeSort.Node.OFFSET = 30
        self.__hasCycle = False

        self.columnWidths = []
        self.rowHeights = []

        # all abstract nodes (type Node) that exist
        self.nodes = []
        # all gui nodes that exist
        self.guiNodes = []

        if(type(layers) is list):
            Log.error("wrong type of layers", callerId)
            return
        # fills nodes and guiNodes
        self.getAbstractNodes(layers.values())

        if(self.__hasCycle):
            Log.error("There is a Cycle in that graph, cannot be handled yet", callerId)
            return
        if(not layers.values()):
            return
        self.sort(self.nodes, view)

    def getAbstractNodes(self, graphItems):
        for graphItem in graphItems:
            if(type(graphItem) is NodeItem):
                self.createNodeItem(graphItem, [])

    def createNodeItem(self, guiNode, visitedGuiNodes):
        # if node not handled yet, add it
        if(guiNode not in self.guiNodes):
            outputNodes = []
            # every connector can hold more connections
            connectedGuiNodes = []
            for guiConnectorItem in guiNode.getTopConnectors():
                connectedGuiNodes += guiConnectorItem.getConnectedNodes()

            for guiNodeItem in connectedGuiNodes:
                if(guiNodeItem in visitedGuiNodes):
                    # TODO: GuiNode.setErrorMArker()
                    self.__hasCycle = True
                    return
                newVisitedNodes = list(visitedGuiNodes)
                newVisitedNodes.append(guiNodeItem)
                if guiNodeItem not in self.guiNodes:
                    self.createNodeItem(guiNodeItem, newVisitedNodes)

                if(self.__hasCycle):
                    return
                outputNodes.append(self.nodes[self.guiNodes.index(guiNodeItem)])

            node = NodeSort.Node(guiNode, outputNodes)
            self.nodes.append(node)
            self.guiNodes.append(guiNode)

    def sort(self, listOfNodes, view):
        firstNodes = self.getListOfFirstNodes(listOfNodes)
        # just reset, firstNOdes used this
        self.setAllUnvisited(listOfNodes)

        self.stepSize = 1
        self.x = 0
        self.y = 0
        self.maxY = 0
        self.maxX = 0

        self.traverseConnectedNodes(firstNodes, 0)

        self.setCellSizes(listOfNodes)
        if(self.vertical):
            self.verticalGrid()

        self.setViewBounds(view)
        
        self.updateGuiNodes(listOfNodes)

    def getListOfFirstNodes(self, listOfNodes):
        firstNodes = []
        for ele in listOfNodes:
            ele.visited = True
            for ele2 in listOfNodes:
                if(ele in ele2.listOfConnectedNodes):
                    ele.visited = False
                    break
            if(ele.visited):
                firstNodes.append(ele)
        return firstNodes

    def setAllUnvisited(self, listOfNodes):
        for ele in listOfNodes:
            ele.visited = False

    def traverseConnectedNodes(self, nodes, x):
        y = 0
        for ele in nodes:
            # ele could be visited before, so just if it was not good (to low) calculated reset it
            if ele.x < x:
                ele.x = x
            if ele.y < y:
                # if ele.x changed there must be recalculation for y
                y = self.getCurrentYMaxInColumn(ele.x)
                ele.y = y

            # maximum for maybe needed for make it pretty
            if self.maxX < ele.x:
                self.maxX = ele.x
            if self.maxY < ele.y:
                self.maxY = ele.y

            self.traverseConnectedNodes(ele.listOfConnectedNodes, ele.x+self.stepSize)

    def getCurrentYMaxInColumn(self, x):
        nodesAtX = self.getNodesInColumn(self.nodes, x)
        if(len(nodesAtX) != 0):
            maxY = max(node.y for node in nodesAtX) + self.stepSize
        else:
            maxY = 0
        return maxY

    def updateGuiNodes(self, listOfNodes):
        # set Position for all nodes
        for node in listOfNodes:
            node.setPosition(self.columnWidths, self.rowHeights)

    def getNodesInColumn(self, nodes, x):
        nodesInColumnX = []
        for ele in nodes:
            if(ele.x == x):
                nodesInColumnX.append(ele)
        return nodesInColumnX

    def getNodesInRow(self, nodes, y):
        nodesInRowY = []
        for ele in nodes:
            if(ele.y == y):
                nodesInRowY.append(ele)
        return nodesInRowY

    def setCellSizes(self, nodes):
        # Set Column Width
        for x in range(0, self.maxX+self.stepSize):
            # maxX included because its the maximum USED
            nodesAtX = self.getNodesInColumn(nodes, x)
            # get maxwidth, every node in the column should have this columnwidth
            maxWidth = max(node.width for node in nodesAtX)
            if(self.vertical):
                maxWidth = max(node.height for node in nodesAtX)

            self.columnWidths.append(maxWidth)
        # Set Row Height
        for y in range(0, self.maxY+self.stepSize):
            # maxY included because its the maximum USED
            nodesAtY = self.getNodesInRow(nodes, y)
            # get Maxheight, every node in the row should have this rowheight
            if(len(nodesAtY) != 0):
                maxHeight = max(node.height for node in nodesAtY)
                if(self.vertical):
                    maxHeight = max(node.width for node in nodesAtY)
            else:
                maxHeight = -1
            self.rowHeights.append(maxHeight)

    def setViewBounds(self, view):
        neededWidth = sum(self.columnWidths)+NodeSort.Node.OFFSET*len(self.columnWidths)
        neededHeight = sum(self.rowHeights)+NodeSort.Node.OFFSET*len(self.rowHeights)

        NodeSort.Node.CENTER_X = int(round(neededWidth/2))
        NodeSort.Node.CENTER_Y = int(round(neededHeight/2))

        marginScreen = -(NodeSort.Node.OFFSET/2)

        x = marginScreen-NodeSort.Node.CENTER_X
        y = marginScreen-NodeSort.Node.CENTER_Y

        view.fitInView(x, y, neededWidth, neededHeight, True)

        # doesnt scale anything, only if there is too much zoom
        view.scaleSymmetric(1)

    # Layout vertical
    def verticalGrid(self):
        for node in self.nodes:
            # swap x and y position
            tmp = node.x
            node.x = node.y
            node.y = tmp

        tmp = self.columnWidths
        self.columnWidths = self.rowHeights
        self.rowHeights = tmp
