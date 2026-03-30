@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_PATH=%SCRIPT_DIR%patch_antigravity.py"
set "PYTHON_CMD="

call py -3 -V >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3"

if not defined PYTHON_CMD (
    call python -V >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD if exist "C:\Program Files\Python313\python.exe" set "PYTHON_CMD="C:\Program Files\Python313\python.exe""
if not defined PYTHON_CMD if exist "C:\Program Files\Python312\python.exe" set "PYTHON_CMD="C:\Program Files\Python312\python.exe""
if not defined PYTHON_CMD if exist "C:\Program Files\Python311\python.exe" set "PYTHON_CMD="C:\Program Files\Python311\python.exe""
if not defined PYTHON_CMD if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set "PYTHON_CMD="%LocalAppData%\Programs\Python\Python313\python.exe""
if not defined PYTHON_CMD if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PYTHON_CMD="%LocalAppData%\Programs\Python\Python312\python.exe""
if not defined PYTHON_CMD if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PYTHON_CMD="%LocalAppData%\Programs\Python\Python311\python.exe""

if not defined PYTHON_CMD (
    echo [ERROR] Python 3 was not found.
    echo Install Python 3 or run patch_antigravity.py with a full python.exe path.
    pause
    exit /b 1
)

%PYTHON_CMD% "%SCRIPT_PATH%" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Patch failed with exit code %EXIT_CODE%.
    pause
    exit /b %EXIT_CODE%
)

echo.
pause
exit /b 0
