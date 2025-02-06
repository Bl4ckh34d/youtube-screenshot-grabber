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
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize scheduler."""
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable] = None
        self._settings = settings if settings is not None else Settings()
        self._interval = self._settings.get('interval', 60)  # seconds
        self._location: Optional[LocationInfo] = None
        self._time_window = self._settings.get('time_window', 30)  # minutes
        self._only_sunsets = self._settings.get('only_sunsets', False)
        self._only_sunrises = self._settings.get('only_sunrises', False)
        self._schedule_enabled = self._settings.get('schedule_enabled', False)

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
            self._settings.set('interval', kwargs['interval'])
        if 'location' in kwargs:
            self._location = kwargs['location']
        if 'time_window' in kwargs:
            self._time_window = kwargs['time_window']
            self._settings.set('time_window', kwargs['time_window'])
        if 'only_sunsets' in kwargs:
            self._only_sunsets = kwargs['only_sunsets']
            self._settings.set('only_sunsets', kwargs['only_sunsets'])
        if 'only_sunrises' in kwargs:
            self._only_sunrises = kwargs['only_sunrises']
            self._settings.set('only_sunrises', kwargs['only_sunrises'])
        if 'schedule_enabled' in kwargs:
            self._schedule_enabled = kwargs['schedule_enabled']
            self._settings.set('schedule_enabled', kwargs['schedule_enabled'])
        logger.info("Scheduler settings updated")

    def _should_capture(self) -> bool:
        """Determine if a capture should be made now."""
        if self._paused:
            logger.debug("Scheduler is paused, not capturing")
            return False
            
        if not self._schedule_enabled:
            logger.debug("Schedule disabled, capturing")
            return True  # If scheduling is disabled, always capture
            
        if not self._location:
            logger.warning("No location set but schedule enabled - defaulting to always capture")
            return True  # If no location set, always capture
            
        should_capture, event = is_near_sunset_or_sunrise(
            self._location,
            self._settings
        )
        
        if should_capture:
            logger.info(f"Capture triggered by {event}")
        else:
            logger.debug("Not in capture window")
        
        return should_capture

    def _run(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                self._manage_processes()
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")

            # Now sleep for the interval
            for _ in range(self._interval):
                if not self._running:
                    break
                time.sleep(1)
        
        logger.info("Scheduler thread exiting")

    def _manage_processes(self) -> None:
        """
        Decide whether to start or kill processes based on scheduling, 
        pause state, and the capture window.
        """
        # 1. If paused, do nothing. (Alternatively, you could kill processes if you prefer.)
        if self._paused:
            logger.debug("Scheduler is paused, not starting or killing processes.")
            return

        # 2. If scheduling is enabled, check if we're near sunrise or sunset.
        if self._schedule_enabled:
            if self._location is None:
                # No location => we can't check sunrise/sunset times. 
                # Decide how you want to handle this. Let's default to "always kill" or "always run."
                logger.warning("Scheduling is enabled but no location set. Defaulting to always run processes.")
                self._start_processes_for_all_urls()
                return
            
            # Check if we're near sunrise/sunset
            in_window, _ = self._is_in_time_window()
            if in_window:
                logger.debug("We are in the capture window (sunrise/sunset). Ensuring processes run.")
                self._start_processes_for_all_urls()
            else:
                logger.debug("Outside capture window. Killing processes.")
                self._app.stream_manager.stop_all()  # Must have a reference to `App` or pass it in
        else:
            # 3. Scheduling is disabled => always ensure processes run
            logger.debug("Scheduling disabled. Ensuring processes run.")
            self._start_processes_for_all_urls()

    def _is_in_time_window(self) -> (bool, str):
        """
        Returns a tuple (is_in_window, event_type)
        where event_type is 'sunrise'/'sunset' or ''.
        """
        from .location import is_near_sunset_or_sunrise
        return is_near_sunset_or_sunrise(self._location, self._settings.all)

    def _start_processes_for_all_urls(self):
        """
        A convenience method to call the main app’s capture_screenshot,
        which handles adding streams for new URLs, etc.
        """
        try:
            self._app.capture_screenshot()
        except Exception as e:
            logger.error(f"Error starting processes: {e}")

    

