@echo off
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
copy /y "%ROOT%\uninstall.ps1" "%TEMP%\download-organizer-uninstall.ps1" >nul
cd /d "%TEMP%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\download-organizer-uninstall.ps1" -Root "%ROOT%"
