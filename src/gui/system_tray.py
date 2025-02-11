import logging
import pystray
from PIL import Image, ImageDraw
from typing import Dict, Any, Optional, Callable
import tkinter as tk
from tkinter import filedialog
import os
from pathlib import Path
import subprocess
import os
import threading
from .location_dialog import LocationDialog
from .url_dialog import URLDialog

logger = logging.getLogger(__name__)

class SystemTray:
    def __init__(self, settings: Dict[str, Any], callbacks: Dict[str, Callable]):
        """Initialize system tray icon."""
        self.settings = settings
        self.callbacks = callbacks
        self.icon = None
        self._paused = False
        self._converting = False  # Track if clip conversion is in progress
        self._conversion_process = None  # Store the conversion process
        
    def create_icon(self) -> Image:
        """Load the icon from assets folder."""
        # Get the path to the icon file
        src_dir = Path(__file__).parent.parent
        icon_path = os.path.join(src_dir, 'assets', 'icon.png')
        
        try:
            # Open and return the icon image
            return Image.open(icon_path)
        except Exception as e:
            logger.error(f"Failed to load icon from {icon_path}: {e}")
            # Fall back to creating a basic icon if loading fails
            return self._create_fallback_icon()
            
    def _create_fallback_icon(self) -> Image:
        """Create a basic camera icon as fallback."""
        # Create a new image with a black background
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), 'black')
        dc = ImageDraw.Draw(image)
        
        # Draw camera body
        dc.rectangle((10, 20, 54, 44), fill='white')
        
        # Draw lens
        dc.ellipse((22, 25, 42, 39), fill='black')
        dc.ellipse((24, 27, 40, 37), fill='white')
        
        # Draw viewfinder
        dc.rectangle((45, 15, 50, 20), fill='white')
        
        return image
        
    def create_menu(self) -> pystray.Menu:
        """Create the system tray menu."""
        def get_interval_menu():
            def create_interval_item(text: str, interval_value: int):
                def set_interval(icon, item):
                    self.callbacks['set_interval'](interval_value)
                return pystray.MenuItem(
                    text,
                    set_interval,
                    checked=lambda item: int(self.settings.get('interval', 60)) == interval_value,
                    radio=True
                )
            
            intervals = [
                ("1 second", 1),
                ("2 seconds", 2),
                ("3 seconds", 3),
                ("4 seconds", 4),
                ("5 seconds", 5),
                ("10 seconds", 10),
                ("15 seconds", 15),
                ("30 seconds", 30),
                ("45 seconds", 45),
                ("1 minute", 60),
                ("1:15 minute", 75),
                ("1:30 minute", 90),
                ("1:45 minute", 105),
                ("2 minutes", 120),
                ("3 minutes", 180),
                ("4 minutes", 240),
                ("5 minutes", 300),
                ("6 minutes", 360),
                ("7 minutes", 420),
                ("8 minutes", 480),
                ("9 minutes", 540),
                ("10 minutes", 600),
                ("15 minutes", 900),
                ("30 minutes", 1800)
            ]
            return pystray.Menu(*[create_interval_item(text, interval) for text, interval in intervals])

        def get_resolution_menu():
            def create_resolution_item(res: str):
                def check_resolution(item):
                    return self.settings.get('resolution', '1080p') == res
                    
                def set_resolution(icon, item):
                    self._handle_resolution_change(res)
                    
                return pystray.MenuItem(
                    res,
                    set_resolution,
                    checked=check_resolution,
                    radio=True
                )
            
            resolutions = ['2160p', '1440p', '1080p', '720p', '480p', '360p']
            return pystray.Menu(*[create_resolution_item(res) for res in resolutions])

        def get_time_window_menu():
            def create_time_window_item(text: str, minutes_value: int):
                def set_time_window(icon, item):
                    self.callbacks['set_time_window'](minutes_value)
                return pystray.MenuItem(
                    text,
                    set_time_window,
                    checked=lambda item: int(self.settings.get('time_window', 30)) == minutes_value,
                    radio=True
                )
            
            time_windows = [
                ('15 minutes', 15),
                ('30 minutes', 30),
                ('45 minutes', 45),
                ('60 minutes', 60),
                ('90 minutes', 90),
                ('120 minutes', 120)
            ]
            return pystray.Menu(*[create_time_window_item(text, minutes) for text, minutes in time_windows])

        def select_output_path(_):
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            path = filedialog.askdirectory()
            root.destroy()
            if path:
                self.callbacks['set_output_path'](path)

        def convert_to_clips(_):
            """
            Iterate over each subfolder in 'output_path', combine its images into
            a single MP4 using FFmpeg at 60 fps, then delete the images.
            """
            # First ensure the capture processes are paused
            if not self._paused:
                self.callbacks['toggle_pause']()

            if self._converting:
                return

            self._converting = True
            self.update_menu()  # Grey out the menu item

            output_path = self.settings.get('output_path')
            if not output_path:
                logger.error("No output path set")
                self._converting = False
                self.update_menu()
                return

            def monitor_process():
                try:
                    self._convert_subfolders_to_clips_ffmpeg(output_path)
                except Exception as e:
                    logger.error(f"Clip conversion error: {e}")
                finally:
                    self._converting = False
                    self._conversion_process = None
                    self.update_menu()

                if self._paused:
                    self.callbacks['toggle_pause']()

            thread = threading.Thread(target=monitor_process, daemon=True)
            thread.start()

        return pystray.Menu(
            pystray.MenuItem(
                "Set YouTube URL",
                action=lambda _: URLDialog(
                    settings=self.callbacks['get_current_settings'](),
                    on_save=self.callbacks['set_youtube_url']
                ).run()
            ),
            pystray.MenuItem(
                "Set Location",
                action=lambda _: LocationDialog(
                    settings=self.callbacks['get_current_settings'](),
                    on_save=self.callbacks['set_location']
                ).run()
            ),
            pystray.MenuItem("Set Output Path", action=select_output_path),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Capture Settings", pystray.Menu(
                pystray.MenuItem("Capture Interval", get_interval_menu()),
                pystray.MenuItem("Resolution", get_resolution_menu()),
                pystray.MenuItem("Time Window", get_time_window_menu())
            )),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Enable Scheduling",
                action=lambda _: self.callbacks['toggle_schedule'](),
                checked=lambda item: self.settings.get('schedule_enabled', False)
            ),
            pystray.MenuItem(
                "Capture Mode",
                pystray.Menu(
                    pystray.MenuItem(
                        "Sunrise and Sunset",
                        action=lambda _: self.callbacks['toggle_capture_mode']('both'),
                        checked=lambda item: not self.settings.get('only_sunsets', False) and not self.settings.get('only_sunrises', False),
                        radio=True
                    ),
                    pystray.MenuItem(
                        "Only Sunrise",
                        action=lambda _: self.callbacks['toggle_capture_mode']('sunrise'),
                        checked=lambda item: (not self.settings.get('only_sunsets', False)
                                            and self.settings.get('only_sunrises', False)),
                        radio=True
                    ),
                    pystray.MenuItem(
                        "Only Sunset",
                        action=lambda _: self.callbacks['toggle_capture_mode']('sunset'),
                        checked=lambda item: (self.settings.get('only_sunsets', False)
                                            and not self.settings.get('only_sunrises', False)),
                        radio=True
                    )
                )
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Convert to Clips",
                action=convert_to_clips,
                enabled=lambda item: not self._converting
            ),
            # --- New setting here ---
            pystray.MenuItem(
                "Shutdown when done",
                action=lambda _: self.callbacks['toggle_shutdown_when_done'](),
                checked=lambda item: self.settings.get('shutdown_when_done', False)
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Pause",
                action=lambda _: self.callbacks['toggle_pause'](),
                checked=lambda item: self._paused
            ),
            pystray.MenuItem("Quit", action=lambda _: self.callbacks['quit']())
        )

    def _handle_resolution_change(self, resolution: str) -> None:
        """Handle resolution change and update menu."""
        self.callbacks['set_resolution'](resolution)
        # Force menu refresh immediately after resolution change
        if self.icon:
            new_menu = self.create_menu()
            self.icon.menu = new_menu
            self.icon.update_menu()

    def update_settings(self, new_settings: Dict[str, Any]) -> None:
        """Update settings and refresh menu."""
        self.settings.update(new_settings)
        if self.icon:
            # Recreate the menu with new settings
            new_menu = self.create_menu()
            self.icon.menu = new_menu
            # Force an update of the menu
            self.icon.update_menu()

    def run(self) -> None:
        """Run the system tray icon."""
        icon_image = self.create_icon()
        self.icon = pystray.Icon(
            "Screenshot Grabber",
            icon_image,
            menu=self.create_menu()
        )
        
        try:
            self.icon.run()
        except Exception as e:
            logger.error(f"Error running system tray: {e}")
            raise
        finally:
            if self.icon:
                self.icon.stop()
                
    def update_menu(self) -> None:
        """Update the system tray menu."""
        if self.icon:
            self.icon.menu = self.create_menu()

    def set_paused(self, paused: bool) -> None:
        """Set the paused state."""
        self._paused = paused
        self.update_menu()

    def _convert_subfolders_to_clips_ffmpeg(self, base_path: str) -> None:
        """
        For each subfolder in 'base_path', rename images to frame0001.jpg, frame0002.jpg, etc.,
        then run FFmpeg to create a .mp4 at self.settings['fps'] fps. Upon success, delete the images.
        """
        subfolders = [
            d for d in os.listdir(base_path)
            if os.path.isdir(os.path.join(base_path, d))
        ]
        
        fps = self.settings.get('fps', 60)

        for folder_name in subfolders:
            folder_path = os.path.join(base_path, folder_name)
            
            # Gather all .jpg images
            image_files = [
                f for f in os.listdir(folder_path)
                if f.lower().endswith(".jpg")
            ]
            if not image_files:
                logger.info(f"No .jpg images in '{folder_name}' - skipping.")
                continue

            # Sort them so the rename sequence (and final video sequence) matches the alphabetical order
            image_files.sort()

            # Rename them to frame0001.jpg, frame0002.jpg, etc.
            logger.info(f"Renaming {len(image_files)} images in '{folder_name}'...")
            for i, old_filename in enumerate(image_files, start=1):
                new_filename = f"frame{i:04d}.jpg"  # adjust zero-padding as needed
                old_path = os.path.join(folder_path, old_filename)
                new_path = os.path.join(folder_path, new_filename)
                try:
                    os.rename(old_path, new_path)
                except Exception as e:
                    logger.error(f"Could not rename {old_filename} -> {new_filename}: {e}")

            output_clip = os.path.join(base_path, f"{folder_name}.mp4")
            logger.info(f"Converting renamed images to clip: '{output_clip}' at {fps} FPS")

            # Build the FFmpeg command using the numeric pattern
            cmd = [
                "ffmpeg",
                "-framerate", str(fps),
                "-i", os.path.join(folder_path, "frame%04d.jpg"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-y",  # Overwrite
                output_clip
            ]

            process = subprocess.run(cmd, capture_output=True, text=True)
            if process.returncode != 0:
                logger.error(f"FFmpeg error for '{folder_name}':\n{process.stderr}")
                continue
            
            logger.info(f"Clip created: {output_clip}. Deleting images...")

            # On success, delete images
            renamed_files = [
                f for f in os.listdir(folder_path)
                if f.lower().startswith('frame') and f.lower().endswith('.jpg')
            ]
            for img_file in renamed_files:
                try:
                    os.remove(os.path.join(folder_path, img_file))
                except Exception as ex:
                    logger.warning(f"Could not delete file {img_file}: {ex}")

            try:
                os.rmdir(folder_path)
            except OSError as e:
                logger.warning(f"Could not remove folder {folder_path}: {e}")