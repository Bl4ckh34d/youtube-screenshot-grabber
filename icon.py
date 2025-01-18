from PIL import Image, ImageDraw

def create_icon_file():
    # Create a white background
    icon_size = 256
    icon_image = Image.new("RGB", (icon_size, icon_size), (255, 255, 255))
    draw = ImageDraw.Draw(icon_image)
    
    # Scale factor for all coordinates
    scale = 4
    
    # Adjust coordinates to make camera larger (using more of the 0-64 base space)
    # Draw camera body (light silver gray)
    camera_body = [
        (4 * scale, 12 * scale),   # top-left
        (60 * scale, 12 * scale),  # top-right
        (60 * scale, 52 * scale),  # bottom-right
        (4 * scale, 52 * scale)    # bottom-left
    ]
    draw.polygon(camera_body, fill=(192, 192, 192))
    
    # Draw camera lens (light blue) - scaled up proportionally
    center_x, center_y = 32 * scale, 32 * scale
    radius = 14 * scale  # Increased radius
    draw.ellipse(
        [center_x - radius, center_y - radius, 
         center_x + radius, center_y + radius],
        fill=(0, 150, 255)
    )
    
    # Draw viewfinder bump (darker gray for contrast) - adjusted position
    viewfinder = [
        (16 * scale, 6 * scale),   # top-left
        (48 * scale, 6 * scale),   # top-right
        (48 * scale, 12 * scale),  # bottom-right
        (16 * scale, 12 * scale)   # bottom-left
    ]
    draw.polygon(viewfinder, fill=(128, 128, 128))
    
    # Save as ICO file with multiple sizes
    # Windows will automatically choose the best size for the system tray
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    icon_image.save("app.ico", format="ICO", sizes=sizes)

if __name__ == "__main__":
    create_icon_file()
