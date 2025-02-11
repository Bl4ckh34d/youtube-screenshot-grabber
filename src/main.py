import os
import logging
import threading
import concurrent.futures
import queue
from datetime import datetime
from pathlib import Path
import yt_dlp
from typing import Dict, Any, List, Optional
import sys
import subprocess

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.logging_config import setup_logging
from src.core.settings import Settings
from src.core.location import get_windows_location, get_location_info
from src.core.screenshot import ScreenshotCapture, StreamManager
from src.core.scheduler import Scheduler
from src.gui.system_tray import SystemTray

# Initialize logging first
setup_logging()
logger = logging.getLogger('src.core.scheduler')

class App:
    def __init__(self):
        """Initialize the application."""
        self.settings = Settings()
        self.screenshot = ScreenshotCapture()
        self.stream_manager = StreamManager()
        self.scheduler = Scheduler(settings=self.settings)
        self.scheduler._app = self
        self._validation_thread = None
        
        # Only use Windows location if no location is saved
        saved_location = self.settings.get('location', {})
        if (saved_location.get('latitude') == 0 and saved_location.get('longitude') == 0):
            windows_location = get_windows_location()
            if windows_location:
                logger.info(f"No saved location found. Using Windows location: {windows_location}")
                self.settings.update({'location': windows_location})
        else:
            logger.info(f"Using saved location: {saved_location}")
        
        # Create system tray with callbacks
        self.system_tray = SystemTray(
            settings=self.settings.all,
            callbacks={
                'set_youtube_url': self.set_youtube_urls,
                'set_location': self.set_location,
                'set_interval': self.set_interval,
                'set_resolution': self.set_resolution,
                'set_time_window': self.set_time_window,
                'set_output_path': self.set_output_path,
                'toggle_schedule': self.toggle_schedule,
                'toggle_capture_mode': self.toggle_capture_mode,
                'toggle_pause': self.toggle_pause,
                'quit': self.quit,
                'get_current_settings': lambda: self.settings.all,
                'toggle_shutdown_when_done': self.toggle_shutdown_when_done
            }
        )
        
        # Start screenshot thread if needed
        if self.settings.get('youtube_urls'):
            self.start_screenshot_thread()
    
    def set_youtube_urls(self, urls: List[str], valid_urls: List[str] = None) -> None:
        # We don't bother with the concurrency validation
        self.settings.set('youtube_urls', urls)
        self.stream_manager.stop_all()
        # Start them again
        self.start_screenshot_thread()

    
    def _is_valid_youtube_url(self, url: str) -> bool:
        """Check if the URL is a valid YouTube URL."""
        youtube_domains = ['youtube.com', 'youtu.be', 'www.youtube.com']
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return any(domain in parsed.netloc for domain in youtube_domains)
        except:
            return False
    
    def set_location(self, location: Dict[str, float]) -> None:
        """Set location and update scheduler."""
        self.settings.set('location', location)
        self.update_scheduler()
    
    def set_interval(self, interval: int) -> None:
        """Set capture interval in seconds."""
        # Ensure interval is an integer
        interval = int(interval)
        self.settings.set('interval', interval)
        self.scheduler.update_settings(interval=interval)
        # Update interval for all running streams
        self.stream_manager.update_interval(interval)
        self.system_tray.update_settings(self.settings.all)
    
    def set_resolution(self, resolution: str) -> None:
        """Set preferred resolution."""
        self.settings.set('resolution', resolution)
        self.system_tray.update_settings(self.settings.all)
        logger.info("Scheduler settings updated")
    
    def set_time_window(self, minutes: int) -> None:
        """Set time window for sunset/sunrise captures."""
        # Ensure minutes is an integer
        minutes = int(minutes)
        self.settings.set('time_window', minutes)
        self.scheduler.update_settings(time_window=minutes)
        self.system_tray.update_settings(self.settings.all)
    
    def set_output_path(self, path: str) -> None:
        """Set output path for screenshots."""
        self.settings.set('output_path', path)
    
    def toggle_schedule(self) -> None:
        """Toggle schedule enabled state."""
        enabled = not self.settings.get('schedule_enabled', False)
        self.settings.set('schedule_enabled', enabled)
        self.scheduler.update_settings(schedule_enabled=enabled)
        self.system_tray.update_settings(self.settings.all)

    def toggle_capture_mode(self, mode: str) -> None:
        """Toggle between different capture modes (both, sunrise, sunset)."""
        if mode == 'both':
            self.settings.set('only_sunsets', False)
            self.settings.set('only_sunrises', False)
        elif mode == 'sunrise':
            self.settings.set('only_sunsets', False)
            self.settings.set('only_sunrises', True)
        elif mode == 'sunset':
            self.settings.set('only_sunsets', True)
            self.settings.set('only_sunrises', False)
            
        self.scheduler.update_settings(
            only_sunsets=self.settings.get('only_sunsets', False),
            only_sunrises=self.settings.get('only_sunrises', False)
        )
        self.system_tray.update_settings(self.settings.all)

    def toggle_pause(self) -> None:
        """Toggle pause state."""
        if self.scheduler._paused:
            # Currently paused: resume the scheduler and all stream processes.
            self.scheduler.resume()
            self.system_tray.set_paused(False)
            for stream in self.stream_manager.streams.values():
                stream.resume()
        else:
            # Currently running: pause the scheduler and all stream processes.
            self.scheduler.pause()
            self.system_tray.set_paused(True)
            for stream in self.stream_manager.streams.values():
                stream.pause()
        self.system_tray.update_settings(self.settings.all)
    
    def quit(self) -> None:
        """Quit the application."""
        logger.info("Quitting application...")

        # 1. Stop scheduler
        self.scheduler.stop()
        
        # 2. Stop all stream processes
        self.stream_manager.stop_all()
        
        os._exit(0)  # Hard kill
    
    def start_screenshot_thread(self) -> None:
        """Start or restart the screenshot thread."""
        self.scheduler.stop()
        
        if self.settings.get('youtube_urls'):
            self.update_scheduler()
    
    def update_scheduler(self) -> None:
        """Update scheduler with current settings."""
        location = self.settings.get('location', {})
        if location.get('latitude') != 0 or location.get('longitude') != 0:
            location_info = get_location_info(
                location['latitude'],
                location['longitude']
            )
        else:
            location_info = None
        
        # Ensure time_window is an integer
        time_window = int(self.settings.get('time_window', 30))
        
        self.scheduler.start(
            callback=self.capture_screenshot,
            interval=int(self.settings.get('interval', 60)),
            location=location_info,
            time_window=time_window,
            only_sunsets=bool(self.settings.get('only_sunsets', False)),
            only_sunrises=bool(self.settings.get('only_sunrises', False)),
            schedule_enabled=bool(self.settings.get('schedule_enabled', False))
        )
    
    def capture_screenshot(self, event_type="") -> Optional[str]:
        try:
            urls = self.settings.get('youtube_urls', [])
            if not urls:
                logger.warning("No YouTube URLs set")
                return

            output_path = self.settings.get('output_path')
            if not output_path:
                logger.warning("No output path set")
                return

            interval = int(self.settings.get('interval', 60))
            resolution = self.settings.get('resolution', '1080p')

            # Remove old streams if needed, then add streams for new URLs
            current_urls = set(self.stream_manager.streams.keys())
            new_urls = set(urls)

            # Remove any that aren't used
            for url in current_urls - new_urls:
                self.stream_manager.remove_stream(url)

            # Whether everything is paused
            is_paused = self.scheduler._paused

            # Add new streams (with event_type so we can name folders properly)
            for url in new_urls - current_urls:
                self.stream_manager.add_stream(
                    url=url,
                    output_path=output_path,
                    interval=interval,
                    resolution=resolution,
                    paused=is_paused,
                    event_type=event_type
                )

        except Exception as e:
            logger.error(f"Error managing screenshot processes: {str(e)}")
            
    def run(self) -> None:
        """Run the application."""
        try:
            self.system_tray.run()
        except Exception as e:
            logger.error(f"Error running app: {e}")
            raise
        finally:
            self.quit()

    def toggle_shutdown_when_done(self) -> None:
        """Toggle whether the PC should shut down automatically after converting clips."""
        current = bool(self.settings.get('shutdown_when_done', False))
        self.settings.set('shutdown_when_done', not current)
        self.system_tray.update_settings(self.settings.all)

    def convert_subfolders_to_clips_and_cleanup(self, event_type: str = "") -> None:
        """
        Converts each subfolder that matches today's date+event_type to an MP4,
        then removes the images and the subfolder.
        If event_type is "", we convert everything for 'today'.
        """
        output_path = self.settings.get('output_path')
        if not output_path:
            logger.warning("No output_path configured; cannot convert.")
            return

        # For today's date
        today_str = datetime.now().strftime('%Y_%m_%d')
        # We'll match subfolders that start with e.g. "2025_02_07_Sunrise_" or "2025_02_07_"
        # If event_type is empty => any subfolder matching today's date

        try:
            subfolders = [
                f for f in os.listdir(output_path)
                if os.path.isdir(os.path.join(output_path, f))
            ]
        except Exception as ex:
            logger.error(f"Error listing subfolders in {output_path}: {ex}")
            return

        # Filter down to those that match the pattern
        matched_subfolders = []
        for folder in subfolders:
            if folder.startswith(today_str):
                if event_type:
                    # If we have "Sunrise" or "Sunset", check it
                    # e.g. "2025_02_07_Sunset_..."
                    if f"_{event_type.capitalize()}_" in folder:
                        matched_subfolders.append(folder)
                else:
                    # If event_type is "", we accept everything that starts with today's date
                    matched_subfolders.append(folder)

        if not matched_subfolders:
            logger.info(f"No subfolders match {today_str} {event_type}, skipping conversion.")
            return

        logger.info(f"Converting subfolders for {today_str} {event_type}: {matched_subfolders}")

        # We'll adapt the conversion logic from SystemTray._convert_subfolders_to_clips_ffmpeg,
        # but do it here synchronously
        fps = self.settings.get('fps', 60)

        for folder_name in matched_subfolders:
            folder_path = os.path.join(output_path, folder_name)
            image_files = [
                f for f in os.listdir(folder_path)
                if f.lower().endswith(".jpg")
            ]
            if not image_files:
                logger.info(f"No images found in {folder_name}, skipping.")
                continue

            # Sort them
            image_files.sort()

            logger.info(f"Renaming {len(image_files)} images in '{folder_name}' for FFmpeg sequence.")
            # rename to frame0001.jpg, frame0002.jpg, etc.
            for i, old_filename in enumerate(image_files, start=1):
                new_filename = f"frame{i:04d}.jpg"
                old_path = os.path.join(folder_path, old_filename)
                new_path = os.path.join(folder_path, new_filename)
                try:
                    os.rename(old_path, new_path)
                except Exception as e:
                    logger.error(f"Could not rename {old_filename} -> {new_filename}: {e}")

            # The final clip name can just be the folder name (plus .mp4):
            output_clip = os.path.join(output_path, f"{folder_name}.mp4")
            logger.info(f"Converting images in '{folder_name}' to '{output_clip}' at {fps} FPS")

            cmd = [
                "ffmpeg",
                "-framerate", str(fps),
                "-i", os.path.join(folder_path, "frame%04d.jpg"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-y",
                output_clip
            ]

            process = subprocess.run(cmd, capture_output=True, text=True)
            if process.returncode != 0:
                logger.error(f"FFmpeg error for '{folder_name}':\n{process.stderr}")
                continue

            logger.info(f"Clip created: {output_clip}. Deleting images and folder...")

            # remove all .jpg
            for img_file in os.listdir(folder_path):
                if img_file.lower().endswith(".jpg"):
                    try:
                        os.remove(os.path.join(folder_path, img_file))
                    except Exception as ex:
                        logger.warning(f"Could not delete file {img_file}: {ex}")

            # remove the folder
            try:
                os.rmdir(folder_path)
            except Exception as ex:
                logger.warning(f"Could not remove folder {folder_path}: {ex}")

        logger.info("All matching subfolders converted and cleaned up.")

def main():
    """Main entry point."""
    try:
        app = App()
        app.run()
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise

if __name__ == "__main__":
    main()
