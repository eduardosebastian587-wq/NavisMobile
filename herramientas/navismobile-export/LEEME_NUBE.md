# NavisMobile — extracción sin bloquear el PC y conversión en la nube

## Por qué
La extracción saturaba el PC (16 GB de RAM, Iris Xe) por dos motivos:
1. **Navisworks quedaba bloqueado**: el plugin extraía dentro de la misma ventana que usas (~1 h).
2. **La conversión pesada corría en el PC**: Blender llegó a picos de 27 GB de RAM (`hito.informe.txt`).

Ahora la cadena se parte en dos:

| Paso | Dónde | Qué hace |
|---|---|---|
| 1. Extracción | PC, Navisworks **oculto** con prioridad baja y la mitad de los núcleos | NWD del área → `<id>.nmraw` + `.piezas.json` → carpeta `proyecto animación/NavisMobile/entrada` de Drive |
| 2. Conversión y publicación | **GitHub Actions** (gratis, 4 CPU / 16 GB) | Drive → GLB → simplificación + Draco → validación → `areas/catalogo.json` |
| 3. App | Teléfono | **Escenas › Recargar** |

## Paso 1 — en el PC (primera vez: probar)
1. Cierra Navisworks y reinstala el plugin (incluye la nueva entrada sin interfaz `NwMobileExport.Lote`):
   ```
   powershell -ExecutionPolicy Bypass -File herramientas\navismobile-export\Install.ps1
   ```
2. Prueba con un NWD de área pequeño (no el modelo completo de 1,3 GB):
   ```
   powershell -ExecutionPolicy Bypass -File herramientas\navismobile-export\extraer_area_oculto.ps1 -Nwd "F:\proyecto animación\AREA_1313_MOLINOS\modelo_fuente\area 1313.nwd" -Id area1313 -Prueba
   ```
   - Debe terminar con `LISTO:` y dejar `area1313.nmraw` en `%LOCALAPPDATA%\NwMobileExport\lote\area1313`.
   - Mientras corre, tu Navisworks normal y el resto del PC siguen disponibles.
3. Si funciona, repite **sin** `-Prueba`: copia el resultado a Drive.
4. **Si falla con «no ejecutó NwMobileExport.Lote»** (el plugin no carga en modo oculto): usa el plan B,
   que usa el exportador FBX nativo de Navisworks (el mismo de `nwd_a_fbx.ps1`):
   ```
   ... extraer_area_oculto.ps1 -Nwd "...\area 1313.nwd" -Id area1313 -Formato fbx
   ```
   El paso 2 acepta igual el `.fbx` (pierde las propiedades SmartPlant de cada TAG, conserva TAG y colores).
5. Revisa el registro del plugin si algo falla: `%LOCALAPPDATA%\NwMobileExport\` (archivos `.log`).

Notas:
- Usa NWD **por área** (~100 MB). Dos Navisworks con el modelo completo no caben en 16 GB.
- `-Raices "0:27/6/0/0"` exporta solo esos nodos; sin `-Raices` exporta todo el documento.
- `-Nucleos 4` limita los núcleos que usa la instancia oculta (por defecto la mitad).

## Paso 2 — desde el celular
GitHub › **NavisMobile** › **Actions** › **Procesar área** › **Run workflow**:
- `archivo`: `area1313.nmraw` (o `hito.fbx`, o un enlace de Drive a un FBX).
- `id`: `area1313` · `nombre`: «Área 1313».
- El resto con sus valores por defecto. Tarda ~5 min; al terminar el área aparece en la app.

La carpeta de Drive debe seguir **compartida por enlace** (la nube descarga sin iniciar sesión).

## Medido en la nube (2026-11-20)
| Entrada | Conversión | Optimización | Resultado |
|---|---|---|---|
| `hito.fbx` real (2,16 GB, 27,9 M triángulos) | 94 s, 1,0 GB RAM | 13 s, 1,3 GB RAM | `hito_movil.glb` 10,3 MB, 2,7 M triángulos, 2 382 elementos, 0 errores |
| `.nmraw` sintético (720 MB, 20 M triángulos, sin simplificar) | 21 s, 1,7 GB RAM | 49 s, 3,2 GB RAM | 26 MB |
