Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
python = fso.GetFile(WshShell.ExpandEnvironmentStrings("%PYTHON_COMMAND%")).ShortPath
If python = "" Then python = "python"
cmd = """" & python & """ -m emirald.scripts.launch_emirald_gui --no-auto-start start"
WshShell.Run "cmd /c " & cmd, 1, False
