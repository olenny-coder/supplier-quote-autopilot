@echo off
REM ============================================================================
REM  set-llm-key.cmd - paste your LLM API key, from Command Prompt.
REM ============================================================================
REM
REM  This is a thin wrapper around set-llm-key.ps1. It exists because typing
REM
REM      .\set-llm-key.ps1
REM
REM  in cmd.exe does NOT work: Windows has no file association for .ps1, so the
REM  command hangs silently with no output and no error - which is baffling when
REM  the file is obviously right there. PowerShell has no such problem.
REM
REM  So use whichever fits the shell you are in:
REM
REM      Command Prompt    set-llm-key.cmd        (or: dev.cmd key)
REM      PowerShell        .\set-llm-key.ps1      (or: .\set-llm-key.cmd)
REM
REM  All arguments are forwarded, so these work too:
REM
REM      set-llm-key.cmd -Key gsk_abc123
REM      set-llm-key.cmd -Key gsk_abc123 -NoRestart
REM
REM ============================================================================

setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0set-llm-key.ps1" %*
exit /b %errorlevel%
