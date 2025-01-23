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
    # Use Asia/Singapore timezone for +8 offset
    return LocationInfo(
        name or f"{lat}, {lon}",
        "Region",
        "Asia/Singapore",  # Timezone for +8 offset
        lat,
        lon
    )

def get_sun_times(location: LocationInfo, date: Optional[datetime] = None) -> Dict[str, datetime]:
    """Get sunrise and sunset times for the location."""
    # Use local time for calculations
    local_tz = pytz.timezone('Asia/Singapore')
    date = date or datetime.now(local_tz)
    if date.tzinfo is None:
        date = local_tz.localize(date)
    
    try:
        s = sun(location.observer, date=date)
        # Convert times to local timezone
        return {
            'sunrise': s['sunrise'].astimezone(local_tz),
            'sunset': s['sunset'].astimezone(local_tz)
        }
    except Exception as e:
        logger.error(f"Error getting sun times: {e}")
        # Return default times in local timezone
        default_date = date.replace(hour=6, minute=0, second=0, microsecond=0)
        return {
            'sunrise': default_date,
            'sunset': default_date.replace(hour=18)
        }

def is_near_sunset_or_sunrise(location: LocationInfo, settings: Dict) -> Tuple[bool, str]:
    """Check if current time is near sunset or sunrise.
    
    Args:
        location: LocationInfo object containing location details
        settings: Settings object containing all program settings
    """
    time_window = settings.get('time_window', 30)
    only_sunsets = settings.get('only_sunsets', False)
    only_sunrises = settings.get('only_sunrises', False)

    # Validate settings - if both are True, treat as "both" mode
    if only_sunsets and only_sunrises:
        logger.warning("Both only_sunsets and only_sunrises are True - defaulting to checking both")
        only_sunsets = False
        only_sunrises = False
    
    local_tz = pytz.timezone('Asia/Singapore')
    now = datetime.now(local_tz)
    
    # Get today's sun times
    sun_times = get_sun_times(location)
    
    # Get tomorrow's sun times if we're near midnight
    tomorrow_sun_times = get_sun_times(location, now + timedelta(days=1))
    
    # Get yesterday's sun times if we're near midnight
    yesterday_sun_times = get_sun_times(location, now - timedelta(days=1))
    
    window = timedelta(minutes=time_window)
    logger.info("------------- Self-Checking Schedule: ------------")
    logger.info(f"Sunset:  {yesterday_sun_times['sunset'].strftime('%d.%m.%Y %H:%M:%S (%Z)')}")
    logger.info(f"Sunrise: {sun_times['sunrise'].strftime('%d.%m.%Y %H:%M:%S (%Z)')}")
    logger.info(f"Sunset:  {sun_times['sunset'].strftime('%d.%m.%Y %H:%M:%S (%Z)')}")
    logger.info(f"Sunrise: {tomorrow_sun_times['sunrise'].strftime('%d.%m.%Y %H:%M:%S (%Z)')}")
    logger.info(f"---------------- Current Settings: ----------------")
    logger.info(f"Capture interval: {settings.get('interval', 60)} seconds | Schedule enabled: {settings.get('schedule_enabled', False)}")
    logger.info(f"Time window:      {time_window} minutes | Resolution: {settings.get('resolution', '1080p')}")
    logger.info(f"Mode: {'Sunset only' if only_sunsets else 'Sunrise only' if only_sunrises else 'Sunrise & Sunset'}")
    
    # Check sunrise if in sunrise-only mode or both mode
    if only_sunrises or (not only_sunsets and not only_sunrises):
        sunrise_windows = [
            (sun_times['sunrise'], "today's sunrise"),
            (tomorrow_sun_times['sunrise'], "tomorrow's sunrise"),
        ]
        
        for sunrise_time, desc in sunrise_windows:
            sunrise_start = sunrise_time - window
            sunrise_end = sunrise_time + window
            logger.debug(f"Checking {desc} window: {sunrise_start.strftime('%H:%M:%S')} to {sunrise_end.strftime('%H:%M:%S')}")
            
            if sunrise_start <= now <= sunrise_end:
                logger.info(f"Within {desc} window")
                return True, "sunrise"
    
    # Check sunset if in sunset-only mode or both mode
    if only_sunsets or (not only_sunsets and not only_sunrises):
        sunset_windows = [
            (yesterday_sun_times['sunset'], "yesterday's sunset"),
            (sun_times['sunset'], "today's sunset"),
        ]
        
        for sunset_time, desc in sunset_windows:
            sunset_start = sunset_time - window
            sunset_end = sunset_time + window
            logger.debug(f"Checking {desc} window: {sunset_start.strftime('%H:%M:%S')} to {sunset_end.strftime('%H:%M:%S')}")
            
            if sunset_start <= now <= sunset_end:
                logger.info(f"Within {desc} window")
                return True, "sunset"
    
    logger.debug("Not within any capture windows")
    return False, ""
