@echo off
rem Start the TCA -> virtual Xbox 360 pad bridge (requires ViGEmBus driver).
rem Usage: run-xbox.bat [config\my-xbox.json]   (default: config\xbox.json)
cd /d "%~dp0"
set CONFIG=%1
if "%CONFIG%"=="" set CONFIG=config\xbox.json
python -m simrail_tca xbox --config %CONFIG%
pause
