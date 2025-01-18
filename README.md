# YouTube Screenshot Grabber

A Windows system tray application that automatically captures screenshots from YouTube streams at customizable intervals.

## Features

- 🎥 Capture screenshots from any YouTube video/stream
- ⚙️ Configurable screenshot intervals (5-60 seconds)
- 📂 Customizable output directory
- 🔔 System notifications for captures and errors
- 🖥️ Runs silently in system tray
- 🎯 Easy-to-use context menu interface

## Requirements

- Windows OS
- Python 3.10+
- FFmpeg (added to system PATH)
- yt-dlp

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/youtube-screenshot-grabber.git
cd youtube-screenshot-grabber
```

2. Install the required Python packages:
```bash
pip install -r requirements.txt
```

3. Make sure FFmpeg is installed and added to your system PATH

## Usage

1. Run the application:
```bash
python WebcamGrabber.py
```

2. Look for the camera icon in your system tray (bottom right of taskbar)

3. Right-click the icon to:
   - Set YouTube URL
   - Change screenshot interval (5-60 seconds)
   - Select output folder
   - Quit the application

4. Screenshots will be saved to the selected output folder with timestamp-based filenames

## Building Executable

To create a standalone executable:

```bash
python -m PyInstaller --onefile --noconsole --icon=app.ico --hidden-import plyer.platforms.win.notification --hidden-import pystray._win32 --hidden-import PIL._tkinter --hidden-import tkinter --hidden-import tkinter.filedialog WebcamGrabber.py
```

The executable will be created in the `dist` folder.

## Dependencies

- PIL (Pillow): Image processing
- pystray: System tray functionality
- plyer: System notifications
- yt-dlp: YouTube video processing
- FFmpeg: Screenshot capture
- astral: Sunrise/sunset calculations
- tkinter: GUI dialogs

## License

MIT License - see [LICENSE](LICENSE) file for details
