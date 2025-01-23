import json
import os
import logging
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'config.json')

DEFAULT_SETTINGS = {
    'youtube_urls': [],  # List of YouTube URLs to capture
    'output_path': 'screenshots',
    'interval': 60,  # seconds
    'resolution': '1080p',
    'location': {
        'latitude': 0,
        'longitude': 0,
        'name': ''
    },
    'schedule_enabled': False,
    'time_window': 30,  # minutes
    'only_sunsets': False,
    'only_sunrises': False
}

class Settings:
    def __init__(self, config_file: str = CONFIG_PATH):
        """Initialize settings manager."""
        self.config_file = config_file
        self._settings = self.load()

    def load(self) -> Dict[str, Any]:
        """Load settings from file or create with defaults."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    settings = json.load(f)
                
                # Convert interval if it's a string
                if 'interval' in settings and isinstance(settings['interval'], str):
                    # Map common interval strings to seconds
                    interval_map = {
                        '1 second': 1,
                        '2 seconds': 2,
                        '3 seconds': 3,
                        '4 seconds': 4,
                        '5 seconds': 5,
                        '10 seconds': 10,
                        '15 seconds': 15,
                        '30 seconds': 30,
                        '45 seconds': 45,
                        '1 minute': 60,
                        '1:15 minute': 75,
                        '1:30 minute': 90,
                        '1:45 minute': 105,
                        '2 minutes': 120,
                        '3 minutes': 180,
                        '4 minutes': 240,
                        '5 minutes': 300,
                        '6 minutes': 360,
                        '7 minutes': 420,
                        '8 minutes': 480,
                        '9 minutes': 540,
                        '10 minutes': 600,
                        '15 minutes': 900,
                        '30 minutes': 1800
                    }
                    settings['interval'] = interval_map.get(settings['interval'], DEFAULT_SETTINGS['interval'])
                
                # Handle legacy preferred_resolution setting
                if 'preferred_resolution' in settings:
                    settings['resolution'] = settings.pop('preferred_resolution')
                
                # Ensure all default settings exist
                for key, value in DEFAULT_SETTINGS.items():
                    if key not in settings:
                        settings[key] = value
                return settings
            except Exception as e:
                logger.error(f"Error loading settings: {e}")
                return DEFAULT_SETTINGS.copy()
        return DEFAULT_SETTINGS.copy()

    def save(self) -> None:
        """Save current settings to file."""
        try:
            # Convert any non-JSON-serializable values
            settings_to_save = {}
            for key, value in self._settings.items():
                if isinstance(value, (str, int, float, bool, list, dict)) or value is None:
                    settings_to_save[key] = value
                else:
                    # Convert other types to string representation
                    settings_to_save[key] = str(value)
            
            with open(self.config_file, 'w') as f:
                json.dump(settings_to_save, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving settings: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        value = self._settings.get(key, default)
        
        # Ensure numeric values for interval and time_window
        if key == 'interval' and not isinstance(value, int):
            try:
                value = int(value)
                self._settings[key] = value  # Update stored value
                self.save()
            except (ValueError, TypeError):
                logger.error(f"Invalid interval value: {value}, using default")
                value = DEFAULT_SETTINGS['interval']
        elif key == 'time_window' and not isinstance(value, int):
            try:
                value = int(value)
                self._settings[key] = value  # Update stored value
                self.save()
            except (ValueError, TypeError):
                logger.error(f"Invalid time window value: {value}, using default")
                value = DEFAULT_SETTINGS['time_window']
                
        return value

    def set(self, key: str, value: Any) -> None:
        """Set a setting value."""
        # Convert interval and time_window to integers
        if key == 'interval' and not isinstance(value, int):
            try:
                value = int(value)
            except (ValueError, TypeError):
                logger.error(f"Invalid interval value: {value}, using default")
                value = DEFAULT_SETTINGS['interval']
        elif key == 'time_window' and not isinstance(value, int):
            try:
                value = int(value)
            except (ValueError, TypeError):
                logger.error(f"Invalid time window value: {value}, using default")
                value = DEFAULT_SETTINGS['time_window']

        self._settings[key] = value
        self.save()

    def update(self, settings: Dict[str, Any]) -> None:
        """Update multiple settings at once."""
        # Convert any non-JSON-serializable values
        for key, value in settings.items():
            if isinstance(value, (str, int, float, bool, list, dict)) or value is None:
                self._settings[key] = value
            else:
                # Convert other types to string representation
                self._settings[key] = str(value)
        self.save()

    @property
    def all(self) -> Dict[str, Any]:
        """Get all settings."""
        return self._settings.copy()
