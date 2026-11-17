# Plan: exportar cada equipo con su TAG (visualización tipo Navisworks)

Objetivo: que la pestaña **Capas** muestre un árbol por disciplina → equipo, con el **TAG** de cada equipo (p. ej. `1241-CV-1306`,
`1313-IA-21470`), que se pueda buscar, ocultar, aislar y encuadrar por equipo, y que al tocar un objeto en 3D se vea su tag y propiedades.
Ejecutable por Sonnet 5.5, en orden. Leer solo lo indicado en cada paso. Ejecución en el PC del usuario (Blender/Navisworks/Python), salvo los pasos marcados «nube».

## Diagnóstico (hechos verificados)
- Hito (`hito_web_5M.glb`): 24 mallas `UNION_MAT_<hex>`, **sin** datos asociados → no hay tags.
- Área 1313 (`area1313_movil.glb`): 36 mallas; cada una trae en `extras` datos de Navisworks (`tag`, `ruta` = «area 1313.nwd / … / 1313-IA-21470 / …», `disciplina`,
  `Elemento - …`) pero **solo del primer elemento** unido. La `ruta` confirma que Navisworks sí tiene el árbol y el tag.
- Correas: `datos/hito_correas.json` ya tiene 6 tags reales (`1241-CV-1305…1311`); equipos 1313: 19 partes con id.
- Causa: las piezas se unen por material para rendimiento (5–21 M triángulos) y se pierde la identidad.
- Scripts de origen (en `herramientas/`): `hito/exportar_hito_glb.py`, `hito/volcar_geometria_hito.py`, `hito/fbx_tags_correas.py`, `hito/extraer_correas_hito.py`,
  `area1313/unir_capas_1313_v4.py`, `area1313/stats_mallas_1313.py`, `area1313/nwd_a_fbx.ps1`.

## Diseño objetivo
1. **Unidad = equipo** (un TAG), no elemento ni material. Cada equipo = un nodo glTF con `extras {tag, nombre, disciplina, area, ruta, props{…}}`.
2. **Unión dentro del equipo**: las piezas de un mismo tag se unen **por material dentro del equipo** (pocas primitivas por nodo) → se conserva el rendimiento.
3. **Equipos pequeños/repetidos** (tuberías, soportes, barandas sin tag propio): agrupar por *tag padre* (línea, sistema) o por disciplina+área, para no pasar de ~2 000–5 000 nodos.
4. **Árbol** `tree.json` separado del GLB (carga rápida de la lista): `{nodos:[{id, tag, nombre, disciplina, padre, hijos, nodoGlb, tris, caja:[x0,y0,z0,x1,y1,z1]}]}`.
5. **Propiedades** en `props.json` (o binario si pesa >5 MB), indexadas por `id`; la app las carga al tocar/abrir la pestaña Propiedades, no al inicio.
6. Mantener los GLB actuales como respaldo («modo rápido»); el nuevo modo («por equipos») se añade como otro modelo en `catalogo.json`.

## Presupuesto (decidir con el usuario antes del paso 3)
- Teléfono objetivo: Xiaomi 14T Pro (Hito 5 M tri a 56–70 fps; 1313 6 M a 44–54 fps).
- Límite sugerido: ≤ 3 000 nodos, ≤ 25 MB por GLB, ≤ 6 M triángulos (versión móvil).
- Preguntar: ¿qué disciplinas por equipo? (mecánico/correas/estructura primero; tuberías agrupadas por línea) y ¿nivel del árbol que se muestra (Área/Sistema/Equipo)?

## Pasos
**1. Inventario de tags (PC, Navisworks/Python).** Exportar a CSV: por elemento → `ruta`, `tag`, `disciplina`, `material/color`, `triángulos`, `caja`. Contar tags únicos y elementos sin tag.
   Entregable: `datos/inventario_tags_<escena>.csv` + resumen (n.º tags, % elementos sin tag, top 20 tags por triángulos). Hecho si el resumen existe.
**2. Regla de agrupación.** Con el inventario, definir en `herramientas/agrupacion.json` cómo se forma cada equipo: campo del tag, tags que se agrupan en el padre, sin-tag → «Sin tag / <disciplina> / <área>».
   Hecho si cada elemento cae en exactamente un equipo.
**3. Exportador por equipo (PC, Blender o script del flujo actual).** Nuevo `herramientas/exportar_por_equipos.py` basado en `exportar_hito_glb.py` / `unir_capas_1313_v4.py`:
   leer el FBX/NWD convertido, agrupar según `agrupacion.json`, unir por material dentro de cada equipo, nombrar el nodo `EQ_<tag>`, escribir `extras`, aplicar Draco + simplificación como hoy
   (`gltf-transform simplify/draco`, receta en `PLAN_EJECUCION.md` §2.3), y generar `tree.json` y `props.json`. Probar primero con **un área pequeña** (las 6 correas + alimentadores del Hito).
   Hecho si el GLB abre en la APK y cada equipo tiene su `extras.tag`.
**4. Validar (PC).** Script `herramientas/validar_equipos.py`: nº de nodos, tags duplicados, nodos sin tag, triángulos totales vs. original (±2 %), tamaño de archivo. Hecho si pasa el presupuesto.
**5. Subir a Drive y catálogo (nube/PC).** Copiar `*_equipos.glb`, `*_tree.json`, `*_props.json` a la carpeta de la escena; en `public/catalogo.json` añadir modelo `{"id":"equipos","nombre":"Por equipos","archivo":…,"arbol":…,"props":…}`;
   `node tools/sincronizar_catalogo.mjs`. Hecho si el catálogo lista el modelo nuevo.
**6. App: árbol de capas (nube, `src/main.js`, `src/datos.js`, `src/visor.js`).**
   - Descargar `tree.json` junto al GLB (caché igual que hoy).
   - Pestaña Capas: árbol plegable Disciplina → Sistema → Equipo con tag, casilla de visibilidad por nodo (propaga a hijos), buscador por tag/nombre (ya existe `#filtroCapas`), tocar = encuadrar.
   - Tocar en 3D: `mallaEn` → subir al nodo `EQ_*` → seleccionar el equipo completo, mostrar tag en la barra `#info` y en Propiedades; Aislar/Ocultar operan por equipo.
   - Propiedades: cargar `props.json` perezosamente por `id`.
   Hecho si en el navegador (Playwright, datos en `datos_locales/`) el árbol lista los equipos y buscar un tag filtra.
**7. App: compilar y probar en teléfono.** `npm run build && npx cap sync android && ./gradlew assembleDebug`; probar con `docs/PRUEBA_LOCAL_BARRAS_TAGS.md` (ampliar con las comprobaciones del árbol).
**8. Iterar el presupuesto.** Si FPS < 40 o memoria alta: subir agrupación (menos nodos), bajar triángulos, o dividir por área (carga por escenas parciales).

## Riesgos
- Tags faltantes o inconsistentes en Navisworks → regla del paso 2 y reporte de «sin tag».
- Demasiados nodos → muchas llamadas de dibujo (draw calls) y menos FPS: por eso se unen por material **dentro** del equipo.
- Pérdida de identidad en selección: la selección por GPU ya identifica la malla; cada malla debe pertenecer a un solo equipo.
- Memoria del modelo «Alta»: no usar para la versión por equipos hasta validar el ligero.
