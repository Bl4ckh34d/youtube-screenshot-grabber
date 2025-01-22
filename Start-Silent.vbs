On Error Resume Next

Set objFSO = CreateObject("Scripting.FileSystemObject")
Set objShell = CreateObject("WScript.Shell")

' Get the script's directory
strScriptPath = objFSO.GetParentFolderName(WScript.ScriptFullName)
objShell.CurrentDirectory = strScriptPath

' Create a log file for debugging
Set objFile = objFSO.CreateTextFile(strScriptPath & "\startup_log.txt", True)
objFile.WriteLine "Script started at " & Now
objFile.WriteLine "Working Directory: " & strScriptPath

' Set PYTHONPATH
objShell.Environment("PROCESS")("PYTHONPATH") = strScriptPath

' Build the command
pythonExe = strScriptPath & "\venv\Scripts\pythonw.exe"
mainScript = "-m src.main"

' Log the command
objFile.WriteLine "Python: " & pythonExe
objFile.WriteLine "Args: " & mainScript
objFile.WriteLine "PYTHONPATH: " & objShell.Environment("PROCESS")("PYTHONPATH")

' Execute the program
Set objExec = objShell.Exec("""" & pythonExe & """ " & mainScript)

If Err.Number <> 0 Then
    objFile.WriteLine "Error: " & Err.Description
End If

objFile.Close
Set objFile = Nothing
Set objExec = Nothing
Set objShell = Nothing
Set objFSO = Nothing
