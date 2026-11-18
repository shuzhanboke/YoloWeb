@echo off
REM Windows launcher for the YoloWebAgentStarter backend.
REM Uses the repository-local .venv and points Ultralytics at a writable
REM project-local config dir so it does not need to touch AppData or network.
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\backend"
set "YOLO_CONFIG_DIR=%CD%\ultralytics_config"
.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000