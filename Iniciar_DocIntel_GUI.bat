@echo off
setlocal EnableExtensions

cd /d "%~dp0"
set "REPO_ROOT=%~dp0"
set "PYTHON_CMD="
set "PYTHON_ARGS="

if exist "%REPO_ROOT%\.venv\Scripts\python.exe" set "PYTHON_CMD=%REPO_ROOT%\.venv\Scripts\python.exe"
if not defined PYTHON_CMD if exist "%REPO_ROOT%\venv\Scripts\python.exe" set "PYTHON_CMD=%REPO_ROOT%\venv\Scripts\python.exe"

if not defined PYTHON_CMD (
    for /f "delims=" %%I in ('where python 2^>nul') do (
        if not defined PYTHON_CMD set "PYTHON_CMD=%%I"
    )
)

if not defined PYTHON_CMD (
    for /f "delims=" %%I in ('where py 2^>nul') do (
        if not defined PYTHON_CMD (
            set "PYTHON_CMD=%%I"
            set "PYTHON_ARGS=-3"
        )
    )
)

if not defined PYTHON_CMD (
    echo [DocIntel] Python 3.11+ nao foi encontrado.
    echo [DocIntel] Instale Python ou crie um ambiente virtual em .venv\.
    pause
    exit /b 1
)

"%PYTHON_CMD%" %PYTHON_ARGS% -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo [DocIntel] PySide6 nao esta instalado neste ambiente.
    choice /C SN /N /M "Deseja instalar as dependencias de GUI agora? [S/N] "
    if errorlevel 2 (
        echo [DocIntel] Instalacao cancelada pelo operador.
        pause
        exit /b 2
    )

    "%PYTHON_CMD%" %PYTHON_ARGS% -m pip install --upgrade pip
    if errorlevel 1 (
        echo [DocIntel] Falha ao atualizar o pip.
        pause
        exit /b 3
    )

    "%PYTHON_CMD%" %PYTHON_ARGS% -m pip install -e .[gui]
    if errorlevel 1 (
        echo [DocIntel] Falha ao instalar as dependencias de GUI.
        pause
        exit /b 4
    )
)

echo [DocIntel] Iniciando GUI...
"%PYTHON_CMD%" %PYTHON_ARGS% "%REPO_ROOT%\launch_docintel_gui.py" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [DocIntel] O launcher foi encerrado com codigo %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%
