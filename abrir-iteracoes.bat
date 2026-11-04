@echo off
rem Abre o app de iteracoes de specs (python -m iteracoes) no navegador.
cd /d "%~dp0"
where python 1>nul 2>nul
if errorlevel 1 (
    echo Python nao encontrado no PATH. Instale o Python 3.11+ e tente de novo.
    pause
    exit /b 1
)
python -m iteracoes %*
if errorlevel 1 pause
