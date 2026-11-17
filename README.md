# NavisMobile

Visor 3D para Android (Capacitor + three.js) de los modelos del proyecto Nueva Centinela (Fluor-Salfa).
Se alimenta de la carpeta de Drive **«proyecto animación»** (`1MMHybb61ep2gstNUdTF552_t81VwB8kw`): los modelos se
descargan al abrir una escena y quedan en el teléfono (Cache API); la app avisa cuando hay versión nueva.

## Instalar
Descargar `apk/NavisMobile-debug.apk` (o el artefacto de GitHub Actions), **desinstalar la NavisMobile anterior**
(la firma es distinta) e instalar. Requiere Android 7+ (API 24) y conexión solo la primera vez por modelo.

## Uso
Pestañas: **Escenas** (abrir/actualizar/borrar descargas, o abrir un `.glb` del teléfono), **Capas**, **Propiedades**,
**Vistas** (estándar y guardadas), **Animación** (recorridos, equipos del Área 1313, correas en movimiento).
Barra: Aislar, Ocultar, Mostrar todo, Encuadrar, Corte (X/Y/Z), Medir (2 toques), ↶ Cámara. ☰ oculta los menús.

### Gestos
| Gesto | Acción |
|---|---|
| 1 dedo (modo Orbitar / Panear / Zoom / Caminar) | según el modo elegido |
| 2 dedos | paneo + pellizco (el punto bajo los dedos queda fijo) |
| Doble toque | fija el pivote en el punto tocado |
| Toque | selecciona el objeto |
| Botón «Fino» | giro y desplazamiento por pasos (0,5°–90°, 1 cm–25 m), sensibilidad, lente y velocidad |
| Caminar | 1 dedo mira; palanca mueve; ⇧/⇩ sube y baja |
| Ratón | izq. según modo · der. paneo · central zoom · rueda zoom al cursor · Mayús paneo |

## Cómo se alimenta de Drive
`public/catalogo.json` lista escenas, modelos y archivos (ID de Drive, nombre, bytes). La descarga usa
`https://drive.usercontent.google.com/download?id=<ID>&export=download&confirm=t` (carpeta compartida por enlace, con CORS).
Si se **sobrescribe** un archivo en Drive el ID se conserva y la app detecta el cambio (`last-modified`/tamaño).
Para archivos nuevos: `node tools/sincronizar_catalogo.mjs` (actualiza IDs/bytes y avisa de `*_web*.glb`/`*recorrido*.json` nuevos),
luego recompilar. El modelo ligero del Área 1313 se sirve desde este repositorio (`modelos_movil/`); conviene copiarlo a Drive.

## Desarrollo y compilación
```bash
npm ci
npm run dev                      # servidor local; /datos/<archivo> sirve ./datos_locales/ para trabajar sin red
npm run build && npx cap sync android
cd android && ./gradlew assembleDebug   # APK en android/app/build/outputs/apk/debug/
```
Necesita JDK 21 y Android SDK (plataforma 36). `.github/workflows/android.yml` compila la APK en CI.

## Contenido
`src/` app · `public/` catálogo y decodificador Draco · `modelos_movil/` GLB ligero 1313 · `tools/` scripts de catálogo/descarga ·
`herramientas/` scripts originales de Drive (Hito y Área 1313) · `datos/` JSON de referencia · `docs/` documentación y visores web de referencia · `apk/` APK de depuración.
