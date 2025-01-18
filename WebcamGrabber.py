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
import tkintermapview
import json
import re

# Set up logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Set all loggers to WARNING level except our app
for logger_name in logging.root.manager.loggerDict:
    if logger_name != __name__:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

logging.info("Starting WebcamGrabber...")

# Set customtkinter appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Constants
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "screenshots")
DEFAULT_SETTINGS = {
    'interval': 45,  # default to 45 seconds
    'output_path': OUTPUT_PATH,
    'youtube_url': None,  # default to None, will be set by user
    'is_paused': True,  # Start paused until URL is set
    'schedule_enabled': False,
    'location': {
        'name': "",
        'region': "",
        'timezone': "",
        'latitude': 0,
        'longitude': 0
    }
}

def get_windows_location():
    """Get the user's location from Windows settings."""
    logging.info("Attempting to get Windows location...")
    try:
        import winreg
        
        def get_reg_value(key_path, value_name):
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
                value, _ = winreg.QueryValueEx(key, value_name)
                winreg.CloseKey(key)
                return value
            except Exception as e:
                logging.warning(f"Failed to read registry key {key_path}: {str(e)}")
                return None
        
        # Try to get location from Windows settings
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location\NonPackaged"
        location_allowed = get_reg_value(key_path, "Value")
        logging.info(f"Windows location access: {location_allowed}")
        
        # Get timezone
        import tzlocal
        timezone = str(tzlocal.get_localzone())
        logging.info(f"Local timezone: {timezone}")
        
        # Use IP-based geolocation
        import requests
        logging.info("Fetching location from IP geolocation service...")
        
        # Try multiple geolocation services
        services = [
            'http://ip-api.com/json',  # No API key needed
            'https://ipapi.co/json/',   # Backup service
        ]
        
        for service in services:
            try:
                response = requests.get(service, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    logging.info(f"Geolocation data received from {service}: {data}")
                    
                    # ip-api.com format
                    if 'lat' in data and 'lon' in data:
                        return {
                            'name': data.get('city', 'Unknown'),
                            'region': data.get('country', 'Unknown'),
                            'timezone': timezone,
                            'latitude': float(data.get('lat', 0)),
                            'longitude': float(data.get('lon', 0))
                        }
                    # ipapi.co format
                    elif 'latitude' in data and 'longitude' in data:
                        return {
                            'name': data.get('city', 'Unknown'),
                            'region': data.get('country_name', 'Unknown'),
                            'timezone': timezone,
                            'latitude': float(data.get('latitude', 0)),
                            'longitude': float(data.get('longitude', 0))
                        }
            except Exception as e:
                logging.warning(f"Failed to get location from {service}: {str(e)}")
                continue
        
        logging.warning("All geolocation services failed")
    except Exception as e:
        logging.warning(f"Failed to get Windows location: {str(e)}")
    return None

# Try to get Windows location first
logging.info("Getting initial location...")
windows_location = get_windows_location()
logging.info(f"Windows location result: {windows_location}")

def load_settings():
    """Load settings from config file."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                loaded_settings = json.load(f)
                # Update default settings with loaded values
                settings = DEFAULT_SETTINGS.copy()
                settings.update(loaded_settings)
                return settings
        return DEFAULT_SETTINGS.copy()
    except Exception as e:
        logging.error(f"Error loading settings: {e}")
        return DEFAULT_SETTINGS.copy()

def save_settings():
    """Save current settings to config file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving settings: {e}")

# Initialize settings
settings = load_settings()

def get_location_info():
    """Get LocationInfo object from current settings."""
    loc = settings['location']
    return LocationInfo(loc['name'], loc['region'], loc['timezone'], 
                       loc['latitude'], loc['longitude'])

def get_sun_times():
    """Get sunrise and sunset times for the current location."""
    location = get_location_info()
    s = sun(location.observer, date=datetime.now(ZoneInfo(location['timezone'])))
    return s['sunrise'], s['sunset']

def set_location(icon, item):
    """Open dialog to set location."""
    # Create the main window
    dialog = ctk.CTk()
    dialog.title("Set Location")
    dialog.geometry("800x600")
    
    # Center the window
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    x = (screen_width - 800) // 2
    y = (screen_height - 600) // 2
    dialog.geometry(f"800x600+{x}+{y}")
    
    # Make window stay on top
    dialog.attributes('-topmost', True)
    dialog.lift()
    
    dialog.grid_columnconfigure(0, weight=1)
    dialog.grid_rowconfigure(0, weight=1)

    # Main container
    main_frame = ctk.CTkFrame(dialog)
    main_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
    main_frame.grid_columnconfigure(0, weight=1)
    main_frame.grid_rowconfigure(1, weight=1)  # Make map row expandable

    # Location info at the top
    loc_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    loc_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
    loc_frame.grid_columnconfigure(1, weight=1)
    
    # Location labels and entries
    labels = ["Name:", "Region:", "Timezone:"]
    entries = {}
    
    for i, label in enumerate(labels):
        ctk.CTkLabel(loc_frame, text=label).grid(row=i, column=0, padx=(0, 5), pady=2, sticky="e")
        entry = ctk.CTkEntry(loc_frame, width=200)
        entry.grid(row=i, column=1, padx=(5, 0), pady=2, sticky="ew")
        entries[label.lower().replace(":", "")] = entry
    
    # Fill current values
    entries["name"].insert(0, settings['location']['name'])
    entries["region"].insert(0, settings['location']['region'])
    entries["timezone"].insert(0, settings['location']['timezone'])
    
    # Map container (to allow overlay)
    map_container = ctk.CTkFrame(main_frame, fg_color="transparent")
    map_container.grid(row=1, column=0, sticky="nsew")
    map_container.grid_columnconfigure(0, weight=1)
    map_container.grid_rowconfigure(0, weight=1)
    
    # Map widget
    map_widget = tkintermapview.TkinterMapView(map_container, width=400, height=300, corner_radius=0)
    map_widget.grid(row=0, column=0, sticky="nsew")
    
    # Schedule toggle overlay (top-right of map)
    schedule_frame = ctk.CTkFrame(map_container, fg_color=dialog._fg_color)
    schedule_frame.grid(row=0, column=0, sticky="ne", padx=10, pady=10)
    
    schedule_var = tk.BooleanVar(value=settings['schedule_enabled'])
    schedule_label = ctk.CTkLabel(schedule_frame, text="Capture Only Sunsets/Sunrises")
    schedule_label.pack(side="left", padx=(10, 5))
    
    schedule_switch = ctk.CTkSwitch(schedule_frame, text="", variable=schedule_var, width=40)
    schedule_switch.pack(side="left", padx=(0, 10))
    
    # Bottom frame for coordinates
    bottom_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    bottom_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
    bottom_frame.grid_columnconfigure(0, weight=1)
    
    # Coordinates
    coord_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
    coord_frame.pack(fill="x")
    coord_frame.grid_columnconfigure(1, weight=1)
    coord_frame.grid_columnconfigure(3, weight=1)
    
    # Latitude
    lat_label = ctk.CTkLabel(coord_frame, text="Latitude:")
    lat_label.grid(row=0, column=0, padx=(0, 5), pady=2, sticky="e")
    lat_var = tk.StringVar(value=f"{settings['location']['latitude']:.4f}")
    lat_entry = ctk.CTkEntry(coord_frame, textvariable=lat_var, width=100)
    lat_entry.grid(row=0, column=1, padx=(5, 10), pady=2, sticky="w")
    
    # Longitude
    lon_label = ctk.CTkLabel(coord_frame, text="Longitude:")
    lon_label.grid(row=0, column=2, padx=(10, 5), pady=2, sticky="e")
    lon_var = tk.StringVar(value=f"{settings['location']['longitude']:.4f}")
    lon_entry = ctk.CTkEntry(coord_frame, textvariable=lon_var, width=100)
    lon_entry.grid(row=0, column=3, padx=(5, 0), pady=2, sticky="w")
    
    # Button frame
    button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
    button_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
    button_frame.grid_columnconfigure(0, weight=1)
    button_frame.grid_columnconfigure(1, weight=1)
    
    # Save and Cancel buttons
    save_button = ctk.CTkButton(button_frame, text="Save", command=lambda: save(dialog, entries, lat_var, lon_var, schedule_var))
    save_button.grid(row=0, column=0, padx=(10, 5), pady=15)
    
    cancel_button = ctk.CTkButton(button_frame, text="Cancel", command=lambda: cancel(dialog))
    cancel_button.grid(row=0, column=1, padx=(5, 10), pady=15)
    
    def on_map_click(coords):
        lat, lon = coords
        lat_var.set(f"{lat:.4f}")
        lon_var.set(f"{lon:.4f}")
        map_widget.delete_all_marker()
        map_widget.set_marker(lat, lon)
    
    map_widget.add_left_click_map_command(on_map_click)
    
    def cleanup_map():
        """Clean up map widget and cancel any pending after events"""
        # Cancel all pending after events
        for widget in map_widget.winfo_children():
            widget.after_cancel()
        map_widget.after_cancel()
        # Destroy the widget
        map_widget.destroy()

    def save(dialog, entries, lat_var, lon_var, schedule_var):
        try:
            settings['location'].update({
                'name': entries["name"].get().strip(),
                'region': entries["region"].get().strip(),
                'timezone': entries["timezone"].get().strip(),
                'latitude': float(lat_var.get()),
                'longitude': float(lon_var.get())
            })
            settings['schedule_enabled'] = schedule_var.get()
            save_settings()
            
            # Update the schedule thread
            update_schedule_thread()
            
            notify("Location Updated", 
                  f"Location set to {settings['location']['name']}, {settings['location']['region']}\n"
                  f"Schedule {'enabled' if settings['schedule_enabled'] else 'disabled'}")
            
            # Clean up map widget before destroying
            cleanup_map()
            dialog.destroy()
        except Exception as e:
            notify("Error", f"Failed to save location: {str(e)}")
    
    def cancel(dialog):
        # Clean up map widget before destroying
        cleanup_map()
        dialog.destroy()
    
    def on_closing():
        # Clean up map widget before destroying
        cleanup_map()
        dialog.destroy()
    
    # Bind window close button
    dialog.protocol("WM_DELETE_WINDOW", on_closing)
    
    dialog.mainloop()

def create_menu(icon=None):
    """Create the system tray menu."""
    logging.info("[create_menu] Creating system tray menu")
    logging.info(f"[create_menu] Current settings - Interval: {settings['interval']}s, Paused: {settings['is_paused']}")

    # Create menu items
    menu_items = [
        MenuItem("⏸ Pause" if not settings['is_paused'] else "▶ Resume", toggle_pause),
        MenuItem("Set YouTube URL", set_youtube_url),
        MenuItem("Screenshot Interval", get_interval_menu()),
        MenuItem("Set Location", set_location),
        MenuItem("Set Output Path", select_output_path),
        MenuItem("Exit", quit_program)
    ]
    
    menu = Menu(*menu_items)
    
    # If icon exists, update its menu, otherwise return the new menu
    if icon:
        icon.menu = menu
    return menu

def should_capture_now():
    """Check if we should capture based on schedule."""
    if not settings['schedule_enabled']:
        return True
        
    try:
        sunrise, sunset = get_sun_times()
        now = datetime.now(sunrise.tzinfo)
        
        # Capture window is 30 minutes before and after sunrise/sunset
        sunrise_start = sunrise - timedelta(minutes=30)
        sunrise_end = sunrise + timedelta(minutes=30)
        sunset_start = sunset - timedelta(minutes=30)
        sunset_end = sunset + timedelta(minutes=30)
        
        in_window = (sunrise_start <= now <= sunrise_end) or (sunset_start <= now <= sunset_end)
        if in_window:
            logging.info(f"In capture window: {now}")
        return in_window
    except Exception as e:
        logging.error(f"Error checking schedule: {e}")
        return True

def update_schedule_thread():
    """Update the schedule thread based on current settings."""
    global schedule_thread
    if hasattr(update_schedule_thread, 'schedule_thread') and schedule_thread.is_alive():
        schedule_thread.stop()
    schedule_thread = threading.Thread(target=schedule_screenshots, daemon=True)
    schedule_thread.start()

def schedule_screenshots():
    """Monitor schedule and log next capture windows."""
    while True:
        try:
            if settings['schedule_enabled']:
                sunrise, sunset = get_sun_times()
                now = datetime.now(sunrise.tzinfo)
                
                # Calculate next capture window
                if now < sunrise - timedelta(minutes=30):
                    next_window = sunrise - timedelta(minutes=30)
                    window_type = "sunrise"
                elif now < sunset - timedelta(minutes=30):
                    next_window = sunset - timedelta(minutes=30)
                    window_type = "sunset"
                else:
                    # Wait for tomorrow's sunrise
                    tomorrow = now.date() + timedelta(days=1)
                    next_sunrise = sun(get_location_info().observer, date=tomorrow)['sunrise']
                    next_window = next_sunrise - timedelta(minutes=30)
                    window_type = "tomorrow's sunrise"
                
                time_until = next_window - now
                logging.info(f"Next capture window: {window_type} at {next_window} (in {time_until})")
            
            time.sleep(60)  # Update schedule info every minute
            
        except Exception as e:
            logging.error(f"Error in schedule thread: {e}")
            time.sleep(60)

def test_screenshots():
    """Take screenshots at regular intervals."""
    logging.info("Starting screenshot capture")
    
    while True:
        try:
            if not settings['is_paused'] and settings['youtube_url']:
                if should_capture_now():
                    capture_screenshot()
                    if settings['schedule_enabled']:
                        logging.info("Captured scheduled screenshot")
                else:
                    logging.debug("Outside of capture window")
            else:
                if not settings['youtube_url']:
                    logging.warning("No YouTube URL set")
                
            time.sleep(settings['interval'])
            
        except Exception as e:
            logging.error(f"Error in screenshot thread: {str(e)}")
            time.sleep(settings['interval'])

def capture_screenshot():
    """Capture a screenshot from the YouTube stream."""
    try:
        logging.info("Taking screenshot...")
        
        # Create output directory if it doesn't exist
        if not os.path.exists(settings['output_path']):
            logging.info(f"Creating output directory: {settings['output_path']}")
            os.makedirs(settings['output_path'])

        # Get video info using yt-dlp
        try:
            logging.info("Using yt-dlp to get video info...")
            ydl_opts = {
                'format': 'best[ext=mp4]',
                'quiet': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(settings['youtube_url'], download=False)
                stream_url = info['url']
                video_title = info.get('title', 'untitled')
                logging.info(f"Video title: {video_title}")
                logging.info("Successfully got stream URL")

            # Create filename with date and cleaned title
            timestamp = datetime.now().strftime("%Y_%m_%d")
            cleaned_title = clean_filename(video_title)
            output_file = os.path.join(settings['output_path'], f"{timestamp}_{cleaned_title}.jpg")
            logging.info(f"Output file will be: {output_file}")

            # Use ffmpeg to capture screenshot
            logging.info("Running ffmpeg to capture screenshot...")
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-i", stream_url,
                "-vframes", "1",
                "-q:v", "2",
                output_file
            ]
            subprocess.run(ffmpeg_cmd, capture_output=True, check=True)
            
            if os.path.exists(output_file):
                file_size = os.path.getsize(output_file)
                logging.info(f"Screenshot saved successfully. Size: {file_size} bytes")
                notify("Screenshot Captured", f"Saved to: {output_file}")
                return True
            else:
                raise Exception("Screenshot file was not created")

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to capture screenshot: {str(e)}"
            logging.error(f"{error_msg}")
            logging.error(f"Command output: {e.output}")
            logging.error(f"Command stderr: {e.stderr}")
            notify("Error", error_msg)
            return False

    except Exception as e:
        error_msg = f"Error capturing screenshot: {str(e)}"
        logging.error(f"{error_msg}", exc_info=True)
        notify("Error", error_msg)
        return False

def set_youtube_url(icon, item):
    """Open dialog to set YouTube URL."""
    # Create the main window
    dialog = ctk.CTk()
    dialog.title("Set YouTube URL")
    dialog.geometry("400x60")  
    
    # Center the window
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    x = (screen_width - 400) // 2
    y = (screen_height - 60) // 2
    dialog.geometry(f"400x60+{x}+{y}")
    
    # Make window stay on top
    dialog.attributes('-topmost', True)
    dialog.lift()
    
    # Create a frame for content with minimal padding
    content_frame = ctk.CTkFrame(dialog, corner_radius=8)
    content_frame.pack(fill="both", expand=True, padx=8, pady=8)
    
    # Create a frame for URL entry and save button
    url_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
    url_frame.pack(expand=True)
    
    def save_url():
        url = url_entry.get().strip()
        if url:
            settings['youtube_url'] = url
            settings['is_paused'] = False  # Auto-unpause when URL is set
            save_settings()
            notify("YouTube URL", "URL saved successfully. Screenshot capture resumed.")
            icon.menu = create_menu(icon)  # Update menu to show Pause option
            dialog.destroy()
        else:
            notify("YouTube URL", "Please enter a valid URL")
    
    # Add URL entry
    url_entry = ctk.CTkEntry(
        url_frame,
        width=280,
        height=30,
        placeholder_text="Enter YouTube URL here..."
    )
    url_entry.pack(side="left", padx=(0, 5))
    if settings['youtube_url']:
        url_entry.insert(0, settings['youtube_url'])
    
    # Add save button next to entry
    save_button = ctk.CTkButton(
        url_frame,
        text="Save",
        width=60,
        height=30,
        command=save_url
    )
    save_button.pack(side="left")
    
    # Bind Enter key to save
    dialog.bind('<Return>', lambda e: save_url())
    
    # Focus the entry
    url_entry.focus()
    
    dialog.mainloop()

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
        save_settings()  # Save interval to config
        logging.info(f"Changed interval from {old_interval}s to {interval}s")
        notify("Interval Changed", f"Screenshot interval set to {interval} seconds")
        # Update the menu to show new checked state
        create_menu(icon)
    return MenuItem(text, set_interval, checked=lambda item: settings['interval'] == interval)

def get_interval_menu():
    """Create a submenu for interval options."""
    logging.info("Creating interval submenu")
    # Create intervals from 5 to 60 seconds in 5-second increments
    intervals = [(f"{secs} seconds", secs) for secs in range(5, 61, 5)]
    logging.info(f"Available intervals: {[i[1] for i in intervals]} seconds")
    menu_items = [create_menu_item(text, secs) for text, secs in intervals]
    return Menu(*menu_items)

def toggle_pause(icon, item):
    """Toggle the pause state."""
    settings['is_paused'] = not settings['is_paused']
    
    # If trying to resume but no URL is set, force pause
    if not settings['is_paused'] and not settings['youtube_url']:
        settings['is_paused'] = True
        notify("Cannot Resume", "Please set a YouTube URL first")
    
    # Save settings
    save_settings()
    
    # Show notification
    state = "paused" if settings['is_paused'] else "resumed"
    notify("Capture Status", f"Screenshot capture {state}")
    
    # Recreate the entire menu to update the text
    icon.menu = create_menu(icon)

def create_icon():
    """Create a system tray icon with a camera design."""
    # Create a transparent background
    icon_size = 128  # Increased from 64 to 128 for better scaling
    icon_image = Image.new("RGBA", (icon_size, icon_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon_image)
    
    # Scale factor to make the camera design larger
    scale = 1.4
    
    # Draw camera body (dark gray with slight transparency)
    camera_body = [
        (32*scale, 44*scale),  # top-left
        (96*scale, 44*scale),  # top-right
        (96*scale, 92*scale),  # bottom-right
        (32*scale, 92*scale)   # bottom-left
    ]
    draw.polygon(camera_body, fill=(64, 64, 64, 255))  # Made fully opaque
    
    # Draw camera lens (light blue with slight transparency)
    center_x, center_y = 64*scale, 68*scale
    radius = 16*scale
    draw.ellipse(
        [center_x - radius, center_y - radius, 
         center_x + radius, center_y + radius],
        fill=(0, 150, 255, 255)  # Made fully opaque
    )
    
    # Draw viewfinder bump (dark gray with slight transparency)
    viewfinder = [
        (50*scale, 36*scale),  # top-left
        (78*scale, 36*scale),  # top-right
        (78*scale, 44*scale),  # bottom-right
        (50*scale, 44*scale)   # bottom-left
    ]
    draw.polygon(viewfinder, fill=(64, 64, 64, 255))  # Made fully opaque
    
    # Resize the image down to Windows system tray size (16x16 or 32x32)
    icon_image = icon_image.resize((32, 32), Image.Resampling.LANCZOS)
    
    return icon_image

def quit_program(icon, item):
    """Quit the program."""
    print("Exiting...")
    icon.stop()
    os._exit(0)

def notify(title, message):
    """Show a notification."""
    notification.notify(
        title=title,
        message=message,
        timeout=5
    )

def get_sun_times():
    """Calculate today's sunrise and sunset times for the given location."""
    s = sun(get_location_info().observer, date=datetime.now(ZoneInfo(get_location_info().timezone)))
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

def run_app():
    """Run the application with system tray icon."""
    logging.info("Starting application")
    icon_image = create_icon()
    icon = Icon("Screenshot Grabber", icon_image, menu=create_menu(None))
    
    icon.menu = create_menu(icon)
    
    logging.info("Starting screenshot thread...")
    screenshot_thread = threading.Thread(target=test_screenshots, daemon=True)
    screenshot_thread.start()
    
    # Start schedule thread
    global schedule_thread
    schedule_thread = threading.Thread(target=schedule_screenshots, daemon=True)
    schedule_thread.start()
    
    logging.info("Application ready")
    icon.run()

if __name__ == "__main__":
    try:
        run_app()
    except Exception as e:
        logging.error(f"Error in main: {str(e)}", exc_info=True)
        notify("Application Error", str(e))