# YouTube Screenshot Grabber

A Windows system tray application that automatically captures screenshots from YouTube streams at customizable intervals.

## Features

- 🎥 Capture screenshots from any YouTube video/stream
- 🎯 Multiple resolution options (480p, 720p, 1080p, best)
- ⚙️ Configurable screenshot intervals (5-60 seconds)
- 🌅 Optional sunrise/sunset scheduling
- 📍 Location-based scheduling support
- 📂 Customizable output directory
- 🔔 System notifications for captures and errors
- 🖥️ Runs silently in system tray
- 🎮 Easy-to-use context menu interface
- 🚀 Minimal resource usage

## Requirements

- Windows OS
- Python 3.10+
- FFmpeg (added to system PATH)

## Installation

1. Clone this repository:
```bash
git clone https://github.com/Bl4ckh34d/youtube-screenshot-grabber.git
cd youtube-screenshot-grabber
```

2. Install the required Python packages:
```bash
pip install -r requirements.txt
```

3. Make sure FFmpeg is installed and added to your system PATH

## Usage

### Quick Start
1. Double-click `Start WebcamGrabber.bat` to run the application
2. Look for the camera icon in your system tray (bottom right of taskbar)
3. Right-click the icon to access all features

### Silent Start
For a completely headless start without any console window:
- Double-click `Start-Silent.vbs`

### System Tray Menu Options
- Set/Change YouTube URL
- Select screenshot resolution (480p, 720p, 1080p, best)
- Adjust capture interval (5-60 seconds)
- Choose output folder
- Configure location for sunrise/sunset scheduling
- Toggle scheduling on/off
- Pause/Resume captures
- Exit application

### Advanced Features

#### Sunrise/Sunset Scheduling
The application can automatically:
- Detect your location (using IP geolocation)
- Calculate sunrise and sunset times
- Only capture screenshots during daylight hours
- Adjust schedule daily based on changing sunrise/sunset times

#### Resolution Selection
Choose from multiple quality options:
- 480p: Fastest, lowest quality
- 720p: Balanced option
- 1080p: High quality (default)
- Best: Highest available quality

## Configuration

The application saves all settings in `config.json`, including:
- Last used YouTube URL
- Selected output path
- Preferred screenshot interval
- Selected resolution
- Location settings
- Schedule preferences

## Dependencies

All required packages are specified in `requirements.txt` with version numbers:
- customtkinter: Modern GUI elements
- Pillow (PIL): Image processing
- pystray: System tray functionality
- plyer: System notifications
- yt-dlp: YouTube video processing
- astral: Sunrise/sunset calculations
- tkintermapview: Location selection
- tzlocal: Timezone handling
- requests: Network requests

## License

MIT License - see [LICENSE](LICENSE) file for details
