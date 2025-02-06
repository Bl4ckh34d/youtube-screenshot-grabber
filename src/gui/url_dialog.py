import logging
import customtkinter as ctk
import threading
import yt_dlp
from typing import Optional, Dict, Any, Callable, List

logger = logging.getLogger(__name__)

class URLDialog:
    def __init__(self, parent: Optional[ctk.CTk] = None, settings: Dict[str, Any] = None,
                 on_save: Optional[Callable[[List[str], List[str]], None]] = None):
        """Initialize URL dialog."""
        self.window = ctk.CTkToplevel(parent) if parent else ctk.CTk()
        self.window.title("Set YouTube URLs")
        self.window.geometry("600x300")  # Made taller for status messages
        try:
            self.window.grab_set()  # Make dialog modal
        except TclError as e:
            logger.warning(f"grab_set failed (another window may have the grab). Ignoring. {e}")
        
        self.settings = settings or {}
        self.on_save = on_save
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True
        }
        
        self._setup_ui()
        
    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        # Create main frame
        main_frame = ctk.CTkFrame(self.window)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # URL input
        url_label = ctk.CTkLabel(main_frame, text="YouTube URLs (one per line):")
        url_label.pack(pady=5)
        
        self.url_entry = ctk.CTkTextbox(main_frame, width=400, height=100)
        self.url_entry.pack(pady=5)
        # Insert any existing URLs
        if self.settings.get('youtube_urls'):
            self.url_entry.insert('1.0', '\n'.join(self.settings.get('youtube_urls', [])))
        
        # Status message
        self.status_label = ctk.CTkLabel(main_frame, text="", text_color="gray")
        self.status_label.pack(pady=5)
        
        # Create buttons frame
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.pack(fill="x", pady=10)
        
        # Save button
        self.save_button = ctk.CTkButton(button_frame, text="Save", command=self._on_save)
        self.save_button.pack(side="right", padx=5)
        
        # Cancel button
        cancel_button = ctk.CTkButton(button_frame, text="Cancel", command=self.window.destroy)
        cancel_button.pack(side="right", padx=5)
    
    def _is_valid_youtube_url(self, url: str) -> bool:
        """Check if the URL is a valid YouTube URL."""
        youtube_domains = ['youtube.com', 'youtu.be', 'www.youtube.com']
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return any(domain in parsed.netloc for domain in youtube_domains)
        except:
            return False
            
    def _on_save(self) -> None:
        """Handle save button click."""
        urls_text = self.url_entry.get('1.0', 'end-1c').strip()
        if not urls_text:
            logger.error("No URLs entered")
            self.status_label.configure(text="No URLs entered", text_color="red")
            self.window.bell()
            return

        # Get all URLs first
        urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
        
        if self.on_save:
            # Pass all URLs for validation, close dialog immediately
            self.on_save(urls, [])  # Pass empty list as valid URLs initially
            self.window.destroy()
            
    def run(self) -> None:
        """Run the dialog."""
        self.window.mainloop()
