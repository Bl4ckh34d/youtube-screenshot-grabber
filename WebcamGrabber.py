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
import yt_dlp
import customtkinter as ctk
import re

# Set customtkinter appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Set up logging (console only, no file)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [%(funcName)s] %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Reduce PIL debug logs
logging.getLogger('PIL').setLevel(logging.INFO)

# Configuration
LOCATION = LocationInfo("Kaohsiung", "Taiwan", "Asia/Taipei", latitude=22.6273, longitude=120.3014)
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "screenshots")
TIMEZONE = ZoneInfo("Asia/Taipei")

# Global variables for settings
settings = {
    'interval': 45,  # default to 45 seconds
    'output_path': OUTPUT_PATH,
    'youtube_url': None,  # default to None, will be set by user
    'is_paused': True  # Start paused until URL is set
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

def clean_filename(filename):
    """Clean a string to be used as a filename."""
    # Remove invalid characters
    cleaned = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace spaces and multiple underscores with single underscore
    cleaned = re.sub(r'[\s_]+', '_', cleaned)
    # Remove any non-ASCII characters
    cleaned = re.sub(r'[^\x00-\x7F]+', '', cleaned)
    # Remove leading/trailing underscores and dots
    cleaned = cleaned.strip('_.')
    # Limit length to avoid too long filenames
    return cleaned[:100]

def capture_screenshot():
    """Capture a screenshot from the YouTube stream."""
    try:
        if not settings['youtube_url']:
            logging.warning("[capture_screenshot] No YouTube URL set")
            notify("Error", "Please set a YouTube URL first")
            return False

        logging.debug(f"[capture_screenshot] Starting capture with URL: {settings['youtube_url']}")
        logging.debug(f"[capture_screenshot] Output path: {settings['output_path']}")

        # Create output directory if it doesn't exist
        if not os.path.exists(settings['output_path']):
            logging.info(f"[capture_screenshot] Creating output directory: {settings['output_path']}")
            os.makedirs(settings['output_path'])

        # Get video info using yt-dlp
        try:
            logging.debug("[capture_screenshot] Using yt-dlp to get video info...")
            ydl_opts = {
                'format': 'best[ext=mp4]',
                'quiet': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(settings['youtube_url'], download=False)
                stream_url = info['url']
                video_title = info.get('title', 'untitled')
                logging.debug(f"[capture_screenshot] Video title: {video_title}")
                logging.debug("[capture_screenshot] Successfully got stream URL")

            # Create filename with date and cleaned title
            timestamp = datetime.now().strftime("%Y_%m_%d")
            cleaned_title = clean_filename(video_title)
            output_file = os.path.join(settings['output_path'], f"{timestamp}_{cleaned_title}.jpg")
            logging.debug(f"[capture_screenshot] Output file will be: {output_file}")

            # Use ffmpeg to capture screenshot
            logging.debug("[capture_screenshot] Running ffmpeg to capture screenshot...")
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-i", stream_url,
                "-vframes", "1",
                "-q:v", "2",
                output_file
            ]
            subprocess.run(ffmpeg_cmd, capture_output=True, check=True)
            
            if os.path.exists(output_file):
                file_size = os.path.getsize(output_file)
                logging.info(f"[capture_screenshot] Screenshot saved successfully. Size: {file_size} bytes")
                notify("Screenshot Captured", f"Saved to: {output_file}")
                return True
            else:
                raise Exception("Screenshot file was not created")

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to capture screenshot: {str(e)}"
            logging.error(f"[capture_screenshot] {error_msg}")
            logging.error(f"[capture_screenshot] Command output: {e.output}")
            logging.error(f"[capture_screenshot] Command stderr: {e.stderr}")
            notify("Error", error_msg)
            return False

    except Exception as e:
        error_msg = f"Error capturing screenshot: {str(e)}"
        logging.error(f"[capture_screenshot] {error_msg}", exc_info=True)
        notify("Error", error_msg)
        return False

def set_youtube_url(icon, item):
    """Open dialog to set YouTube URL."""
    # Create the main window
    dialog = ctk.CTk()
    dialog.title("Set YouTube URL")
    dialog.geometry("400x140")  # Reduced height since we removed description
    
    # Center the window
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    x = (screen_width - 400) // 2
    y = (screen_height - 140) // 2
    dialog.geometry(f"400x140+{x}+{y}")
    
    # Make window stay on top
    dialog.attributes('-topmost', True)
    dialog.lift()
    
    # Create a frame for content with padding
    content_frame = ctk.CTkFrame(dialog, corner_radius=8)
    content_frame.pack(fill="both", expand=True, padx=12, pady=12)
    
    # Add title label
    title_label = ctk.CTkLabel(
        content_frame,
        text="Enter YouTube URL",
        font=ctk.CTkFont(size=16, weight="bold")
    )
    title_label.pack(pady=(12, 12))
    
    # Add URL entry
    url_entry = ctk.CTkEntry(
        content_frame,
        width=350,
        height=30,
        placeholder_text="https://www.youtube.com/watch?v=..."
    )
    url_entry.pack(pady=(0, 12))
    if settings['youtube_url']:
        url_entry.insert(0, settings['youtube_url'])
    
    # Create a frame for buttons
    button_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
    button_frame.pack(pady=(0, 0))
    
    def save_url():
        url = url_entry.get().strip()
        if url:
            settings['youtube_url'] = url
            settings['is_paused'] = False  # Auto-unpause when URL is set
            notify("YouTube URL", "URL has been updated successfully. Screenshot capture resumed.")
            icon.menu = create_menu(icon)  # Update menu to show Pause option
        else:
            notify("YouTube URL", "Please enter a valid URL")
        dialog.destroy()
    
    def cancel():
        dialog.destroy()
    
    # Add buttons with smaller size (Windows convention: Cancel on left, Save on right)
    cancel_button = ctk.CTkButton(
        button_frame,
        text="Cancel",
        width=100,
        height=28,
        command=cancel,
        fg_color="transparent",
        border_width=1,
        text_color=("gray10", "gray90")
    )
    cancel_button.pack(side="left", padx=8)
    
    save_button = ctk.CTkButton(
        button_frame,
        text="Save",
        width=100,
        height=28,
        command=save_url
    )
    save_button.pack(side="left", padx=8)
    
    # Bind Enter key to save
    dialog.bind('<Return>', lambda e: save_url())
    # Bind Escape key to cancel
    dialog.bind('<Escape>', lambda e: cancel())
    
    # Focus the entry
    url_entry.focus()
    
    dialog.mainloop()

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

def create_menu_item(text, interval):
    """Create a menu item for a specific interval."""
    def set_interval(icon, item):
        old_interval = settings['interval']
        settings['interval'] = interval
        logging.info(f"[set_interval] Changed interval from {old_interval}s to {interval}s")
        notify("Interval Changed", f"Screenshot interval set to {interval} seconds")
    return MenuItem(text, set_interval)

def get_interval_menu():
    """Create a submenu for interval options."""
    logging.debug("[get_interval_menu] Creating interval submenu")
    # Create intervals from 5 to 60 seconds in 5-second increments
    intervals = [(f"{secs} seconds", secs) for secs in range(5, 61, 5)]
    logging.debug(f"[get_interval_menu] Available intervals: {[i[1] for i in intervals]} seconds")
    menu_items = [create_menu_item(text, secs) for text, secs in intervals]
    return Menu(*menu_items)

def create_menu(icon):
    """Create the system tray menu."""
    logging.debug("[create_menu] Creating system tray menu")
    menu = Menu(
        MenuItem("Set YouTube URL", set_youtube_url),
        MenuItem("Interval", get_interval_menu()),
        MenuItem("Select Output Path", select_output_path),
        MenuItem("Resume Capture" if settings['is_paused'] else "Pause Capture", toggle_pause),
        Menu.SEPARATOR,
        MenuItem("Quit", quit_program)
    )
    logging.debug(f"[create_menu] Current settings - Interval: {settings['interval']}s, Paused: {settings['is_paused']}")
    return menu

def toggle_pause(icon, item):
    """Toggle the pause state."""
    old_state = settings['is_paused']
    settings['is_paused'] = not settings['is_paused']
    logging.info(f"[toggle_pause] Pause state changed from {old_state} to {settings['is_paused']}")
    
    if settings['is_paused']:
        logging.debug("[toggle_pause] Screenshot capture paused")
        notify("Screenshot Grabber", "Screenshot capture paused")
    else:
        logging.debug("[toggle_pause] Screenshot capture resumed")
        notify("Screenshot Grabber", "Screenshot capture resumed")
    
    # Update the menu
    logging.debug("[toggle_pause] Updating menu with new pause state")
    icon.menu = create_menu(icon)

def test_screenshots():
    """Take screenshots at regular intervals."""
    logging.info("[test_screenshots] Starting screenshot thread")
    last_interval = settings['interval']
    
    while True:
        try:
            # Check if interval has changed
            if last_interval != settings['interval']:
                logging.info(f"[test_screenshots] Detected interval change: {last_interval}s -> {settings['interval']}s")
                last_interval = settings['interval']
            
            if settings['is_paused']:
                logging.debug("[test_screenshots] Screenshot capture is paused")
            elif not settings['youtube_url']:
                logging.debug("[test_screenshots] No YouTube URL set")
            else:
                logging.debug(f"[test_screenshots] Taking screenshot (interval: {settings['interval']}s)")
                capture_screenshot()
            
            logging.debug(f"[test_screenshots] Sleeping for {settings['interval']} seconds")
            time.sleep(settings['interval'])
            
        except Exception as e:
            logging.error(f"[test_screenshots] Error in screenshot thread: {str(e)}", exc_info=True)
            notify("Test Error", str(e))

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
    logging.info("[run_app] Starting application")
    
    # Create the icon
    logging.debug("[run_app] Creating system tray icon")
    icon_image = create_icon()
    
    # Create the icon with menu
    logging.debug("[run_app] Setting up system tray menu")
    icon = Icon("Screenshot Scheduler", icon_image, menu=create_menu(None))
    
    # Start the screenshot thread
    logging.info("[run_app] Starting screenshot thread...")
    screenshot_thread = threading.Thread(target=test_screenshots, daemon=True)
    screenshot_thread.start()
    
    # Run the icon (this will block until quit is selected)
    logging.info("[run_app] Starting system tray icon...")
    icon.run()

def quit_program(icon, item):
    """Quit the program."""
    print("Exiting...")
    icon.stop()
    os._exit(0)

if __name__ == "__main__":
    try:
        logging.info("Starting WebcamGrabber...")
        run_app()
    except Exception as e:
        logging.error(f"Error in main: {str(e)}", exc_info=True)
        notify("Application Error", str(e))