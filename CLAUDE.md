# CLAUDE.md - Hexagon Pattern Generator for Fusion 360

## Project Overview

This is a Fusion 360 Add-In that generates hexagonal honeycomb patterns with precise geometric control. The add-in creates hexagon patterns that can be used for honeycomb structures, ventilation grilles, decorative panels, and other engineering applications.

**Current Version**: v2.2.0
**Platform**: macOS and Windows compatible
**Language**: Python
**API**: Autodesk Fusion 360 API

## Key Technical Concepts

### Hexagon Geometry Fundamentals

For a regular hexagon with flat-to-flat distance `d`:
- **Side length**: `a = d / √3`
- **Circumradius** (center to vertex): `R = d / √3`
- **Inradius** (center to flat side): `r = d / 2`
- **Vertex-to-vertex distance**: `2R = 2d / √3 ≈ 1.1547 × d`
- **Area**: `A = (3√3/2) × a²`
- **Perimeter**: `P = 6a`

**Key Insight**: In our implementation, "diameter" always refers to the flat-to-flat distance, not the vertex-to-vertex distance.

### Honeycomb Pattern Mathematics

#### Center-to-Center Spacing Formula (v2.1.2)

For hexagons with flat-to-flat distance `d` and wall thickness `w`:

**Effective spacing unit** = `d + w`

**Pointy-Top Orientation**:
- Horizontal spacing: `(d + w) × √3`
- Vertical spacing: `(d + w) × 1.5`
- Row offset: `horizontal_spacing / 2`

**Flat-Top Orientation**:
- Horizontal spacing: `(d + w) × 1.5`
- Vertical spacing: `(d + w) × √3`
- Row offset: `horizontal_spacing / 2`

**Example**: 10mm diameter + 2mm wall thickness = 20.785mm horizontal spacing (√3 × 12)

### Wall Thickness in Honeycomb Patterns

In a true honeycomb structure:
- Walls are **shared** between adjacent cells
- Wall thickness is the material thickness between hexagon cavities
- NOT the gap or spacing between separate hexagons
- Each wall serves two adjacent cells (efficient material usage)

## Critical Implementation Details

### 1. Radius Calculation (HexagonGenerator.py, lines 437-443)

```python
# Convert diameter to radius for internal calculations
# For hexagons: diameter is the flat-to-flat distance
# Circumradius = flat-to-flat / √3
if numSides == 6:
    radius = diameter / math.sqrt(3)
else:
    # For other polygons, treat diameter as the circumscribed circle diameter
    radius = diameter / 2
```

**Important Note**: Fusion 360's API uses centimeters internally. The add-in accepts input in millimeters through the UI but all calculations work directly with Fusion's internal cm units. This eliminates unit conversion errors.

### 2. Pattern Spacing Calculation (HexagonGenerator.py, lines 704-736)

```python
# Calculate the effective spacing unit
effective_flat_to_flat = d + w

if orientation == 'Pointy Top':
    x_spacing = math.sqrt(3) * effective_flat_to_flat  
    y_spacing = 1.5 * effective_flat_to_flat
    row_offset = x_spacing / 2
else:  # Flat Top
    x_spacing = 1.5 * effective_flat_to_flat
    y_spacing = math.sqrt(3) * effective_flat_to_flat
    row_offset = x_spacing / 2
```

### 3. Profile Selection for Cutting (v2.1 Fix)

The add-in identifies individual hexagon profiles (not the composite boundary) by comparing bounding boxes:
- If profile width/height < 50% of sketch bounds → it's a hexagon hole
- This ensures we cut hexagon-shaped holes, not the entire body

### 4. Null Safety (v2.1.1 Fix)

All `inputs.itemById()` calls include null checks to prevent AttributeError:
```python
if not baseSelection or not performCut or not previewMode:
    return
```

## Mathematical References and Sources

### Primary References

1. **Red Blob Games - Hexagonal Grids**
   - URL: https://www.redblobgames.com/grids/hexagons/
   - Key formulas for hex grid spacing and coordinate systems
   - Flat-top vs pointy-top orientation mathematics

2. **Hexagon Geometry Calculators**
   - https://www.omnicalculator.com/math/hexagon
   - https://www.gigacalculator.com/calculators/hexagon-calculator.php
   - Conversion formulas between circumradius, inradius, and flat-to-flat distance

3. **Honeycomb Mathematics**
   - https://calculate.org.au/wp-content/uploads/sites/15/2016/02/Honeycombs-Hexagonal-Geometry-Answers.pdf
   - The honeycomb conjecture and optimal tessellation
   - Why hexagons minimize perimeter for given area

### Key Formulas Discovered

From our research and testing:

1. **Hexagon dimensions relationship**:
   - `flat_to_flat = √3 × side_length`
   - `circumradius = side_length`
   - `inradius = (√3/2) × side_length`

2. **Grid spacing for honeycomb** (verified by measurement):
   - Center-to-center = √3 × (flat_to_flat + wall_thickness)
   - This gives 20.785mm for 10mm hexagons with 2mm walls

## Common Issues and Solutions

### Issue 1: Hexagons Cut Away Entire Body
**Cause**: Profile selection was choosing the composite profile instead of individual hexagons
**Solution**: Use bounding box comparison to identify individual hexagon profiles (v2.1)

### Issue 2: Incorrect Spacing Between Hexagons
**Cause**: Wrong multiplication factors in spacing formula
**Solution**: Use √3 multiplier for appropriate orientation axis (v2.1.2)

### Issue 3: AttributeError on Input Change
**Cause**: `inputs.itemById()` returning None during UI initialization
**Solution**: Add null checks before accessing input properties (v2.1.1)

### Issue 4: UI Groups Not Collapsible
**Cause**: Missing `.children` property usage for GroupCommandInput
**Solution**: Use `groupInput.children.addValueInput()` pattern (v2.1)

## Testing Commands

### Linting and Validation
```bash
# Run validation script
python validate_api.py

# Lint the code
uv run ruff check HexagonGenerator.py

# Auto-fix linting issues
uv run ruff check --fix HexagonGenerator.py
```

### Measurement Verification
```bash
# Verify spacing calculations
python hexagon_calculation_check.py

# Final verification of formulas
python final_verification.py
```

## Development Notes

### Fusion 360 API Patterns Used

1. **Modern Extent Definition** (v2.0+):
   ```python
   extent = adsk.fusion.ToEntityExtentDefinition.create(cutToEntity, True)
   extrudeInput.setOneSideExtent(extent, adsk.fusion.ExtentDirections.NegativeExtentDirection)
   ```

2. **Participant Bodies for Scoped Cuts**:
   ```python
   extrudeInput.participantBodies = [targetBody]
   ```

3. **Profile Projection** (simplified in v2.1):
   ```python
   sketch.project(edge)  # Instead of sketch.project2([edge], True)
   ```

### Code Style Guidelines

- NO comments in production code unless explicitly requested
- Use descriptive variable names
- Follow existing code patterns in the file
- Maintain consistent indentation (4 spaces)
- Keep functions focused and single-purpose

## Version History Summary

- **v2.2.0**: Fixed critical unit consistency - removed all mm/cm conversions, works directly in Fusion's internal units
- **v2.1.3**: Applied 1.25x compensation factor to fix hexagon sizing discrepancy (workaround for unit issue)
- **v2.1.2**: Fixed spacing formulas to match honeycomb geometry (√3 multiplication)
- **v2.1.1**: Added null safety for CommandInputs
- **v2.1.0**: Fixed profile selection, UI groups, and wall thickness understanding
- **v2.0.0**: Redesigned with industry-standard terminology
- **v1.0.0**: Initial release

## Key Measurements for Validation

With 6mm diameter (flat-to-flat) and 1mm wall thickness:
- Expected flat-to-flat: 6mm (user input)
- Expected vertex-to-vertex: 6.93mm (6 × 2/√3)
- Expected wall thickness: 1mm between adjacent cells

With 10mm diameter (flat-to-flat) and 2mm wall thickness:
- Expected center-to-center: 20.785mm (√3 × 12)
- Expected vertex-to-vertex within hexagon: 11.547mm
- Expected edge-to-edge between hexagons: 2mm (wall thickness)

## Future Improvements

1. Add support for variable wall thickness across pattern
2. Implement gradient patterns (varying hexagon sizes)
3. Add hexagon orientation per row option
4. Support for partial hexagons at boundaries
5. Performance optimization for very large patterns (>1000 hexagons)

## Important File Locations

- Main add-in code: `HexagonGenerator.py`
- Manifest file: `HexagonGenerator.manifest`
- Validation script: `validate_api.py`
- Icon resources: `resources/` directory
- This documentation: `CLAUDE.md`

## Installation Path

**macOS**: `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/`
**Windows**: `%appdata%\Autodesk\Autodesk Fusion 360\API\AddIns\`

---

*Last Updated: v2.2.0*
*Mathematical formulas verified through user measurement and online research*
*Unit consistency fixed - all calculations now use Fusion's internal cm units directly*