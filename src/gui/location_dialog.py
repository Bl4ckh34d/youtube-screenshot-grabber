import logging
import customtkinter as ctk
import tkintermapview
from typing import Optional, Dict, Any, Callable

logger = logging.getLogger(__name__)

class LocationDialog:
    def __init__(self, parent: Optional[ctk.CTk] = None, settings: Dict[str, Any] = None,
                 on_save: Optional[Callable[[Dict[str, float]], None]] = None):
        """Initialize location dialog."""
        self.window = ctk.CTkToplevel(parent) if parent else ctk.CTk()
        self.window.title("Set Location")
        self.window.geometry("800x600")
        self.window.grab_set()  # Make dialog modal
        
        self.settings = settings or {}
        self.on_save = on_save
        self.map_widget = None
        
        self._setup_ui()
        
    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        # Create main frame
        main_frame = ctk.CTkFrame(self.window)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Create input frame for coordinates
        input_frame = ctk.CTkFrame(main_frame)
        input_frame.pack(fill="x", padx=5, pady=5)
        
        # Latitude input
        lat_label = ctk.CTkLabel(input_frame, text="Latitude:")
        lat_label.pack(side="left", padx=5)
        self.lat_entry = ctk.CTkEntry(input_frame)
        self.lat_entry.pack(side="left", padx=5)
        self.lat_entry.insert(0, str(self.settings.get('location', {}).get('latitude', '')))
        
        # Longitude input
        lon_label = ctk.CTkLabel(input_frame, text="Longitude:")
        lon_label.pack(side="left", padx=5)
        self.lon_entry = ctk.CTkEntry(input_frame)
        self.lon_entry.pack(side="left", padx=5)
        self.lon_entry.insert(0, str(self.settings.get('location', {}).get('longitude', '')))
        
        # Create map frame
        logger.info("Creating map frame...")
        map_frame = ctk.CTkFrame(main_frame)
        map_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Create map widget
        logger.info("Initializing map widget...")
        try:
            self.map_widget = tkintermapview.TkinterMapView(
                map_frame,
                width=800,
                height=400,
                corner_radius=0
            )
            logger.info("Map widget created successfully")
            self.map_widget.pack(fill="both", expand=True)
            
            # Configure tile server
            logger.info("Setting tile server...")
            try:
                # Try OpenStreetMap first as it's more reliable
                self.map_widget.set_tile_server("https://tile.openstreetmap.org/{z}/{x}/{y}.png", max_zoom=19)
                logger.info("OpenStreetMap tile server configured")
            except Exception as e:
                logger.error(f"Failed to set OpenStreetMap tile server, trying Google Maps: {e}")
                try:
                    self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=19)
                    logger.info("Google Maps tile server configured")
                except Exception as e:
                    logger.error(f"Failed to set Google Maps tile server: {e}")
                    raise
            
            # Set initial position
            try:
                lat = float(self.lat_entry.get() or 0)
                lon = float(self.lon_entry.get() or 0)
                if lat != 0 or lon != 0:
                    logger.info(f"Setting map position to {lat}, {lon}")
                    self.map_widget.set_position(lat, lon)
                    self.map_widget.set_zoom(12)
                    self.map_widget.set_marker(lat, lon)
                    logger.info("Map position and marker set")
                else:
                    logger.info("No location set, using default position")
                    self.map_widget.set_position(0, 0)
                    self.map_widget.set_zoom(2)
                    logger.info("Default position set")
            except Exception as e:
                logger.error(f"Error setting map position: {e}")
                
            # Add click handler
            logger.info("Adding map click handler...")
            self.map_widget.add_left_click_map_command(self._on_map_click)
            logger.info("Map click handler added")
            
        except Exception as e:
            logger.error(f"Error creating map widget: {e}")
            # Create error label
            error_label = ctk.CTkLabel(
                map_frame,
                text="Map loading failed.\nYou can still set coordinates using the fields above.",
                font=("Arial", 14)
            )
            error_label.pack(expand=True)
        
        # Create buttons frame
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.pack(fill="x", pady=10)
        
        # Save button
        save_button = ctk.CTkButton(button_frame, text="Save", command=self._on_save)
        save_button.pack(side="right", padx=5)
        
        # Cancel button
        cancel_button = ctk.CTkButton(button_frame, text="Cancel", command=self.window.destroy)
        cancel_button.pack(side="right", padx=5)
    
    def _on_map_click(self, coords) -> None:
        """Handle map click event."""
        try:
            lat, lon = coords
            self.lat_entry.delete(0, 'end')
            self.lat_entry.insert(0, str(lat))
            self.lon_entry.delete(0, 'end')
            self.lon_entry.insert(0, str(lon))
            
            # Update marker
            if self.map_widget:
                self.map_widget.delete_all_marker()
                self.map_widget.set_marker(lat, lon)
        except Exception as e:
            logger.error(f"Error handling map click: {e}")
    
    def _on_save(self) -> None:
        """Handle save button click."""
        try:
            lat = float(self.lat_entry.get())
            lon = float(self.lon_entry.get())
            if self.on_save:
                self.on_save({'latitude': lat, 'longitude': lon})
            self.window.destroy()
        except ValueError:
            logger.error("Invalid coordinates entered")
            # Show error message to user
            self.window.bell()
            
    def run(self) -> None:
        """Run the dialog."""
        self.window.mainloop()
