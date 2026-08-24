Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
python = fso.GetFile(WshShell.ExpandEnvironmentStrings("%PYTHON_COMMAND%")).ShortPath
If python = "" Then python = "python"
workingDir = fso.GetFolder(".").ShortPath
arg = WScript.Arguments(0)
cmd = """" & python & """ -m axiom_logic.scripts.control " & arg
WshShell.Run "cmd /c " & cmd, 1, False
