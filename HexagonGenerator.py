"""
Hexagon Pattern Generator v3.0.0 — Fusion 360 Add-In

Creates honeycomb / n-polygon patterns on planar faces or sketch profiles,
with optional through-cut. Cross-platform (macOS + Windows).

v3.0.0 clean rewrite:
  * SketchLines.addScribedPolygon — one native call per cell, no drift
  * BRepFace.isPointOnFace for true containment (respects face holes)
  * Profile containment via TemporaryBRepManager planar face
  * Hex profile selection by area match (deterministic)
  * Fixed orientation: "Pointy Top" now actually draws pointy-top hexagons
  * Region bounds from real loop vertices in sketch space, not world AABB
  * Module-level handler registry — event handlers survive Python GC
"""

import contextlib
import math
import traceback

import adsk.core
import adsk.fusion

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CMD_ID = 'HexagonGeneratorCmd'
CMD_NAME = 'Hexagon Pattern Generator'
CMD_DESC = 'Create a hexagon/polygon honeycomb pattern on a face or sketch region'

WORKSPACE_ID = 'FusionSolidEnvironment'
TAB_ID = 'SolidTab'
PANEL_ID = 'flight505_3DPrintTools_panel'
PANEL_NAME = '3D Print Tools'
PANEL_ANCHOR = 'SolidModifyPanel'

DEFAULT_DIAMETER_CM = 1.0   # 10 mm (Fusion internal is cm)
DEFAULT_WALL_CM = 0.2       # 2 mm
DEFAULT_SIDES = 6

AREA_MATCH_TOLERANCE = 0.02  # 2% of expected polygon area

# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------

_handlers = []   # keep event handlers alive — Fusion holds only weak refs
_app = None
_ui = None


def _log(msg):
    with contextlib.suppress(Exception):
        adsk.core.Application.get().log(f'[HexagonGenerator] {msg}')


def _error(prefix):
    if _ui:
        _ui.messageBox(f'{prefix}\n{traceback.format_exc()}')


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def run(context):
    global _app, _ui
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface
        _register()
    except Exception:
        _error('Failed to load Hexagon Pattern Generator:')


def stop(context):
    try:
        _unregister()
    except Exception:
        _error('Failed to unload Hexagon Pattern Generator:')


def _register():
    cmd_def = _ui.commandDefinitions.itemById(CMD_ID)
    if not cmd_def:
        cmd_def = _ui.commandDefinitions.addButtonDefinition(
            CMD_ID, CMD_NAME, CMD_DESC, './resources'
        )

    created = _CommandCreatedHandler()
    cmd_def.commandCreated.add(created)
    _handlers.append(created)

    workspace = _ui.workspaces.itemById(WORKSPACE_ID)
    if not workspace:
        return
    solid_tab = workspace.toolbarTabs.itemById(TAB_ID)
    if not solid_tab:
        return

    panel = solid_tab.toolbarPanels.itemById(PANEL_ID)
    if not panel:
        panel = solid_tab.toolbarPanels.add(
            PANEL_ID, PANEL_NAME, PANEL_ANCHOR, False
        )
    if panel and not panel.controls.itemById(CMD_ID):
        ctrl = panel.controls.addCommand(cmd_def)
        ctrl.isPromotedByDefault = True


def _unregister():
    if not _ui:
        return

    workspace = _ui.workspaces.itemById(WORKSPACE_ID)
    if workspace:
        solid_tab = workspace.toolbarTabs.itemById(TAB_ID)
        # Clean the v3 panel and the legacy v1 panel location for safety.
        for pid in (PANEL_ID, 'SolidCreatePanel'):
            panel = None
            if solid_tab:
                panel = solid_tab.toolbarPanels.itemById(pid)
            if not panel:
                panel = workspace.toolbarPanels.itemById(pid)
            if panel:
                ctrl = panel.controls.itemById(CMD_ID)
                if ctrl:
                    ctrl.deleteMe()
                if pid == PANEL_ID and panel.controls.count == 0:
                    panel.deleteMe()

    cmd_def = _ui.commandDefinitions.itemById(CMD_ID)
    if cmd_def:
        cmd_def.deleteMe()

    _handlers.clear()


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

class _CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            cmd.isRepeatable = False

            _build_inputs(cmd.commandInputs)

            on_execute = _CommandExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

            on_input_changed = _InputChangedHandler()
            cmd.inputChanged.add(on_input_changed)
            _handlers.append(on_input_changed)

            on_validate = _ValidateInputsHandler()
            cmd.validateInputs.add(on_validate)
            _handlers.append(on_validate)
        except Exception:
            _error('Command creation failed:')


def _build_inputs(inputs):
    pattern_group = inputs.addGroupCommandInput('patternGroup', 'Pattern Parameters')
    pattern_group.isExpanded = True
    pg = pattern_group.children

    base_sel = pg.addSelectionInput(
        'baseSelection', 'Base Face/Profile',
        'Select a planar face or sketch profile for the pattern',
    )
    base_sel.addSelectionFilter('PlanarFaces')
    base_sel.addSelectionFilter('Profiles')
    base_sel.setSelectionLimits(1, 1)

    pg.addValueInput(
        'hexDiameter', 'Hexagon Diameter', 'mm',
        adsk.core.ValueInput.createByReal(DEFAULT_DIAMETER_CM),
    )
    pg.addValueInput(
        'wallThickness', 'Wall Thickness', 'mm',
        adsk.core.ValueInput.createByReal(DEFAULT_WALL_CM),
    )
    pg.addIntegerSpinnerCommandInput(
        'numSides', 'Number of Sides', 3, 20, 1, DEFAULT_SIDES
    )

    mode = pg.addDropDownCommandInput(
        'patternMode', 'Pattern Mode',
        adsk.core.DropDownStyles.LabeledIconDropDownStyle,
    )
    mode.listItems.add('Bounded (Within Face)', True)
    mode.listItems.add('Unbounded (Extend Beyond)', False)

    align = pg.addDropDownCommandInput(
        'alignment', 'Pattern Alignment',
        adsk.core.DropDownStyles.LabeledIconDropDownStyle,
    )
    align.listItems.add('Center Aligned', True)
    align.listItems.add('Corner Aligned', False)

    orient = pg.addDropDownCommandInput(
        'orientation', 'Cell Orientation',
        adsk.core.DropDownStyles.LabeledIconDropDownStyle,
    )
    orient.listItems.add('Pointy Top', True)
    orient.listItems.add('Flat Top', False)

    adv_group = inputs.addGroupCommandInput('advancedGroup', 'Advanced Options')
    adv_group.isExpanded = False
    ag = adv_group.children
    ag.addBoolValueInput('includeBoundary', 'Project Face Boundary', True, '', False)
    ag.addBoolValueInput('previewMode', 'Preview Only (No Cut)', True, '', False)

    cut_group = inputs.addGroupCommandInput('cutGroup', 'Cut Options')
    cut_group.isExpanded = True
    cg = cut_group.children
    cg.addBoolValueInput('performCut', 'Perform Cut Operation', True, '', True)

    cut_to = cg.addSelectionInput(
        'cutToSelection', 'Cut To Face/Plane',
        'Target face or plane for cut extent (optional — empty = through all)',
    )
    cut_to.addSelectionFilter('PlanarFaces')
    cut_to.addSelectionFilter('ConstructionPlanes')
    cut_to.setSelectionLimits(0, 1)

    body_sel = cg.addSelectionInput(
        'bodySelection', 'Body to Cut',
        'Required when base is a sketch profile',
    )
    body_sel.addSelectionFilter('SolidBodies')
    body_sel.setSelectionLimits(0, 1)
    body_sel.isEnabled = False
    body_sel.isVisible = False


class _InputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            inputs = args.inputs
            changed_id = args.input.id

            preview = inputs.itemById('previewMode')
            perform_cut = inputs.itemById('performCut')
            cut_to = inputs.itemById('cutToSelection')
            body_sel = inputs.itemById('bodySelection')
            base_sel = inputs.itemById('baseSelection')
            pattern_mode = inputs.itemById('patternMode')
            include_boundary = inputs.itemById('includeBoundary')

            if not all([preview, perform_cut, cut_to, body_sel,
                        base_sel, pattern_mode, include_boundary]):
                return

            if changed_id == 'previewMode':
                perform_cut.isEnabled = not preview.value
                if preview.value:
                    perform_cut.value = False
                    cut_to.isEnabled = False
                    cut_to.isVisible = False
                    body_sel.isEnabled = False
                    body_sel.isVisible = False

            elif changed_id == 'performCut':
                if not preview.value:
                    cut_to.isEnabled = perform_cut.value
                    cut_to.isVisible = perform_cut.value
                    is_profile = (
                        base_sel.selectionCount > 0
                        and base_sel.selection(0).entity.objectType
                        == 'adsk::fusion::Profile'
                    )
                    show = perform_cut.value and is_profile
                    body_sel.isVisible = show
                    body_sel.isEnabled = show

            elif changed_id == 'baseSelection':
                is_profile = (
                    base_sel.selectionCount > 0
                    and base_sel.selection(0).entity.objectType
                    == 'adsk::fusion::Profile'
                )
                show = is_profile and perform_cut.value and not preview.value
                body_sel.isVisible = show
                body_sel.isEnabled = show
                if not show:
                    body_sel.clearSelection()

            elif changed_id == 'patternMode':
                include_boundary.isEnabled = (
                    pattern_mode.selectedItem.name == 'Bounded (Within Face)'
                )
        except Exception:
            _error('Input change failed:')


class _ValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            inputs = args.inputs

            base_sel = inputs.itemById('baseSelection')
            hex_d = inputs.itemById('hexDiameter')
            wall = inputs.itemById('wallThickness')
            sides = inputs.itemById('numSides')
            preview = inputs.itemById('previewMode')
            perform_cut = inputs.itemById('performCut')

            if not all([base_sel, hex_d, wall, sides, preview, perform_cut]):
                args.areInputsValid = False
                return

            if base_sel.selectionCount == 0:
                args.areInputsValid = False
                return
            if hex_d.value <= 0 or wall.value < 0 or sides.value < 3:
                args.areInputsValid = False
                return

            if perform_cut.value and not preview.value:
                base_entity = base_sel.selection(0).entity

                cut_to = inputs.itemById('cutToSelection')
                if cut_to and cut_to.selectionCount > 0:
                    cut_entity = cut_to.selection(0).entity
                    if (base_entity.objectType == 'adsk::fusion::BRepFace'
                            and cut_entity.objectType == 'adsk::fusion::BRepFace'
                            and base_entity == cut_entity):
                        args.areInputsValid = False
                        return

                if base_entity.objectType == 'adsk::fusion::Profile':
                    body_sel = inputs.itemById('bodySelection')
                    if not body_sel or body_sel.selectionCount == 0:
                        args.areInputsValid = False
                        return

            args.areInputsValid = True
        except Exception:
            args.areInputsValid = False


class _CommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            inputs = args.command.commandInputs
            params = _collect_params(inputs)
            _generate(**params)
            _log_params(params)
        except Exception:
            _error('Execution failed:')


def _collect_params(inputs):
    base_entity = inputs.itemById('baseSelection').selection(0).entity
    hex_d = inputs.itemById('hexDiameter').value          # cm (Fusion internal)
    wall = inputs.itemById('wallThickness').value          # cm
    sides = int(inputs.itemById('numSides').value)
    pattern_mode = inputs.itemById('patternMode').selectedItem.name
    alignment = inputs.itemById('alignment').selectedItem.name
    orientation = inputs.itemById('orientation').selectedItem.name
    include_boundary = inputs.itemById('includeBoundary').value
    preview = inputs.itemById('previewMode').value
    perform_cut = inputs.itemById('performCut').value and not preview

    cut_to_entity = None
    target_body = None
    if perform_cut:
        cti = inputs.itemById('cutToSelection')
        if cti and cti.selectionCount > 0:
            cut_to_entity = cti.selection(0).entity
        bsi = inputs.itemById('bodySelection')
        if bsi and bsi.selectionCount > 0:
            target_body = bsi.selection(0).entity

    return {
        'base_entity': base_entity,
        'diameter': hex_d,
        'wall': wall,
        'num_sides': sides,
        'pattern_mode': pattern_mode,
        'alignment': alignment,
        'orientation': orientation,
        'include_boundary': include_boundary,
        'preview': preview,
        'perform_cut': perform_cut,
        'cut_to_entity': cut_to_entity,
        'target_body': target_body,
    }


def _log_params(p):
    parts = [
        f"hex={p['diameter'] * 10:g}mm",
        f"wall={p['wall'] * 10:g}mm",
        f"sides={p['num_sides']}",
        f"mode={p['pattern_mode']}",
        f"align={p['alignment']}",
        f"orient={p['orientation']}",
    ]
    if p['include_boundary']:
        parts.append('with_boundary')
    if p['preview']:
        parts.append('preview')
    if p['perform_cut']:
        parts.append('cut')
    _log('pattern ' + ' '.join(parts))


# ---------------------------------------------------------------------------
# Pattern generation
# ---------------------------------------------------------------------------

def _generate(base_entity, diameter, wall, num_sides, pattern_mode,
              alignment, orientation, include_boundary,
              perform_cut, cut_to_entity, target_body, **_unused):
    # **_unused swallows `preview` from _collect_params — it's already
    # been folded into perform_cut by the collector.
    design = adsk.fusion.Design.cast(_app.activeProduct)
    root = design.rootComponent

    sketch = _create_sketch(root, base_entity)

    if include_boundary and base_entity.objectType == 'adsk::fusion::BRepFace':
        _project_face_boundary(sketch, base_entity)

    bounds = _region_bounds_2d(sketch, base_entity)
    centers = _tessellate(bounds, diameter, wall, orientation, alignment)

    if pattern_mode == 'Bounded (Within Face)':
        centers = _filter_centers_inside(
            sketch, base_entity, centers, diameter, num_sides
        )

    if not centers:
        _log('no cells fit inside the selected region')
        return

    _draw_polygons(sketch, centers, diameter, num_sides, orientation)

    if perform_cut:
        profiles = _match_hex_profiles(sketch, diameter, num_sides)
        if profiles:
            _perform_cut(root, profiles, base_entity, target_body, cut_to_entity)
        else:
            _log('warning: no matching polygon profiles found for cut')


def _create_sketch(root, base_entity):
    if base_entity.objectType == 'adsk::fusion::BRepFace':
        return root.sketches.add(base_entity)
    if base_entity.objectType == 'adsk::fusion::Profile':
        return root.sketches.add(base_entity.parentSketch.referencePlane)
    raise ValueError(f'Unsupported base entity type: {base_entity.objectType}')


def _project_face_boundary(sketch, face):
    try:
        outer_loop = face.loops.item(0)
        for edge in outer_loop.edges:
            sketch.project(edge)
    except Exception:
        pass  # reference geometry is nice-to-have, not load-bearing


def _region_bounds_2d(sketch, base_entity):
    """Bounds in sketch 2D space, taken from the true outer loop vertices
    (not the axis-aligned world bounding box — that can be loose for
    rotated or non-planar-aligned faces)."""
    xs = []
    ys = []

    if base_entity.objectType == 'adsk::fusion::BRepFace':
        outer = base_entity.loops.item(0)
        for edge in outer.edges:
            for v in (edge.startVertex, edge.endVertex):
                if v is None:
                    continue
                p2 = sketch.modelToSketchSpace(v.geometry)
                xs.append(p2.x)
                ys.append(p2.y)

    elif base_entity.objectType == 'adsk::fusion::Profile':
        outer = base_entity.profileLoops.item(0)
        for pc in outer.profileCurves:
            g = pc.geometry  # Curve3D in world coordinates
            for attr in ('startPoint', 'endPoint', 'center'):
                if hasattr(g, attr):
                    pt = getattr(g, attr)
                    if pt is not None:
                        p2 = sketch.modelToSketchSpace(pt)
                        xs.append(p2.x)
                        ys.append(p2.y)

    if not xs or not ys:
        bbox = base_entity.boundingBox
        p_min = sketch.modelToSketchSpace(bbox.minPoint)
        p_max = sketch.modelToSketchSpace(bbox.maxPoint)
        return p_min.x, p_min.y, p_max.x, p_max.y

    return min(xs), min(ys), max(xs), max(ys)


def _tessellate(bounds, diameter, wall, orientation, alignment):
    """Generate honeycomb center positions covering the region bounding box.

    Formulas from https://www.redblobgames.com/grids/hexagons/.

    Pointy-top grid (corners at top/bottom, flat edges left/right):
        x_spacing  = d + w                   (flat-to-flat + wall, in-row)
        y_spacing  = (d + w) * sqrt(3) / 2   (between staggered rows)
        row_offset = (d + w) / 2             (every other row shifts by half)

    Flat-top grid (flat edges top/bottom, corners left/right):
        swap x and y.
    """
    s = diameter + wall
    if orientation == 'Pointy Top':
        x_spacing = s
        y_spacing = s * math.sqrt(3) / 2
    else:  # Flat Top
        y_spacing = s
        x_spacing = s * math.sqrt(3) / 2
    row_offset = s / 2

    min_x, min_y, max_x, max_y = bounds
    width = max_x - min_x
    height = max_y - min_y

    if alignment == 'Center Aligned':
        cx = (min_x + max_x) / 2
        cy = (min_y + max_y) / 2
        cols = int(width / max(x_spacing, 1e-9)) + 3
        rows = int(height / max(y_spacing, 1e-9)) + 3
        start_x = cx - (cols // 2) * x_spacing
        start_y = cy - (rows // 2) * y_spacing
    else:  # Corner Aligned
        margin = diameter / 2 + wall
        start_x = min_x + margin
        start_y = min_y + margin
        cols = int(width / max(x_spacing, 1e-9)) + 2
        rows = int(height / max(y_spacing, 1e-9)) + 2

    centers = []
    for r in range(rows):
        y = start_y + r * y_spacing
        for c in range(cols):
            x = start_x + c * x_spacing
            if r % 2 == 1:
                x += row_offset
            centers.append((x, y))
    return centers


def _filter_centers_inside(sketch, base_entity, centers, diameter, num_sides):
    """Keep only centers whose polygon fits fully inside the base region.
    Tests N sample points on the polygon's circumscribed circle."""
    contains = _build_containment_predicate(sketch, base_entity)
    if contains is None:
        return centers  # fail open

    # For a regular n-polygon with inradius d/2,
    # circumradius = (d/2) / cos(pi/n) (= max distance from center to corner).
    circumradius = (diameter / 2) / math.cos(math.pi / num_sides)

    kept = []
    for (cx, cy) in centers:
        ok = True
        for i in range(num_sides):
            a = (2 * math.pi * i) / num_sides
            px = cx + circumradius * math.cos(a)
            py = cy + circumradius * math.sin(a)
            if not contains(px, py):
                ok = False
                break
        if ok:
            kept.append((cx, cy))
    return kept


def _build_containment_predicate(sketch, base_entity):
    """Return a predicate f(x, y) -> bool testing points in sketch 2D space."""

    if base_entity.objectType == 'adsk::fusion::BRepFace':
        face = base_entity

        def test_face(x, y):
            p3 = sketch.sketchToModelSpace(adsk.core.Point3D.create(x, y, 0))
            return face.isPointOnFace(p3)

        return test_face

    if base_entity.objectType == 'adsk::fusion::Profile':
        temp_face = _profile_to_temp_brep_face(base_entity)
        if temp_face is not None:
            def test_profile(x, y):
                p3 = sketch.sketchToModelSpace(
                    adsk.core.Point3D.create(x, y, 0)
                )
                return temp_face.isPointOnFace(p3)
            return test_profile

        _log('profile containment: temp BRep face unavailable, '
             'falling back to bbox')
        bbox = base_entity.boundingBox
        mn = sketch.modelToSketchSpace(bbox.minPoint)
        mx = sketch.modelToSketchSpace(bbox.maxPoint)

        def test_bbox(x, y):
            return mn.x <= x <= mx.x and mn.y <= y <= mx.y

        return test_bbox

    return None


def _profile_to_temp_brep_face(profile):
    """Build a temporary planar BRep face from a sketch Profile's outer loop.
    Returns None on any failure — caller should fall back."""
    try:
        temp_mgr = adsk.fusion.TemporaryBRepManager.get()

        outer = profile.profileLoops.item(0)
        curves_3d = []
        for pc in outer.profileCurves:
            g = pc.geometry
            if g is not None:
                curves_3d.append(g)
        if not curves_3d:
            return None

        # createWireFromCurves returns (wire_body, edge_map)
        wire_result = temp_mgr.createWireFromCurves(curves_3d, True)
        wire_body = wire_result[0] if isinstance(wire_result, tuple) else wire_result
        if wire_body is None:
            return None

        face_body = temp_mgr.createFaceFromPlanarWires([wire_body])
        if face_body is None or face_body.faces.count == 0:
            return None
        return face_body.faces.item(0)
    except Exception:
        return None


def _draw_polygons(sketch, centers, diameter, num_sides, orientation):
    """Draw a regular polygon at each center via addScribedPolygon.

    addScribedPolygon(centerPoint, edgeCount, angle, radius, isInscribed):
      * isInscribed=False  -> `radius` is the inradius (center → edge mid)
        which is exactly d/2 for our flat-to-flat definition.
      * `angle` rotates the first corner CCW from the +X axis.

    For hexagons (num_sides = 6):
      * angle = 0      -> corners at 0°, 60°, 120°, ... : two corners on
                          the X axis, flat edges top and bottom.  FLAT TOP.
      * angle = pi/6   -> corners at 30°, 90°, 150°, ...: a corner straight
                          up on the Y axis, flat edges left and right.
                          POINTY TOP.  (This is the bug fix from v2.2.1,
                          where the label was inverted.)

    For other n, we put a corner at the top (+Y axis).
    """
    if num_sides == 6:  # noqa: SIM108 — nested ternary hurts readability here
        angle = math.pi / 6 if orientation == 'Pointy Top' else 0.0
    else:
        angle = math.pi / 2

    inradius = diameter / 2
    lines = sketch.sketchCurves.sketchLines
    for (cx, cy) in centers:
        center_pt = adsk.core.Point3D.create(cx, cy, 0)
        lines.addScribedPolygon(center_pt, num_sides, angle, inradius, False)


def _match_hex_profiles(sketch, diameter, num_sides):
    """Return sketch profiles whose area matches a regular n-polygon with
    inradius d/2. Deterministic, independent of profile count or layout.

    Regular n-polygon area with inradius r:
        A = n * r^2 * tan(pi / n)

    For a hexagon with d = 10 mm: A = 6 * 25 * tan(30°) = 86.6 mm² (0.866 cm²).
    """
    r = diameter / 2
    expected_area = num_sides * r * r * math.tan(math.pi / num_sides)
    tol = expected_area * AREA_MATCH_TOLERANCE

    matched = []
    for p in sketch.profiles:
        try:
            area = p.areaProperties().area
        except Exception:
            continue
        if abs(area - expected_area) <= tol:
            matched.append(p)

    _log(f'matched {len(matched)} cell profiles '
         f'(expected area {expected_area:.4f} cm²)')
    return matched


def _perform_cut(root, profiles, base_entity, target_body, cut_to_entity):
    if target_body is None and base_entity.objectType == 'adsk::fusion::BRepFace':
        target_body = base_entity.body
    if target_body is None:
        raise ValueError('No target body specified for cut operation')

    profile_coll = adsk.core.ObjectCollection.create()
    for p in profiles:
        profile_coll.add(p)

    extrudes = root.features.extrudeFeatures
    ext_input = extrudes.createInput(
        profile_coll, adsk.fusion.FeatureOperations.CutFeatureOperation
    )

    if cut_to_entity:
        extent = adsk.fusion.ToEntityExtentDefinition.create(cut_to_entity, True)
    else:
        extent = adsk.fusion.ThroughAllExtentDefinition.create()

    ext_input.setOneSideExtent(
        extent, adsk.fusion.ExtentDirections.NegativeExtentDirection
    )
    ext_input.participantBodies = [target_body]
    extrudes.add(ext_input)
