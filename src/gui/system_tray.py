import logging
import pystray
from PIL import Image, ImageDraw
from typing import Dict, Any, Optional, Callable
import tkinter as tk
from tkinter import filedialog

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
        
    def create_icon(self) -> Image:
        """Create a camera icon."""
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
            resolutions = ['2160p', '1440p', '1080p', '720p', '480p', '360p']
            return pystray.Menu(*[
                pystray.MenuItem(
                    res,
                    action=lambda _, r=res: self.callbacks['set_resolution'](r),
                    checked=lambda item, r=res: self.settings.get('resolution') == r,
                    radio=True
                ) for res in resolutions
            ])

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

        return pystray.Menu(
            pystray.MenuItem(
                "Set YouTube URL",
                action=lambda _: URLDialog(
                    settings=self.settings,
                    on_save=self.callbacks['set_youtube_url']
                ).run()
            ),
            pystray.MenuItem(
                "Set Location",
                action=lambda _: LocationDialog(
                    settings=self.settings,
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
                        "Capture Both Sunrise and Sunset",
                        action=lambda _: self.callbacks['toggle_only_sunsets'](),
                        checked=lambda item: not self.settings.get('only_sunsets', False),
                        radio=True
                    ),
                    pystray.MenuItem(
                        "Capture Only Sunset",
                        action=lambda _: self.callbacks['toggle_only_sunsets'](),
                        checked=lambda item: self.settings.get('only_sunsets', False),
                        radio=True
                    )
                )
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Pause",
                action=lambda _: self.callbacks['toggle_pause'](),
                checked=lambda item: self._paused
            ),
            pystray.MenuItem("Quit", action=lambda _: self.callbacks['quit']())
        )

    def update_settings(self, new_settings: Dict[str, Any]) -> None:
        """Update settings and refresh menu."""
        self.settings.update(new_settings)
        if self.icon:
            self.icon.menu = self.create_menu()

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
