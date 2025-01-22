import logging
import threading
from typing import Dict, Any, List
import sys
from pathlib import Path
import yt_dlp

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.logging_config import setup_logging
from src.core.settings import Settings
from src.core.location import get_windows_location, get_location_info
from src.core.screenshot import ScreenshotCapture
from src.core.scheduler import Scheduler
from src.gui.system_tray import SystemTray

logger = setup_logging()

class App:
    def __init__(self):
        """Initialize the application."""
        self.settings = Settings()
        self.screenshot = ScreenshotCapture()
        self.scheduler = Scheduler()
        self._validation_thread = None
        
        # Initialize with Windows location if available
        windows_location = get_windows_location()
        if windows_location:
            logger.info(f"Got Windows location: {windows_location}")
            self.settings.update({'location': windows_location})
        
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
                'toggle_only_sunsets': self.toggle_only_sunsets,
                'toggle_pause': self.toggle_pause,
                'quit': self.quit
            }
        )
        
        # Start screenshot thread if needed
        if self.settings.get('youtube_urls'):
            self.start_screenshot_thread()
    
    def set_youtube_urls(self, urls: List[str], valid_urls: List[str] = None) -> None:
        """Set YouTube URLs and handle validation."""
        # If we received initial URLs (from dialog)
        if not valid_urls:
            logger.info("Starting URL validation")
            # Pause screenshot taking
            self.scheduler.pause()
            self.system_tray.set_paused(True)
            
            # Store unvalidated URLs temporarily
            self.settings.set('pending_urls', urls)
            
            # Start validation in background
            def validate_urls():
                valid_urls = []
                for url in urls:
                    if self._is_valid_youtube_url(url):
                        try:
                            with yt_dlp.YoutubeDL(self.screenshot.ydl_opts) as ydl:
                                ydl.extract_info(url, download=False)
                                valid_urls.append(url)
                                logger.info(f"Validated URL: {url}")
                        except Exception as e:
                            logger.warning(f"Invalid stream URL {url}: {str(e)}")
                
                # Update settings with validated URLs
                self.settings.set('youtube_urls', valid_urls)
                self.settings.set('pending_urls', None)
                
                # Start prefetching stream info
                resolution = self.settings.get('resolution', '1080p')
                self.screenshot.prefetch_stream_info(valid_urls, resolution)
                
                logger.info(f"URL validation complete. {len(valid_urls)} valid URLs found")
                # Note: User must manually resume via system tray
            
            self._validation_thread = threading.Thread(target=validate_urls, daemon=True)
            self._validation_thread.start()
        
        # If we received validated URLs (from validation process)
        else:
            self.settings.set('youtube_urls', valid_urls)
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
        self.system_tray.update_settings(self.settings.all)
    
    def set_resolution(self, resolution: str) -> None:
        """Set preferred resolution."""
        self.settings.set('resolution', resolution)
        self.system_tray.update_settings(self.settings.all)
    
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

    def toggle_only_sunsets(self) -> None:
        """Toggle only sunsets state."""
        only_sunsets = not self.settings.get('only_sunsets', False)
        self.settings.set('only_sunsets', only_sunsets)
        self.scheduler.update_settings(only_sunsets=only_sunsets)
        self.system_tray.update_settings(self.settings.all)

    def toggle_pause(self) -> None:
        """Toggle pause state."""
        if self.scheduler._paused:
            self.scheduler.resume()
            self.system_tray.set_paused(False)
        else:
            self.scheduler.pause()
            self.system_tray.set_paused(True)
        self.system_tray.update_settings(self.settings.all)
    
    def quit(self) -> None:
        """Quit the application."""
        self.scheduler.stop()
        if self.system_tray.icon:
            self.system_tray.icon.stop()
    
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
            schedule_enabled=bool(self.settings.get('schedule_enabled', False))
        )
    
    def capture_screenshot(self) -> None:
        """Capture screenshots from all configured streams."""
        try:
            urls = self.settings.get('youtube_urls', [])
            if not urls:
                logger.warning("No YouTube URLs set")
                return
                
            output_path = self.settings.get('output_path')
            if not output_path:
                logger.warning("No output path set")
                return
            
            resolution = self.settings.get('resolution', '1080p')
            
            # Capture from each stream
            for url in urls:
                try:
                    # Get stream info (cached if available)
                    stream_info = self.screenshot.get_stream_info(url, resolution)
                    
                    # Capture screenshot
                    screenshot_path = self.screenshot.capture_screenshot(
                        stream_info,
                        output_path
                    )
                    
                    if screenshot_path:
                        logger.info(f"Screenshot saved to: {screenshot_path}")
                    else:
                        logger.error(f"Failed to capture screenshot from {url}")
                        
                except Exception as e:
                    logger.error(f"Error capturing screenshot from {url}: {e}")
                    continue  # Continue with next URL if one fails
                    
        except Exception as e:
            logger.error(f"Error in capture process: {e}")
    
    def run(self) -> None:
        """Run the application."""
        try:
            self.system_tray.run()
        except Exception as e:
            logger.error(f"Error running app: {e}")
            raise
        finally:
            self.quit()

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
