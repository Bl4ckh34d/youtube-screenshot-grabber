import subprocess
import json
import logging
from typing import Dict, Optional, Tuple
from astral import LocationInfo
from astral.sun import sun
from datetime import datetime, timedelta
import pytz
import requests

logger = logging.getLogger(__name__)

def get_windows_location() -> Optional[Dict[str, float]]:
    """Get the user's location from various sources."""
    # Try Windows location API first
    try:
        cmd = [
            'powershell',
            '-NoProfile',
            '-Command',
            # Set output encoding to ASCII and use Write-Output instead of Write-Host
            '[Console]::OutputEncoding = [System.Text.Encoding]::ASCII; ' +
            '$loc = Get-CimInstance -Namespace "root/standard/microsoft/windows/geolocation" -ClassName location; ' +
            'Write-Output "$($loc.Latitude),$($loc.Longitude)"'
        ]
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True,
            encoding='ascii',  # Use ASCII encoding
            errors='ignore',   # Ignore any non-ASCII characters
            check=True
        )
        output = result.stdout.strip()
        if ',' in output:
            lat, lon = map(float, output.split(','))
            logger.info(f"Got location from Windows: {lat}, {lon}")
            return {'latitude': lat, 'longitude': lon}
    except Exception as e:
        logger.debug(f"Could not get Windows location: {e}")

    # Try IP geolocation as fallback
    try:
        # Try ipapi.co first
        response = requests.get('https://ipapi.co/json/', timeout=5)
        data = response.json()
        
        if 'latitude' in data and 'longitude' in data:
            lat = float(data['latitude'])
            lon = float(data['longitude'])
            logger.info(f"Got location from ipapi.co: {lat}, {lon}")
            return {'latitude': lat, 'longitude': lon}
        
        # If ipapi.co fails, try ip-api.com as backup
        response = requests.get('http://ip-api.com/json/', timeout=5)
        data = response.json()
        
        if data.get('status') == 'success':
            lat = float(data['lat'])
            lon = float(data['lon'])
            logger.info(f"Got location from ip-api.com: {lat}, {lon}")
            return {'latitude': lat, 'longitude': lon}
            
    except Exception as e:
        logger.debug(f"Could not get location from IP services: {e}")

    # Default to a neutral location if all methods fail
    logger.info("Using default location (UTC+0)")
    return {'latitude': 0, 'longitude': 0}

def get_location_info(lat: float, lon: float, name: str = "") -> LocationInfo:
    """Create LocationInfo object from coordinates."""
    return LocationInfo(
        name or f"{lat}, {lon}",
        "Region",
        "Etc/GMT",  # We'll calculate the actual timezone offset
        lat,
        lon
    )

def get_sun_times(location: LocationInfo, date: Optional[datetime] = None) -> Dict[str, datetime]:
    """Get sunrise and sunset times for the location."""
    date = date or datetime.now(pytz.UTC)
    if date.tzinfo is None:
        date = pytz.UTC.localize(date)
    try:
        s = sun(location.observer, date=date)
        return {
            'sunrise': s['sunrise'],
            'sunset': s['sunset']
        }
    except Exception as e:
        logger.error(f"Error getting sun times: {e}")
        # Return default times in UTC
        default_date = date.replace(hour=6, minute=0, second=0, microsecond=0)
        return {
            'sunrise': default_date,
            'sunset': default_date.replace(hour=18)
        }

def is_near_sunset_or_sunrise(location: LocationInfo, 
                            time_window: int = 30,
                            only_sunsets: bool = False) -> Tuple[bool, str]:
    """Check if current time is near sunset or sunrise."""
    now = datetime.now(pytz.UTC)
    sun_times = get_sun_times(location)
    window = timedelta(minutes=time_window)
    
    # Check sunset
    sunset_start = sun_times['sunset'] - window
    sunset_end = sun_times['sunset'] + window
    if sunset_start <= now <= sunset_end:
        return True, "sunset"
    
    # Check sunrise if not only looking for sunsets
    if not only_sunsets:
        sunrise_start = sun_times['sunrise'] - window
        sunrise_end = sun_times['sunrise'] + window
        if sunrise_start <= now <= sunrise_end:
            return True, "sunrise"
    
    return False, ""
