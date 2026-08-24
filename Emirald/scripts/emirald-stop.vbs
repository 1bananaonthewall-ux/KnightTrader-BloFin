Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
python = fso.GetFile(WshShell.ExpandEnvironmentStrings("%PYTHON_COMMAND%")).ShortPath
If python = "" Then python = "python"
cmd = """" & python & """ -m emirald.scripts.stop_emirald --quiet"
WshShell.Run "cmd /c " & cmd, 1, False
