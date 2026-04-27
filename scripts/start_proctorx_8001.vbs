Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
rootDir = fso.GetParentFolderName(scriptDir)
shell.CurrentDirectory = rootDir
shell.Run "cmd /c """ & scriptDir & "\run_proctorx_8001.cmd""", 0, False
