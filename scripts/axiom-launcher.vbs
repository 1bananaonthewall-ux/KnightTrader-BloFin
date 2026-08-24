Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
python = fso.GetFile(WshShell.ExpandEnvironmentStrings("%PYTHON_COMMAND%")).ShortPath
If python = "" Then python = "python"
workingDir = fso.GetFolder(".").ShortPath
arg = WScript.Arguments(0)
cmd = """" & python & """ -m hermes_trader.scripts.launch_hermes_gui --no-auto-start " & arg
WshShell.Run "cmd /c " & cmd, 1, False
