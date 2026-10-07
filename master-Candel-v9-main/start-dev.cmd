@echo off
setlocal

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "BACKEND_PORT=7007"
set "PYTHON=python"

if exist "%ROOT%.venv\Scripts\python.exe" set "PYTHON=%ROOT%.venv\Scripts\python.exe"

if not exist "%BACKEND%\.env" (
    copy "%BACKEND%\.env.example" "%BACKEND%\.env" >nul
    echo Created backend\.env from backend\.env.example.
    echo Set MONGO_URL and DB_NAME in backend\.env, then run start-dev.cmd again.
    exit /b 1
)

"%PYTHON%" -c "import fastapi, motor, dotenv, uvicorn" >nul 2>nul
if errorlevel 1 (
    echo Backend Python dependencies are missing.
    echo Install them with: "%PYTHON%" -m pip install -r "%BACKEND%\requirements.txt"
    exit /b 1
)

if not exist "%FRONTEND%\node_modules\.bin\vite.cmd" (
    echo Frontend dependencies are missing.
    echo Install them with: cd /d "%FRONTEND%" ^&^& npm ci
    exit /b 1
)

set "VITE_API_SAME_ORIGIN=true"
set "CODESPACE_BACKEND_PROXY_TARGET=http://127.0.0.1:%BACKEND_PORT%"

start "Master Candle Backend" /D "%BACKEND%" cmd /k ""%PYTHON%" -m uvicorn server:app --host 127.0.0.1 --port %BACKEND_PORT%"
start "Master Candle Frontend" /D "%FRONTEND%" cmd /k "npm run dev"

echo Backend:  http://127.0.0.1:%BACKEND_PORT%
echo Frontend: http://127.0.0.1:5173
echo Health:   http://127.0.0.1:%BACKEND_PORT%/api/health
echo Runtime:  http://127.0.0.1:%BACKEND_PORT%/api/v1/runtime
echo Signals:  http://127.0.0.1:%BACKEND_PORT%/api/v1/signals/live
echo ML status:http://127.0.0.1:%BACKEND_PORT%/api/v1/ml/status
echo Close both opened command windows to stop the services.
