import logging
import customtkinter as ctk
from typing import Optional, Dict, Any, Callable

logger = logging.getLogger(__name__)

class URLDialog:
    def __init__(self, parent: Optional[ctk.CTk] = None, settings: Dict[str, Any] = None,
                 on_save: Optional[Callable[[str], None]] = None):
        """Initialize URL dialog."""
        self.window = ctk.CTkToplevel(parent) if parent else ctk.CTk()
        self.window.title("Set YouTube URL")
        self.window.geometry("600x150")
        self.window.grab_set()  # Make dialog modal
        
        self.settings = settings or {}
        self.on_save = on_save
        
        self._setup_ui()
        
    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        # Create main frame
        main_frame = ctk.CTkFrame(self.window)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # URL input
        url_label = ctk.CTkLabel(main_frame, text="YouTube URL:")
        url_label.pack(pady=5)
        
        self.url_entry = ctk.CTkEntry(main_frame, width=400)
        self.url_entry.pack(pady=5)
        self.url_entry.insert(0, self.settings.get('youtube_url', ''))
        
        # Create buttons frame
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.pack(fill="x", pady=10)
        
        # Save button
        save_button = ctk.CTkButton(button_frame, text="Save", command=self._on_save)
        save_button.pack(side="right", padx=5)
        
        # Cancel button
        cancel_button = ctk.CTkButton(button_frame, text="Cancel", command=self.window.destroy)
        cancel_button.pack(side="right", padx=5)
    
    def _on_save(self) -> None:
        """Handle save button click."""
        url = self.url_entry.get().strip()
        if url:
            if self.on_save:
                self.on_save(url)
            self.window.destroy()
        else:
            logger.error("No URL entered")
            self.window.bell()
            
    def run(self) -> None:
        """Run the dialog."""
        self.window.mainloop()
