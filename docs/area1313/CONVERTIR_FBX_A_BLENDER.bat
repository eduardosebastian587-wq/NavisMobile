@echo off
rem ==========================================================================
rem  CONVERTIR_FBX_A_BLENDER.bat  -  FBX (Navisworks) -> .blend
rem  Uso: doble clic (elige el FBX) o arrastra un .fbx sobre este archivo.
rem  Resultado: convertidos_blender\<nombre>.blend  +  <nombre>.informe.txt
rem  Si Blender esta instalado en otra ruta, escribela en BLENDER_MANUAL.
rem ==========================================================================
setlocal EnableExtensions
chcp 65001 >nul
set "BLENDER_MANUAL="
set "DIR=%~dp0"
set "SCRIPT=%DIR%herramientas\fbx_a_blender.py"

if not exist "%SCRIPT%" (
  echo No se encuentra herramientas\fbx_a_blender.py junto a este .bat
  pause & exit /b 1
)

rem ---- 1. Buscar Blender (se queda con la version mas nueva) ----
set "BLENDER=%BLENDER_MANUAL%"
if not defined BLENDER for /d %%D in ("%ProgramFiles%\Blender Foundation\Blender*") do if exist "%%D\blender.exe" set "BLENDER=%%D\blender.exe"
if not defined BLENDER if exist "%ProgramFiles(x86)%\Steam\steamapps\common\Blender\blender.exe" set "BLENDER=%ProgramFiles(x86)%\Steam\steamapps\common\Blender\blender.exe"
if not defined BLENDER for /f "delims=" %%B in ('where blender 2^>nul') do set "BLENDER=%%B"
if not defined BLENDER (
  echo.
  echo  No se encontro Blender en este equipo.
  echo  Descargalo gratis desde https://www.blender.org/download/  ^(version 4.2 o superior^)
  echo  o escribe su ruta en la linea BLENDER_MANUAL de este archivo.
  echo.
  pause & exit /b 1
)
echo Blender: %BLENDER%

rem ---- 2. Elegir el FBX ----
set "FBX=%~1"
if not defined FBX for /f "usebackq delims=" %%F in (`powershell -NoProfile -STA -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Add-Type -AssemblyName System.Windows.Forms; $d=New-Object System.Windows.Forms.OpenFileDialog; $d.Title='Elige el FBX a convertir'; $d.Filter='FBX (*.fbx)|*.fbx'; $d.InitialDirectory=$env:DIR; if($d.ShowDialog() -eq 'OK'){$d.FileName}"`) do set "FBX=%%F"
if not defined FBX ( echo No se eligio ningun archivo. & pause & exit /b 1 )
for %%I in ("%FBX%") do set "NOMBRE=%%~nI"
set "SALIDA=%DIR%convertidos_blender\%NOMBRE%.blend"

rem ---- 3. Modo de conversion ----
echo.
echo  Archivo: %FBX%
echo.
echo  [1] Normal     - cada pieza separada, agrupadas por TAG   (recomendado)
echo  [2] Por equipo - un objeto por TAG (comodo para animar despieces)
echo  [3] Liviano    - un objeto por color y 50%% de triangulos (modelos enormes)
echo  [4] Original   - conserva el arbol completo de Navisworks
echo.
choice /c 1234 /n /m "Elige 1, 2, 3 o 4: "
set "OPC="
if errorlevel 4 ( set "OPC=--jerarquia mantener" & goto :convertir )
if errorlevel 3 ( set "OPC=--unir material --decimar 0.5" & goto :convertir )
if errorlevel 2 ( set "OPC=--unir tag" & goto :convertir )

:convertir
echo.
echo Convirtiendo... (un FBX de 300 MB puede tardar varios minutos; no cierres esta ventana)
echo.
"%BLENDER%" -b --factory-startup --python-exit-code 1 --python "%SCRIPT%" -- "%FBX%" --salida "%SALIDA%" %OPC%
if errorlevel 1 (
  echo.
  echo  La conversion fallo. Revisa los mensajes de arriba.
  pause & exit /b 1
)

echo.
echo  Listo: %SALIDA%
choice /c SN /m "Abrir en Blender ahora"
if errorlevel 2 exit /b 0
start "" "%BLENDER%" "%SALIDA%"
exit /b 0
