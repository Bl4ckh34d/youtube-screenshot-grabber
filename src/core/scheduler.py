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
        self._was_in_window = False  # track previous state
        self._current_event_type = ""  # track which event we are capturing

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
        """Decide whether to start or kill processes based on scheduling, pause state, etc."""
        if self._paused:
            logger.debug("Scheduler is paused, not starting or killing processes.")
            return

        if self._schedule_enabled:
            if not self._location:
                logger.warning("Scheduling is enabled but no location set. Defaulting to always run processes.")
                self._start_processes_for_all_urls("", force=True)  # no event type
                self._was_in_window = True
                return
            
            in_window, event_type = self._is_in_time_window()
            if in_window:
                logger.debug(f"In capture window for {event_type}. Ensuring processes run.")
                self._start_processes_for_all_urls(event_type)
                self._was_in_window = True
                self._current_event_type = event_type
            else:
                logger.debug("Outside capture window.")
                
                # If we WERE in the window but now are NOT => time to kill processes + convert
                if self._was_in_window:
                    logger.debug("We just left the capture window. Stopping processes + auto-convert.")
                    self._app.stream_manager.stop_all()
                    
                    # Now do automatic clip conversion
                    self._app.convert_subfolders_to_clips_and_cleanup(
                        self._current_event_type
                    )

                    # If "shutdown_when_done" is True, call quit method
                    if self._app.settings.get('shutdown_when_done', False):
                        logger.info("Shutting down (shutdown_when_done is enabled).")
                        self._app.quit()
                    
                self._was_in_window = False
                self._current_event_type = ""
        else:
            # scheduling disabled => always run
            logger.debug("Scheduling disabled. Ensuring processes run.")
            self._start_processes_for_all_urls("", force=True)
            self._was_in_window = True

    def _is_in_time_window(self) -> (bool, str):
        """
        Returns a tuple (is_in_window, event_type)
        where event_type is 'sunrise'/'sunset' or ''.
        """
        from .location import is_near_sunset_or_sunrise
        return is_near_sunset_or_sunrise(self._location, self._settings.all)

    def _start_processes_for_all_urls(self, event_type: str, force: bool = False):
        """
        A convenience method to call the main app’s capture_screenshot,
        optionally passing which event type ("sunrise" or "sunset").
        If 'force' is True, we do it even if we're not in a window.
        """
        try:
            self._app.capture_screenshot(event_type=event_type)
        except Exception as e:
            logger.error(f"Error starting processes: {e}")
