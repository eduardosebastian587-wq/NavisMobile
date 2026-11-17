# NavisMobile — plan de optimización paso a paso

Documento autocontenido para una sesión nueva de Claude. No hace falta el historial de ninguna conversación.
Idioma de trabajo y de la interfaz: español. Usuario: Eduardo (precomisionamiento mecánico, proyecto Nueva Centinela).

Leer antes de empezar, en este orden:
1. [`AUDITORIA.md`](AUDITORIA.md) — estado del proyecto y hallazgos (se citan aquí como S1, F2, N1…).
2. [`PLAN_EJECUCION.md`](PLAN_EJECUCION.md) — especificación técnica del visor (formatos, IDs de Drive, módulos).
   Sigue vigente **salvo** lo que este documento corrige en «Cambios respecto del plan anterior».

## Objetivo

Una APK que Eduardo use en terreno para **verificar equipos y contrastar medidas** contra el modelo de la planta:
abrir un área, tocar un equipo y ver su TAG, buscar por TAG, medir, leer coordenadas de planta, marcar el equipo
como verificado, todo **sin conexión**. La calidad visual y las animaciones son secundarias.

## Modelo de Claude recomendado

| Fases | Modelo | Motivo |
|---|---|---|
| 0, 1, 3, 6 | **Claude Sonnet 5.5** (`claude-sonnet-5-5`) | Trabajo bien especificado: configuración, módulos de datos, interfaz, compilación. |
| 2, 4, 5 | **Claude Opus 5.5** (`claude-opus-5-5`) | Render y selección por GPU, formato de teselas con identificador por vértice, scripts de Blender/Navisworks: errores sutiles y caros de depurar. |

Si se prefiere un solo modelo para todo: Opus 5.5.

## Dónde se ejecuta cada fase

- **Nube** (sesión de Claude Code sobre este repo): fases 0, 1, 2, 3, 5 y 6. Hay Node 22, Java, Gradle, Chromium con
  Playwright; no hay Android SDK (se descarga, `PLAN_EJECUCION.md` §6) ni emulador.
- **PC de Eduardo** (Windows, Navisworks Manage 2027, Blender 5.2, 16 GB RAM): fase 4. Navisworks no existe fuera
  de Windows y el NWD es un formato cerrado. Se necesita una sesión de Claude con acceso a ese PC (Claude Code de
  escritorio o una carpeta conectada por Remote Control).

## Reglas de trabajo

- Una fase por sesión. Al terminar: ejecutar la verificación indicada, hacer commit, y actualizar la tabla
  «Estado» del final de este archivo.
- No dar una fase por terminada si su verificación no pasó; anotar qué falló.
- Ramas de trabajo + PR solo si Eduardo lo pide. No subir modelos, APK ni claves al repo.
- **No escribir en ningún archivo del repo el ID de Drive del NWD completo de planta** (hallazgo S2).
- Decisiones ya tomadas por Eduardo (no volver a preguntar): la app descarga los modelos desde Drive y los guarda
  en el teléfono; la APK lleva firma nueva; los `.nwd/.fbx/.blend` se quedan en Drive.

## Cambios respecto del plan anterior

| `PLAN_EJECUCION.md` decía | Ahora |
|---|---|
| Mallas unidas por material, sin identidad | Identificador de objeto por vértice + tabla de objetos (fase 4). |
| Dos escenas (Hito, 1313) | Además, escena «Planta» por áreas (fases 4–5). |
| APK debug compilada por CI | Firma fija propia (fase 3, S3). |
| APK copiada al repo en `apk/` | *Release* de GitHub o artefacto de CI (C5). |
| Modelo ligero del 1313 dentro del repo | Moverlo a Drive y borrarlo del repo (C4, S1). |
| Draco | Para los archivos nuevos: `EXT_meshopt_compression` + `KHR_mesh_quantization` (F4). Los GLB existentes con Draco se siguen leyendo. |
| Animaciones, correas en movimiento, recorridos | Pasan a la fase 6 (opcional). No bloquean la entrega de terreno. |

---

## Fase 0 — Decisiones previas (preguntar a Eduardo una sola vez)

1. **S1**: ¿el repo puede seguir público? Si no → pasarlo a privado (lo hace Eduardo en GitHub) y, en la fase 1,
   mover `modelos_movil/area1313_movil.glb` a Drive.
2. **S2**: ¿restringir el enlace del NWD completo?
3. ¿Qué áreas necesita primero en terreno? (lista de nodos del árbol de Navisworks, p. ej. `1241`, `1313`).
4. ¿El proyecto tiene licencia de Autodesk Construction Cloud / BIM 360? Si la tiene, la app oficial abre el NWD
   sin desarrollo y puede servir mientras se construye esto (`AUDITORIA.md` §5, opción A).

Las fases 1–3 no dependen de las respuestas 3 y 4; continuar con ellas.

## Fase 1 — Base del proyecto (nube)

1. `package.json`: `"private": true`, `"type": "module"`, quitar `"main"`, scripts `dev`, `build`, `test`.
2. `vite.config.js` con `base: './'`; copiar el decodificador Draco y el de meshopt a `public/`.
3. `.gitignore`: añadir `*.apk`, `*.aab`, `*.jks`, `*.keystore`, `android/app/release`, `android/build`,
   `android/capacitor-cordova-android-plugins`, `.DS_Store`.
4. Corregir `src/navegacion.js`:
   - **N1** `zoom()`: si `d < 1e-6`, salir sin hacer nada.
   - **N2** vista `planta`: usar `[0, 1, 0.0025]`.
   - **N3** `actualizar()`: aplicar `palanca`/`vertical` solo si `modo === 'caminar'`.
   - **N4** añadir `destruir()` que quite todos los escuchas (guardar las funciones al registrarlas).
   - **N5** en `wheel`, multiplicar `deltaY` por 16 si `deltaMode === 1`.
5. `pruebas/navegacion.test.mjs` con `node --test`: orbitar, panear (el punto sigue al dedo al píxel), pellizco,
   zoom con ancla en la cámara (no produce `NaN`), planta sin salto, palanca solo en modo caminar.
   Simular el DOM con un objeto `{clientWidth, clientHeight, addEventListener, setPointerCapture, getBoundingClientRect}`.
6. `README.md` breve (qué es, cómo compilar, gestos).
7. Si la respuesta a S1 fue «privado» o no hubo respuesta: quitar `modelos_movil/` del repo y pedir a Eduardo que
   suba el GLB a la carpeta de Drive del 1313; usar su ID en el catálogo.

**Verificación:** `npm test` pasa. `npm run build` puede seguir fallando por `main.js` (se resuelve en la fase 2).

## Fase 2 — Visor mínimo utilizable (nube)

Escribir según `PLAN_EJECUCION.md` §3–§4, **solo** esto: `public/catalogo.json`, `src/datos.js`, `src/visor.js`,
`src/main.js`. Dejar fuera `equipos.js`, `correas.js`, `recorridos.js` y la pestaña «Animación» (ocultarla).

Añadidos obligatorios:

1. **Presupuesto de memoria**: al cargar, sumar triángulos; si el modelo supera 4 M, avisar antes de abrir.
   Ocultar los modelos marcados `pesado` salvo que se active «Mostrar modelos pesados» en ajustes.
2. **Pérdida de contexto WebGL** (F5): escuchar `webglcontextlost`/`webglcontextrestored` y recargar la escena desde caché.
3. **Profundidad** (N6): `logarithmicDepthBuffer: true` o, si penaliza el rendimiento, calcular cerca/lejos sobre la
   caja de lo cargado. Medir ambos y dejar el mejor.
4. **Sin conexión** (F6): `navigator.storage.persist()`, botón «Descargar todo para terreno» por escena, e indicador
   por archivo (descargado / versión nueva / falta). La app debe abrir sin red si los archivos están en caché.
5. **CSP** en `index.html` (S5): `default-src 'self'; connect-src 'self' https://drive.usercontent.google.com https://*.googleusercontent.com; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; worker-src 'self' blob:; script-src 'self' 'wasm-unsafe-eval'`.
   Comprobar con una descarga real que Drive no redirige a otro dominio; ajustar si lo hace.
6. Liberar memoria al cambiar de escena: `geometry.dispose()`, `material.dispose()`, `renderer.renderLists.dispose()`.

**Verificación** (Playwright + Chromium, `PLAN_EJECUCION.md` §8): la escena Hito ligera se ve; se listan las capas;
tocar selecciona; medir entre dos puntos conocidos da la distancia esperada; corte funciona; segunda apertura sin
red (`context.setOffline(true)`) carga desde caché; consola sin errores. Guardar una captura.

## Fase 3 — APK firmada (nube)

1. `capacitor.config.json`, `npx cap add android`, `npx cap sync android` (`PLAN_EJECUCION.md` §6).
2. `AndroidManifest.xml`: `android:largeHeap="true"`, orientación libre, `keepScreenOn` mientras hay una escena abierta.
3. **Firma fija** (S3): generar una vez `navismobile.jks` con `keytool`. **No** va al repo. Entregárselo a Eduardo con
   `SendUserFile` e indicarle que lo guarde y lo cargue como secretos de GitHub (`KEYSTORE_BASE64`, `KEYSTORE_PASSWORD`,
   `KEY_ALIAS`, `KEY_PASSWORD`). `android/app/build.gradle` lee la firma de variables de entorno.
4. `.github/workflows/android.yml`: compila `assembleRelease` firmado y sube la APK como artefacto; con una etiqueta
   `v*` la publica como *Release*.
5. Compilar aquí y entregar la APK con `SendUserFile`.

**Verificación:** `unzip -l` muestra `assets/public/index.html`, `catalogo.json` y los decodificadores;
`apksigner verify --print-certs` muestra el certificado propio. Decir a Eduardo, sin rodeos, que la prueba en
teléfono queda a su cargo y pedirle: ¿abre?, ¿cuántos FPS marca `#info` con Hito ligero?, ¿sentido de giro al
caminar correcto? (ver `AUDITORIA.md` §4).

## Fase 4 — Convertir la planta por áreas con TAG (PC de Eduardo)

Entrada: `_MODELO_ORIGINAL_PLANTA/MODELO_FLUOR_RAPIDO_2026-08-30.nwd` (1,3 GB) en Drive para escritorio.
Herramientas existentes en `AREA_1313_MOLINOS/herramientas/`: `nwd_a_fbx.ps1`, `fbx_a_blender.py`. Leerlas primero.

1. **Inventario.** Abrir el NWD en Navisworks y obtener el árbol hasta el nivel de área
   (`TOTAL_PROYECTO_1.vue / AMSA_DMC / <sector> / <área> / <disciplina>`). Guardar `herramientas/planta/areas.csv`
   con: ruta del nodo, nombre, nº de ítems con geometría. Intentar automatizarlo con un script de la API .NET;
   si no, Eduardo copia la lista a mano.
2. **Origen común.** Reutilizar `navisblend_origin.json` si existe; si no, crearlo con el centro de la caja del
   documento redondeado a 1 m. Registrar también unidades y qué eje del modelo es Norte, Este y Elevación.
   **Todas** las áreas usan este mismo origen.
3. **Exportar un FBX por área** con `nwd_a_fbx.ps1` (selección = nodo de área). Empezar por un área pequeña y por
   las que pidió Eduardo. Un FBX de varias áreas juntas tiende a salir truncado: no agrupar.
   Comprobar que cada FBX contiene el nodo `Objects` y que su tamaño es coherente.
4. **Nuevo `herramientas/planta/fbx_a_tesela.py`** (Blender en segundo plano), derivado de `fbx_a_blender.py`.
   Por cada área:
   - recentrar con el origen común y pasar a metros;
   - definir «objeto» = nodo del FBX al nivel de equipo (probar con qué nivel del árbol el nombre coincide con el
     TAG; dejarlo como parámetro `--nivel`);
   - asignar a cada objeto un número entero `id` (1…N) y escribirlo en un atributo de vértice;
   - simplificar **por objeto** con un error máximo proporcional a su tamaño, hasta el presupuesto del área
     (3–4 M triángulos); eliminar objetos cuya caja mida < 3 cm;
   - unir por material y exportar GLB con el atributo personalizado `_ID` (`export_attributes=True`);
   - escribir `<area>_objetos.json`:
     `{"formato":"objetos-v1","area":"1241","objetos":[{"id":1,"nombre":"…","disciplina":"Mechanical","caja":[x0,y0,z0,x1,y1,z1],"tri":1234}]}`
     con la caja en coordenadas del visor (Three: `(x, z, -y)` respecto de Blender).
5. **Compresión**: `gltf-transform meshopt <entrada> <salida> --level medium` y comprobar con `gltf-transform inspect`
   que `_ID` sigue presente y **sin cuantizar** (los valores deben ser enteros exactos; si no, almacenarlo como
   `VEC2` de `uint16`: `id = x + y*65536`). Objetivo ≤ 25 MB por área.
6. **Maqueta general**: unir todas las áreas, simplificar a ≤ 1,5 M triángulos en total, sin `_ID` por objeto sino
   con `_ID` = índice del área. Sirve para orientarse y para elegir área tocándola.
7. Subir a Drive en una carpeta nueva `PLANTA_MOVIL/` (GLB + JSON) y generar `planta_indice.json`:
   `{"formato":"planta-v1","origen":{"este":…,"norte":…,"elevacion":…,"ejes":"…"},"general":{…},"areas":[{"id":"1241","nombre":"…","caja":[…],"glb":{"drive":"…","bytes":…},"objetos":{"drive":"…"}}]}`.
8. **Propiedades** (solo si el nombre del nodo no trae el TAG): en Navisworks, *Inspector de selección* → definir
   propiedades rápidas (TAG, descripción, servicio) → exportar CSV por área; `fbx_a_tesela.py --propiedades x.csv`
   las cruza por nombre. Un plugin propio queda como último recurso.

**Verificación por área:** nº de objetos del JSON ≈ nº de ítems del inventario; tres TAG elegidos por Eduardo
aparecen en el JSON; una cota conocida medida en Blender sobre la tesela difiere < 2 cm de la de Navisworks;
dos áreas vecinas cargadas juntas encajan sin desfase.

## Fase 5 — Funciones de terreno en la app (nube)

Requiere al menos un área de la fase 4. Para desarrollar sin esperar, generar una tesela sintética con `_ID`
(cubos con nombre) mediante un script de `@gltf-transform/core`.

1. **Escena «Planta»** en el catálogo, alimentada por `planta_indice.json` (se descarga desde Drive; así se añaden
   áreas sin recompilar). Al abrir: maqueta general. Tocar un área o elegirla en la lista → descarga/carga su
   tesela y libera la anterior. Nunca más de un área de detalle cargada.
2. **Selección por objeto**: en la pasada de identidad de `visor.js`, un `ShaderMaterial` que codifica `_ID` en RGB
   (una llamada de dibujo por malla). Resultado: `id` → fila de `<area>_objetos.json`.
3. **Resaltado**: atributo/uniforme `uSel` en un `onBeforeCompile` del material: los fragmentos cuyo `_ID` coincide
   se tiñen del color de acento; el resto se atenúa si «Aislar» está activo. No crear mallas nuevas.
4. **Pestaña «Propiedades»**: TAG/nombre, disciplina, dimensiones de la caja, coordenadas de planta del centro.
5. **Buscar** (campo en la pestaña «Capas»): por TAG o nombre, sobre el JSON del área cargada y, si no hay
   resultado, sobre un índice global liviano (`tag → área`) incluido en `planta_indice.json`. Elegir un resultado →
   carga el área si hace falta, encuadra la caja del objeto y lo resalta.
6. **Coordenadas de planta** (F3): `planta = origen + transformación(punto del visor)`. Mostrar Norte/Este/Elevación
   del punto tocado en `#info` y de ambos extremos en «Medir», más ΔN, ΔE, ΔElev y distancia.
7. **Lista de verificación**: en «Propiedades», botones *Conforme / Observación / No instalado* + nota. Guardar en
   `localStorage` por `área + id` con fecha. Colorear en el modelo (verde/ámbar/rojo) con un interruptor
   «Ver estado». Pestaña nueva «Verificación»: avance por área y «Exportar CSV» (compartir con `@capacitor/share`
   o descarga directa).
8. **Filtros por disciplina** en «Capas» (ocultar Piping, Electrical, etc.) usando la tabla de objetos.

**Verificación** (Playwright, con la tesela sintética y con un área real si existe): tocar un objeto devuelve el
`id` correcto en 20 puntos de prueba; buscar un TAG encuadra su caja; las coordenadas de planta de un punto conocido
coinciden con las de Navisworks (< 5 cm); cambiar de área tres veces no aumenta la memoria de forma sostenida
(`performance.memory` o `renderer.info.memory`); el CSV exportado contiene las marcas hechas.

## Fase 6 — Opcional

- `equipos.js`, `correas.js`, `recorridos.js` y pestaña «Animación» (`PLAN_EJECUCION.md` §2.4 y §4).
- Reexportar Hito y 1313 con meshopt + cuantización (mitad de memoria en GPU, F4).
- Actualizar `three` a la última versión y repetir las verificaciones de las fases 2 y 5.
- Fotos adjuntas a una observación (`@capacitor/camera`).

---

## Estado

Actualizar al cerrar cada fase (fecha, resultado de la verificación, pendientes).

| Fase | Estado | Notas |
|---|---|---|
| 0 Decisiones | Pendiente | |
| 1 Base | Pendiente | |
| 2 Visor mínimo | Pendiente | |
| 3 APK firmada | Pendiente | |
| 4 Planta por áreas | Pendiente | Requiere PC con Navisworks |
| 5 Funciones de terreno | Pendiente | |
| 6 Opcional | Pendiente | |
