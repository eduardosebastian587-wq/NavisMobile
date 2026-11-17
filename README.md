# NavisMobile

Visor móvil de modelos 3D (Android, Capacitor + Vite + three.js) para el proyecto Nueva Centinela. Se alimenta de la carpeta de
Google Drive **«proyecto animación»** (`1MMHybb61ep2gstNUdTF552_t81VwB8kw`): al abrir una escena descarga los modelos desde Drive,
los guarda en el teléfono y avisa cuando hay una versión nueva.

## Instalación de la APK
1. **Desinstale** la NavisMobile anterior (la firma es distinta, Android no permite actualizar encima).
2. Descargue `apk/NavisMobile-debug.apk` (o el artefacto *NavisMobile-debug* del flujo «APK Android» en GitHub Actions) y ábrala
   permitiendo instalar desde orígenes desconocidos.
3. Abra la app → pestaña **Escenas** → elija escena y calidad. La primera apertura descarga (17–47 MB); las siguientes usan la copia local.

## Cómo se alimenta de Drive
- `public/catalogo.json` lista escenas, modelos (`.glb`), recorridos, animaciones y datos de equipos con su ID de Drive.
- La descarga es directa y sin clave: `https://drive.usercontent.google.com/download?id=<ID>&export=download&confirm=t`
  (Drive devuelve CORS abierto, así que `fetch()` funciona en el WebView).
- La app compara `content-length`/`last-modified` con un `HEAD` y muestra «hay una versión nueva» si el archivo cambió.
  Sobrescribir el archivo en Drive (conserva el ID) basta para que el teléfono reciba la versión nueva **sin recompilar**.
- Si se **añaden o reemplazan archivos con otro ID**: `node tools/sincronizar_catalogo.mjs` actualiza IDs y tamaños por nombre
  y avisa de archivos nuevos (`*_web*.glb`, `*recorrido*.json`); luego recompile la APK (el catálogo va dentro de ella).
- El modelo ligero del Área 1313 (`modelos_movil/area1313_movil.glb`) se sirve desde este repo (raw.githubusercontent.com).
  Conviene copiarlo a la carpeta de Drive y cambiar su entrada en `catalogo.json` por un `drive` para un flujo 100 % Drive.
- Los `.nwd`, `.fbx`, `.blend` (GB) permanecen en Drive.

## Navegación
| Gesto | Orbitar | Panear | Zoom | Caminar |
|---|---|---|---|---|
| 1 dedo | gira alrededor del pivote | desplaza la vista | acerca/aleja hacia el punto tocado | mira alrededor |
| 2 dedos | paneo + pellizco con el punto bajo los dedos fijo (todos los modos) | | | |
| Doble toque | fija el pivote en el punto tocado | | | |
| Palanca / ⇧⇩ | — | — | — | avanza, retrocede, lateral, sube/baja |

Ratón: izq. según modo, der. paneo, central zoom, rueda = zoom hacia el cursor, Mayús = paneo.
**Fino**: sensibilidad, giro por pasos (0,5°–90°), desplazamiento por pasos (1 cm–25 m), lente (15–100°) y velocidad al caminar.
**↶ Cámara** deshace el último movimiento. Barra: Aislar, Ocultar, Mostrar todo, Encuadrar, Corte (plano X/Y/Z), Medir (dos toques).
Pestañas: Escenas, Capas (una por malla/material), Propiedades, Vistas (estándar y guardadas) y Animación (recorridos de cámara,
animaciones de equipos del 1313, correas en movimiento en Hito).

## Desarrollo
```
npm ci
npm run dev        # http://localhost:5173 ; si existe datos_locales/<archivo> se usa en vez de Drive
npm run build      # genera dist/
npx cap sync android && cd android && ./gradlew assembleDebug
```
Necesita Node 22, JDK 21 y Android SDK (plataforma 36, build-tools 36.0.0). El flujo `.github/workflows/android.yml` compila la APK en GitHub.

## Contenido
- `index.html`, `src/` — aplicación (`main.js` interfaz, `visor.js` render y selección por GPU, `navegacion.js`, `datos.js`, `equipos.js`, `correas.js`, `recorridos.js`).
- `public/catalogo.json`, `public/draco/` — catálogo y decodificador Draco (sin CDN: funciona sin conexión).
- `tools/` — sincronización del catálogo y descarga de herramientas desde Drive.
- `herramientas/hito`, `herramientas/area1313` — scripts y plantillas HTML con los que se generaron los datos.
- `datos/` — copia de referencia de los JSON pequeños.  `docs/` — estructura de la carpeta y los `.bat`.
- `modelos_movil/` — modelo ligero del Área 1313 (6 M triángulos).  `PLAN_EJECUCION.md` — plan de traspaso.

## Limitaciones
- Las pistas de animación `camara`, `disciplina:*`, `visible` y `resplandor` se ignoran (los modelos están unidos por material).
- No hay árbol de especificación ni propiedades de Navisworks ni conflictos (Clash): los datos del proyecto no los tienen.
