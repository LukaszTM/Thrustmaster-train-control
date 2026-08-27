@echo off
rem Open the graphical interface of the SimRail <- Thrustmaster TCA bridge.
cd /d "%~dp0"
start "SimRail TCA" pythonw -m simrail_tca gui
