import logging
import threading
import time
from datetime import datetime
from typing import Optional, Callable
from astral import LocationInfo

from .location import is_near_sunset_or_sunrise
from .settings import Settings

logger = logging.getLogger(__name__)

class Scheduler:
    def __init__(self):
        """Initialize scheduler."""
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable] = None
        self._settings = Settings()
        self._interval = self._settings._settings.get('interval', 60)  # seconds
        self._location: Optional[LocationInfo] = None
        self._time_window = 30  # minutes
        self._only_sunsets = False
        self._only_sunrises = False
        self._schedule_enabled = False

    def start(self, callback: Callable,
             interval: Optional[int] = None,
             location: Optional[LocationInfo] = None,
             time_window: int = 30,
             only_sunsets: bool = False,
             only_sunrises: bool = False,
             schedule_enabled: bool = False) -> None:
        """Start the scheduler with given parameters."""
        self._callback = callback
        if interval is not None:  # Allow interval override but default to settings
            self._interval = interval
        self._location = location
        self._time_window = time_window
        self._only_sunsets = only_sunsets
        self._only_sunrises = only_sunrises
        self._schedule_enabled = schedule_enabled
        
        logger.info(f"Starting scheduler with: schedule_enabled={schedule_enabled}, " +
                   f"location={'set' if location else 'not set'}, " +
                   f"time_window={time_window}min, only_sunsets={only_sunsets}, " +
                   f"only_sunrises={only_sunrises}, " +
                   f"check_interval={self._interval}s")
        
        if not self._thread or not self._thread.is_alive():
            self._running = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            logger.info("Scheduler thread started")
            logger.info("Scheduler started")

    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None
        logger.info("Scheduler stopped")

    def pause(self) -> None:
        """Pause the scheduler."""
        self._paused = True
        logger.info("Scheduler paused")

    def resume(self) -> None:
        """Resume the scheduler."""
        self._paused = False
        logger.info("Scheduler resumed")

    def update_settings(self, **kwargs) -> None:
        """Update scheduler settings."""
        if 'interval' in kwargs:
            self._interval = kwargs['interval']
        if 'location' in kwargs:
            self._location = kwargs['location']
        if 'time_window' in kwargs:
            self._time_window = kwargs['time_window']
        if 'only_sunsets' in kwargs:
            self._only_sunsets = kwargs['only_sunsets']
        if 'only_sunrises' in kwargs:
            self._only_sunrises = kwargs['only_sunrises']
        if 'schedule_enabled' in kwargs:
            self._schedule_enabled = kwargs['schedule_enabled']
        logger.info("Scheduler settings updated")

    def _should_capture(self) -> bool:
        """Determine if a capture should be made now."""
        if not self._schedule_enabled:
            logger.debug("Schedule disabled, capturing")
            return True  # If scheduling is disabled, always capture
            
        if not self._location:
            logger.warning("No location set but schedule enabled - defaulting to always capture")
            return True  # If no location set, always capture
            
        should_capture, event = is_near_sunset_or_sunrise(
            self._location,
            self._time_window,
            self._only_sunsets,
            self._only_sunrises
        )
        
        if should_capture:
            logger.info(f"Capture triggered by {event}")
        else:
            logger.debug("Not in capture window")
        
        return should_capture

    def _run(self) -> None:
        """Main scheduler loop."""
        while self._running:
            if not self._paused and self._callback and self._should_capture():
                try:
                    self._callback()
                except Exception as e:
                    logger.error(f"Error in scheduler callback: {e}")
            
            # Sleep for the interval
            for _ in range(self._interval):
                if not self._running:
                    break
                time.sleep(1)
