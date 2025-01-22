import os
import cv2
import yt_dlp
import logging
import subprocess
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any
import concurrent.futures

# Get module logger
logger = logging.getLogger(__name__)

class StreamInfoCache:
    """Cache for stream information to reduce API calls."""
    def __init__(self, cache_duration: int = 10800):  # 3 hours in seconds
        self._cache = {}
        self._cache_duration = timedelta(seconds=cache_duration)

    def get(self, url: str) -> Optional[Dict[str, Any]]:
        """Get cached stream info if not expired."""
        if url in self._cache:
            info, timestamp = self._cache[url]
            if datetime.now() - timestamp < self._cache_duration:
                return info
            del self._cache[url]
        return None

    def set(self, url: str, info: Dict[str, Any]) -> None:
        """Cache stream information."""
        self._cache[url] = (info, datetime.now())

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()

class ScreenshotCapture:
    def __init__(self):
        """Initialize screenshot capture with caching."""
        self.stream_cache = StreamInfoCache()
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True
        }
        self._prefetch_thread = None

    def get_stream_info(self, url: str, preferred_resolution: str = '1080p') -> Dict[str, Any]:
        """Get stream information, using cache if available."""
        # Check cache first
        cached_info = self.stream_cache.get(url)
        if cached_info:
            logger.info("Using cached stream info")
            return cached_info

        # Get fresh info
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                formats = info.get('formats', [])
                best_format = self._get_best_matching_format(formats, preferred_resolution)
                
                result = {
                    'url': best_format['url'],
                    'resolution': f"{best_format.get('height', 0)}p",
                    'title': info.get('title', 'Untitled'),
                    'format_id': best_format['format_id']
                }
                
                # Cache the result
                self.stream_cache.set(url, result)
                return result
        except Exception as e:
            logger.error(f"Error getting stream info: {e}")
            raise

    def _get_best_matching_format(self, formats: list, preferred: str) -> Dict[str, Any]:
        """Find the best matching format for the preferred resolution."""
        target_height = int(preferred.rstrip('p'))
        formats = [f for f in formats if f.get('height')]
        
        if not formats:
            raise ValueError("No valid formats found")
            
        # Sort by height and prefer formats closer to target
        formats.sort(key=lambda x: abs(x['height'] - target_height))
        return formats[0]

    def capture_screenshot(self, stream_info: Dict[str, Any], output_path: str) -> Optional[str]:
        """Capture a screenshot from the stream."""
        try:
            # Create stream-specific subdirectory using cleaned title
            stream_dir = self._clean_filename(stream_info['title'])
            stream_path = os.path.join(output_path, stream_dir)
            os.makedirs(stream_path, exist_ok=True)
            
            # Generate output filename
            now = datetime.now()
            timestamp = now.strftime('%Y-%m-%d_%H-%M-%S')
            filename = f"{timestamp}.jpg"
            full_path = os.path.join(stream_path, filename)
            
            # Use ffmpeg to capture frame
            cmd = [
                'ffmpeg',
                '-y',  # Overwrite output file
                '-i', stream_info['url'],
                '-vframes', '1',  # Capture one frame
                '-q:v', '2',  # High quality
                full_path
            ]
            
            # Use CREATE_NO_WINDOW flag
            startupinfo = None
            if os.name == 'nt':  # Windows
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            subprocess.run(cmd, 
                         capture_output=True, 
                         check=True,
                         startupinfo=startupinfo,
                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            
            logger.info(f"Screenshot saved to: {full_path}")
            return full_path
            
        except Exception as e:
            logger.error(f"Error capturing screenshot: {e}")
            return None

    def _clean_filename(self, filename: str) -> str:
        """Clean a string to be used as a filename."""
        # Replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Remove any non-ASCII characters
        filename = ''.join(char for char in filename if ord(char) < 128)
        
        # Limit filename length (Windows max path is 260, leave room for path)
        name, ext = os.path.splitext(filename)
        if len(filename) > 200:  # Leave room for path
            name = name[:196]  # Leave room for extension
            filename = name + ext
        
        return filename.strip()

    def prefetch_stream_info(self, urls: list[str], preferred_resolution: str = '1080p') -> None:
        """Prefetch stream information for multiple URLs in parallel."""
        def _fetch_single_url(url: str):
            try:
                if not self.stream_cache.get(url):  # Only fetch if not in cache
                    logger.debug(f"Cache miss for {url}, fetching stream info")
                    info = self.get_stream_info(url, preferred_resolution)
                    logger.debug(f"Successfully prefetched stream info for {url} (Resolution: {info.get('resolution', 'unknown')})")
                else:
                    logger.debug(f"Using cached info for {url}")
            except Exception as e:
                logger.error(f"Error prefetching stream info for {url}: {e}")

        # For single URLs, process directly without thread overhead
        if len(urls) == 1:
            logger.debug(f"Processing single URL without thread overhead: {urls[0]}")
            _fetch_single_url(urls[0])
            return

        # Cancel any existing prefetch for multiple URLs
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            logger.debug("Cancelling existing prefetch thread")
            self._prefetch_thread = None

        def _prefetch():
            logger.debug(f"Starting parallel stream info prefetch for {len(urls)} URLs")
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(urls), 50)) as executor:
                logger.debug(f"Created thread pool with {min(len(urls), 50)} workers")
                executor.map(_fetch_single_url, urls)
            logger.debug("Stream info prefetch completed")

        # Start new prefetch thread for multiple URLs
        self._prefetch_thread = threading.Thread(target=_prefetch, daemon=True)
        self._prefetch_thread.start()
        logger.debug("Started prefetch thread")
