@echo off
REM start.bat - run Pipeline Lab locally.
REM Creates this app's own .venv if needed, installs its dependencies,
REM warns if any of the three engine venvs is missing, then starts
REM uvicorn and opens the browser.
REM
REM ASCII only: the Windows console renders this file in its OEM code
REM page, where a typographic dash arrives as mojibake.

setlocal

cd /d "%~dp0"

set "VENV_PY=%~dp0backend\.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo Creating this app's virtual environment...
    python -m venv backend\.venv
    if errorlevel 1 (
        echo.
        echo Failed to create backend\.venv. Is Python on PATH?
        pause
        exit /b 1
    )
)

echo Checking this app's own dependencies...
"%VENV_PY%" -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo.
    echo Failed to install requirements.txt. See the error above.
    pause
    exit /b 1
)

if not exist "..\preprocessing-effects-framework\.venv\Scripts\python.exe" (
    echo.
    echo WARNING: preprocessing-effects-framework\.venv not found.
    echo A run on that engine will fail until its own venv is set up.
    echo See README.md's "Prerequisites" section.
)
if not exist "..\Artefact\Research_Impact_of_Preprocess\.venv\Scripts\python.exe" (
    echo.
    echo WARNING: Artefact\Research_Impact_of_Preprocess\.venv not found.
    echo A run on that engine will fail until its own venv is set up.
    echo See README.md's "Prerequisites" section.
)
if not exist "..\..\pipeline-lab-engine\.venv\Scripts\python.exe" (
    echo.
    echo WARNING: pipeline-lab-engine\.venv not found.
    echo The Compose/Network/Trends tabs need it. A lab run will still
    echo launch but fails immediately with a missing-package error,
    echo because the dashboard falls back to its own interpreter.
    echo See README.md's "Prerequisites" section.
)

echo.
echo Starting Pipeline Lab at http://127.0.0.1:8000
echo Press Ctrl+C in this window to stop it.
echo.

start "" "http://127.0.0.1:8000"
cd backend
"%VENV_PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

endlocal
