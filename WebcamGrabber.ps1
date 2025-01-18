# Hide the PowerShell console window
Add-Type -Name Window -Namespace Console -MemberDefinition '
[DllImport("Kernel32.dll")]
public static extern IntPtr GetConsoleWindow();
[DllImport("user32.dll")]
public static extern bool ShowWindow(IntPtr hWnd, Int32 nCmdShow);
'
$consolePtr = [Console.Window]::GetConsoleWindow()
[Console.Window]::ShowWindow($consolePtr, 0)

# Set working directory to script location
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

# Create and activate virtual environment if it doesn't exist
if (-not (Test-Path "venv")) {
    python -m venv venv
    ./venv/Scripts/Activate.ps1
    python -m pip install -r requirements.txt
} else {
    ./venv/Scripts/Activate.ps1
}

# Start the WebcamGrabber
pythonw WebcamGrabber.py
