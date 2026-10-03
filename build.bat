@echo off
REM Build AWSMonitor.exe with PyInstaller
cd /d "%~dp0"
pip install -r requirements.txt
pyinstaller AWSMonitor.spec --noconfirm
echo.
echo Built: dist\AWSMonitor\AWSMonitor.exe  (one-folder) or dist\AWSMonitor.exe
echo Next: compile installer.iss with Inno Setup to get Setup-AWSMonitor.exe
pause
