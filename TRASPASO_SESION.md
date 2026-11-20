# NavisMobile — traspaso de sesión (2026-11-20)

Documento autocontenido para continuar en una sesión nueva sin el historial. Idioma de trabajo: español.
Usuario: Eduardo (Fluor-Salfa, proyecto Nueva Centinela). PC con Windows: 16 GB de RAM, 12 hilos, Iris Xe, Navisworks Manage 2027 (licencia de educación).

## 1. Objetivo y arquitectura vigente
Extraer áreas del modelo Navisworks **sin saturar el PC** y publicarlas en la app NavisMobile (APK Capacitor + three.js, lee `areas/catalogo.json` de este repositorio, rama `main`).

| Paso | Dónde | Pieza |
|---|---|---|
| 1. Extracción | PC, Navisworks **oculto** (Automation API), prioridad baja, mitad de núcleos | `herramientas/navismobile-export/extraer_area_oculto.ps1` + entrada sin ventanas `NwMobileExport.Lote` (`plugin/PluginLote.cs`) |
| 2. Subida | Google Drive: `proyecto animación/NavisMobile/entrada` (carpeta id `1oS1rKvtUJx_vjEDAHMSapuujrcVJ2fBY`) | la copia el script al final (`<id>.nmraw` + `.piezas.json` + `.log`) |
| 3. Conversión y publicación | GitHub Actions **«Procesar área»** (`.github/workflows/procesar_area.yml`) | Drive → `raw_a_glb.py` (o `fbx_a_glb_stream.py`) → `optimizar.cjs` (Draco) → validación → `publicar_area.mjs` → commit en `main` |

Guía para el usuario: `herramientas/navismobile-export/LEEME_NUBE.md`.

### Lanzar «Procesar área» desde una sesión de Claude
```
gh api -X POST repos/eduardosebastian587-wq/navismobile/actions/workflows/procesar_area.yml/dispatches -f ref=main \
  -f 'inputs[archivo]=area1300.nmraw' -f 'inputs[id]=area1300nube' -f 'inputs[nombre]=Área 1300 — completa (procesada en la nube)'
```
- `archivo`: nombre del archivo, que se busca en la carpeta compartida «proyecto animación» (id `1MMHybb61ep2gstNUdTF552_t81VwB8kw`, sin entrar en `_por_borrar`). También acepta un enlace de Drive: un `.nmraw` lleva `inputs[piezas]` con el enlace de su `.piezas.json`; sin él, se trata como `.fbx`.
- Opcionales: `celda` (0.08), `ratio` (0.25), `publicar` (true).
- Seguir la ejecución con `gh api repos/.../actions/runs/<id>/jobs`.
  - `gh` solo funciona vía REST (`gh api`); GraphQL está bloqueado.
  - El token `GH_TOKEN` de la CLI no es válido para `gh auth`, pero `gh api` sí funciona.
- Se publica en una **rama**: hacer `git pull` en `main` después.

### Criterio del usuario para versiones de un área
«**Deja el que tenga más detalles**». Se publica con un id nuevo (`…nube`), se compara con la versión anterior y se quita la menos detallada (catálogo y archivos `areas/<id>_movil.glb` + `_elementos.json`). Comparar con `@gltf-transform/core` + `draco3dgltf` (triángulos) y con el JSON de elementos (elementos, TAG, con propiedades).

## 2. Estado del catálogo (`main`)
| id | nombre | origen |
|---|---|---|
| `area1300` | Área 1300 — completa | antigua (FBX), con 2 modelos: `completo` 35,4 MB y `equipos` 0,7 MB (+ `area1300_tags.json`) |
| `area1313` | Área 1313 — molinos | escena aparte con animaciones; **no tocar** |
| `hitom331` | Hito M33-1 — correas y domo | nube, desde `HITO_M33-1/modelo_fuente/hito.fbx` |
| `area1313nube` | Área 1313 — completa (nube) | nube, desde `Area_1313_ 2026-23-10_17_22.fbx`; reemplazó a `area1313d` |
| `area1251nube` | Área 1251 — completa (nube) | nube, desde `area1251.nmraw` (extracción oculta); reemplazó a `area1251` |
| `area1411nube` | Área 1411 — completa (nube) | nube, desde `area1411.nmraw` (extracción oculta); reemplazó a `area1411` |

## 3. Área 1300 — extracción hecha, versiones de la nube publicadas (2026-11-20)
- Extracción oculta OK (commit 7f1a8e3 confirmado): 12,8 min, 196 659 piezas, 106 864 276 triángulos, 7 968 TAG, `area1300.nmraw` 3 848 687 240 bytes, ya completo en Drive. Las rutas necesitan el nodo raíz del NWD: `MODELO_FLUOR_RAPIDO_2026-08-30.nwd/TOTAL_PROYECTO_2.vue/AMSA_DMC/1300|MODELO_FLUOR_RAPIDO_2026-08-30.nwd/TOTAL_PROYECTO_4.vue/AMSA_DMC/1300` (con `-ExcluirNombres "MecMiscellaneous,Unknown"`).
- «Procesar área» tarda ~3 min con este archivo. Versiones publicadas en `main` (triángulos medidos con gltf-transform + draco3dgltf):

| id | celda | ratio | triángulos | GLB | elementos |
|---|---|---|---|---|---|
| `area1300` (antigua, `_movil_v2.glb`) | — | — | 12 464 388 | 35,4 MB | 10 583 |
| `area1300nube` | 0,08 | 0,25 | 4 245 432 | 16,8 MB | 7 699 |
| `area1300nube60` | 0,08 | 0,6 | 4 496 980 | 17,8 MB | 7 699 |
| `area1300nube04` | 0,04 | 0,6 | 7 045 003 | 27,0 MB | 7 714 |

- Hallazgos: `celda` es el parámetro que más pesa (en `raw_a_glb.py` la celda efectiva por pieza es `min(celda, 2.ª dimensión/3)`); `ratio` casi no cambia nada. El filtro `--min 0.06` (fijo en `procesar_area.yml`) descarta 2 997 piezas pequeñas, por eso los elementos no suben. El workflow aborta si el GLB supera 95 MB.
- **Decisión pendiente del usuario:** la antigua sigue ganando en detalle. Opciones: relanzar con `celda` 0,02 (GLB estimado 40–50 MB), bajar `--min`, o dejar la antigua y borrar `area1300nube`/`nube60`/`nube04`. La antigua tiene además «Solo equipos» y `area1300_tags.json`. No se ha reemplazado ni borrado nada.

## 4. Datos y rutas útiles
- **Drive «proyecto animación»** (compartida por enlace; descarga sin login: `https://drive.usercontent.google.com/download?id=<ID>&export=download&confirm=t`, funciona incluso con archivos en la papelera):
  - `_MODELO_ORIGINAL_PLANTA/MODELO_FLUOR_RAPIDO_2026-08-30.nwd`: 1 321 320 793 bytes, sano.
  - `AREA_1313_MOLINOS/modelo_fuente/area 1313.nwd` (99 MB), `HITO_M33-1/modelo_fuente/hito M33-1.nwd` (121 MB).
  - `_por_borrar/` (~5,2 GB), incluido el FBX truncado del 1251 (sin `Connections`). El usuario lo borrará a mano.
- **Drive «Proyecto REA»** (no compartida por enlace): `NavisBlend/` (plugin Navisworks→Blender con instanciado), `Navisworks apk/base.apk` (APK original).
- **PC del usuario:**
  - repositorio: `C:\Users\Lenovo\NavisMobile_app`;
  - Drive montado en `C:\Users\Lenovo\Streaming de Google Drive\Mi unidad`;
  - modelo sano copiado y verificado en `F:\proyecto animación\MODELO_FLUOR_RAPIDO_2026-08-30.nwd` (SHA-256 `BED775434BFC3CF0A18713E167B45E69BE7D5135A23FD19739B15ED64D4D906A`); el dañado quedó como `…2026-08-30.dañado.nwd`;
  - modelo de trabajo diario: `F:\MODELO_FLUOR_RAPIDO_2025-12-17.nwd` (abre bien).
- **Rendimiento medido** (extracción oculta en el PC; nube = GitHub Actions):

  | Área | Extracción en el PC | Nube |
  |---|---|---|
  | 1313 (`area 1313.nwd`) | 5,5 min, Roamer 1,2 GB, PC usable | 1–2,5 min por área |
  | 1251 (modelo completo) | 13 min, 3,8 GB | ídem |
  | 1411 | 3,2 min | ídem |

## 5. Lecciones (para prompts de Cowork)
- No cerrar ni matar Navisworks sin preguntar: un reinicio durante un guardado dañó un NWD.
- No abrir el modelo completo en dos Navisworks a la vez (no cabe en 16 GB).
- **No mover, renombrar ni borrar nada dentro de carpetas de Drive:** eso mandó `area1251.nmraw` a la papelera.
- Comprobar las subidas en drive.google.com, no en el explorador de Windows (que muestra también archivos pendientes).
- Las llamadas largas de Cowork a la PC cortan a los 80 s, pero el proceso sigue: no relanzar.
- Prompts para Cowork: `herramientas/navismobile-export/PROMPT_COWORK*.md` (v5 es el vigente).

## 6. Verificar el plugin sin Windows
El plugin (`net48`) no se puede compilar aquí contra las DLL reales. Para comprobar que compila:
1. Instalar .NET 8 con `dotnet-install.sh`.
2. Crear una réplica mínima de `Autodesk.Navisworks.Api` (firmas usadas por `Plugin.cs`, `Exportador.cs` y `PluginLote.cs`) y dos ensamblados vacíos con los nombres `Autodesk.Navisworks.ComApi` e `Interop.ComApi`.
3. Compilar: `dotnet build NwMobileExport.csproj -p:NavisworksDir=<carpeta de la réplica>`.

La compilación real la hace `Install.ps1` en el PC (última: 0 errores).

## 7. Otros pendientes (menores)
- Borrar a mano `_por_borrar` en Drive (~5,2 GB).
- `export.log` del plugin no recibe líneas desde la instancia oculta (misma virtualización). Cosmético: ahora cada extracción tiene su `<id>.nmraw.log`.
