"""
Create simple SVG placeholder icons for the Hexagon Generator add-in.
These can be used as placeholders until proper icons are created.
"""

import os

def create_svg_hexagon(size):
    """Create an SVG hexagon icon."""
    # Calculate center and radius
    center = size / 2
    radius = (size / 2) - 2
    
    # Calculate hexagon points (pointy-top orientation)
    points = []
    for i in range(6):
        angle = (i * 60) * 3.14159 / 180
        x = center + radius * (1 if i == 0 or i == 3 else 0.5 if i == 1 or i == 5 else -0.5 if i == 2 or i == 4 else -1)
        y = center + radius * (0 if i == 0 or i == 3 else -0.866 if i == 1 or i == 2 else 0.866 if i == 4 or i == 5 else 0)
        points.append(f"{x:.1f},{y:.1f}")
    
    svg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">
  <polygon points="{' '.join(points)}" fill="#007BFF" stroke="#005AC8" stroke-width="1"/>
</svg>"""
    
    return svg_content

def create_simple_png_placeholder(size, filename):
    """Create a simple text file as placeholder (Fusion will show question mark)."""
    # This creates an empty file which will cause Fusion to show a question mark
    # This is acceptable as a temporary placeholder
    with open(filename, 'wb') as f:
        # Write minimal PNG header (will show as broken/placeholder)
        f.write(b'\x89PNG\r\n\x1a\n')
    print(f"Created placeholder {filename}")

def main():
    """Create all required icon files."""
    resources_dir = './resources'
    
    # Ensure resources directory exists
    if not os.path.exists(resources_dir):
        os.makedirs(resources_dir)
    
    # Create SVG icons
    for size_spec, size in [('16x16', 16), ('32x32', 32)]:
        svg_file = os.path.join(resources_dir, f'{size_spec}.svg')
        with open(svg_file, 'w') as f:
            f.write(create_svg_hexagon(size))
        print(f"Created {svg_file}")
    
    # Create PNG placeholders (these will show as question marks in Fusion)
    create_simple_png_placeholder(16, os.path.join(resources_dir, '16x16.png'))
    create_simple_png_placeholder(32, os.path.join(resources_dir, '32x32.png'))
    create_simple_png_placeholder(32, os.path.join(resources_dir, '16x16@2x.png'))
    create_simple_png_placeholder(64, os.path.join(resources_dir, '32x32@2x.png'))
    
    print("\nIcon placeholders created!")
    print("Note: PNG files are placeholders and will show as question marks.")
    print("SVG files should display as hexagon shapes.")

if __name__ == '__main__':
    main()