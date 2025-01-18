from PIL import Image, ImageDraw

def create_icon_file():
    # Create a white background
    icon_size = 64
    icon_image = Image.new("RGB", (icon_size, icon_size), (255, 255, 255))
    draw = ImageDraw.Draw(icon_image)
    
    # Draw camera body (dark gray)
    camera_body = [
        (16, 22),  # top-left
        (48, 22),  # top-right
        (48, 46),  # bottom-right
        (16, 46)   # bottom-left
    ]
    draw.polygon(camera_body, fill=(64, 64, 64))
    
    # Draw camera lens (light blue)
    center_x, center_y = 32, 34
    radius = 8
    draw.ellipse(
        [center_x - radius, center_y - radius, 
         center_x + radius, center_y + radius],
        fill=(0, 150, 255)
    )
    
    # Draw viewfinder bump (dark gray)
    viewfinder = [
        (25, 18),  # top-left
        (39, 18),  # top-right
        (39, 22),  # bottom-right
        (25, 22)   # bottom-left
    ]
    draw.polygon(viewfinder, fill=(64, 64, 64))
    
    # Save as ICO file
    icon_image.save("app.ico", format="ICO")

if __name__ == "__main__":
    create_icon_file()
