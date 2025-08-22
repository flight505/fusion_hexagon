"""
Create placeholder icons for the Hexagon Generator add-in.
This creates simple hexagon-shaped icons in the required sizes.
"""

from PIL import Image, ImageDraw
import os

def create_hexagon_icon(size, filename):
    """Create a hexagon icon of the specified size."""
    # Create a new image with transparent background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Calculate hexagon vertices
    center_x = size // 2
    center_y = size // 2
    radius = size // 2 - 2  # Leave small margin
    
    # Calculate hexagon points (flat-top orientation)
    points = []
    for i in range(6):
        angle = i * 60
        x = center_x + radius * math.cos(math.radians(angle + 30))
        y = center_y + radius * math.sin(math.radians(angle + 30))
        points.append((x, y))
    
    # Draw filled hexagon with Fusion-style blue
    draw.polygon(points, fill=(0, 123, 255, 255), outline=(0, 90, 200, 255))
    
    # Save the image
    img.save(filename, 'PNG')
    print(f"Created {filename}")

def create_simple_hexagon_icon(size, filename):
    """Create a simple hexagon icon using basic shapes."""
    # Create a new image with transparent background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Simple approach: draw a blue circle as placeholder
    margin = 2
    draw.ellipse(
        [margin, margin, size-margin, size-margin],
        fill=(0, 123, 255, 255),
        outline=(0, 90, 200, 255)
    )
    
    # Add "H" text in center for Hexagon
    text_size = size // 3
    text_x = size // 2 - text_size // 4
    text_y = size // 2 - text_size // 2
    
    # Draw H character
    draw.rectangle([text_x - text_size//4, text_y, text_x - text_size//6, text_y + text_size], fill=(255, 255, 255, 255))
    draw.rectangle([text_x + text_size//6, text_y, text_x + text_size//4, text_y + text_size], fill=(255, 255, 255, 255))
    draw.rectangle([text_x - text_size//4, text_y + text_size//2 - 1, text_x + text_size//4, text_y + text_size//2 + 1], fill=(255, 255, 255, 255))
    
    # Save the image
    img.save(filename, 'PNG')
    print(f"Created {filename}")

def main():
    """Create all required icon files."""
    resources_dir = './resources'
    
    # Ensure resources directory exists
    if not os.path.exists(resources_dir):
        os.makedirs(resources_dir)
    
    # Try to import PIL
    try:
        import math
        # Create icons with hexagon shape
        create_hexagon_icon(16, os.path.join(resources_dir, '16x16.png'))
        create_hexagon_icon(32, os.path.join(resources_dir, '32x32.png'))
        
        # Create high-resolution versions
        create_hexagon_icon(32, os.path.join(resources_dir, '16x16@2x.png'))
        create_hexagon_icon(64, os.path.join(resources_dir, '32x32@2x.png'))
        
    except ImportError:
        print("PIL not available, creating simple placeholder icons")
        # Create simple placeholder icons
        create_simple_hexagon_icon(16, os.path.join(resources_dir, '16x16.png'))
        create_simple_hexagon_icon(32, os.path.join(resources_dir, '32x32.png'))
        create_simple_hexagon_icon(32, os.path.join(resources_dir, '16x16@2x.png'))
        create_simple_hexagon_icon(64, os.path.join(resources_dir, '32x32@2x.png'))
    
    print("Icon creation complete!")

if __name__ == '__main__':
    main()