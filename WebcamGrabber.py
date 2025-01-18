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
    'preferred_resolution': '1080p',  # Default to 1080p
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
    def cleanup_map():
        """Clean up map widget"""
        map_widget.destroy()

    def update_sun_times(lat, lon):
        """Update sun times based on coordinates"""
        try:
            # Temporarily update location to get sun times
            current_location = settings['location'].copy()
            settings['location'].update({
                'latitude': float(lat),
                'longitude': float(lon)
            })
            
            sun_times = get_sun_times()
            if sun_times:
                sunrise = sun_times[0].strftime('%H:%M')
                sunset = sun_times[1].strftime('%H:%M')
                sunrise_entry.configure(state="normal")
                sunrise_entry.delete(0, tk.END)
                sunrise_entry.insert(0, sunrise)
                sunrise_entry.configure(state="readonly")
                sunset_entry.configure(state="normal")
                sunset_entry.delete(0, tk.END)
                sunset_entry.insert(0, sunset)
                sunset_entry.configure(state="readonly")
            
            # Restore original location
            settings['location'] = current_location
        except Exception as e:
            logging.error(f"Failed to update sun times: {e}")

    def save_location(lat, lon):
        """Save location and update settings"""
        try:
            settings['location'].update({
                'latitude': float(lat),
                'longitude': float(lon)
            })
            save_settings()
            
            # Update the schedule thread
            update_schedule_thread()
            
            notify("Location Updated", 
                  f"Location set to {settings['location']['latitude']}, {settings['location']['longitude']}")
        except Exception as e:
            notify("Error", f"Failed to save location: {str(e)}")

    def validate_and_save_coordinate(value, coord_type):
        """Validate coordinate input and save if valid"""
        try:
            float_val = float(value)
            if coord_type == 'lat' and -90 <= float_val <= 90:
                save_location(float_val, float(lon_entry.get()))
                return True
            elif coord_type == 'lon' and -180 <= float_val <= 180:
                save_location(float(lat_entry.get()), float_val)
                return True
            return False
        except ValueError:
            return False

    def on_schedule_toggle():
        """Handle schedule toggle changes"""
        settings['schedule_enabled'] = schedule_var.get()
        save_settings()
        update_schedule_thread()
        notify("Schedule Updated", 
              f"Sunset/Sunrise capture {'enabled' if settings['schedule_enabled'] else 'disabled'}")

    def on_closing():
        cleanup_map()
        dialog.destroy()

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
    
    # Create main container with padding
    main_frame = ctk.CTkFrame(dialog)
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Create top frame for coordinates and sun times
    settings_frame = ctk.CTkFrame(main_frame)
    settings_frame.pack(fill="x", padx=5, pady=(0, 10))
    
    # Configure grid columns - two equal sections
    settings_frame.grid_columnconfigure(1, weight=1)  # Entry column 1
    settings_frame.grid_columnconfigure(3, weight=1)  # Entry column 2
    
    def validate_lat(event=None):
        """Validate latitude input"""
        value = lat_entry.get()
        if not validate_and_save_coordinate(value, 'lat'):
            lat_entry.delete(0, tk.END)
            lat_entry.insert(0, str(settings['location']['latitude']))

    def validate_lon(event=None):
        """Validate longitude input"""
        value = lon_entry.get()
        if not validate_and_save_coordinate(value, 'lon'):
            lon_entry.delete(0, tk.END)
            lon_entry.insert(0, str(settings['location']['longitude']))
    
    # Create coordinate entries
    lat_label = ctk.CTkLabel(settings_frame, text="Latitude:")
    lat_label.grid(row=0, column=0, padx=5, pady=2, sticky="e")
    lat_entry = ctk.CTkEntry(settings_frame, width=150)
    lat_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
    lat_entry.insert(0, str(settings['location']['latitude']))
    lat_entry.bind('<FocusOut>', validate_lat)
    lat_entry.bind('<Return>', validate_lat)
    
    lon_label = ctk.CTkLabel(settings_frame, text="Longitude:")
    lon_label.grid(row=1, column=0, padx=5, pady=2, sticky="e")
    lon_entry = ctk.CTkEntry(settings_frame, width=150)
    lon_entry.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
    lon_entry.insert(0, str(settings['location']['longitude']))
    lon_entry.bind('<FocusOut>', validate_lon)
    lon_entry.bind('<Return>', validate_lon)
    
    # Add sun times display (read-only)
    sunrise_label = ctk.CTkLabel(settings_frame, text="Sunrise:")
    sunrise_label.grid(row=0, column=2, padx=5, pady=2, sticky="e")
    sunrise_entry = ctk.CTkEntry(settings_frame, width=150)
    sunrise_entry.configure(state="readonly")
    sunrise_entry.grid(row=0, column=3, padx=5, pady=2, sticky="ew")
    
    sunset_label = ctk.CTkLabel(settings_frame, text="Sunset:")
    sunset_label.grid(row=1, column=2, padx=5, pady=2, sticky="e")
    sunset_entry = ctk.CTkEntry(settings_frame, width=150)
    sunset_entry.configure(state="readonly")
    sunset_entry.grid(row=1, column=3, padx=5, pady=2, sticky="ew")
    
    # Initialize sun times
    update_sun_times(settings['location']['latitude'], settings['location']['longitude'])
    
    # Create map frame that will expand with window
    map_frame = ctk.CTkFrame(main_frame)
    map_frame.pack(fill="both", expand=True, padx=5, pady=5)
    
    # Create map widget
    map_widget = tkintermapview.TkinterMapView(map_frame, width=800, height=400, corner_radius=0)
    map_widget.pack(fill="both", expand=True)
    
    # Add schedule toggle switch overlay on map
    schedule_var = ctk.BooleanVar(value=settings['schedule_enabled'])
    schedule_switch = ctk.CTkSwitch(
        map_frame,
        text="Capture Only Sunsets/Sunrises",
        variable=schedule_var,
        command=on_schedule_toggle,
        width=200
    )
    schedule_switch.place(relx=1.0, y=10, anchor="ne", x=-10)
    
    # Set initial map position and marker
    if settings['location']['latitude'] != 0 or settings['location']['longitude'] != 0:
        lat = settings['location']['latitude']
        lon = settings['location']['longitude']
        map_widget.set_position(lat, lon)
        map_widget.set_zoom(12)
        map_widget.set_marker(lat, lon)
    else:
        map_widget.set_zoom(8)
    
    def on_map_click(coords):
        lat, lon = coords
        lat_entry.delete(0, tk.END)
        lat_entry.insert(0, str(lat))
        lon_entry.delete(0, tk.END)
        lon_entry.insert(0, str(lon))
        
        # Add marker at clicked position
        map_widget.delete_all_marker()
        map_widget.set_marker(lat, lon)
        
        # Update sun times for new location
        update_sun_times(lat, lon)
        
        # Save location immediately
        save_location(lat, lon)
    
    map_widget.add_left_click_map_command(on_map_click)
    
    # Bind window close button
    dialog.protocol("WM_DELETE_WINDOW", on_closing)
    
    dialog.mainloop()

def update_schedule_thread():
    """Update the schedule thread based on current settings."""
    global schedule_thread
    
    # Stop existing thread if running
    if schedule_thread and schedule_thread.is_alive():
        schedule_thread = None
    
    # Start new thread if scheduling is enabled
    if settings['schedule_enabled']:
        schedule_thread = threading.Thread(target=schedule_screenshots, daemon=True)
        schedule_thread.start()
        
        # Force immediate schedule update
        sunrise, sunset = get_sun_times()
        now = datetime.now(sunrise.tzinfo)
        if now < sunrise - timedelta(minutes=30):
            next_window = sunrise - timedelta(minutes=30)
            window_type = "sunrise"
        elif now < sunset - timedelta(minutes=30):
            next_window = sunset - timedelta(minutes=30)
            window_type = "sunset"
        else:
            tomorrow = now.date() + timedelta(days=1)
            next_sunrise = sun(get_location_info().observer, date=tomorrow)['sunrise']
            next_window = next_sunrise - timedelta(minutes=30)
            window_type = "tomorrow's sunrise"
        
        time_until = next_window - now
        logging.info(f"Next capture window: {window_type} at {next_window} (in {time_until})")

def schedule_screenshots():
    """Monitor schedule and log next capture windows."""
    last_date = None
    while True:
        try:
            if settings['schedule_enabled']:
                sunrise, sunset = get_sun_times()
                now = datetime.now(sunrise.tzinfo)
                current_date = now.date()
                
                # Only update if it's a new day
                if current_date != last_date:
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
                    last_date = current_date
            
            # Sleep until next minute
            now = datetime.now()
            sleep_seconds = 60 - now.second
            time.sleep(sleep_seconds)
            
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
                'quiet': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(settings['youtube_url'], download=False)
                # Get best matching format based on preferred resolution
                best_format = get_best_matching_format(info['formats'], settings['preferred_resolution'])
                if not best_format:
                    raise Exception("No suitable video format found")
                
                stream_url = best_format['url']
                video_title = info.get('title', 'untitled')
                actual_height = best_format.get('height', 'unknown')
                logging.info(f"Video title: {video_title}")
                logging.info(f"Selected resolution: {actual_height}p")
                logging.info("Successfully got stream URL")

            # Create filename with full timestamp and cleaned title
            timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            cleaned_title = clean_filename(video_title)
            output_file = os.path.join(settings['output_path'], f"{timestamp}_{cleaned_title}.jpg")
            logging.info(f"Output file will be: {output_file}")

            # Use ffmpeg to capture screenshot
            logging.info("Running ffmpeg to capture screenshot...")
            startupinfo = None
            if os.name == 'nt':  # Windows
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-i", stream_url,
                "-vframes", "1",
                "-q:v", "2",
                output_file
            ]
            subprocess.run(ffmpeg_cmd, capture_output=True, check=True, startupinfo=startupinfo)
            
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

def create_menu(icon=None):
    """Create the system tray menu."""
    logging.info("[create_menu] Creating system tray menu")
    logging.info(f"[create_menu] Current settings - Interval: {settings['interval']}s, Paused: {settings['is_paused']}")

    # Create settings submenu
    settings_menu = Menu(
        MenuItem("Set YouTube URL", set_youtube_url),
        MenuItem("Set Output Path", select_output_path),
        MenuItem("Set Location", set_location),
        MenuItem("Set Interval", get_interval_menu()),
        MenuItem("Set Resolution", get_resolution_menu())
    )

    # Create main menu items
    menu_items = [
        MenuItem("⬛ Pause" if not settings['is_paused'] else "▶ Resume", toggle_pause),
        MenuItem("Settings", settings_menu),
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

def create_resolution_menu_item(text, resolution):
    """Create a menu item for a specific resolution."""
    def set_resolution(icon, item):
        old_resolution = settings['preferred_resolution']
        settings['preferred_resolution'] = resolution
        save_settings()
        logging.info(f"Changed resolution from {old_resolution} to {resolution}")
        notify("Resolution Changed", f"Screenshot resolution set to {resolution}")
        # Update menu to show new checked state
        create_menu(icon)
    return MenuItem(text, set_resolution, checked=lambda item: settings['preferred_resolution'] == resolution)

def get_resolution_menu():
    """Create a submenu for resolution options."""
    logging.info("Creating resolution submenu")
    # Common YouTube resolutions
    resolutions = [
        ("4K (2160p)", "2160p"),
        ("1440p", "1440p"),
        ("1080p", "1080p"),
        ("720p", "720p"),
        ("480p", "480p"),
        ("360p", "360p")
    ]
    logging.info(f"Available resolutions: {[r[1] for r in resolutions]}")
    menu_items = [create_resolution_menu_item(text, res) for text, res in resolutions]
    return Menu(*menu_items)

def get_best_matching_format(formats, preferred_resolution):
    """Find the best matching format for the preferred resolution."""
    # Extract height from preferred resolution (e.g., '1080p' -> 1080)
    target_height = int(preferred_resolution.replace('p', ''))
    
    # Filter for mp4 formats with both video and audio
    valid_formats = [
        f for f in formats 
        if f.get('ext') == 'mp4' and 
        f.get('acodec') != 'none' and 
        f.get('vcodec') != 'none'
    ]
    
    if not valid_formats:
        logging.warning("No valid mp4 formats found, falling back to any format")
        valid_formats = formats
    
    # Sort formats by how close they are to the target resolution
    valid_formats.sort(
        key=lambda f: (
            abs(f.get('height', 0) - target_height),  # Distance from target height
            -f.get('height', 0),  # Prefer higher resolution if same distance
            -f.get('filesize', 0)  # Prefer larger filesize if same height
        )
    )
    
    best_format = valid_formats[0] if valid_formats else None
    if best_format:
        actual_height = best_format.get('height', 'unknown')
        logging.info(f"Selected format: {actual_height}p (wanted {preferred_resolution})")
    
    return best_format

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