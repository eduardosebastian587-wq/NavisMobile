#requires -Version 5.1
<#
=====================================================================================
  extraer_area_oculto.ps1 · NavisMobile · extracción SIN bloquear tu Navisworks
-------------------------------------------------------------------------------------
  Abre un .nwd en una instancia OCULTA de Navisworks (Automation API, igual que
  nwd_a_fbx.ps1), le baja la prioridad, extrae la geometría con el plugin
  NwMobileExport (entrada "Lote", sin ventanas) y deja el resultado en la carpeta
  de Google Drive para que GitHub Actions haga la conversión y la publicación.

  Tu PC solo hace la extracción. La conversión a GLB, la compresión Draco y la
  publicación en la app ocurren en la nube (.github/workflows/procesar_area.yml).

  Uso típico (un NWD de área, se exporta completo):
    powershell -ExecutionPolicy Bypass -File herramientas\navismobile-export\extraer_area_oculto.ps1 `
               -Nwd "F:\proyecto animación\AREA_1313_MOLINOS\modelo_fuente\area 1313.nwd" -Id area1313

  Opciones:
    -Raices "0:27/6/0/0,0:28"   solo esos nodos (ids de find_items); vacío = todo el documento
    -Excluir "..."              nodos a omitir
    -Rutas "A/B/1300|C/D/1300"  nodos por nombre (se suman a -Raices); si un nombre no existe, el error lista los disponibles
    -ExcluirNombres "MecMiscellaneous,Unknown"   omite en todo el subárbol los nodos con esos nombres
    -Destino <carpeta>          dónde dejar el resultado (por defecto la carpeta NavisMobile\entrada en Drive)
    -Nucleos N                  núcleos que puede usar Navisworks (por defecto la mitad)
    -Formato fbx                plan B: usa el exportador FBX nativo de Navisworks en vez del plugin
    -Prueba                     solo comprueba que todo carga (abre, extrae y muestra el resultado)

  Salida estándar: ETAPA:<...> · ERROR:<mensaje> · LISTO:<ruta>
  Código de salida: 0 = correcto · 1 = error
=====================================================================================
#>
param(
  [Parameter(Mandatory = $true)][string]$Nwd,
  [Parameter(Mandatory = $true)][ValidatePattern('^[A-Za-z0-9_-]+$')][string]$Id,
  [string]$Raices = '',
  [string]$Excluir = '',
  [string]$Rutas = '',
  [string]$ExcluirNombres = '',
  [string]$Destino = '',
  [int]$Nucleos = 0,
  [ValidateSet('nmraw', 'fbx')][string]$Formato = 'nmraw',
  [string]$NavisDir = '',
  [switch]$Prueba
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
function Etapa([string]$t) { [Console]::Out.WriteLine("ETAPA:$t  [" + (Get-Date -Format 'HH:mm:ss') + "]"); [Console]::Out.Flush() }

$PLUGIN_LOTE = 'NwMobileExport.Lote.NWMX'
$PLUGIN_FBX = 'NativeExportPluginAdaptor_LcFbxExporterPlugin_Export.Navisworks'
$t0 = Get-Date

try {
  if (-not (Test-Path -LiteralPath $Nwd)) { throw "No existe el archivo: $Nwd" }

  # ---- Carpeta de destino: Google Drive para escritorio (streaming o espejo) ----
  if (-not $Destino) {
    $candidatas = @(
      (Join-Path $env:USERPROFILE 'Streaming de Google Drive\Mi unidad\proyecto animación'),
      'G:\Mi unidad\proyecto animación', 'G:\My Drive\proyecto animación'
    )
    $base = $candidatas | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $base) { throw 'No encontré la carpeta "proyecto animación" de Google Drive. Indícala con -Destino.' }
    $Destino = Join-Path $base 'NavisMobile\entrada'
  }
  New-Item -ItemType Directory -Force -Path $Destino | Out-Null

  # Se trabaja en disco local y se copia a Drive al final (la sincronización no compite con la extracción).
  $local = Join-Path $env:LOCALAPPDATA "NwMobileExport\lote\$Id"
  New-Item -ItemType Directory -Force -Path $local | Out-Null
  Get-ChildItem -LiteralPath $local -File -ErrorAction SilentlyContinue | Remove-Item -Force
  $salida = if ($Formato -eq 'fbx') { Join-Path $local "$Id.fbx" } else { Join-Path $local "$Id.nmraw" }

  # ---- Ubicar Navisworks Manage/Simulate ----
  if (-not $NavisDir) {
    $bases = @($env:ProgramFiles, $env:ProgramW6432) | Where-Object { $_ } | Select-Object -Unique
    $NavisDir = $bases | ForEach-Object { Get-ChildItem (Join-Path $_ 'Autodesk') -Directory -ErrorAction SilentlyContinue } |
      Where-Object { $_.Name -match '^Navisworks (Manage|Simulate) (\d{4})$' -and (Test-Path (Join-Path $_.FullName 'Autodesk.Navisworks.Automation.dll')) } |
      Sort-Object { [int]($_.Name -replace '\D', '') } -Descending | Select-Object -First 1 -ExpandProperty FullName
  }
  if (-not $NavisDir) { throw 'No se encontró Navisworks Manage/Simulate (falta Autodesk.Navisworks.Automation.dll).' }
  if ($Formato -eq 'nmraw') {
    $bundle = Join-Path $env:APPDATA 'Autodesk\ApplicationPlugins\NwMobileExport.bundle'
    if (-not (Test-Path $bundle)) { throw "El plugin NwMobileExport no está instalado ($bundle). Ejecuta Install.ps1 con Navisworks cerrado." }
  }
  Add-Type -Path (Join-Path $NavisDir 'Autodesk.Navisworks.Automation.dll')

  # ---- Instancia oculta con prioridad baja ----
  Etapa 'iniciando Navisworks oculto'
  $antes = @(Get-Process Roamer -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
  $app = New-Object Autodesk.Navisworks.Api.Automation.NavisworksApplication
  try {
    $mio = Get-Process Roamer -ErrorAction SilentlyContinue | Where-Object { $antes -notcontains $_.Id } | Select-Object -First 1
    if ($mio) {
      $n = [Environment]::ProcessorCount
      if ($Nucleos -le 0) { $Nucleos = [Math]::Max(1, [Math]::Floor($n / 2)) }
      $Nucleos = [Math]::Min($Nucleos, $n)
      try { $mio.PriorityClass = 'BelowNormal' } catch { }
      try { $mio.ProcessorAffinity = [IntPtr]([long]([Math]::Pow(2, $Nucleos) - 1)) } catch { }
      Etapa "Navisworks oculto pid $($mio.Id): prioridad baja, $Nucleos de $n núcleos"
    } else { Etapa 'aviso: no identifiqué el proceso oculto; sigue con prioridad normal' }

    $app.DisableProgress()
    Etapa "abriendo $Nwd"
    $app.OpenFile($Nwd, [string[]]@())
    Etapa "extrayendo ($Formato)"
    if ($Formato -eq 'fbx') {
      [void]$app.ExecuteAddInPlugin($PLUGIN_FBX, [string[]]@($salida))
    } else {
      $args2 = @("salida=$salida")
      if ($Raices) { $args2 += "raices=$Raices" }
      if ($Excluir) { $args2 += "excluir=$Excluir" }
      if ($Rutas) { $args2 += "rutas=$Rutas" }
      if ($ExcluirNombres) { $args2 += "excluir_nombres=$ExcluirNombres" }
      try { $r = $app.ExecuteAddInPlugin($PLUGIN_LOTE, [string[]]$args2) }
      catch { throw "Navisworks no ejecutó $PLUGIN_LOTE ($($_.Exception.Message)). Si el plugin no carga en modo oculto, usa -Formato fbx (plan B)." }
    }
  } finally {
    Etapa 'cerrando Navisworks oculto'
    $app.Dispose()
  }

  # ---- Comprobar resultado ----
  if ($Formato -eq 'nmraw') {
    $estado = "$salida.estado.json"
    if (Test-Path $estado) {
      $e = Get-Content $estado -Raw -Encoding UTF8 | ConvertFrom-Json
      if ($e.estado -ne 'listo') { throw "El plugin terminó con estado '$($e.estado)': $($e.error)" }
    }
    foreach ($f in @($salida, "$salida.piezas.json")) { if (-not (Test-Path $f)) { throw "No se generó $f" } }
  } else {
    $limite = (Get-Date).AddMinutes(30)
    while ((Test-Path $salida) -and (Get-Date) -lt $limite) {
      try { $fs = [IO.File]::Open($salida, 'Open', 'Read', 'None'); $fs.Close(); break } catch { Start-Sleep -Milliseconds 700 }
    }
    if (-not (Test-Path $salida) -or (Get-Item $salida).Length -lt 1024) { throw 'Navisworks no generó el FBX.' }
  }
  $mb = [Math]::Round((Get-ChildItem $local -File | Measure-Object Length -Sum).Sum / 1MB)
  Etapa "extracción lista: $mb MB en $([Math]::Round(((Get-Date) - $t0).TotalMinutes, 1)) min"
  if ($Prueba) { [Console]::Out.WriteLine("LISTO:$local (modo prueba: no se copió a Drive)"); exit 0 }

  # ---- Copiar a Drive (el .piezas.json primero: el .nmraw es la señal de "listo") ----
  Etapa "copiando a $Destino"
  Get-ChildItem $local -File | Where-Object { $_.Name -notlike '*.estado.json' } |
    Sort-Object { if ($_.Extension -in '.nmraw', '.fbx') { 1 } else { 0 } } |
    ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $Destino $_.Name) -Force }
  $archivo = Split-Path $salida -Leaf
  [Console]::Out.WriteLine("LISTO:" + (Join-Path $Destino $archivo))
  [Console]::Out.WriteLine('')
  [Console]::Out.WriteLine('Cuando Google Drive termine de subirlo, publícalo desde el celular:')
  [Console]::Out.WriteLine("  GitHub > NavisMobile > Actions > Procesar área > Run workflow > archivo = $archivo , id = $Id")
  $gh = Get-Command gh -ErrorAction SilentlyContinue
  if ($gh) { [Console]::Out.WriteLine("  o aquí:  gh workflow run procesar_area.yml -f archivo=$archivo -f id=$Id") }
  exit 0
} catch {
  [Console]::Out.WriteLine('ERROR:' + $_.Exception.Message); [Console]::Out.Flush()
  exit 1
}
