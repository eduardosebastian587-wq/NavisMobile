@echo off
chcp 65001 >nul
title Visor 3D v4 - Maqueta Industrial (portico, molinos, pescantes)
rem ================================================================
rem  Inicia el servidor local del visor 3D v4 y abre el visor.
rem  Cierra la ventana "Servidor Visor 3D v4" para detenerlo.
rem  Uso: INICIAR_VISOR_V4.bat                 -> modelo ___area_1313 (calidad equilibrada)
rem       INICIAR_VISOR_V4.bat ultra           -> calidad ultra
rem       INICIAR_VISOR_V4.bat equilibrado otro_modelo.fbx
rem ================================================================
cd /d "%~dp0"
set PUERTO=8040
set CALIDAD=%~1
if not defined CALIDAD set CALIDAD=equilibrado
set MODELO=%~2
if not defined MODELO set MODELO=___area_1313.fbx
set PY=
where py >nul 2>nul && set PY=py
if not defined PY ( where python >nul 2>nul && set PY=python )
if not defined PY (
  echo.
  echo  [ERROR] No se encontro Python en este equipo.
  echo  Instala Python desde https://www.python.org/downloads/ marcando "Add python.exe to PATH".
  echo.
  pause
  exit /b 1
)
echo  Iniciando servidor en http://localhost:%PUERTO%/ ...
start "Servidor Visor 3D v4" %PY% servidor_visor.py %PUERTO%
timeout /t 2 /nobreak >nul
start "" "http://localhost:%PUERTO%/index_v4.html?modelo=%MODELO%&calidad=%CALIDAD%"
echo  Visor abierto en el navegador. Puedes cerrar esta ventana.
timeout /t 4 >nul
