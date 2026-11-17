# NavisMobile — auditoría del proyecto

Fecha: 2026-11-17 · Alcance: repositorio `eduardosebastian587-wq/NavisMobile` (commit `d64737e`), carpetas de Drive
relacionadas y el archivo `MODELO_FLUOR_RAPIDO_2026-08-30.nwd` · Plan de acción derivado: [`PLAN_OPTIMIZACION.md`](PLAN_OPTIMIZACION.md)

## 1. Resumen

El proyecto está en **fase inicial**: hay una maqueta de interfaz, un módulo de navegación y un plan detallado, pero
**la app todavía no compila ni se puede ejecutar** (faltan 6 de los 7 módulos y todo el proyecto Android).
Lo que existe está bien encaminado: el módulo de navegación pasó las pruebas que le hice y el plan técnico es sólido.

Los tres hallazgos que más pesan:

1. **Confidencialidad**: el repositorio es público y contiene un modelo 3D de la planta más los identificadores de
   descarga de otros modelos en Drive. Requiere una decisión tuya antes de seguir.
2. **El diseño actual no sirve para verificar equipos**: los modelos se exportan con las mallas unidas por material,
   así que al tocar un equipo la app no puede saber cuál es (no hay TAG ni propiedades).
3. **El modelo completo de planta no cabe en un teléfono como un solo archivo**: hay que dividirlo por áreas (§5).

## 2. Qué se revisó y cómo

| Comprobación | Resultado |
|---|---|
| Inventario del repo | 8 archivos, 1 commit. Código propio: `index.html`, `src/estilos.css`, `src/navegacion.js` (247 líneas). |
| `npm ci` | Correcto. |
| `npx vite build` | **Falla**: `Failed to resolve /src/main.js` (el archivo no existe). |
| `npm audit` | 4 vulnerabilidades moderadas, todas en la cadena de `@gltf-transform/cli` (herramienta de desarrollo; no viaja en la APK). |
| `npm outdated` | `three` 0.170 → 0.187 disponible. Capacitor 8 y Vite 8 al día. |
| `gltf-transform inspect` del GLB | 6,0 M triángulos, 8,4 M vértices, posiciones y normales en `float32`. |
| Prueba de `navegacion.js` | Script con eventos de puntero simulados (orbitar, panear, zoom, pellizco, caminar, vistas). Detalle en §4. |
| Acceso público | `raw.githubusercontent.com/.../area1313_movil.glb` responde 200 sin credenciales y con CORS abierto. |
| NWD en Drive | 1 321 320 793 bytes. Cabecera `#LcUStream-V1.1 binary double release` (formato propietario de Navisworks). Descargable por enlace sin login. |

No se pudo probar: nada en teléfono real ni en WebView (no hay app que ejecutar), ni la conversión del NWD (requiere
Navisworks en Windows).

## 3. Hallazgos

Severidad: **A** = resolver antes de continuar · **M** = resolver durante el desarrollo · **B** = mejora.

### Seguridad y confidencialidad

| # | Sev. | Hallazgo | Recomendación |
|---|---|---|---|
| S1 | A | Repo **público** con `modelos_movil/area1313_movil.glb` (geometría de la planta) y `PLAN_EJECUCION.md` con ~20 IDs de Drive de modelos descargables sin login. Cualquiera puede bajar esos modelos. | Confirmar si la información de ingeniería del proyecto puede ser pública. Si no: pasar el repo a privado y sacar el GLB del historial. |
| S2 | A | El NWD completo de planta (1,3 GB) está compartido como «cualquiera con el enlace». | Mantener su ID fuera del repo (este informe no lo incluye). Valorar restringir el enlace: la app no necesita el NWD, solo los derivados. |
| S3 | M | El plan propone APK *debug* compilada en CI: cada máquina genera una firma distinta, así que cada actualización obligaría a desinstalar y se perderían las descargas. | Crear un almacén de claves propio una vez y guardarlo en los secretos de GitHub; firmar siempre con él. |
| S4 | M | `.gitignore` no excluye `*.jks`, `*.keystore`, `*.apk`, `android/app/release`. | Añadirlos antes de crear el proyecto Android. |
| S5 | B | Sin `Content-Security-Policy` en `index.html`. | Añadir una CSP que solo permita `self` y `drive.usercontent.google.com`. |

### Funcionalidad y arquitectura

| # | Sev. | Hallazgo | Recomendación |
|---|---|---|---|
| F1 | A | La app no existe aún: faltan `main.js`, `visor.js`, `datos.js`, `equipos.js`, `correas.js`, `recorridos.js`, `catalogo.json`, `android/`. | Fases 1–3 del plan. |
| F2 | A | **Sin identidad de equipos**. Los GLB tienen una malla por material (`UNION_MAT_*`); la pestaña «Propiedades» solo podría mostrar color y nº de triángulos. Para verificar en terreno se necesita TAG por objeto. | Exportar con un identificador por vértice y una tabla de objetos (plan, fase 4). |
| F3 | A | **Sin coordenadas de planta**. Los modelos están recentrados y el desplazamiento no se guarda en ningún archivo que la app lea. Sin él no se pueden mostrar Norte/Este/Elevación para replantear. | Guardar el origen común en el catálogo y mostrar coordenadas de planta al tocar y al medir. |
| F4 | M | Consumo de memoria: el GLB «ligero» ocupa 17 MB en disco pero al decodificar Draco son ~200 MB de vértices + ~70 MB de índices en GPU. El de «calidad alta» (21 M triángulos) ronda 1 GB: cerrará la app en la mayoría de los teléfonos. | Cuantizar atributos (posición 16 bits, normal 8 bits: la mitad de memoria) y fijar un presupuesto de ~4 M triángulos cargados a la vez. |
| F5 | M | Sin manejo de `webglcontextlost` previsto. En Android con modelos grandes ocurre al cambiar de app. | Recargar la escena al recuperar el contexto. |
| F6 | M | Caché de modelos en Cache API: Android puede vaciarla si falta espacio. En faena sin señal eso deja la app sin modelos. | `navigator.storage.persist()` (ya previsto) + botón «Descargar todo para terreno» + aviso de estado. Migrar a `@capacitor/filesystem` si se observa desalojo. |
| F7 | B | Selección por render de 1 píxel (plan §4): correcta, pero cada toque dibuja el modelo entero una vez más. | Aceptable; limitar a un cálculo por gesto (ya está así en `navegacion.js`). |

### Calidad del código y del repositorio

| # | Sev. | Hallazgo | Recomendación |
|---|---|---|---|
| C1 | M | Sin pruebas automáticas. | Convertir mi script de prueba de navegación en prueba del repo (`npm test`). |
| C2 | M | `package.json`: sin scripts `dev`/`build`, sin `"type": "module"`, sin `"private": true`, `"main": "index.js"` inexistente. | Corregir en fase 1. |
| C3 | M | Sin `README.md` ni CI. | Fases 1 y 3. |
| C4 | M | Binario de 17 MB dentro de git; cada versión nueva engorda el historial para siempre. | Mover modelos a Drive o a *Releases* de GitHub. |
| C5 | B | El plan indica entregar la APK copiándola al repo (`apk/`). | Publicarla como *Release* o artefacto de CI. |
| C6 | B | `PLAN_EJECUCION.md` indica trabajar directo sobre `main`. | Ramas + revisión antes de fusionar. |

## 4. Prueba de `src/navegacion.js`

| Caso | Resultado |
|---|---|
| Orbitar (arrastre horizontal y vertical) | Correcto: el modelo sigue al dedo. |
| Panear 100×50 px | Correcto y exacto: el punto se desplaza exactamente esos píxeles. |
| Rueda y pellizco | Correcto: abrir los dedos de 200 a 300 px reduce la distancia ×0,667. |
| Zoom repetido 400 veces | Se detiene a 5 cm del pivote; no lo atraviesa. |
| Caminar con palanca | Correcto: 4,00 m en 1 s a 4 m/s. |
| Caminar, mirar con el dedo | Arrastrar a la derecha gira la vista a la **izquierda** (convención «arrastrar el mundo»). Es coherente, pero conviene que lo valides en el teléfono; es un cambio de signo. |

Defectos encontrados (todos menores):

- **N1** `zoom()` con el ancla en la posición exacta de la cámara divide por cero y deja la cámara en `NaN` (pantalla negra). Confirmado. Arreglo: salir si la distancia es ~0.
- **N2** La vista «planta» queda 0,0015 rad del polo, pero el límite de cabeceo es 0,002: el primer giro posterior produce un salto pequeño (8 cm a 170 m). Arreglo: usar 0,0025.
- **N3** `actualizar()` aplica la palanca en cualquier modo; si la interfaz no la pone a cero al salir de «caminar», la cámara sigue desplazándose. Arreglo: aplicar solo en modo caminar.
- **N4** No hay método para quitar los escuchas de eventos (necesario si se recrea el visor).
- **N5** La rueda asume `deltaY` en píxeles (solo afecta a ratón en escritorio).
- **N6** Plano cercano/lejano: con un modelo de planta de kilómetros la relación lejos/cerca crece y aparecerá parpadeo de superficies. Arreglo: `logarithmicDepthBuffer` o límites por área cargada.

## 5. Cómo ver `MODELO_FLUOR_RAPIDO_2026-08-30.nwd` dentro de la APK

**Ninguna app propia puede abrir un NWD directamente.** Es un formato cerrado de Autodesk; solo lo leen Navisworks
(Windows) y los servicios de Autodesk. Siempre hay un paso de conversión. Las opciones:

| Opción | Qué es | A favor | En contra |
|---|---|---|---|
| **A. App de Autodesk** (Autodesk Construction Cloud / BIM 360 móvil) | Subir el NWD a Autodesk Docs y abrirlo con la app oficial. | Cero desarrollo; propiedades completas. | Necesita licencia del proyecto y que el cliente permita subirlo; no es tu APK; el uso sin conexión depende de la licencia. Conviene preguntar si el proyecto ya la tiene. |
| **B. Visor de Autodesk dentro de la APK** (Platform Services) | Autodesk convierte el NWD en la nube y su visor web se incrusta en la app. | Lee NWD con propiedades. | De pago por conversión, pensado para uso con conexión, y el modelo se sube a servidores externos. Mala opción para faena. |
| **C. Planta dividida por áreas con TAG** *(recomendada)* | Desde Navisworks se exporta cada área; se simplifica y se guarda como GLB con un identificador por objeto y una tabla de TAG. La app carga una maqueta general liviana y descarga el detalle del área que se abre. | Funciona sin conexión, usa la cadena que ya tienes (NWD → FBX → Blender → GLB), permite buscar por TAG y marcar verificaciones. | La conversión se hace en tu PC con Navisworks (unas horas de máquina la primera vez) y hay que repetirla cuando cambie el modelo. |
| D. Un solo GLB de toda la planta | Lo mismo que hoy, a escala de planta. | Simple. | Inviable: solo el área 1313 tiene 21 M de triángulos; la planta completa son cientos de millones. Reducido a lo que aguanta un teléfono (~4 M) los equipos quedan irreconocibles. |

### Diseño recomendado (opción C)

- **Dos niveles de detalle.** *Maqueta general*: toda la planta en ≤ 1,5 M triángulos, sin detalle fino, para
  orientarse. *Área*: cada nodo de área del árbol de Navisworks (p. ej. `1241`, `1313`) en ≤ 3–4 M triángulos, con
  todos sus equipos reconocibles. Se carga un área a la vez; al cambiar, se libera la anterior.
- **Identidad de equipos.** Las mallas siguen unidas por material (rendimiento), pero cada vértice lleva el número
  de su objeto. Un archivo aparte por área (`<area>_objetos.json`) da nombre/TAG, disciplina y caja de cada número.
  Con eso la app puede: tocar → ver TAG; buscar TAG → volar al equipo y resaltarlo; aislar por disciplina.
- **Coordenadas de planta.** El origen común (`navisblend_origin.json`) va en el catálogo; la app muestra
  Norte / Este / Elevación del punto tocado y de cada extremo de una medición.
- **Lista de verificación.** Por equipo: Conforme / Observación / No instalado + nota. Se guarda en el teléfono y
  se exporta a CSV para el informe.
- **Sin conexión.** Botón «Descargar todo para terreno» que baja la maqueta general y las áreas elegidas antes de subir a faena.

Sobre «replantear»: la app permitirá leer coordenadas del modelo y medir distancias entre elementos, que es lo que
sirve para contrastar contra ejes y puntos de referencia marcados en terreno. **No reemplaza al instrumento
topográfico**: el GPS del teléfono tiene un error de varios metros y no funciona bajo techo, así que la app no
ubicará al usuario dentro del modelo con precisión.

### Lo que hace falta de tu parte

- Un PC con Navisworks Manage (ya lo tienes: 2027) para la exportación; no se puede hacer en la nube.
- La lista de áreas que necesitas primero en terreno, para priorizar.
- Decisiones S1 y S2 de este informe.
