@echo off
rem Start the SimRail <- Thrustmaster TCA bridge.
rem Usage: run.bat [config\z-ed.json]   (default: config\bez-ed.json)
cd /d "%~dp0"
set CONFIG=%1
if "%CONFIG%"=="" set CONFIG=config\bez-ed.json
python -m simrail_tca run --config %CONFIG%
pause
