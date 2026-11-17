@echo off
chcp 65001 >nul
setlocal
title Visor Area 1313 v2 (barandas y huecos)
rem ---------------------------------------------------------------------------------------------
rem  Abre el recorrido del Area 1313 (molinos, portico CN-1406, pescantes) en Google Chrome.
rem  Uso:  INICIAR_VISOR_1313.bat [calidad: auto^|alta^|media^|baja]
rem  Requiere internet (Three.js por CDN). Cierra esta ventana para apagar el servidor.
rem ---------------------------------------------------------------------------------------------
cd /d "%~dp0"
set "PUERTO=8060"
set "CAL=%~1"
if not defined CAL set "CAL=auto"
if not exist "convertidos_blender\area1313_web_v2.glb" ( echo [ERROR] Falta convertidos_blender\area1313_web_v2.glb ^(herramientas\unir_capas_1313.py^) & pause & exit /b 1 )
if not exist "index_1313_v2.html" ( echo [ERROR] Falta index_1313.html ^(py herramientas\generar_visor_1313.py^) & pause & exit /b 1 )
set "PY="
for %%P in (py python) do (
  if not defined PY ( %%P -c "pass" >nul 2>nul && set "PY=%%P" )
)
if not defined PY if exist "%LOCALAPPDATA%\Python\bin\python.exe" set "PY=%LOCALAPPDATA%\Python\bin\python.exe"
if not defined PY ( echo [ERROR] No se encontro Python. & pause & exit /b 1 )
netstat -ano | findstr /r /c:":%PUERTO% .*LISTENING" >nul
if errorlevel 1 (
  start "Servidor Visor Area 1313 (cerrar para apagar)" /min "%PY%" servidor_visor.py %PUERTO%
  timeout /t 2 /nobreak >nul
)
set "URL=http://localhost:%PUERTO%/index_1313_v2.html?calidad=%CAL%^&modelo=convertidos_blender/area1313_web_v2.glb"
set "CHROME="
for %%C in ("%ProgramFiles%\Google\Chrome\Application\chrome.exe" "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe") do (
  if not defined CHROME if exist %%C set "CHROME=%%~C"
)
if defined CHROME ( start "" "%CHROME%" "%URL%" ) else ( echo [AVISO] No se encontro Google Chrome; se abre el navegador predeterminado. & start "" "%URL%" )
echo  Visor abierto en %URL%
echo  Atajos: ESPACIO play/pausa - R reiniciar - O camara libre - C calidad - T titulo - H panel
timeout /t 4 >nul
