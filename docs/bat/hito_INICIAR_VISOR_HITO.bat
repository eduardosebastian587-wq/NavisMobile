@echo off
chcp 65001 >nul
setlocal
title Visor Hito M33-1 (servidor local)
rem ---------------------------------------------------------------------------------------------
rem  Abre el recorrido realista del Hito M33-1 en el navegador.
rem  Uso:  INICIAR_VISOR_HITO.bat [ruta_modelo.glb] [calidad: auto^|alta^|media^|baja]
rem  Requiere internet (Three.js por CDN). Cierra esta ventana para apagar el servidor.
rem ---------------------------------------------------------------------------------------------
cd /d "%~dp0"
set "PUERTO=8050"
set "MODELO=%~1"
if not defined MODELO set "MODELO=convertidos_blender/hito_web.glb"
set "CAL=%~2"
if not defined CAL set "CAL=auto"
if not exist "%MODELO:/=\%" (
  echo [ERROR] No existe "%MODELO%". Generalo con EXPORTAR_HITO_GLB.bat
  pause & exit /b 1
)
if not exist "index_hito.html" (
  echo [ERROR] Falta index_hito.html. Generalo con EXPORTAR_HITO_GLB.bat
  pause & exit /b 1
)
set "PY="
for %%P in (py python) do (
  if not defined PY ( %%P -c "pass" >nul 2>nul && set "PY=%%P" )
)
if not defined PY if exist "%LOCALAPPDATA%\Python\bin\python.exe" set "PY=%LOCALAPPDATA%\Python\bin\python.exe"
if not defined PY if exist "C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe" set "PY=C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe"
if not defined PY ( echo [ERROR] No se encontro Python. & pause & exit /b 1 )

rem Si el puerto ya esta ocupado (otro visor abierto), se reutiliza ese servidor.
netstat -ano | findstr /r /c:":%PUERTO% .*LISTENING" >nul
if errorlevel 1 (
  start "Servidor Visor Hito (cerrar para apagar)" /min "%PY%" servidor_visor.py %PUERTO%
  timeout /t 2 /nobreak >nul
)
start "" "http://localhost:%PUERTO%/index_hito.html?modelo=%MODELO%&calidad=%CAL%"
echo  Visor abierto en http://localhost:%PUERTO%/index_hito.html
echo  Atajos: ESPACIO play/pausa - R reiniciar - O camara libre - C calidad - T titulo
timeout /t 4 >nul
