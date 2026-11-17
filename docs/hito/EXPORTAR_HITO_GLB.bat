@echo off
chcp 65001 >nul
setlocal
title Hito M33-1 - Cadena completa: escena del video al visor web realista
rem ---------------------------------------------------------------------------------------------
rem  hito_realista.blend (escena del video)
rem   1) extraer_escena_hito.py      = convertidos_blender\hito_escena_video.json (materiales, sol, cielo, camara)
rem   2) volcar_geometria_hito.py    = geometria en %%TEMP%%\hito_trabajo\geo (no se sube a Drive)
rem   3) detectar_sueltos_hito.py    = elementos sueltos (criterio medible) = convertidos_blender\hito_sueltos.json
rem   4) separar_sueltos_hito.py     = hito_realista_limpio.blend (sueltos en coleccion excluida, no borrados)
rem   5) optimizar_recorrido_hito.py = convertidos_blender\hito_recorrido.json (25 s, holgura 3 m) + campo de distancias
rem   6) exportar_hito_visor.py      = convertidos_blender\hito_web.glb y hito_sueltos.glb (Draco)
rem   7) generar_visor_hito.py       = index_hito.html (no se edita a mano)
rem  Uso:  EXPORTAR_HITO_GLB.bat [millones_de_triangulos=13] [duracion_s=25] [holgura_m=3]
rem ---------------------------------------------------------------------------------------------
cd /d "%~dp0"
set "BL=C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
set "M=%~1"
if not defined M set "M=13"
set "DUR=%~2"
if not defined DUR set "DUR=25"
set "HOLG=%~3"
if not defined HOLG set "HOLG=3"
set "TRAB=%TEMP%\hito_trabajo"
if not exist "%BL%" ( echo [ERROR] No se encontro Blender en "%BL%" & pause & exit /b 1 )
set "BLEND=convertidos_blender\hito_realista.blend"
if not exist "%BLEND%" set "BLEND=F:\proyecto animación\convertidos_blender\hito_realista.blend"
if not exist "%BLEND%" ( echo [ERROR] No se encontro hito_realista.blend & pause & exit /b 1 )
for %%F in ("%BLEND%") do set "LIMPIO=%%~dpFhito_realista_limpio.blend"
call :python
if not defined PY ( echo [ERROR] No se encontro Python. & pause & exit /b 1 )
"%PY%" -c "import numpy, scipy" >nul 2>nul || (
  echo  Instalando numpy y scipy para Python...
  "%PY%" -m pip install --quiet numpy scipy || ( echo [ERROR] No se pudo instalar numpy/scipy & pause & exit /b 1 )
)
if not exist "%TRAB%" mkdir "%TRAB%"
echo  Escena del video: %BLEND%
echo.
echo  [1/7] Extrayendo materiales, sol, cielo y camara del video...
"%BL%" -b "%BLEND%" --factory-startup --python-exit-code 1 --python "herramientas\extraer_escena_hito.py" -- "convertidos_blender\hito_escena_video.json" || goto :error
echo  [2/7] Volcando geometria para el analisis...
"%BL%" -b "%BLEND%" --factory-startup --python-exit-code 1 --python "herramientas\volcar_geometria_hito.py" -- "%TRAB%\geo" || goto :error
echo  [3/7] Detectando elementos sueltos...
"%PY%" "herramientas\detectar_sueltos_hito.py" "%TRAB%\geo" || goto :error
copy /y "%TRAB%\geo\sueltos.json" "convertidos_blender\hito_sueltos.json" >nul
echo  [4/7] Separando elementos sueltos (modelo limpio)...
"%BL%" -b "%BLEND%" --factory-startup --python-exit-code 1 --python "herramientas\separar_sueltos_hito.py" -- "%TRAB%\geo\sueltos_mascaras.npz" "%LIMPIO%" "%TRAB%\control" || goto :error
echo  [5/7] Planificando recorrido de %DUR% s sin interferencias (holgura %HOLG% m)...
"%PY%" "herramientas\optimizar_recorrido_hito.py" "%TRAB%\geo" "convertidos_blender\hito_escena_video.json" "convertidos_blender\hito_recorrido.json" %DUR% %HOLG% || goto :error
echo  [6/7] Exportando modelos web (objetivo %M% M triangulos)...
"%BL%" -b "%LIMPIO%" --factory-startup --python-exit-code 1 --python "herramientas\exportar_hito_visor.py" -- "convertidos_blender\hito_web.glb" %M% || goto :error
"%BL%" -b "%LIMPIO%" --factory-startup --python-exit-code 1 --python "herramientas\exportar_hito_visor.py" -- "convertidos_blender\hito_sueltos.glb" %M% --sueltos || goto :error
echo  [7/7] Generando index_hito.html...
"%PY%" "herramientas\generar_visor_hito.py" || goto :error
echo.
echo  Listo. Abre INICIAR_VISOR_HITO.bat para ver el recorrido.
echo  Renders de control de los elementos sueltos: %TRAB%\control
pause
exit /b 0

:error
echo.
echo [ERROR] La cadena se detuvo en el paso anterior. Revisa los mensajes de arriba.
pause
exit /b 1

:python
rem Busca un Python que realmente funcione (el alias de Microsoft Store no sirve).
set "PY="
for %%P in (py python) do (
  if not defined PY ( %%P -c "pass" >nul 2>nul && set "PY=%%P" )
)
if not defined PY if exist "%LOCALAPPDATA%\Python\bin\python.exe" set "PY=%LOCALAPPDATA%\Python\bin\python.exe"
if not defined PY if exist "C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe" set "PY=C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe"
exit /b 0
