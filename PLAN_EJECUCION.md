# NavisMobile — plan de ejecución (traspaso entre sesiones)

Documento autocontenido. Quien lo ejecute **no necesita el historial de la conversación anterior**.
Idioma de trabajo y de la interfaz: español. Usuario: Eduardo (Fluor-Salfa, proyecto Nueva Centinela).

## 0. Encargo

1. Optimizar la APK `base.apk` (NavisMobile, `com.navismobile.viewer`) para que **se alimente de los archivos de la carpeta de
   Google Drive «proyecto animación»** (`1MMHybb61ep2gstNUdTF552_t81VwB8kw`).
2. Añadir **funciones de navegación** (orbitar, panear, zoom, caminar, movimiento fino) para lograr movimientos más exactos.
3. Dejar el **proyecto completo en este repositorio** (`eduardosebastian587-wq/NavisMobile`, público, rama `main`).
4. «REA» = carpeta de Drive `Proyecto REA` (`1tGcILEXkEoiKmUTdkFnP_D8cnsTwGNyn`): contiene `PLAN_NavisBlend.md`
   (`1R5bmY1U2wsE4hOVupojVoR-9tX4dU_ZT`), `NavisBlend/` y `Navisworks apk/base.apk` (`1-hq1HE7SQMswIZtOsZ56d0dvuaYXaeYg`).

Decisiones ya aceptadas por el usuario (no volver a preguntar):
- La app **descarga los modelos desde Drive al abrir una escena** y los guarda en el teléfono (no se empaquetan en la APK).
- La APK nueva irá con **otra firma** (no hay clave original): el usuario desinstalará la anterior.
- Los `.nwd`, `.fbx`, `.blend` (GB) **se quedan en Drive**; al repo van fuentes, scripts, JSON y documentación.

## 1. Estado actual del repositorio

| Archivo | Estado |
|---|---|
| `index.html` | **Hecho.** Maqueta de la interfaz (pestañas Escenas/Capas/Propiedades/Vistas/Animación, barra, panel de navegación). Los `id` de este archivo son el contrato con `src/main.js`. |
| `src/estilos.css` | **Hecho.** |
| `src/navegacion.js` | **Hecho, sin probar.** Clase `Navegacion` (ver §5). |
| `modelos_movil/area1313_movil.glb` | **Hecho.** Área 1313 simplificada: 6,0 M triángulos, 17 MB, Draco (el original tiene 21 M). |
| `package.json` | Dependencias instaladas: `three@0.170`, `@capacitor/core|android|cli@8`, `vite@8`, `@gltf-transform/cli`. Falta añadir scripts `dev`/`build`. |
| `src/main.js`, `src/visor.js`, `src/datos.js`, `src/equipos.js`, `src/correas.js`, `src/recorridos.js` | **Pendiente** (§4). |
| `public/catalogo.json`, `public/draco/` | **Pendiente** (§3). |
| `android/`, `capacitor.config.json`, `.github/workflows/` | **Pendiente** (§6). |
| `herramientas/`, `docs/` | **Pendiente** (§7). |

## 2. Hechos verificados (no hace falta re-investigar)

### 2.1 La APK original
- Capacitor + Vite + three.js; el JS viene minificado y **sin fuentes** → se reescribe el visor, no se parchea.
- Lee `models/index.json` → por modelo `model.glb`, `tree.json`, `props.bin`, `views.json`, `meta.json`. Solo trae 4 modelos de
  ejemplo ajenos al proyecto (architecture, gatehouse, mep, structure). Los datos del proyecto **no tienen** `tree.json` ni
  `props.bin` (las mallas están unidas por material), así que «Árbol» pasa a ser «Capas» (una por malla/material).
- Funciones a conservar: aislar, ocultar, mostrar todo, encuadrar, corte (X/Y/Z + invertir), medir, vistas, recorrido,
  botón ☰ para ocultar menús. «Conflictos» (Clash XML) se elimina: no hay datos.
- `appId` `com.navismobile.viewer`, `appName` `NavisMobile`, `webDir` `dist`. Estética: fondo `#1b1e24`, acento `#4aa3ff`.

### 2.2 Acceso a Drive
- La carpeta está compartida por enlace. Descarga directa **sin clave ni login**:
  `https://drive.usercontent.google.com/download?id=<ID>&export=download&confirm=t`
- La respuesta trae `access-control-allow-origin: *`, `content-length`, `last-modified` y `accept-ranges: bytes`, y admite
  `HEAD` → **`fetch()` funciona directo desde el WebView** (no hace falta plugin nativo) y se puede detectar si un archivo
  cambió comparando `last-modified` + `content-length`.
- Al sobrescribir un archivo desde Drive para escritorio se **conserva el ID** → la app recibe la versión nueva sin recompilar.
- Listado de una carpeta sin clave de API (para el script de catálogo):
  `https://drive.google.com/embeddedfolderview?id=<ID_CARPETA>` devuelve HTML con `id="entry-<ID>"` y
  `class="flip-entry-title">nombre`.
- En esta nube: `curl` llega a Drive, `dl.google.com`, `maven.google.com`, `services.gradle.org`, npm. Hay Java, Node 22,
  Gradle 8.14.3 en `/opt/gradle`; **no hay Android SDK** (hay que bajarlo, §6).

### 2.3 IDs de Drive que usa la app

**HITO_M33-1 / convertidos_blender** (carpeta `1hXOqD2XSBIL5tIVNijl1unl86dgoMZQu`)

| Archivo | ID | Bytes | Nota |
|---|---|---|---|
| `hito_web_5M.glb` | `1KBg3nLHi5xpA3L2uE5UEXk3NtSLPcpA1` | 17 991 852 | 5,0 M tri, Draco. **Modelo por defecto en móvil.** |
| `hito_web.glb` | `17vMz70kZwvMVObYbdLW-ynaKwOaoqv9v` | 31 662 072 | 12,3 M tri. Calidad alta (avisar del consumo de memoria). |
| `hito_sueltos.glb` | `14oB2Qoro31XgCZOaPqIpFMJ7Y06B38CF` | 575 940 | Elementos sueltos (capa opcional, oculta por defecto). |
| `hito_escena_video.json` | `1ElaFhmVtcIIFkgSD-7I879SnpJr2T3_V` | 45 412 | Materiales, `soles[].hacia_sol_three`, `cielo`, `camara.lente_mm`. |
| `hito_recorrido.json` | `1yawuCXCdrsZEQ6icm5ELLDn_6TuWt15d` | 39 468 | Recorrido 25 s. |
| `hito_recorrido_50s.json` | `1fu7vwBtxyMoDppvrNYMRTi9BGrLttlsV` | 99 726 | Recorrido continuo 66 s. |
| `hito_recorrido_correas.json` | `1e04npkGpO9fmT0sp6lzjhIwpibPAjENl` | 71 202 | Recorrido de correas 45 s. |
| `hito_correas.json` | `1vUP540NkQT96PqHMt-eJEU0kF8RMvkMc` | 8 991 | Líneas centrales de las 6 correas. |

**AREA_1313_MOLINOS** (carpeta `1i8hrtOqsLmtepYtAn5kAUrhbaDf8LcMk`; `convertidos_blender` = `1pKUki46-Yvu0kjT0lQZOlgGXxs7pn-dk`)

| Archivo | ID | Bytes | Nota |
|---|---|---|---|
| `area1313_web_v4.glb` | `1-dAhbih23mGeuOojZJyj5z5P7bhuPNcx` | 46 950 328 | 21,0 M tri, Draco + `KHR_materials_specular`. Solo «calidad alta». |
| `area1313_web_v4_equipos.bin` | `1nxZ3oALCMQf2TagVZJy1TA67Doe9wkSd` | 8 246 756 | Geometría de las partes animadas. |
| `area1313_web_v4_equipos.json` | `1KoHOZXvBup82z2BqZZkhtQCcaHDvvbMC` | 6 100 | Índice de partes (idéntico al de v1–v3). |
| `animaciones.json` | `1K7hxq6BrmVH8FnvPbxGKqyFB_FXwb82v` | 32 497 | 7 animaciones. |
| `area1313_recorrido.json` | `1ceTpXi-sVQ9cUjB6z7NVf1RNbZKOd25k` | 91 638 | Recorrido. |
| `area1313_recorrido_90s.json` | `1sAwO_jCNClN-sqgZtMdeGyagXa6wLklv` | 135 236 | Recorrido 90 s (`desfase_ciclo_s`). |

Modelo ligero del Área 1313 (no está en Drive): `modelos_movil/area1313_movil.glb` de este repo, accesible en
`https://raw.githubusercontent.com/eduardosebastian587-wq/NavisMobile/main/modelos_movil/area1313_movil.glb`
(comprobar que esa URL responde con CORS antes de depender de ella; si no, empaquetarlo en `public/`).
Se generó con: `gltf-transform simplify area1313_web_v4.glb s.glb --ratio 0.2 --error 0.0008`, luego
`simplify s.glb s2.glb --ratio 0.6 --error 0.004`, luego `draco s2.glb area1313_movil.glb --quantize-position 14`
(con `NODE_OPTIONS=--max-old-space-size=12000`). Sugerir al usuario copiarlo a Drive para un flujo 100 % Drive.

Otras carpetas: `herramientas` Hito `1qQkwp-b8YMo3q_YxHk8jmgJN2XWXjWdQ`, `herramientas` 1313 `1MJ-mh_-L4LU0jUR4dqL-52_eyZJNK008`,
raíz Hito `1VVo20Hb69eCJBjNai6feqKIqMGLeEcDB`, `LEEME_ESTRUCTURA.md` `1EtKt5Mci-5abdhg_KYcSHb2WVhv6govd`.
Visores web de referencia (de ahí salen los algoritmos de §2.4): `HITO_M33-1/index_hito.html` `1sbFgPetcNOceoPttNE9Rz_mDp9WIj68G`,
`herramientas/plantilla_visor_1313.html` `1U1PBq3yH2HmPjlHj92ZP84UF8tFbO8Tu`, `herramientas/generar_visor_1313.py` `1O9NddEQspXjhS2_gkv56fb0S1JslpvW9`.

### 2.4 Formatos de datos

- **GLB**: exportados desde Blender, +Y arriba, metros, ya recentrados. Requieren `DRACOLoader` (copiar el decodificador de
  `node_modules/three/examples/jsm/libs/draco/gltf/` a `public/draco/`; no usar CDN: la app debe funcionar sin conexión).
  Nodos `UNION_MAT_<hex>[_A<opacidad>]` (Hito: 24 mallas) y además `V4_<disciplina>_<hex>` y `*_relleno` (1313: 36).
  Los colores del video ya vienen horneados en los materiales del GLB. `MAT_C6B88D` es el terreno.
- **Recorridos** (`formato: recorrido-hito-v1`): `fps` (30), `trayectoria_three` = lista de `[px,py,pz, mx,my,mz]`
  (posición de cámara y **punto de mira**, en coordenadas de Three). Duración = `(n-1)/fps`. Interpolar linealmente entre
  cuadros. Opcional `desfase_ciclo_s`: tiempo del ciclo de equipos = `t - desfase`.
- **Equipos 1313** (`formato: equipos-1313-v1`): `TX,TY,TZ` y `partes[]` con `id`, `padre`, `pivote [x,y,z]`,
  `estirable {y1,y2}` (opcional), `mallas[] {color:int, disciplina, vert, pos, nor}`. En el `.bin`: posiciones
  `Float32Array(buf, pos, vert*3)` y normales `Int8Array(buf, nor, vert*3)` normalizadas; sin índices (3 vértices por triángulo).
  Montaje (copiado de `plantilla_visor_1313.html`, función `prepararGrua`):
  - grupo `marco` con `rotation.y = Math.PI` y `position.set(TX, TZ, -TY)`; dentro, todo en coordenadas del visor v4;
  - cada parte es un `Group` situado en su pivote (`pivote` propio, o el del padre, o 0); posición = pivote − pivote del padre;
    las mallas van dentro desplazadas `−pivote`; guardar `rest = nodo.position.clone()`;
  - parte **estirable** (gancho + cable): la malla cuelga del contenedor del padre con posición `−pivote del padre`, se guarda
    `pos0` y al animar Δy se recalcula cada Y: `y + dy * (y<=y1 ? 1 : y>=y2 ? 0 : (y2-y)/(y2-y1))`; `frustumCulled=false`.
  - Jerarquía: `portico › carro_1 › gancho_1p/gancho_1a/m_carro`, `portico › m_ruedas`, `pluma_1404 › gancho_1404/m_1404`,
    `pluma_1405 › gancho_1405/m_1405`, `molino_1401 › molino_1401_giro`, `molino_1402 › molino_1402_giro`
    (`gancho_2p`, `gancho_2a`, `carro_2` tienen 0 triángulos).
  - Perfiles PBR por disciplina: ver `PERFILES` y `POR_COLOR` en `generar_visor_1313.py`.
- **animaciones.json**: `animaciones[] {id, nombre, descripcion, duracion, bucle?: una|bucle|vaiven, pistas[]}`;
  pista = `{objetivo, propiedad, interpolacion?: suave|lineal|escalon|curva, claves: [[t, [x,y,z]], …]}`.
  `posicion` = Δ metros sobre `rest`; `rotacion` = Δ grados (`rotation.set(x,y,z,'XYZ')`). «suave» = smoothstep por tramo.
  En el modelo unido solo se pueden aplicar las pistas cuyo `objetivo` es una parte de equipos. Las pistas `camara`,
  `disciplina:*`, `visible`, `resplandor` **se ignoran** (decirlo en la interfaz). Las 7: `ciclo-completo` (60 s),
  `portico-rieles` (44), `molinos-giro` (6, bucle), `pescantes` (44), `ganchos` (26), `ejemplo-izaje` (16), `secuencia-4d` (20).
- **hito_correas.json**: `correas[] {tag, sentido_carga, tramos[] {tipo: carga|retorno, ancho_m, puntos[[x,y,z]], largo_m}}`
  en **ejes de Blender** → Three = `(x, z, -y)`. Cada tramo avanza en el orden de sus puntos. Dibujar una cinta fina sobre la
  línea central (ancho `ancho_m`, +3 cm) con textura de franjas cuyo `offset` se anima (~3 m/s).
- **hito_escena_video.json**: usar `soles[].hacia_sol_three` (dirección) y `energia` para la luz direccional; `camara.lente_mm`
  y `sensor_mm` para el campo de visión inicial. Sin sombras por defecto (rendimiento).

## 3. Catálogo (`public/catalogo.json`)

```json
{"version": 1, "carpeta_drive": "1MMHybb61ep2gstNUdTF552_t81VwB8kw",
 "escenas": [
  {"id": "hito", "nombre": "Hito M33-1 — área seca", "descripcion": "Correas, alimentadores, domo, harneros, puente grúa",
   "modelos": [{"id": "movil", "nombre": "Ligero (5 M)", "archivo": {"drive": "1KBg…", "nombre": "hito_web_5M.glb", "bytes": 17991852}},
               {"id": "alta", "nombre": "Alta (12 M)", "pesado": true, "archivo": {"drive": "17vM…", "nombre": "hito_web.glb", "bytes": 31662072}}],
   "escena": {"drive": "1Ela…", "nombre": "hito_escena_video.json"},
   "recorridos": [{"drive": "…", "nombre": "hito_recorrido.json"}, …],
   "correas": {"drive": "…", "nombre": "hito_correas.json"},
   "capas_extra": [{"nombre": "Elementos sueltos", "archivo": {"drive": "…", "nombre": "hito_sueltos.glb"}}]},
  {"id": "area1313", "nombre": "Área 1313 — molinos", "descripcion": "Molinos ML-1401/1402, pórtico CN-1406, pescantes CN-1404/1405",
   "modelos": [{"id": "movil", "nombre": "Ligero (6 M)", "archivo": {"url": "https://raw.githubusercontent.com/…/area1313_movil.glb", "nombre": "area1313_movil.glb", "bytes": 17371648}},
               {"id": "alta", "nombre": "Alta (21 M)", "pesado": true, "archivo": {"drive": "1-dA…", "nombre": "area1313_web_v4.glb"}}],
   "equipos": {"json": {…}, "bin": {…}}, "animaciones": {…}, "recorridos": […]}]}
```

`tools/sincronizar_catalogo.mjs`: recorre las carpetas con `embeddedfolderview`, actualiza IDs/bytes por **nombre de archivo**
y avisa de archivos nuevos `*_web*.glb` / `*recorrido*.json`. Uso: `node tools/sincronizar_catalogo.mjs`.

## 4. Módulos por escribir

**`src/datos.js`** — `urlDe(archivo)` (Drive o `url`); `obtener(archivo, {progreso})` → `ArrayBuffer`: busca en Cache API
(`caches.open('navismobile-v1')`, clave `https://cache.local/<id>`), si no está descarga leyendo `response.body` por trozos
(progreso con `bytes`) y guarda; metadatos (`last-modified`, tamaño) en `localStorage`. `comprobar(archivo)` hace `HEAD` y
devuelve `al_dia | cambio | sin_conexion | no_descargado`; si hay cambio, se vuelve a descargar. `borrar(archivo)`.
Llamar a `navigator.storage.persist()`. En desarrollo (`import.meta.env.DEV`) intentar antes `/datos/<nombre>` (carpeta
local servida por un plugin de Vite) para probar sin red.

**`src/visor.js`** — `WebGLRenderer` (antialias, `localClippingEnabled`), `PerspectiveCamera`, luz hemisférica + direccional,
entorno `RoomEnvironment` con PMREM. **Render bajo demanda** (solo si hay cambios o animación) y resolución dinámica:
`pixelRatio` 1 mientras se interactúa, `min(devicePixelRatio, 2)` en reposo. Carga con `GLTFLoader.parse` + `DRACOLoader`.
**Selección sin raycast** (con 5–21 M de triángulos el raycast de Three tarda segundos): renderizar 1×1 píxel con
`camera.setViewOffset(w,h,x,y,1,1)` a un `WebGLRenderTarget`:
 - pasada de **profundidad**: `ShaderMaterial` propio con `clipping: true` que empaqueta `gl_FragCoord.z` en RGBA
   (`enc = fract(z*vec4(1,255,65025,16581375)); enc -= enc.yzww*vec4(1/255,1/255,1/255,0)`), fondo blanco; leer con
   `readRenderTargetPixels`, desempaquetar, y `new Vector3(ndcX, ndcY, z*2-1).unproject(camera)` → punto del mundo
   (z ≥ 1 = sin impacto). Esto da `puntoEn(x, y)` para pivote, zoom dirigido y medición;
 - pasada de **identidad**: cambiar temporalmente el material de cada malla por un `MeshBasicMaterial` con color = índice.
 Los ayudantes (marca de pivote, líneas de medida, cintas de correa) van en la capa 1 y se excluyen de estas pasadas.

**`src/equipos.js`**, **`src/correas.js`**, **`src/recorridos.js`** — según §2.4. El reproductor de recorrido pone
`nav.bloqueada = true`, aplica posición/mira por cuadro y, en el 1313, mueve los equipos con `t - desfase_ciclo_s`.

**`src/main.js`** — conecta todo con los `id` de `index.html`:
- *Escenas*: tarjeta por escena con botones por modelo, estado de caché (descargado / hay versión nueva / tamaño),
  «Actualizar», «Borrar descarga» y «Abrir GLB del teléfono» (`<input type=file>` + `URL.createObjectURL`).
- *Capas*: lista de mallas con muestra de color, nº de triángulos y casilla de visibilidad; tocar = seleccionar.
- *Propiedades*: nombre, material, triángulos, dimensiones de la caja, color, metal/rugosidad.
- *Vistas*: Planta, Frente, Atrás, Izquierda, Derecha, Iso; «Guardar vista actual» (por escena, en `localStorage`).
- *Animación*: recorridos (▶/⏸, barra de tiempo, velocidad 0,25–2×), animaciones del 1313 (lista, ▶/⏸, bucle),
  casilla «Correas en movimiento».
- Barra: Aislar, Ocultar, Mostrar todo, Encuadrar (selección o todo), Corte (`renderer.clippingPlanes`, un plano, eje X/Y/Z,
  deslizador sobre la caja del modelo, invertir), Medir (dos toques → línea + etiqueta en m), ↶ Cámara (`nav.deshacer()`).
- Panel de navegación: botones de modo (`data-m`), «Fino» abre `#fino`; `#sens` → `nav.sens`; `data-g` → `nav.girar(±paso)`;
  `data-d` → `nav.mover(±paso)`; `#fov`; `#vel` → `nav.velocidad`. En modo caminar mostrar `#palanca` (joystick que escribe
  en `nav.palanca`, valores −1..1) y `#vert` (`nav.vertical` ±1 mientras se mantiene pulsado).
- Marca de pivote: esfera pequeña en `nav.mira` cuyo tamaño escala con la distancia, visible al orbitar.
- `#info`: triángulos, FPS aproximado, distancia al pivote.

## 5. `src/navegacion.js` (ya escrito)

`new Navegacion(camera, dom, {alCambiar, puntoEn(x,y), alTocar(x,y), alInteractuar(activo), alModo(m)})`.
Propiedades: `mira`, `modo` (`orbitar|panear|zoom|caminar`), `sens`, `velocidad`, `palanca` (Vector2), `vertical`, `bloqueada`.
Métodos: `fijarModelo(caja)`, `fijarModo(m)`, `girar(guiñada, cabeceo, sobreSi)`, `mover(dx,dy,dz,horizontal)`,
`panearPx`, `zoom(factor, ancla)`, `fijarPivote(p)`, `encuadrar(caja, dir)`, `vista(nombre)`, `estado()/aplicar(e, suave)`,
`recordar()/deshacer()`, `actualizar(dt)` (llamar cada cuadro; devuelve si hubo cambio).
Gestos: 1 dedo según el modo; 2 dedos = paneo + pellizco con el punto bajo los dedos fijo; doble toque = fija el pivote en el
punto tocado; ratón: izq. según modo, der. paneo, central zoom, rueda = zoom hacia el cursor, Mayús = paneo.
**Sin probar**: verificar en particular el sentido de los giros y que el zoom no atraviese el modelo.

## 6. Compilación de la APK

1. `package.json`: `"dev": "vite"`, `"build": "vite build"`, `"type": "module"`. `vite.config.js` con `base: './'`.
2. `capacitor.config.json`: `{"appId":"com.navismobile.viewer","appName":"NavisMobile","webDir":"dist"}`.
3. `npm run build && npx cap add android && npx cap sync android`.
4. Android SDK: bajar `commandlinetools-linux` de `https://dl.google.com/android/repository/`, aceptar licencias con
   `sdkmanager --licenses`, instalar `platform-tools`, `platforms;android-<la que pida Capacitor 8>`, `build-tools;<idem>`;
   `ANDROID_HOME` y `android/local.properties` (`sdk.dir=…`). Gradle hereda el proxy de `JAVA_TOOL_OPTIONS`; si falla TLS,
   leer `/root/.ccr/README.md`.
5. `cd android && ./gradlew assembleDebug` → `android/app/build/outputs/apk/debug/app-debug.apk`. Entregar al usuario
   copiándola al repo en `apk/NavisMobile-debug.apk` (o como artefacto del flujo de CI) y con `SendUserFile`.
6. `.github/workflows/android.yml`: Node 22 + JDK 21 + `android-actions/setup-android`, `npm ci`, `npm run build`,
   `npx cap sync android`, `./gradlew assembleDebug`, `actions/upload-artifact`.
7. Icono: reutilizar los `mipmap-*` de la APK original (extraer con `unzip base.apk 'res/mipmap*'`).

## 7. Contenido del repositorio además de la app

- `herramientas/hito/` y `herramientas/area1313/`: scripts `.py/.ps1/.js/.bat` y plantillas HTML de las dos carpetas
  `herramientas` de Drive (sin `_respaldos`). Bajar cada archivo con la URL de §2.2; listar con `embeddedfolderview`.
- `datos/`: los JSON pequeños de §2.3 (recorridos, correas, escena, animaciones, equipos.json) como copia de referencia.
- `docs/`: `LEEME_ESTRUCTURA.md`, `PLAN_NavisBlend.md`, y los `.bat` de las raíces.
- `README.md`: qué es, cómo instalar la APK, cómo se alimenta de Drive, cómo actualizar el catálogo, cómo compilar,
  tabla de gestos de navegación.
- `.gitignore`: `node_modules`, `dist`, `android/app/build`, `android/.gradle`, `datos_locales`.

## 8. Pruebas antes de entregar

1. Navegador (Playwright + Chromium ya instalados; ver instrucciones del entorno): `npm run dev`, abrir la escena Hito
   ligera con los datos servidos en local, capturar pantalla y revisar que el modelo se ve, que las capas se listan y que
   no hay errores en consola. WebGL por software es lento con 5 M de triángulos: dar tiempo de espera amplio.
2. Probar por script: orbitar/panear/zoom (eventos de puntero sintéticos), `puntoEn` sobre un punto conocido, medir,
   corte, reproducir un recorrido y la animación `ciclo-completo` del 1313 (comprobar que el pórtico se mueve).
3. Probar una descarga real desde Drive en el navegador (CORS) y la segunda apertura desde caché.
4. Compilar la APK y comprobar con `unzip -l` que incluye `assets/public/index.html`, `catalogo.json` y `draco/`.
   No hay emulador en la nube: decir claramente al usuario que la prueba en teléfono queda a su cargo.

## 9. Entrega

- Commits en `main` de `eduardosebastian587-wq/NavisMobile` (repositorio vacío al empezar; no crear PR salvo que se pida).
- Informar al usuario: qué quedó hecho y probado, qué no se pudo probar (teléfono real), que debe desinstalar la app
  anterior, y que el modelo ligero del 1313 conviene copiarlo a la carpeta de Drive.
