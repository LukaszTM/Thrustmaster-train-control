@echo off
rem Start the SimRail <- Thrustmaster TCA bridge with the EU07 profile.
rem Usage: run.bat [config\en76.json]
cd /d "%~dp0"
set CONFIG=%1
if "%CONFIG%"=="" set CONFIG=config\eu07.json
python -m simrail_tca run --config %CONFIG%
pause
