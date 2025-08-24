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

            # Create a group for pattern parameters with industry-standard terminology
            patternGroup = inputs.addGroupCommandInput('patternGroup', 'Pattern Parameters')
            patternGroup.isExpanded = True  # Make group expandable/collapsible
            patternGroupInputs = patternGroup.children

            # Base Face/Profile selection (add to pattern group)
            baseSelection = patternGroupInputs.addSelectionInput(
                'baseSelection', 'Base Face/Profile', 'Select a planar face or sketch profile for the pattern'
            )
            baseSelection.addSelectionFilter('PlanarFaces')
            baseSelection.addSelectionFilter('Profiles')
            baseSelection.setSelectionLimits(1, 1)

            # Phase 2: Industry-standard terminology
            # Hexagon Diameter input (instead of radius)
            defaultDiameter = 1.0  # 10mm = 1cm default diameter (Fusion uses cm internally)
            patternGroupInputs.addValueInput(
                'hexDiameter',
                'Hexagon Diameter',
                'mm',
                adsk.core.ValueInput.createByReal(defaultDiameter),
            )

            # Wall Thickness input (instead of offset/spacing)
            defaultWallThickness = 0.2  # 2mm = 0.2cm default wall thickness (Fusion uses cm internally)
            patternGroupInputs.addValueInput(
                'wallThickness',
                'Wall Thickness',
                'mm',
                adsk.core.ValueInput.createByReal(defaultWallThickness)
            )

            # Number of Sides input (for future polygon support)
            patternGroupInputs.addValueInput(
                'numSides',
                'Number of Sides',
                '',
                adsk.core.ValueInput.createByReal(6)  # Default to hexagon
            )

            # Pattern Mode dropdown
            patternModeList = patternGroupInputs.addDropDownCommandInput(
                'patternMode',
                'Pattern Mode',
                adsk.core.DropDownStyles.LabeledIconDropDownStyle
            )
            patternModeList.listItems.add('Bounded (Within Face)', True)
            patternModeList.listItems.add('Unbounded (Extend Beyond)', False)

            # Pattern Alignment dropdown
            alignmentList = patternGroupInputs.addDropDownCommandInput(
                'alignment',
                'Pattern Alignment',
                adsk.core.DropDownStyles.LabeledIconDropDownStyle
            )
            alignmentList.listItems.add('Center Aligned', True)
            alignmentList.listItems.add('Corner Aligned', False)

            # Orientation option
            orientationList = patternGroupInputs.addDropDownCommandInput(
                'orientation', 'Cell Orientation', adsk.core.DropDownStyles.LabeledIconDropDownStyle
            )
            orientationList.listItems.add('Pointy Top', True)
            orientationList.listItems.add('Flat Top', False)

            # Create a group for advanced options
            advancedGroup = inputs.addGroupCommandInput('advancedGroup', 'Advanced Options')
            advancedGroup.isExpanded = False  # Start collapsed
            advancedGroupInputs = advancedGroup.children

            # Include Boundary checkbox
            includeBoundary = advancedGroupInputs.addBoolValueInput(
                'includeBoundary',
                'Project Face Boundary',
                True,
                '',
                False
            )

            # Preview Mode checkbox
            previewMode = advancedGroupInputs.addBoolValueInput(
                'previewMode',
                'Preview Only (No Cut)',
                True,
                '',
                False
            )

            # Create a group for cut options
            cutGroup = inputs.addGroupCommandInput('cutGroup', 'Cut Options')
            cutGroup.isExpanded = True
            cutGroupInputs = cutGroup.children

            # Cut operation checkbox
            performCut = cutGroupInputs.addBoolValueInput('performCut', 'Perform Cut Operation', True, '', True)

            # Cut to face/plane selection
            cutToSelection = cutGroupInputs.addSelectionInput(
                'cutToSelection', 'Cut To Face/Plane', 'Select target face or plane for cut extent (optional)'
            )
            cutToSelection.addSelectionFilter('PlanarFaces')
            cutToSelection.addSelectionFilter('ConstructionPlanes')
            cutToSelection.setSelectionLimits(0, 1)

            # Body to cut selection (only enabled when base is a profile)
            bodySelection = cutGroupInputs.addSelectionInput(
                'bodySelection', 'Body to Cut', 'Select solid body to cut (required if base is a sketch profile)'
            )
            bodySelection.addSelectionFilter('SolidBodies')
            bodySelection.setSelectionLimits(0, 1)
            bodySelection.isEnabled = False
            bodySelection.isVisible = False

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

            # Handle preview mode change
            if changedInput.id == 'previewMode':
                previewMode = inputs.itemById('previewMode')
                performCut = inputs.itemById('performCut')
                cutToSelection = inputs.itemById('cutToSelection')
                bodySelection = inputs.itemById('bodySelection')

                # Add null checks for all inputs
                if not previewMode or not performCut or not cutToSelection or not bodySelection:
                    return
                    
                # Disable cut options in preview mode
                performCut.isEnabled = not previewMode.value
                if previewMode.value:
                    performCut.value = False
                    cutToSelection.isEnabled = False
                    cutToSelection.isVisible = False
                    bodySelection.isEnabled = False
                    bodySelection.isVisible = False

            # Handle perform cut checkbox change
            elif changedInput.id == 'performCut':
                performCut = inputs.itemById('performCut')
                cutToSelection = inputs.itemById('cutToSelection')
                bodySelection = inputs.itemById('bodySelection')
                previewMode = inputs.itemById('previewMode')

                # Add null checks for all inputs
                if not performCut or not cutToSelection or not bodySelection or not previewMode:
                    return
                    
                if not previewMode.value:
                    cutToSelection.isEnabled = performCut.value
                    cutToSelection.isVisible = performCut.value

                    # Check if base is a profile to determine if body selection is needed
                    baseSelection = inputs.itemById('baseSelection')
                    if baseSelection.selectionCount > 0:
                        selection = baseSelection.selection(0)
                        if selection.entity.objectType == 'adsk::fusion::Profile':
                            bodySelection.isVisible = performCut.value
                            bodySelection.isEnabled = performCut.value

            # Handle base selection change
            elif changedInput.id == 'baseSelection':
                baseSelection = inputs.itemById('baseSelection')
                bodySelection = inputs.itemById('bodySelection')
                performCut = inputs.itemById('performCut')
                previewMode = inputs.itemById('previewMode')

                # Add null checks for all inputs
                if not baseSelection or not bodySelection or not performCut or not previewMode:
                    return
                
                if baseSelection.selectionCount > 0:
                    selection = baseSelection.selection(0)
                    # If base is a profile, enable body selection when cut is enabled
                    if selection.entity.objectType == 'adsk::fusion::Profile' and performCut.value and not previewMode.value:
                        bodySelection.isVisible = True
                        bodySelection.isEnabled = True
                    else:
                        bodySelection.isEnabled = False
                        bodySelection.isVisible = False
                        bodySelection.clearSelection()

            # Handle pattern mode change
            elif changedInput.id == 'patternMode':
                patternMode = inputs.itemById('patternMode')
                includeBoundary = inputs.itemById('includeBoundary')
                
                # Add null checks for all inputs
                if not patternMode or not includeBoundary:
                    return
                    
                # Enable boundary projection for bounded mode
                includeBoundary.isEnabled = (patternMode.selectedItem.name == 'Bounded (Within Face)')

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
            if not baseSelection or baseSelection.selectionCount == 0:
                args.areInputsValid = False
                return

            # Check if diameter is positive
            hexDiameter = inputs.itemById('hexDiameter')
            if not hexDiameter or hexDiameter.value <= 0:
                args.areInputsValid = False
                return

            # Check if wall thickness is non-negative
            wallThickness = inputs.itemById('wallThickness')
            if not wallThickness or wallThickness.value < 0:
                args.areInputsValid = False
                return

            # Check number of sides is valid (3 or more)
            numSides = inputs.itemById('numSides')
            if not numSides or numSides.value < 3:
                args.areInputsValid = False
                return

            # If perform cut is enabled and not in preview mode
            previewMode = inputs.itemById('previewMode')
            performCut = inputs.itemById('performCut')
            
            # Add null checks
            if not previewMode or not performCut:
                args.areInputsValid = False
                return

            if performCut.value and not previewMode.value and baseSelection.selectionCount > 0:
                selection = baseSelection.selection(0)

                # v2.1: Validate cut-to face is not the same as base face
                cutToSelection = inputs.itemById('cutToSelection')
                if cutToSelection.selectionCount > 0:
                    cutToEntity = cutToSelection.selection(0).entity
                    baseEntity = selection.entity

                    # Check if both are faces and if they're the same face
                    if (baseEntity.objectType == 'adsk::fusion::BRepFace' and
                        cutToEntity.objectType == 'adsk::fusion::BRepFace' and
                        baseEntity == cutToEntity):
                        args.areInputsValid = False
                        return

                # Check if body selection is needed for profiles
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

            # Get input values with new terminology
            baseSelection = inputs.itemById('baseSelection').selection(0)
            hexDiameter = inputs.itemById('hexDiameter').value  # Already in cm from Fusion
            wallThickness = inputs.itemById('wallThickness').value  # Already in cm from Fusion
            numSides = int(inputs.itemById('numSides').value)
            patternMode = inputs.itemById('patternMode').selectedItem.name
            alignment = inputs.itemById('alignment').selectedItem.name
            orientation = inputs.itemById('orientation').selectedItem.name
            includeBoundary = inputs.itemById('includeBoundary').value
            previewMode = inputs.itemById('previewMode').value
            performCut = inputs.itemById('performCut').value and not previewMode

            cutToEntity = None
            if performCut and inputs.itemById('cutToSelection').selectionCount > 0:
                cutToEntity = inputs.itemById('cutToSelection').selection(0).entity

            targetBody = None
            if performCut and inputs.itemById('bodySelection').selectionCount > 0:
                targetBody = inputs.itemById('bodySelection').selection(0).entity

            # Generate the pattern with new parameters
            generator = HexagonPatternGenerator()
            generator.generateV2(
                baseSelection.entity,
                hexDiameter,
                wallThickness,
                numSides,
                patternMode,
                alignment,
                orientation,
                includeBoundary,
                performCut,
                cutToEntity,
                targetBody
            )

            # Report success only for preview mode
            if previewMode:
                ui.messageBox('Pattern preview generated successfully! Review the sketch before proceeding.')

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

    def generateV2(self, baseEntity, diameter, wallThickness, numSides, patternMode, alignment,
                   orientation, includeBoundary, performCut, cutToEntity, targetBody):
        """Generate pattern with v2.0 features and corrected algorithm."""
        try:
            # Create or get sketch
            sketch = self._createSketch(baseEntity)

            # Project face boundary if requested (Phase 4 feature)
            if includeBoundary and baseEntity.objectType == 'adsk::fusion::BRepFace':
                self._projectFaceBoundary(baseEntity, sketch)

            # Get the region bounds
            bounds = self._getRegionBounds(baseEntity, sketch)

            # Convert diameter to radius for internal calculations
            # For hexagons: diameter is the flat-to-flat distance
            # Circumradius = flat-to-flat / √3
            if numSides == 6:
                radius = diameter / math.sqrt(3)
            else:
                # For other polygons, treat diameter as the circumscribed circle diameter
                radius = diameter / 2

            # Phase 3: Corrected pattern generation algorithm
            centers = self._generateCentersV2(bounds, diameter, wallThickness, alignment, orientation)

            # Phase 4: Boundary control
            if patternMode == 'Bounded (Within Face)':
                # Only include cells fully within the boundary
                validCenters = self._filterValidCenters(centers, baseEntity, radius, sketch)
            else:
                # Unbounded mode - use all generated centers
                validCenters = centers

            # Draw polygons (hexagons or other n-sided shapes)
            profiles = self._drawPolygons(sketch, validCenters, radius, numSides, orientation)

            # Perform cut if requested and not in preview mode
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

        r = radius  # Already in cm
        o = offset  # Already in cm

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
        r = radius  # Already in cm

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
        r = radius  # Already in cm
        profiles = []

        for center in centers:
            vertices = self._getHexagonVertices(center['x'], center['y'], r, orientation)

            # Draw hexagon edges
            lines = sketch.sketchCurves.sketchLines
            for i in range(6):
                pt1 = adsk.core.Point3D.create(vertices[i]['x'], vertices[i]['y'], 0)
                pt2 = adsk.core.Point3D.create(vertices[(i + 1) % 6]['x'], vertices[(i + 1) % 6]['y'], 0)
                lines.addByTwoPoints(pt1, pt2)

        # v2.1 Fix: Correctly identify hexagon profiles for cutting
        # The hexagons are the holes/voids we want to cut out
        # Each hexagon creates a profile with profileLoops.count == 1
        # We need to collect these individual hexagon profiles, NOT the outer boundary

        # First, check if we drew any hexagons
        if len(centers) == 0:
            return profiles

        # Get the bounding box of the sketch to identify the outer boundary
        sketchBounds = sketch.boundingBox

        for profile in sketch.profiles:
            # Skip profiles that are likely the outer boundary
            profileBounds = profile.boundingBox

            # Check if this profile is much smaller than the sketch bounds
            # (indicating it's a hexagon, not the outer boundary)
            widthRatio = (profileBounds.maxPoint.x - profileBounds.minPoint.x) / (sketchBounds.maxPoint.x - sketchBounds.minPoint.x)
            heightRatio = (profileBounds.maxPoint.y - profileBounds.minPoint.y) / (sketchBounds.maxPoint.y - sketchBounds.minPoint.y)

            # If the profile is less than 50% of the sketch size, it's likely a hexagon
            if widthRatio < 0.5 and heightRatio < 0.5:
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

    def _projectFaceBoundary(self, face, sketch):
        """Project face boundary edges to sketch as reference."""
        try:
            # Get the outer loop of the face
            outerLoop = face.loops.item(0)  # First loop is always the outer boundary

            # Project each edge in the loop to the sketch
            for edge in outerLoop.edges:
                # Use the simple project method for compatibility
                sketch.project(edge)

        except:
            # Silently fail if projection not supported
            pass

    def _generateCentersV2(self, bounds, diameter, wallThickness, alignment, orientation):
        """Generate pattern centers with v2.1.2 corrected honeycomb algorithm."""
        centers = []

        d = diameter  # Already in cm
        w = wallThickness  # Already in cm

        # v2.1.2 Fix: Correct honeycomb spacing based on hexagon geometry
        # For hexagons with flat-to-flat distance d and wall thickness w:
        # The side length a = d/√3
        # Adjacent hexagons are separated by wall thickness w
        # So the effective flat-to-flat for spacing = d + w
        # Then the effective side length = (d + w)/√3
        
        # Calculate the effective side length for spacing
        effective_flat_to_flat = d + w
        effective_side_length = effective_flat_to_flat / math.sqrt(3)

        if orientation == 'Pointy Top':
            # For pointy-top hexagons:
            # Based on user measurement: center-to-center = √3 * (d + w)
            # This suggests the spacing should be multiplied by √3
            x_spacing = math.sqrt(3) * effective_flat_to_flat  
            y_spacing = 1.5 * effective_flat_to_flat
            row_offset = x_spacing / 2
        else:  # Flat Top
            # For flat-top hexagons:
            # Horizontal spacing = 1.5 * effective_flat_to_flat
            # Vertical spacing = √3 * effective_flat_to_flat
            x_spacing = 1.5 * effective_flat_to_flat
            y_spacing = math.sqrt(3) * effective_flat_to_flat
            row_offset = x_spacing / 2

        # Calculate pattern origin based on alignment
        if alignment == 'Center Aligned':
            # Center the pattern on the face
            center_x = (bounds['minX'] + bounds['maxX']) / 2
            center_y = (bounds['minY'] + bounds['maxY']) / 2

            # Calculate how many cells fit in each direction
            width = bounds['maxX'] - bounds['minX']
            height = bounds['maxY'] - bounds['minY']

            cols = int(width / x_spacing) + 2
            rows = int(height / y_spacing) + 2

            # Start from center and work outward
            start_x = center_x - (cols // 2) * x_spacing
            start_y = center_y - (rows // 2) * y_spacing
        else:  # Corner Aligned
            # Start from bottom-left corner
            margin = d / 2 + w
            start_x = bounds['minX'] + margin
            start_y = bounds['minY'] + margin

            width = bounds['maxX'] - bounds['minX']
            height = bounds['maxY'] - bounds['minY']

            cols = int(width / x_spacing) + 1
            rows = int(height / y_spacing) + 1

        # Generate grid of centers
        for row in range(rows):
            y = start_y + row * y_spacing
            for col in range(cols):
                x = start_x + col * x_spacing

                # Apply row offset for honeycomb pattern
                if row % 2 == 1:
                    x += row_offset

                centers.append({'x': x, 'y': y})

        return centers

    def _drawPolygons(self, sketch, centers, radius, numSides, orientation):
        """Draw n-sided polygons (default hexagons) in the sketch."""
        r = radius  # Already in cm
        profiles = []

        for center in centers:
            vertices = self._getPolygonVertices(center['x'], center['y'], r, numSides, orientation)

            # Draw polygon edges
            lines = sketch.sketchCurves.sketchLines
            for i in range(numSides):
                pt1 = adsk.core.Point3D.create(vertices[i]['x'], vertices[i]['y'], 0)
                pt2 = adsk.core.Point3D.create(vertices[(i + 1) % numSides]['x'],
                                              vertices[(i + 1) % numSides]['y'], 0)
                lines.addByTwoPoints(pt1, pt2)

        # v2.1 Fix: Collect individual polygon profiles for cutting
        if len(centers) == 0:
            return profiles

        # Get sketch bounds to identify outer boundary
        sketchBounds = sketch.boundingBox

        for profile in sketch.profiles:
            profileBounds = profile.boundingBox

            # Check if profile is smaller than sketch (individual polygon, not boundary)
            widthRatio = (profileBounds.maxPoint.x - profileBounds.minPoint.x) / (sketchBounds.maxPoint.x - sketchBounds.minPoint.x)
            heightRatio = (profileBounds.maxPoint.y - profileBounds.minPoint.y) / (sketchBounds.maxPoint.y - sketchBounds.minPoint.y)

            if widthRatio < 0.5 and heightRatio < 0.5:
                profiles.append(profile)

        return profiles

    def _getPolygonVertices(self, cx, cy, radius, numSides, orientation):
        """Calculate vertices for an n-sided polygon."""
        vertices = []

        # Adjust start angle based on orientation
        if numSides == 6:  # Hexagon
            startAngle = 0 if orientation == 'Pointy Top' else math.pi / 6
        else:
            # For other polygons, start at top
            startAngle = -math.pi / 2

        angleStep = 2 * math.pi / numSides

        for i in range(numSides):
            angle = startAngle + i * angleStep
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            vertices.append({'x': x, 'y': y})

        return vertices


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
        # Removed startup message for cleaner experience

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

