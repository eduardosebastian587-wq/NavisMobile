<#
=====================================================================================
  nwd_a_fbx.ps1 · Visor 3D v3 · Conversión Navisworks (.nwd) → FBX
-------------------------------------------------------------------------------------
  Abre un archivo .nwd con la API de automatización de Navisworks (sin interfaz) y
  lo exporta a FBX con el mismo exportador de "Salida › Exportar escena › FBX".

  · Requiere Navisworks Manage o Simulate instalado (Freedom no exporta).
  · Usa las opciones del exportador FBX guardadas en Navisworks
    (Opciones › Exportadores de archivos › FBX): limitación de polígonos, texturas,
    luces, cámaras, unidades, formato binario/ASCII, versión.
  · Lo invoca servidor_visor.py; también puede usarse a mano:
      powershell -ExecutionPolicy Bypass -File herramientas\nwd_a_fbx.ps1 `
                 -Entrada "F:\proyecto animación\area 1313.nwd" -Salida "C:\tmp\area 1313.fbx"

  Salida estándar (la lee el servidor para mostrar el avance en el visor):
      ETAPA:<iniciando|abriendo|exportando|listo>     ERROR:<mensaje>
  Código de salida: 0 = correcto · 1 = error
=====================================================================================
#>
param(
  [Parameter(Mandatory = $true)][string]$Entrada,
  [Parameter(Mandatory = $true)][string]$Salida,
  [string]$NavisDir = ''
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

function Etapa([string]$t) { [Console]::Out.WriteLine("ETAPA:$t"); [Console]::Out.Flush() }

# Identificador interno del exportador FBX de Navisworks (lcodpfbx.dll)
$PLUGIN_FBX = 'NativeExportPluginAdaptor_LcFbxExporterPlugin_Export.Navisworks'

try {
  if (-not (Test-Path -LiteralPath $Entrada)) { throw "No existe el archivo de entrada: $Entrada" }

  # ---- Ubicar Navisworks (Manage/Simulate, la versión más reciente) ----
  if (-not $NavisDir) {
    $bases = @($env:ProgramFiles, $env:ProgramW6432) | Where-Object { $_ } | Select-Object -Unique
    $NavisDir = $bases | ForEach-Object { Get-ChildItem (Join-Path $_ 'Autodesk') -Directory -ErrorAction SilentlyContinue } |
      Where-Object { $_.Name -match '^Navisworks (Manage|Simulate) (\d{4})$' -and (Test-Path (Join-Path $_.FullName 'Autodesk.Navisworks.Automation.dll')) } |
      Sort-Object { [int]($_.Name -replace '\D', '') } -Descending | Select-Object -First 1 -ExpandProperty FullName
  }
  if (-not $NavisDir) { throw 'No se encontró Navisworks Manage/Simulate instalado (se necesita Autodesk.Navisworks.Automation.dll).' }
  $dll = Join-Path $NavisDir 'Autodesk.Navisworks.Automation.dll'
  if (-not (Test-Path -LiteralPath $dll)) { throw "No se encontró $dll" }

  $carpetaSalida = Split-Path -Parent $Salida
  if ($carpetaSalida -and -not (Test-Path -LiteralPath $carpetaSalida)) { New-Item -ItemType Directory -Force -Path $carpetaSalida | Out-Null }
  if (Test-Path -LiteralPath $Salida) { Remove-Item -LiteralPath $Salida -Force }

  Add-Type -Path $dll
  Etapa 'iniciando'
  # Lanza una instancia oculta de Roamer.exe (no interfiere con un Navisworks abierto por el usuario)
  $app = New-Object Autodesk.Navisworks.Api.Automation.NavisworksApplication
  try {
    $app.DisableProgress()
    Etapa 'abriendo'
    $app.OpenFile($Entrada, [string[]]@())
    Etapa 'exportando'
    [void]$app.ExecuteAddInPlugin($PLUGIN_FBX, [string[]]@($Salida))
  } finally {
    $app.Dispose()      # cierra la instancia de Navisworks (libera memoria y el archivo)
  }

  # Seguridad: espera a que el FBX quede liberado (Navisworks puede seguir escribiéndolo unos instantes)
  $limite = (Get-Date).AddMinutes(30)
  while ((Test-Path -LiteralPath $Salida) -and (Get-Date) -lt $limite) {
    try { $fs = [IO.File]::Open($Salida, 'Open', 'Read', 'None'); $fs.Close(); break }
    catch { Start-Sleep -Milliseconds 700 }
  }

  if (-not (Test-Path -LiteralPath $Salida) -or (Get-Item -LiteralPath $Salida).Length -lt 1024) {
    throw 'Navisworks terminó sin generar el FBX. Revise que el modelo tenga elementos visibles y las opciones del exportador FBX.'
  }
  Etapa 'listo'
  exit 0
} catch {
  [Console]::Out.WriteLine('ERROR:' + $_.Exception.Message); [Console]::Out.Flush()
  exit 1
}
