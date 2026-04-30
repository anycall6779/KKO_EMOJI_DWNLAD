@echo off
if not exist "%~dp0.initialized" (
    call "%~dp0setup.bat"
    if errorlevel 1 exit /b 1
)
python "%~dp0launcher.py"
pause
