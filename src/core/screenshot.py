import os
import cv2
import yt_dlp
import logging
import subprocess
import threading
import multiprocessing as mp
from queue import Empty
from time import sleep, time
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
            return cached_info

        # Get fresh info
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                logger.info(f"Fetching fresh info from YouTube for {url}")
                info = ydl.extract_info(url, download=False)
                formats = info.get('formats', [])
                best_format = self._get_best_matching_format(formats, preferred_resolution)
                
                # Get raw title and remove date/time part
                raw_title = info.get('title', 'Untitled')
                logger.debug(f"Raw YouTube title: {raw_title}")
                if ' 2025-' in raw_title:
                    raw_title = raw_title.split(' 2025-')[0].strip()
                    logger.debug(f"Cleaned YouTube title: {raw_title}")
                
                result = {
                    'url': best_format['url'],
                    'resolution': f"{best_format.get('height', 0)}p",
                    'preferred_resolution': preferred_resolution,
                    'title': raw_title,
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
        selected_format = formats[0]

        return selected_format

    def capture_screenshot(self, stream_info: Dict[str, Any], output_path: str) -> Optional[str]:
        """Capture a screenshot from the stream."""
        try:
            # Generate output filename with timestamp
            now = datetime.now()
            timestamp = now.strftime('%Y-%m-%d_%H-%M-%S')
            
            # Clean the title once, use it for both folder and file
            clean_title = self._clean_filename(stream_info['title'])
            logger.info(f"Title from stream_info: {stream_info['title']}")
            logger.info(f"Clean title for folder: {clean_title}")
            
            # Create stream-specific subdirectory using just the clean title
            stream_path = os.path.join(output_path, clean_title)
            logger.debug(f"Creating folder: {stream_path}")
            os.makedirs(stream_path, exist_ok=True)
            
            # Use timestamp only for the file
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

            # Run ffmpeg and capture error output
            process = subprocess.run(
                cmd,
                startupinfo=startupinfo,
                capture_output=True,
                text=True
            )
            
            if process.returncode != 0:
                logger.error(f"ffmpeg error output: {process.stderr}")
                raise Exception(f"ffmpeg failed: {process.stderr}")

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

class StreamProcess:
    def __init__(self, url: str, output_path: str, interval: int, resolution: str = '1080p'):
        self.url = url
        self.output_path = output_path
        self.interval = interval
        self.resolution = resolution
        self.process = None
        self.stop_event = None
        self.screenshot_capture = ScreenshotCapture()
        # Create a pause event that is shared with the child process.
        self.pause_event = mp.Event()
        self.pause_event.set()  # Initially running (not paused)

    def pause(self):
        # Clear the event: any call to wait() in the child will now block.
        self.pause_event.clear()

    def resume(self):
        # Set the event: any blocked wait() calls will return immediately.
        self.pause_event.set()

    def _capture_loop(self, stop_event: mp.Event):
        """Continuous capture loop running in its own process."""
        logger.info(f"Starting capture loop for {self.url}")
        try:
            # Get initial stream info
            stream_info = self.screenshot_capture.get_stream_info(self.url, self.resolution)
            logger.info(f"Got stream info for {self.url}")

            while not stop_event.is_set():
                # Wait here until the process is resumed. If the pause event is cleared,
                # this will block until resume() is called.
                self.pause_event.wait()

                start_time = time()
                try:
                    # Take screenshot directly in this process.
                    screenshot_path = self.screenshot_capture.capture_screenshot(stream_info, self.output_path)
                    if screenshot_path:
                        logger.info(f"Screenshot saved: {screenshot_path}")
                except Exception as e:
                    logger.error(f"Error taking screenshot for {self.url}: {e}")

                # Calculate sleep time for the next capture
                elapsed = time() - start_time
                sleep_time = max(0, self.interval - elapsed)
                logger.debug(f"Capture took {elapsed:.2f}s, sleeping for {sleep_time:.2f}s")

                # Sleep in small increments so the process can respond quickly to a pause command.
                # Alternatively, you can simply call sleep(sleep_time) if quick responsiveness isn’t critical.
                sleep(sleep_time)

        except Exception as e:
            logger.error(f"Error in capture loop for {self.url}: {e}")

    def start(self):
        """Start the stream capture process."""
        self.stop_event = mp.Event()
        self.process = mp.Process(
            target=self._capture_loop,
            args=(self.stop_event,),
            daemon=False
        )
        self.process.start()
        logger.info(f"Started capture process for {self.url}")

    def stop(self):
        if self.stop_event:
            self.stop_event.set()
        if self.process:
            self.process.join(timeout=1)
            if self.process.is_alive():
                self.process.terminate()
            self.process = None
        logger.info(f"Stopped capture process for {self.url}")

class StreamManager:
    """Manages multiple stream capture processes."""
    def __init__(self):
        self.streams: Dict[str, StreamProcess] = {}

    def add_stream(self, url: str, output_path: str, interval: int,
               resolution: str = '1080p', paused: bool = False):
        """Add and start a new stream capture process."""
        if url in self.streams:
            self.remove_stream(url)
        
        stream_process = StreamProcess(url, output_path, interval, resolution)
        self.streams[url] = stream_process
        
        # Start the process
        stream_process.start()
        
        # If we are paused, immediately pause the new process.
        if paused:
            stream_process.pause()

    def remove_stream(self, url: str):
        """Stop and remove a stream capture process."""
        if url in self.streams:
            self.streams[url].stop()  # calls StreamProcess.stop()
            del self.streams[url]

    def update_interval(self, interval: int):
        """Update interval for all streams."""
        urls = list(self.streams.keys())
        for url in urls:
            stream = self.streams[url]
            output_path = stream.output_path
            resolution = stream.resolution
            self.remove_stream(url)
            self.add_stream(url, output_path, interval, resolution)

    def stop_all(self):
        """Stop all stream capture processes in parallel."""
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Start stopping all streams in parallel
            futures = [
                executor.submit(self.remove_stream, url)
                for url in list(self.streams.keys())
            ]
            # Wait for all to complete
            concurrent.futures.wait(futures)
