from PIL import Image, ImageDraw

def create_icon_file():
    # Create a transparent background
    icon_size = 256
    icon_image = Image.new("RGBA", (icon_size, icon_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon_image)
    
    # Scale factor for all coordinates
    scale = 4
    
    # Draw camera body (vibrant blue)
    camera_body = [
        (4 * scale, 12 * scale),   # top-left
        (60 * scale, 12 * scale),  # top-right
        (60 * scale, 52 * scale),  # bottom-right
        (4 * scale, 52 * scale)    # bottom-left
    ]
    draw.polygon(camera_body, fill=(30, 144, 255), outline=(0, 0, 0), width=2)
    
    # Draw camera lens (bright red) with black outline
    center_x, center_y = 32 * scale, 32 * scale
    radius = 14 * scale
    # Draw black outline
    draw.ellipse(
        [center_x - radius - 2, center_y - radius - 2,
         center_x + radius + 2, center_y + radius + 2],
        fill=(0, 0, 0)
    )
    # Draw lens
    draw.ellipse(
        [center_x - radius, center_y - radius,
         center_x + radius, center_y + radius],
        fill=(255, 69, 0)
    )
    
    # Draw inner lens circle (yellow)
    inner_radius = 8 * scale
    draw.ellipse(
        [center_x - inner_radius, center_y - inner_radius,
         center_x + inner_radius, center_y + inner_radius],
        fill=(255, 215, 0)
    )
    
    # Draw viewfinder bump (dark blue with black outline)
    viewfinder = [
        (16 * scale, 6 * scale),   # top-left
        (48 * scale, 6 * scale),   # top-right
        (48 * scale, 12 * scale),  # bottom-right
        (16 * scale, 12 * scale)   # bottom-left
    ]
    draw.polygon(viewfinder, fill=(0, 0, 139), outline=(0, 0, 0), width=2)
    
    # Add flash light indicator (white circle with red outline)
    flash_x, flash_y = 52 * scale, 18 * scale
    flash_radius = 3 * scale
    draw.ellipse(
        [flash_x - flash_radius - 1, flash_y - flash_radius - 1,
         flash_x + flash_radius + 1, flash_y + flash_radius + 1],
        fill=(255, 0, 0)
    )
    draw.ellipse(
        [flash_x - flash_radius, flash_y - flash_radius,
         flash_x + flash_radius, flash_y + flash_radius],
        fill=(255, 255, 255)
    )
    
    # Save as ICO file with multiple sizes
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    icon_image.save("app.ico", format="ICO", sizes=sizes)

if __name__ == "__main__":
    create_icon_file()
