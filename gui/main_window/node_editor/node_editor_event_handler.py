from PyQt5.QtCore import Qt, QPointF, QPoint, QRect, QRectF, QSize, QSizeF
from PyQt5.QtGui import QTransform, QCursor, QPainterPath
from PyQt5.QtWidgets import QGraphicsView, QRubberBand, QMenu, QInputDialog, QMessageBox

from backend.caffe.dict_helper import DictHelper
from gui.main_window.node_editor.items.connection_item import ConnectionItem
from gui.main_window.node_editor.items.connector_item import ConnectorItem

from gui.main_window.node_editor.items.node_item import NodeItem
from gui.main_window.node_editor.node_editor_constants import Constants

class NodeEditorEventHandler:
    def __init__(self, nodeEditor, view, scene):
        self.nodeEditor = nodeEditor
        self.view = view
        self.scene = scene

        # Declare local variables used in mouse and keyboard events
        self.previousGlobalMousePos = QPointF(0.0, 0.0)
        self.previousLocalMousePos = QPointF(0.0, 0.0)
        self.clickOrigin = QPoint(0, 0)
        self.clearSelection = False
        self.setSelectionToItem = None
        self.removeFromSelection = False
        self.removeFromSelectionItemID = None
        self.pressedItem = None

        # Save the last item the mouse has moved over
        self.lastHoveredItem = None

        # Save whether a button of the mouse or keyboard is currently being held down by user
        self.leftMouseButtonHold = False
        self.middleMouseButtonHold = False

        self.copySelection = []

        self.blockTranslate = False

        # Save whether there is an ongoing rubber band selection
        self.dragMode = "Drag"
        self.dragModeBlocked = False
        self.view.setCursor(QCursor(Qt.OpenHandCursor))
        self.view.setTransformationAnchor(QGraphicsView.NoAnchor)

        # Set standard drag mode and create rubber band element
        self.rubberBand = QRubberBand(QRubberBand.Rectangle, view)

        # Save if editing is allowed
        self.disabled = False

    def wheelEvent(self, QGraphicsSceneWheelEvent):
        # Handle the wheel event, which changes the zoom of the view
        oldScalePos = self.view.mapToScene(QGraphicsSceneWheelEvent.pos())

        if QGraphicsSceneWheelEvent.angleDelta().y() > 0:
            self.view.scaleSymmetric(Constants.viewScaleFactor)
        else:
            self.view.scaleSymmetric(1 / Constants.viewScaleFactor)

        # Store the position of the mouse with the new scaling factor
        newScalePos = self.view.mapToScene(QGraphicsSceneWheelEvent.pos())

        # Translate the view so that the mouse is the anchor for the zoom
        translationFactor = newScalePos - oldScalePos
        self.view.translate(translationFactor.x(), translationFactor.y())

    def mousePressEvent(self, QMouseEvent):
        # Block all changes of the dragging mode
        self.dragModeBlocked = True

        # Transform position into scene position
        scenePos = self.view.mapToScene(QMouseEvent.pos())

        # Take action according to pressed mouse button
        if QMouseEvent.button() == Qt.LeftButton:
            # Store that left mouse button is held down
            self.leftMouseButtonHold = True

            # Further actions according to current mouse mode
            if self.dragMode == "Drag":
                # First of, clear former selection
                self.networkManager.clearSelection()
                for item in self.scene.selectedItems():
                    item.setSelected(False)

                # Store the global position to calculate translation of view on mouse move
                self.previousGlobalMousePos = QMouseEvent.pos()
            elif self.dragMode == "Selection":
                # First of, clear former selection
                self.networkManager.clearSelection()

                # Start the rubber band rectangle selection
                self.clickOrigin = scenePos
                self.rubberBand.setGeometry(QRect(self.view.mapFromScene(self.clickOrigin), QSize()))
                self.rubberBand.show()
            elif self.dragMode == "Items":
                # Selection change when left mouse button is pressed, also prepare for moving selected elements
                self.previousLocalMousePos = scenePos
                self.pressedItem = self.scene.itemAt(scenePos, QTransform())

                if isinstance(self.pressedItem, NodeItem):
                    #check if a connection is in the selection, if yes, clear it from the selection
                    for item in self.scene.selectedItems():
                        if isinstance(item, ConnectionItem):
                            item.setSelected(False)
                    # Check if ctrl key is held down
                    if QMouseEvent.modifiers() & Qt.ControlModifier:
                        # Check if there are connection elements in the selection, if yes, clear selection
                        for item in self.scene.selectedItems():
                            if isinstance(item, ConnectionItem):
                                self.networkManager.clearSelection()
                                break

                        # Check if the item has already been selected
                        if self.pressedItem.isSelected():
                            # Start removing from selection. only finish if items are not moved before mouse release
                            self.removeFromSelection = True
                            self.removeFromSelectionItemID = self.pressedItem.getLayerID()
                        else:
                            self.networkManager.addLayerToSelection(self.pressedItem.getLayerID())
                    else:
                        # Check if there is no currently selected Item
                        if len(self.scene.selectedItems()) == 0:
                            # Select the new Item
                            self.networkManager.setSelection(self.pressedItem.getLayerID())
                        elif len(self.scene.selectedItems()) == 1:
                            # Check if the item has already been selected
                            if self.pressedItem.isSelected():
                                # Start clearing selection, only finish if item is not moved before mouse release
                                self.clearSelection = True
                            else:
                                self.networkManager.setSelection(self.pressedItem.getLayerID())
                        elif len(self.scene.selectedItems()) > 1:
                            # Prepare for the item that has been pressed to be the only selected Item, if it is not moved in the meantime
                            self.setSelectionToItem = scenePos
                elif isinstance(self.pressedItem, ConnectorItem):
                    # Connector has been clicked, start the connection process (further handling in mouse move event)
                    self.scene.startConnection(self.pressedItem, scenePos)
                elif isinstance(self.pressedItem, ConnectionItem):
                    if QMouseEvent.modifiers() & Qt.ControlModifier:
                        # Check if there are node items in the selection, if yes, clear selection
                        if len(self.scene.selectedItems()) > 0:
                            for item in self.scene.selectedItems():
                                if isinstance(item, NodeItem):
                                    self.networkManager.clearSelection()
                                break
                            if self.pressedItem.isSelected():
                                self.pressedItem.setSelected(False)
                            else:
                                self.pressedItem.setSelected(True)
                        else:
                            if self.pressedItem.isSelected():
                                self.pressedItem.setSelected(False)
                            else:
                                self.pressedItem.setSelected(True)
                    else:
                        # Check if the item is already selected
                        if self.pressedItem.isSelected():
                            if len(self.scene.selectedItems()) > 0:
                                self.networkManager.clearSelection()
                                for item in self.scene.selectedItems():
                                    item.setSelected(False)
                                self.pressedItem.setSelected(True)
                            else:
                                self.pressedItem.setSelected(False)
                        else:
                            self.networkManager.clearSelection()
                            for item in self.scene.selectedItems():
                                item.setSelected(False)
                            self.pressedItem.setSelected(True)
        elif QMouseEvent.button() == Qt.RightButton:
            # Store the item that has been pressed by the mouse
            pressedItem = self.scene.itemAt(scenePos, QTransform())

            if isinstance(pressedItem, NodeItem):
                # Make sure item selection is correct
                if not pressedItem.isSelected():
                    if QMouseEvent.modifiers() & Qt.ControlModifier:
                        self.networkManager.addLayerToSelection(pressedItem.getLayerID())
                    else:
                        self.networkManager.setSelection(pressedItem.getLayerID())

                contextMenu = QMenu()
                renamingAction = None
                addTopAction = None
                addBottomAction = None
                removeAction = None
                if not self.disabled:
                    renamingAction = contextMenu.addAction("Rename")
                    addTopAction = contextMenu.addAction("Add top")
                    addBottomAction = contextMenu.addAction("Add bottom")
                copyItemsAction = contextMenu.addAction("Copy")
                if not self.disabled:
                    removeAction = contextMenu.addAction("Remove")

                action = contextMenu.exec_(QMouseEvent.screenPos().toPoint())
                if action is not None:
                    if action == addTopAction:
                        name, ok = QInputDialog.getText(self.view, "Add top blob", "Top blob name:")
                        name = name.strip()
                        duplicateFound = True # search for duplicates
                        # check if name is not whitespace and if name is duplicate, if name is wrong keep asking
                        # until user cancels or enters a valid name
                        while ok:
                            if len(name) == 0:
                                QMessageBox.warning(self.view, "Top blob name is empty",
                                                    "The name for the top blob can't be empty or all whitespace characters.")
                                name, ok = QInputDialog.getText(self.view, "Add top blob", "Top blob name:")
                                name = name.strip()
                            elif duplicateFound:
                                node = self.nodeEditor.getNode(pressedItem.getLayerID())
                                if len(node.getTopConnectors()) > 0:  # if no top connectors, this part ca be skipped
                                    for blob in node.getTopConnectors():
                                        if name == blob.getBlobName():
                                            QMessageBox.warning(self.view, "Top blob name already exists",
                                                                "The name you chose already exists on this Layer, please choose another name.")
                                            name, ok = QInputDialog.getText(self.view, "Change name of top blob",
                                                                            "Top blob name:")
                                            name = name.strip()
                                            duplicateFound = True
                                            break  # stop for loop, continue while loop
                                        else:
                                            duplicateFound = False
                                else:
                                    break  # if no other top blob was found
                            else:
                                break  # if string is valid
                        if ok:
                            self.nodeEditor.tryToAddTopBlob(pressedItem.getLayerID(), name)
                    elif action == addBottomAction:
                        self.nodeEditor.tryToAddBottomBlob(pressedItem.getLayerID(), "")
                    elif action == copyItemsAction:
                        self.nodeEditor.setCopySelection()
                    elif action == removeAction:
                        self.networkManager.deleteSelectedLayers()
                    elif action == renamingAction:
                        layerParams = DictHelper(self.nodeEditor.getNetworkManager().network).layerParams(pressedItem.getLayerID())
                        name, ok = QInputDialog.getText(self.view, "Rename this layer", "New name:", text=layerParams["name"])
                        name = name.strip()
                        while ok:
                            if len(name) == 0:
                                QMessageBox.warning(self.view, "Name is empty",
                                                    "The name of the layer can't be empty or all whitespace characters.")
                                name, ok = QInputDialog.getText(self.view, "Rename this layer", "New name:")
                                name = name.strip()
                            else:
                                layerParams["name"] = name
                                break
            elif isinstance(pressedItem, ConnectionItem):
                self.networkManager.clearSelection()
                for item in self.scene.selectedItems():
                    item.setSelected(False)
                pressedItem.setSelected(True)
            elif pressedItem == None:
                # Open a context menu.
                contextMenu = QMenu()
                # If an item has been copied, show the 'Paste' action.
                if len(self.copySelection) > 0 and not self.disabled:
                    pastAction = contextMenu.addAction("Paste")
                    contextMenu.addSeparator()
                # Add the 'Arrange Network' actions.
                horArrangeAction = contextMenu.addAction("Arrange Network Horizontally")
                vertArrangeAction = contextMenu.addAction("Arrange Network Vertically")
                # Execute the menu and act according to the selected action.
                action = contextMenu.exec_(QMouseEvent.screenPos().toPoint())
                if action and action.text() == 'Paste':
                    self.networkManager.duplicateLayers(self.copySelection, self.view.mapToScene(QMouseEvent.pos()))
                elif action and action.text() == 'Arrange Network Horizontally':
                    self.view.arrangeHorizontallyClicked.emit()
                elif action and action.text() == 'Arrange Network Vertically':
                    self.view.arrangeVerticallyClicked.emit()

    def mouseMoveEvent(self, QMouseEvent):
        # Transform position into scene position
        scenePos = self.view.mapToScene(QMouseEvent.pos())

        if self.leftMouseButtonHold:
            if self.dragMode == "Drag":
                # Set the new mouse cursor
                self.view.setCursor(QCursor(Qt.ClosedHandCursor))

                # Calculate the movement for the view translation
                offset = self.previousGlobalMousePos - QMouseEvent.pos()
                self.previousGlobalMousePos = QMouseEvent.pos()

                offset *= 1/self.view.getScale()

                self.view.translate(-offset.x(), -offset.y())
            elif self.dragMode == "Selection":
                # Check if the user has left the scene with the mouse, if yes, translate accordingly
                if QMouseEvent.pos().x() > self.view.viewport().width() and QMouseEvent.pos().y() > self.view.viewport().height():
                    QCursor.setPos(self.view.mapToGlobal(QPoint(self.view.viewport().width(), self.view.viewport().height())))
                    self.view.translate(-3 * self.view.getScale(), -3 * self.view.getScale())
                elif QMouseEvent.pos().x() < 0 and QMouseEvent.pos().y() < 0:
                    QCursor.setPos(self.view.mapToGlobal(QPoint(1, 1)))
                    self.view.translate(3 * self.view.getScale(), 3 * self.view.getScale())
                elif QMouseEvent.pos().x() > self.view.viewport().width() and QMouseEvent.pos().y() < 0:
                    QCursor.setPos(self.view.mapToGlobal(QPoint(self.view.viewport().width(), 1)))
                    self.view.translate(-3 * self.view.getScale(), 3 * self.view.getScale())
                elif QMouseEvent.pos().x() < 0 and QMouseEvent.pos().y() > self.view.viewport().height():
                    QCursor.setPos(self.view.mapToGlobal(QPoint(1, self.view.viewport().height())))
                    self.view.translate(3 * self.view.getScale(), -3 * self.view.getScale())
                elif QMouseEvent.pos().x() > self.view.viewport().width():
                    QCursor.setPos(self.view.mapToGlobal(QPoint(self.view.viewport().width(), QMouseEvent.pos().y())))
                    self.view.translate(-3 * self.view.getScale(), 0)
                elif QMouseEvent.pos().y() > self.view.viewport().height():
                    QCursor.setPos(self.view.mapToGlobal(QPoint(QMouseEvent.pos().x(), self.view.viewport().height())))
                    self.view.translate(0, -3 * self.view.getScale())
                elif QMouseEvent.pos().x() < -1:
                    QCursor.setPos(self.view.mapToGlobal(QPoint(1, QMouseEvent.pos().y())))
                    self.view.translate(3 * self.view.getScale(), 0)
                elif QMouseEvent.pos().y() < -1:
                    QCursor.setPos(self.view.mapToGlobal(QPoint(QMouseEvent.pos().x(), 1)))
                    self.view.translate(0, 3 * self.view.getScale())

                # Map origin coordinates to current view coordinates
                clickOriginView = self.view.mapFromScene(self.clickOrigin)

                # Calculate the new top left point as well as width and height
                topLeft = QPoint(min(clickOriginView.x(), self.view.mapFromGlobal(QCursor.pos()).x()),
                                 min(clickOriginView.y(), self.view.mapFromGlobal(QCursor.pos()).y()))
                size = QSize(abs(clickOriginView.x() - self.view.mapFromGlobal(QCursor.pos()).x()),
                             abs(clickOriginView.y() - self.view.mapFromGlobal(QCursor.pos()).y()))

                self.rubberBand.setGeometry(QRect(topLeft, size))
            elif self.dragMode == "Items":
                if self.scene.currentlyConnecting is not None and not self.disabled:
                    self.scene.currentlyConnecting.updateMousePosition(scenePos)
                else:
                    # Moving should only be enabled for node items
                    if isinstance(self.pressedItem, NodeItem):
                        if self.pressedItem.isSelected():
                            # Cancel the selection clearing
                            if self.clearSelection:
                                self.clearSelection = False
                            elif self.removeFromSelection:
                                self.removeFromSelection = False
                                self.removeFromSelectionItemID = None
                            elif self.setSelectionToItem is not None:
                                self.setSelectionToItem = None
                        else:  # if the selected item was not selected before
                            self.networkManager.clearSelection()
                            self.networkManager.setSelection(
                            self.scene.itemAt(self.setSelectionToItem, QTransform()).getLayerID())
                            self.clearSelection = False
                            self.removeFromSelection = False
                            self.removeFromSelectionItemID = None
                            self.setSelectionToItem = None
                        # Calculate the change in mouse position
                        currentLocalMousePos = scenePos
                        translation = currentLocalMousePos - self.previousLocalMousePos
                        self.previousLocalMousePos = currentLocalMousePos

                        # Move all selected Elements according to mouse movement
                        resetMouse = self.translateItems(translation.x(), translation.y())

                        if resetMouse:
                            QCursor.setPos(QCursor.pos().x() - translation.x(), QCursor.pos().y() - translation.y())
        else:
            if self.lastHoveredItem != self.scene.itemAt(scenePos, QTransform()):
                # If no button is held down, change mouse pointer according to item it hovers over
                if self.scene.itemAt(scenePos, QTransform()) is None:
                    if QMouseEvent.modifiers() & Qt.ControlModifier:
                        self.view.setCursor(QCursor(Qt.CrossCursor))
                        self.dragMode = "Selection"
                    else:
                        self.view.setCursor(QCursor(Qt.OpenHandCursor))
                        self.dragMode = "Drag"
                else:
                    self.view.setCursor(QCursor(Qt.ArrowCursor))
                    self.dragMode = "Items"

        # Set a new last hovered item
        self.lastHoveredItem = self.scene.itemAt(scenePos, QTransform())

    def mouseReleaseEvent(self, QMouseEvent):
        # Transform position into scene position
        scenePos = self.view.mapToScene(QMouseEvent.pos())

        if QMouseEvent.button() == Qt.LeftButton:
            # Store that button is no longer being held down
            self.leftMouseButtonHold = False

            if self.dragMode == "Drag":
                self.view.setCursor(Qt.OpenHandCursor)
            elif self.dragMode == "Selection":
                # Disable the rubber band selection and hide it
                self.isRubberBandSelection = False
                self.rubberBand.hide()

                # Set the scene selection to all elements within the rubber band area
                painterPath = QPainterPath()

                # Calculate rectangle selection position, using the rubber band will fail at this point
                clickOriginView = self.view.mapFromScene(self.clickOrigin)
                sceneOrigin = self.view.mapToScene(clickOriginView)
                topLeft = QPointF(min(sceneOrigin.x(), scenePos.x()),
                                 min(sceneOrigin.y(), scenePos.y()))
                size = QSizeF(abs(sceneOrigin.x() - scenePos.x()),
                             abs(sceneOrigin.y() - scenePos.y()))

                # Select every element within the rectangle selection
                painterPath.addRect(QRectF(topLeft, size))
                self.scene.setSelectionArea(painterPath, QTransform())

                # Get the ids of all selected elements to set selection to other ui elements
                selectedIDs = []

                # Kick all connection items out of that selection
                for item in self.scene.selectedItems():
                    if isinstance(item, NodeItem):
                        selectedIDs.append(item.getLayerID())
                    item.setSelected(False)

                self.networkManager.setSelectionList(selectedIDs)
            elif self.dragMode == "Items":
                if self.scene.currentlyConnecting is not None:
                    self.scene.connectCurrentConnection(scenePos)
                elif isinstance(self.pressedItem, ConnectorItem):
                    for item in self.scene.selectedItems():
                        item.setSelected(False)
                    self.networkManager.clearSelection()
                    for connection in self.pressedItem.getConnections():
                        connection.setSelected(True)
                elif self.clearSelection:
                    self.networkManager.clearSelection()
                    self.clearSelection = False
                elif self.removeFromSelection and self.removeFromSelectionItemID is not None:
                    self.networkManager.removeLayerFromSelection(self.removeFromSelectionItemID)
                    self.removeFromSelection = False
                    self.removeFromSelectionItemID = None
                elif self.setSelectionToItem is not None:
                    self.networkManager.setSelection(self.scene.itemAt(self.setSelectionToItem, QTransform()).getLayerID())
                    self.setSelectionToItem = None

        # Unblock the drag mode
        self.dragModeBlocked = False

        # Change the cursor type according to the bool value
        if self.lastHoveredItem is None:
            if QMouseEvent.modifiers() & Qt.ControlModifier:
                self.view.setCursor(QCursor(Qt.CrossCursor))
                self.dragMode = "Selection"
            else:
                self.view.setCursor(QCursor(Qt.OpenHandCursor))
                self.dragMode = "Drag"
        else:
            self.view.setCursor(QCursor(Qt.ArrowCursor))
            self.dragMode = "Items"

    def keyPressEvent(self, QKeyEvent):
        if QKeyEvent.key() == Qt.Key_Control:
            self.setCrosshairState(True)
        else:
            if QKeyEvent.key() == Qt.Key_Up:
                self.translateItems(0, - 5 * self.view.getScale())
            if QKeyEvent.key() == Qt.Key_Down:
                self.translateItems(0, 5 * self.view.getScale())
            if QKeyEvent.key() == Qt.Key_Right:
                self.translateItems(5 * self.view.getScale(), 0)
            if QKeyEvent.key() == Qt.Key_Left:
                self.translateItems(- 5 * self.view.getScale(), 0)
            if QKeyEvent.key() == Qt.Key_C:
                if QKeyEvent.modifiers() & Qt.ControlModifier:
                    self.copySelection = []
                    for item in self.scene.selectedItems():
                        # If getLayerId gives an error, do not copy the element
                        try:
                            self.copySelection.append(item.getLayerID())
                        except AttributeError:
                            None
            if QKeyEvent.key() == Qt.Key_V and not self.disabled:
                if len(self.copySelection) > 0:
                    self.networkManager.duplicateLayers(self.copySelection)

    def keyReleaseEvent(self, QKeyEvent):
        if QKeyEvent.key() == Qt.Key_Control:
            self.setCrosshairState(False)
        elif QKeyEvent.key() == Qt.Key_Delete and not self.disabled:
            self.networkManager.deleteSelectedLayers()

    def setNetworkManager(self, networkManager):
        self.networkManager = networkManager

    def setCrosshairState(self, ctrlPressed):
        # Only change state when user is not currently selecting anything
        if not self.dragModeBlocked:
            # Change the cursor type according to the bool value
            if self.lastHoveredItem is None:
                if ctrlPressed:
                    self.view.setCursor(QCursor(Qt.CrossCursor))
                    self.dragMode = "Selection"
                else:
                    self.view.setCursor(QCursor(Qt.OpenHandCursor))
                    self.dragMode = "Drag"
            else:
                self.view.setCursor(QCursor(Qt.ArrowCursor))
                self.dragMode = "Items"

    def translateItems(self, deltaX, deltaY):
        # Moving should only be enabled for node items
        if self.scene.selectedItems() and isinstance(self.scene.selectedItems()[0], NodeItem):

            # Prevent multiple layers from changing relative positions when the scenes border is reached
            selectedItems = self.scene.selectedItems()
            if len(selectedItems) > 0:
                selectedItemsBoundingRect = selectedItems[0].sceneBoundingRect()

                for i in range(1, len(selectedItems)):
                    selectedItemsBoundingRect = selectedItemsBoundingRect.united(selectedItems[i].sceneBoundingRect())

                # Fix for wrong scene bounding rects right and bottom
                selectedItemsBoundingRect.setWidth(selectedItemsBoundingRect.width() + 3)
                selectedItemsBoundingRect.setHeight(selectedItemsBoundingRect.height() + 3)

                newBoundingRect = QRectF(selectedItemsBoundingRect)
                newBoundingRect.moveTo(selectedItemsBoundingRect.topLeft() + QPointF(deltaX, deltaY))

                sceneRect = self.scene.sceneRect()

                moved = False
                if newBoundingRect.left() < sceneRect.left():
                    deltaX = sceneRect.left() - selectedItemsBoundingRect.left()
                    moved = True
                elif newBoundingRect.right() > sceneRect.right():
                    deltaX = sceneRect.right() - selectedItemsBoundingRect.right()
                    moved = True

                if newBoundingRect.top() < sceneRect.top():
                    deltaY = sceneRect.top() - selectedItemsBoundingRect.top()
                    moved = True
                elif newBoundingRect.bottom() > sceneRect.bottom():
                    deltaY = sceneRect.bottom() - selectedItemsBoundingRect.bottom()
                    moved = True

            for item in self.scene.selectedItems():
                item.setPos(item.scenePos() + QPointF(deltaX, deltaY))

            # Check if any of the objects have reached the boundary and the view should be translated
            if len(selectedItems) > 0:
                selectedItemsBoundingRect = selectedItems[0].sceneBoundingRect()

                for i in range(1, len(selectedItems)):
                    selectedItemsBoundingRect = selectedItemsBoundingRect.united(
                        selectedItems[i].sceneBoundingRect())

                newRect = self.view.mapFromScene(selectedItemsBoundingRect).boundingRect()

                if newRect.left() < 0 or newRect.right() > self.view.viewport().width() or newRect.top() < 0 or newRect.bottom() > self.view.viewport().height():
                    self.view.translate(-deltaX, -deltaY)
                    moved = True

            return moved

    def setCopySelection(self):
        self.copySelection = []
        for item in self.scene.selectedItems():
            self.copySelection.append(item.getLayerID())

    def setDisabled(self, disabled):
        self.disabled = disabled
