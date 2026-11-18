#requires -Version 5.1
<#  Compila y despliega NwMobileExport en %APPDATA%\Autodesk\ApplicationPlugins\NwMobileExport.bundle
    Navisworks debe estar cerrado (la DLL se carga solo al arrancar).  -NoBuild despliega .\build tal cual.  #>
param([int]$Year = 2027, [switch]$NoBuild, [switch]$Uninstall)
$ErrorActionPreference = 'Stop'
$Name = 'NwMobileExport'
$root = $PSScriptRoot
$dest = Join-Path $env:APPDATA "Autodesk\ApplicationPlugins\$Name.bundle"
if ($Uninstall) { if (Test-Path $dest) { Remove-Item -LiteralPath $dest -Recurse -Force; "Eliminado $dest" }; return }
if (Get-Process Roamer -ErrorAction SilentlyContinue) { throw 'Navisworks está abierto: ciérralo antes de instalar.' }
if (-not $NoBuild) {
    & dotnet build (Join-Path $root 'plugin\NwMobileExport.csproj') -c Release -o (Join-Path $root 'build') "-p:NavisworksDir=C:\Program Files\Autodesk\Navisworks Manage $Year" --nologo -v q
    if ($LASTEXITCODE -ne 0) { throw 'Falló la compilación.' }
}
$contents = Join-Path $dest "Contents\$Year"
New-Item -ItemType Directory -Force -Path $contents | Out-Null
Copy-Item (Join-Path $root "build\$Name.dll") (Join-Path $contents "$Name.dll") -Force
Copy-Item (Join-Path $root 'plugin\PackageContents.xml') (Join-Path $dest 'PackageContents.xml') -Force
Get-ChildItem -LiteralPath $dest -Recurse -File | Unblock-File
"Instalado en $dest. Abre Navisworks para cargarlo."
