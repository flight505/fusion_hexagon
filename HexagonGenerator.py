"""
Hexagon Pattern Generator Add-In for Autodesk Fusion 360
Mac-compatible Python implementation

This add-in creates hexagonal honeycomb patterns on selected faces or sketch profiles
with options for radius, spacing, and cut-through operations.
"""

import math
import traceback

import adsk.core
import adsk.fusion

# Global variables to maintain state
app = None
ui = None
handlers = []


class HexagonGeneratorCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """Handler for when the command is created."""

    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            cmd = args.command
            cmd.isRepeatable = False

            # Connect to the command execute event
            onExecute = HexagonGeneratorCommandExecuteHandler()
            cmd.execute.add(onExecute)
            handlers.append(onExecute)

            # Connect to the input changed event
            onInputChanged = HexagonGeneratorCommandInputChangedHandler()
            cmd.inputChanged.add(onInputChanged)
            handlers.append(onInputChanged)

            # Connect to the validate inputs event
            onValidateInputs = HexagonGeneratorCommandValidateInputsHandler()
            cmd.validateInputs.add(onValidateInputs)
            handlers.append(onValidateInputs)

            # Create command inputs
            inputs = cmd.commandInputs

            # Create a group for hexagon pattern parameters
            patternGroup = inputs.addGroupCommandInput('patternGroup', 'Hexagon Pattern Parameters')

            # Base Face/Profile selection
            baseSelection = inputs.addSelectionInput(
                'baseSelection', 'Base Face/Profile', 'Select a planar face or sketch profile as the base region'
            )
            baseSelection.addSelectionFilter('PlanarFaces')
            baseSelection.addSelectionFilter('Profiles')
            baseSelection.setSelectionLimits(1, 1)

            # Hexagon Radius input
            defaultRadius = 5.0  # 5mm default
            inputs.addValueInput(
                'hexRadius',
                'Hexagon Radius',
                'mm',
                adsk.core.ValueInput.createByReal(defaultRadius / 10),  # Convert to cm (Fusion internal units)
            )

            # Offset (spacing) input
            defaultOffset = 1.0  # 1mm default
            inputs.addValueInput(
                'hexOffset', 'Offset (Spacing)', 'mm', adsk.core.ValueInput.createByReal(defaultOffset / 10)
            )

            # Create a group for cut options
            cutGroup = inputs.addGroupCommandInput('cutGroup', 'Cut Options (Optional)')

            # Cut operation checkbox
            performCut = inputs.addBoolValueInput('performCut', 'Perform Cut Operation', True, '', False)

            # Cut to face/plane selection
            cutToSelection = inputs.addSelectionInput(
                'cutToSelection', 'Cut To Face/Plane', 'Select target face or plane for cut extent (optional)'
            )
            cutToSelection.addSelectionFilter('PlanarFaces')
            cutToSelection.addSelectionFilter('ConstructionPlanes')
            cutToSelection.setSelectionLimits(0, 1)
            cutToSelection.isEnabled = False
            cutToSelection.isVisible = False

            # Body to cut selection (only enabled when base is a profile)
            bodySelection = inputs.addSelectionInput(
                'bodySelection', 'Body to Cut', 'Select solid body to cut (required if base is a sketch profile)'
            )
            bodySelection.addSelectionFilter('SolidBodies')
            bodySelection.setSelectionLimits(0, 1)
            bodySelection.isEnabled = False
            bodySelection.isVisible = False

            # Orientation option
            orientationList = inputs.addDropDownCommandInput(
                'orientation', 'Hexagon Orientation', adsk.core.DropDownStyles.LabeledIconDropDownStyle
            )
            orientationList.listItems.add('Pointy Top', True)
            orientationList.listItems.add('Flat Top', False)

        except:
            if ui:
                ui.messageBox(f'Failed:\n{traceback.format_exc()}')


class HexagonGeneratorCommandInputChangedHandler(adsk.core.InputChangedEventHandler):
    """Handler for when command inputs change."""

    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            inputs = args.inputs
            changedInput = args.input

            # Handle perform cut checkbox change
            if changedInput.id == 'performCut':
                performCut = inputs.itemById('performCut')
                cutToSelection = inputs.itemById('cutToSelection')
                bodySelection = inputs.itemById('bodySelection')

                cutToSelection.isEnabled = performCut.value
                cutToSelection.isVisible = performCut.value

                # Check if base is a profile to determine if body selection is needed
                baseSelection = inputs.itemById('baseSelection')
                if baseSelection.selectionCount > 0:
                    selection = baseSelection.selection(0)
                    if selection.entity.objectType == 'adsk::fusion::Profile':
                        bodySelection.isEnabled = performCut.value
                        bodySelection.isVisible = performCut.value

            # Handle base selection change
            elif changedInput.id == 'baseSelection':
                baseSelection = inputs.itemById('baseSelection')
                bodySelection = inputs.itemById('bodySelection')
                performCut = inputs.itemById('performCut')

                if baseSelection.selectionCount > 0:
                    selection = baseSelection.selection(0)
                    # If base is a profile, enable body selection when cut is enabled
                    if selection.entity.objectType == 'adsk::fusion::Profile' and performCut.value:
                        bodySelection.isEnabled = True
                        bodySelection.isVisible = True
                    else:
                        bodySelection.isEnabled = False
                        bodySelection.isVisible = False
                        bodySelection.clearSelection()

        except:
            if ui:
                ui.messageBox(f'Input change failed:\n{traceback.format_exc()}')


class HexagonGeneratorCommandValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    """Handler for validating command inputs."""

    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            inputs = args.inputs

            # Check if base selection is made
            baseSelection = inputs.itemById('baseSelection')
            if baseSelection.selectionCount == 0:
                args.areInputsValid = False
                return

            # Check if radius is positive
            hexRadius = inputs.itemById('hexRadius')
            if hexRadius.value <= 0:
                args.areInputsValid = False
                return

            # Check if offset is non-negative
            hexOffset = inputs.itemById('hexOffset')
            if hexOffset.value < 0:
                args.areInputsValid = False
                return

            # If perform cut is enabled and base is a profile, body must be selected
            performCut = inputs.itemById('performCut')
            if performCut.value and baseSelection.selectionCount > 0:
                selection = baseSelection.selection(0)
                if selection.entity.objectType == 'adsk::fusion::Profile':
                    bodySelection = inputs.itemById('bodySelection')
                    if bodySelection.selectionCount == 0:
                        args.areInputsValid = False
                        return

            args.areInputsValid = True

        except:
            args.areInputsValid = False


class HexagonGeneratorCommandExecuteHandler(adsk.core.CommandEventHandler):
    """Handler for command execution."""

    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            inputs = args.command.commandInputs

            # Get input values
            baseSelection = inputs.itemById('baseSelection').selection(0)
            hexRadius = inputs.itemById('hexRadius').value * 10  # Convert from cm to mm for clarity
            hexOffset = inputs.itemById('hexOffset').value * 10  # Convert from cm to mm
            performCut = inputs.itemById('performCut').value
            orientation = inputs.itemById('orientation').selectedItem.name

            cutToEntity = None
            if performCut and inputs.itemById('cutToSelection').selectionCount > 0:
                cutToEntity = inputs.itemById('cutToSelection').selection(0).entity

            targetBody = None
            if performCut and inputs.itemById('bodySelection').selectionCount > 0:
                targetBody = inputs.itemById('bodySelection').selection(0).entity

            # Generate the hexagon pattern
            generator = HexagonPatternGenerator()
            generator.generate(baseSelection.entity, hexRadius, hexOffset, performCut, cutToEntity, targetBody, orientation)

            # Report success
            ui.messageBox('Hexagon pattern generated successfully!')

        except:
            if ui:
                ui.messageBox(f'Command execution failed:\n{traceback.format_exc()}')


class HexagonPatternGenerator:
    """Main class for generating hexagon patterns."""

    def __init__(self):
        self.app = adsk.core.Application.get()
        self.ui = self.app.userInterface
        self.design = self.app.activeProduct
        self.rootComp = self.design.rootComponent

    def generate(self, baseEntity, radius, offset, performCut, cutToEntity, targetBody, orientation):
        """Generate the hexagon pattern on the specified base."""
        try:
            # Create or get sketch
            sketch = self._createSketch(baseEntity)

            # Get the region bounds
            bounds = self._getRegionBounds(baseEntity, sketch)

            # Generate hexagon centers
            centers = self._generateHexagonCenters(bounds, radius, offset, orientation)

            # Filter centers that fit within the region
            validCenters = self._filterValidCenters(centers, baseEntity, radius, sketch)

            # Draw hexagons
            profiles = self._drawHexagons(sketch, validCenters, radius, orientation)

            # Perform cut if requested
            if performCut and profiles:
                self._performCut(profiles, baseEntity, cutToEntity, targetBody)

        except:
            raise

    def _createSketch(self, baseEntity):
        """Create a sketch on the base entity."""
        if baseEntity.objectType == 'adsk::fusion::BRepFace':
            return self.rootComp.sketches.add(baseEntity)
        elif baseEntity.objectType == 'adsk::fusion::Profile':
            # Use the profile's parent sketch plane
            parentSketch = baseEntity.parentSketch
            return self.rootComp.sketches.add(parentSketch.referencePlane)
        else:
            raise ValueError('Unsupported base entity type')

    def _getRegionBounds(self, baseEntity, sketch):
        """Get the bounding box of the region."""
        if baseEntity.objectType == 'adsk::fusion::BRepFace' or baseEntity.objectType == 'adsk::fusion::Profile':
            bbox = baseEntity.boundingBox
        else:
            raise ValueError('Unsupported base entity type')

        # Convert to sketch coordinates
        minPoint = sketch.modelToSketchSpace(bbox.minPoint)
        maxPoint = sketch.modelToSketchSpace(bbox.maxPoint)

        return {'minX': minPoint.x, 'minY': minPoint.y, 'maxX': maxPoint.x, 'maxY': maxPoint.y}

    def _generateHexagonCenters(self, bounds, radius, offset, orientation):
        """Generate potential hexagon center points."""
        centers = []

        # Convert radius and offset to internal units (cm)
        r = radius / 10
        o = offset / 10

        if orientation == 'Pointy Top':
            # Horizontal spacing
            dx = math.sqrt(3) * r + o
            # Vertical spacing
            dy = 1.5 * r + o * math.sqrt(3) / 2
        else:  # Flat Top
            # Horizontal spacing
            dx = 1.5 * r + o * math.sqrt(3) / 2
            # Vertical spacing
            dy = math.sqrt(3) * r + o

        # Generate grid of centers with margin
        margin = r + o
        x_start = bounds['minX'] - margin
        y_start = bounds['minY'] - margin
        x_end = bounds['maxX'] + margin
        y_end = bounds['maxY'] + margin

        row = 0
        y = y_start
        while y <= y_end:
            x = x_start
            if orientation == 'Pointy Top':
                # Offset every other row
                if row % 2 == 1:
                    x += dx / 2
            else:  # Flat Top
                if row % 2 == 1:
                    x += dx / 2

            while x <= x_end:
                centers.append({'x': x, 'y': y})
                x += dx

            y += dy
            row += 1

        return centers

    def _filterValidCenters(self, centers, baseEntity, radius, sketch):
        """Filter centers to only include those that fit within the region."""
        validCenters = []
        r = radius / 10  # Convert to cm

        for center in centers:
            # Check if hexagon at this center fits within the region
            vertices = self._getHexagonVertices(center['x'], center['y'], r, 'Pointy Top')

            allInside = True
            for vertex in vertices:
                point3d = sketch.sketchToModelSpace(adsk.core.Point3D.create(vertex['x'], vertex['y'], 0))

                if baseEntity.objectType == 'adsk::fusion::BRepFace':
                    # Check if point is on face
                    if not self._isPointOnFace(baseEntity, point3d):
                        allInside = False
                        break
                elif baseEntity.objectType == 'adsk::fusion::Profile' and not self._isPointInProfile(baseEntity, vertex, sketch):
                    allInside = False
                    break

            if allInside:
                validCenters.append(center)

        return validCenters

    def _getHexagonVertices(self, cx, cy, radius, orientation):
        """Calculate hexagon vertices given center and radius."""
        vertices = []

        # Start angle: 0 degrees for pointy top, 30 degrees for flat top
        startAngle = 0 if orientation == 'Pointy Top' else math.pi / 6

        for i in range(6):
            angle = startAngle + i * math.pi / 3
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            vertices.append({'x': x, 'y': y})

        return vertices

    def _isPointOnFace(self, face, point):
        """Check if a point is on the face."""
        # Use face's evaluator to check containment
        evaluator = face.evaluator
        (success, param) = evaluator.getParameterAtPoint(point)
        if success:
            (success, testPoint) = evaluator.getPointAtParameter(param)
            if success:
                # Check if the point is close enough to be considered on the face
                distance = point.distanceTo(testPoint)
                return distance < 0.001  # 0.01mm tolerance
        return False

    def _isPointInProfile(self, profile, point2d, sketch):
        """Check if a 2D point is within a profile using simple containment."""
        # For simplicity, check against bounding box
        # In a production version, implement proper point-in-polygon test
        bbox = profile.boundingBox
        minPoint = sketch.modelToSketchSpace(bbox.minPoint)
        maxPoint = sketch.modelToSketchSpace(bbox.maxPoint)

        return (
            point2d['x'] >= minPoint.x
            and point2d['x'] <= maxPoint.x
            and point2d['y'] >= minPoint.y
            and point2d['y'] <= maxPoint.y
        )

    def _drawHexagons(self, sketch, centers, radius, orientation):
        """Draw hexagons in the sketch."""
        r = radius / 10  # Convert to cm
        profiles = []

        for center in centers:
            vertices = self._getHexagonVertices(center['x'], center['y'], r, orientation)

            # Draw hexagon edges
            lines = sketch.sketchCurves.sketchLines
            for i in range(6):
                pt1 = adsk.core.Point3D.create(vertices[i]['x'], vertices[i]['y'], 0)
                pt2 = adsk.core.Point3D.create(vertices[(i + 1) % 6]['x'], vertices[(i + 1) % 6]['y'], 0)
                lines.addByTwoPoints(pt1, pt2)

        # Get all profiles from the sketch
        for profile in sketch.profiles:
            profiles.append(profile)

        return profiles

    def _performCut(self, profiles, baseEntity, cutToEntity, targetBody):
        """Perform the cut operation."""
        try:
            # Determine the target body
            if targetBody is None and baseEntity.objectType == 'adsk::fusion::BRepFace':
                targetBody = baseEntity.body

            if targetBody is None:
                raise ValueError('No target body specified for cut operation')

            # Create object collection for profiles
            profileCollection = adsk.core.ObjectCollection.create()
            for profile in profiles:
                profileCollection.add(profile)

            # Create extrude input
            extrudes = self.rootComp.features.extrudeFeatures
            extrudeInput = extrudes.createInput(profileCollection, adsk.fusion.FeatureOperations.CutFeatureOperation)

            # Set the extent
            if cutToEntity:
                # Use ToEntityExtentDefinition
                extent = adsk.fusion.ToEntityExtentDefinition.create(cutToEntity, True)
                extrudeInput.setOneSideExtent(extent, adsk.fusion.ExtentDirections.NegativeExtentDirection)
            else:
                # Use ThroughAllExtentDefinition for through-all cut
                extent = adsk.fusion.ThroughAllExtentDefinition.create()
                extrudeInput.setOneSideExtent(extent, adsk.fusion.ExtentDirections.NegativeExtentDirection)

            # Set participant body
            extrudeInput.participantBodies = [targetBody]

            # Create the extrude feature
            extrudes.add(extrudeInput)

        except:
            raise


def run(context):
    """Entry point for the add-in."""
    try:
        global app, ui
        app = adsk.core.Application.get()
        ui = app.userInterface

        # Get the command definition or create it
        cmdDef = ui.commandDefinitions.itemById('HexagonGeneratorCmd')
        if not cmdDef:
            cmdDef = ui.commandDefinitions.addButtonDefinition(
                'HexagonGeneratorCmd',
                'Hexagon Pattern Generator',
                'Create hexagon pattern on a face or sketch region',
                './resources',
            )

        # Connect to the command created event
        onCommandCreated = HexagonGeneratorCommandCreatedHandler()
        cmdDef.commandCreated.add(onCommandCreated)
        handlers.append(onCommandCreated)

        # Add the command to the Solid > Create panel
        workspace = ui.workspaces.itemById('FusionSolidEnvironment')
        if workspace:
            panel = workspace.toolbarPanels.itemById('SolidCreatePanel')
            if panel:
                cmdControl = panel.controls.itemById('HexagonGeneratorCmd')
                if not cmdControl:
                    panel.controls.addCommand(cmdDef)

        # Make the command available
        if context['IsApplicationStartup'] is False:
            ui.messageBox('Hexagon Pattern Generator Add-In loaded successfully')

    except:
        if ui:
            ui.messageBox(f'Failed to run add-in:\n{traceback.format_exc()}')


def stop(context):
    """Clean up when the add-in is stopped."""
    try:
        # Remove the command from the UI
        workspace = ui.workspaces.itemById('FusionSolidEnvironment')
        if workspace:
            panel = workspace.toolbarPanels.itemById('SolidCreatePanel')
            if panel:
                cmdControl = panel.controls.itemById('HexagonGeneratorCmd')
                if cmdControl:
                    cmdControl.deleteMe()

        # Delete the command definition
        cmdDef = ui.commandDefinitions.itemById('HexagonGeneratorCmd')
        if cmdDef:
            cmdDef.deleteMe()

    except:
        if ui:
            ui.messageBox(f'Failed to stop add-in:\n{traceback.format_exc()}')

