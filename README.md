# YouTube Screenshot Grabber

A Python application that captures screenshots from YouTube livestreams at regular intervals or during sunset/sunrise times.

## Features

- Capture screenshots from YouTube livestreams at configurable intervals
- Schedule captures around sunset and sunrise times
- System tray interface for easy control
- Support for multiple video resolutions
- Configurable output directory
- Location-based sunset/sunrise scheduling
- Pause/resume functionality

For a detailed list of changes and updates, please see our [Changelog](CHANGELOG.md).

## Project Structure

```
youtube-screenshot-grabber/
├── src/
│   ├── __init__.py
│   ├── main.py              # Main entry point
│   ├── gui/                 # GUI components
│   │   ├── location_dialog.py
│   │   ├── url_dialog.py
│   │   └── system_tray.py
│   ├── core/               # Core functionality
│   │   ├── settings.py
│   │   ├── screenshot.py
│   │   ├── scheduler.py
│   │   └── location.py
│   └── utils/              # Utility functions
│       ├── logging_config.py
│       └── file_utils.py
└── tests/                  # Test directory
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Bl4ckh34d/youtube-screenshot-grabber.git
cd youtube-screenshot-grabber
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Run the application:
```bash
python -m src.main
```

2. The application will appear in your system tray

3. Right-click the tray icon to:
   - Set YouTube URL
   - Configure capture interval
   - Set output directory
   - Choose video resolution
   - Set location for sunset/sunrise scheduling
   - Enable/disable scheduling
   - Pause/resume captures

## Configuration

The application saves its configuration in `config.json` with the following settings:

- `youtube_url`: URL of the YouTube livestream
- `output_path`: Directory for saving screenshots
- `interval`: Capture interval in seconds
- `resolution`: Preferred video resolution
- `location`: Coordinates for sunset/sunrise calculations
- `schedule_enabled`: Whether to use sunset/sunrise scheduling
- `time_window`: Minutes before/after sunset/sunrise to capture
- `only_sunsets`: Only capture during sunsets

## Requirements

- Python 3.10 or higher
- FFmpeg (must be in system PATH)
- Required Python packages (see requirements.txt)

## License

This project is licensed under the MIT License - see the LICENSE file for details.
