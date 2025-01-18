import os
import subprocess
from datetime import datetime, timedelta
from astral import LocationInfo
from astral.sun import sun
import time
import threading
from plyer import notification
from pystray import Icon, MenuItem, Menu
from PIL import Image, ImageDraw
from zoneinfo import ZoneInfo
import tkinter as tk
from tkinter import filedialog
import logging

# Set up logging (console only, no file)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Configuration
LOCATION = LocationInfo("Kaohsiung", "Taiwan", "Asia/Taipei", latitude=22.6273, longitude=120.3014)
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "screenshots")
TIMEZONE = ZoneInfo("Asia/Taipei")

# Global variables for settings
settings = {
    'interval': 45,  # default to 45 seconds
    'output_path': OUTPUT_PATH,
    'youtube_url': None  # default to None, will be set by user
}

# Ensure output directory exists
os.makedirs(settings['output_path'], exist_ok=True)

def notify(title, message):
    """Show a notification."""
    notification.notify(
        title=title,
        message=message,
        timeout=5
    )

def get_sun_times():
    """Calculate today's sunrise and sunset times for the given location."""
    s = sun(LOCATION.observer, date=datetime.now(TIMEZONE))
    return s['sunrise'], s['sunset']

def capture_screenshot():
    """Capture a screenshot from the YouTube stream."""
    try:
        if not settings['youtube_url']:
            notify("Error", "Please set a YouTube URL first")
            return False

        # Create output directory if it doesn't exist
        if not os.path.exists(settings['output_path']):
            os.makedirs(settings['output_path'])

        # Get current time for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(settings['output_path'], f"screenshot_{timestamp}.jpg")

        # Use yt-dlp to get the stream URL
        try:
            cmd = ["yt-dlp", "-g", settings['youtube_url']]
            stream_url = subprocess.check_output(cmd, text=True).strip()

            # Use ffmpeg to capture screenshot
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-i", stream_url,
                "-vframes", "1",
                "-q:v", "2",
                output_file
            ]
            subprocess.run(ffmpeg_cmd, capture_output=True, check=True)

            # Show notification
            notify("Screenshot Captured", f"Saved to: {output_file}")
            return True

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to capture screenshot: {str(e)}"
            logging.error(error_msg)
            notify("Error", error_msg)
            return False

    except Exception as e:
        error_msg = f"Error capturing screenshot: {str(e)}"
        logging.error(error_msg)
        notify("Error", error_msg)
        return False

def set_youtube_url(icon, item):
    """Open dialog to set YouTube URL."""
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    # Create a dialog window
    dialog = tk.Toplevel(root)
    dialog.title("Set YouTube URL")
    dialog.geometry("400x150")
    dialog.lift()  # Bring to front
    dialog.focus_force()  # Force focus
    
    # Center the window
    dialog.update_idletasks()
    width = dialog.winfo_width()
    height = dialog.winfo_height()
    x = (dialog.winfo_screenwidth() // 2) - (width // 2)
    y = (dialog.winfo_screenheight() // 2) - (height // 2)
    dialog.geometry(f'+{x}+{y}')
    
    # Add label and entry
    tk.Label(dialog, text="Enter YouTube URL:").pack(pady=10)
    entry = tk.Entry(dialog, width=50)
    entry.pack(pady=5)
    if settings['youtube_url']:
        entry.insert(0, settings['youtube_url'])
    
    def save_url():
        url = entry.get().strip()
        if url:
            settings['youtube_url'] = url
            notify("YouTube URL", "URL has been updated successfully")
        else:
            notify("YouTube URL", "Please enter a valid URL")
        dialog.destroy()
        root.destroy()
    
    def cancel():
        dialog.destroy()
        root.destroy()
    
    # Add buttons
    button_frame = tk.Frame(dialog)
    button_frame.pack(pady=20)
    tk.Button(button_frame, text="Save", command=save_url).pack(side=tk.LEFT, padx=10)
    tk.Button(button_frame, text="Cancel", command=cancel).pack(side=tk.LEFT)
    
    root.mainloop()

def schedule_screenshots():
    """Schedule screenshots 30 minutes before and after sunrise and sunset."""
    sunrise, sunset = get_sun_times()

    # Define the 30-minute intervals for sunrise and sunset
    intervals = [(sunrise - timedelta(minutes=30), sunrise + timedelta(minutes=30)),
                 (sunset - timedelta(minutes=30), sunset + timedelta(minutes=30))]

    for start_time, end_time in intervals:
        now = datetime.now(TIMEZONE)
        if end_time < now:
            continue  # Skip past events

        print(f"Scheduling screenshots from {start_time} to {end_time}...")

        while now < end_time:
            if now >= start_time:
                capture_screenshot()
            time.sleep(settings['interval'])
            now = datetime.now(TIMEZONE)

def background_thread():
    """Run the screenshot scheduler in a background thread."""
    try:
        logging.info("Starting background thread...")
        schedule_screenshots()
    except Exception as e:
        logging.error(f"Error in background thread: {str(e)}", exc_info=True)
        notify("Background Error", str(e))

def select_output_path(icon, item):
    """Open a directory selection dialog."""
    # Create a hidden root window for the dialog
    root = tk.Tk()
    root.withdraw()
    
    # Open directory selection dialog
    new_path = filedialog.askdirectory(
        title="Select Screenshot Directory",
        initialdir=settings['output_path']
    )
    
    if new_path:  # If a directory was selected
        settings['output_path'] = new_path
        os.makedirs(settings['output_path'], exist_ok=True)
        notify("Settings Updated", f"New screenshot directory: {new_path}")

def set_interval(icon, item, seconds):
    """Set the screenshot interval."""
    settings['interval'] = seconds
    notify("Settings Updated", f"New interval: {seconds} seconds")

def create_menu_item(text, seconds):
    """Create a menu item for a specific interval."""
    def handler(icon, item):
        set_interval(icon, item, seconds)
    
    def checked(item):
        return settings['interval'] == seconds
    
    return MenuItem(text, handler, radio=True, checked=checked)

def get_interval_menu():
    """Create a submenu for interval options."""
    # Create intervals from 5 to 60 seconds in 5-second increments
    intervals = [(f"{secs} seconds", secs) for secs in range(5, 61, 5)]
    return Menu(*[create_menu_item(text, secs) for text, secs in intervals])

def create_icon():
    """Create a system tray icon with a camera design."""
    # Create a transparent background
    icon_size = 64
    icon_image = Image.new("RGBA", (icon_size, icon_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon_image)
    
    # Draw camera body (dark gray with slight transparency)
    camera_body = [
        (16, 22),  # top-left
        (48, 22),  # top-right
        (48, 46),  # bottom-right
        (16, 46)   # bottom-left
    ]
    draw.polygon(camera_body, fill=(64, 64, 64, 230))
    
    # Draw camera lens (light blue with slight transparency)
    center_x, center_y = 32, 34
    radius = 8
    draw.ellipse(
        [center_x - radius, center_y - radius, 
         center_x + radius, center_y + radius],
        fill=(0, 150, 255, 230)
    )
    
    # Draw viewfinder bump (dark gray with slight transparency)
    viewfinder = [
        (25, 18),  # top-left
        (39, 18),  # top-right
        (39, 22),  # bottom-right
        (25, 22)   # bottom-left
    ]
    draw.polygon(viewfinder, fill=(64, 64, 64, 230))

    return icon_image

def run_app():
    """Run the application with system tray icon."""
    # Create the icon
    icon_image = create_icon()
    
    # Define menu with settings
    menu = Menu(
        MenuItem("Set YouTube URL", set_youtube_url),
        MenuItem("Interval", get_interval_menu()),
        MenuItem("Select Output Path", select_output_path),
        Menu.SEPARATOR,
        MenuItem("Quit", quit_program)
    )

    # Create the icon
    icon = Icon("Screenshot Scheduler", icon_image, menu=menu)
    
    # Start the screenshot thread
    logging.info("Starting screenshot thread...")
    screenshot_thread = threading.Thread(target=test_screenshots, daemon=True)
    screenshot_thread.start()
    
    # Run the icon (this will block until quit is selected)
    logging.info("Starting system tray icon...")
    icon.run()

def quit_program(icon, item):
    """Quit the program."""
    print("Exiting...")
    icon.stop()
    os._exit(0)

def test_screenshots():
    """Take screenshots continuously."""
    logging.info("Starting screenshot test mode...")
    try:
        while True:
            logging.debug(f"Taking screenshot (interval: {settings['interval']} seconds)")
            capture_screenshot()
            logging.debug("Waiting for next screenshot...")
            time.sleep(settings['interval'])
    except Exception as e:
        logging.error(f"Error in test_screenshots: {str(e)}", exc_info=True)
        notify("Test Error", str(e))

if __name__ == "__main__":
    try:
        logging.info("Starting WebcamGrabber...")
        run_app()
    except Exception as e:
        logging.error(f"Error in main: {str(e)}", exc_info=True)
        notify("Application Error", str(e))