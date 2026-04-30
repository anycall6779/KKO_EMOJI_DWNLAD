@echo off
Setup
echo.
echo  ================================================
echo  Setup
echo  ================================================
echo.
echo  [1/3] Checking Python...
python --version > nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] Python is not installed!
    echo.
    echo  Please install Python 3.8 or later:
    echo    https://www.python.org/downloads/
    echo.
    echo  IMPORTANT: Check Add Python to PATH during install.
    echo.
    pause
    start https://www.python.org/downloads/
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  [OK] %PYVER%
echo.
echo  [2/3] Checking pip...
python -m pip --version > nul 2>&1
if errorlevel 1 (
    echo  [ERROR] pip not found. Please reinstall Python.
    pause
    exit /b 1
)
echo  [OK] pip found
echo.
echo  [3/3] Installing required packages...
echo.
echo  Installing httpx...
python -m pip install httpx -q --disable-pip-version-check
echo  [OK] httpx ready
echo  Installing Pillow...
python -m pip install Pillow -q --disable-pip-version-check
echo  [OK] Pillow ready
echo.
echo  ================================================
echo   Setup complete! All packages installed.
echo  ================================================
echo.
echo done > "%~dp0.initialized"
echo  You can now run start.bat to use the downloader.
echo.
choice /c YN /m "Run the downloader now? (Y/N): "
if errorlevel 2 goto END
if errorlevel 1 python "%~dp0launcher.py"
:END
echo.
pause
