# Contexto para la sesión local — instalar y probar NavisMobile en el teléfono

Autocontenido: no hace falta el historial de las sesiones anteriores. Idioma: español. Usuario: Eduardo (Fluor-Salfa, Nueva Centinela).
Sé breve y eficiente con los tokens: no releas archivos grandes, no leas `.glb`, `node_modules` ni `android/`.

## Qué es
NavisMobile (`com.navismobile.viewer`): visor 3D Android (Capacitor 8 + three.js + Vite). Descarga los modelos desde la carpeta de Drive
«proyecto animación» al abrir una escena y los guarda en el teléfono (Cache API). Catálogo: `public/catalogo.json`. Detalle: `README.md`, `PLAN_EJECUCION.md`.
- Repo: `eduardosebastian587-wq/NavisMobile` · rama de trabajo **`claude/dreamy-volta-6igg2d`** (no tocar `main` sin permiso del usuario).
- APK de depuración lista: `apk/NavisMobile-debug.apk` (última: commit `37ef32e`). Firma distinta a la APK original.
- Teléfono de pruebas: Xiaomi 14T Pro (2407FPN8EG), Android 16. Computador Windows `DESKTOP-K3D5DB7`, carpeta `C:\Users\Lenovo\NavisMobile`.

## Estado ya verificado (commit 64dec01, en el teléfono)
Descarga desde Drive, apertura de Hito Ligero (≈56–70 fps, 5 M tri) y Área 1313 Ligero (6,2 M tri, 44–54 fps), capas, orbitar/panear/zoom/pellizco,
caminar, fino, vistas, propiedades, aislar/ocultar/encuadrar/↶, corte X/Y/Z, medir, recorridos, correas, caché y reapertura sin descarga, sin errores WebGL/memoria.
Fallo ya corregido: Drive respondía 403/CORS al `fetch` del WebView → ahora la descarga va por red nativa (`@capacitor/filesystem`, `CapacitorHttp` en `src/datos.js`).
Ajustes del commit 37ef32e (**sin probar en teléfono**): el toque de selección ya no cambia de pestaña, tope de zoom 0,3 m, texto de la barra de tiempo al arrastrar con el recorrido en pausa.
Conocido y menor: `Error injecting safe area CSS` en logcat (sin efecto).

## Qué falta probar (pedir al usuario lo que requiera manos)
1. Instalar la APK nueva y confirmar que abre y que Hito/1313 siguen descargados (misma firma: `adb install -r`, sin desinstalar).
2. Doble toque sobre geometría: debe fijar el pivote **sin** saltar a la pestaña Propiedades.
3. Zoom: pellizco/rueda/modo Zoom no debe acercar a menos de ~0,3 m del punto de referencia.
4. Recorrido en pausa: arrastrar la barra de tiempo debe actualizar el texto «x.x s».
5. Giro de pantalla vertical/horizontal (el visor debe redimensionarse). **Solo con permiso del usuario** (cambia un ajuste del sistema).
6. Sensación táctil real y sentido natural de los giros (orbitar, caminar): lo juzga el usuario con los dedos.
7. Opcional, solo si lo anterior va bien y el usuario lo acepta: modelo **Alta** (Hito 12 M / 1313 21 M; riesgo de memoria) y modo avión real.

## Pasos
```powershell
cd C:\Users\Lenovo\NavisMobile
git fetch origin claude/dreamy-volta-6igg2d
git checkout claude/dreamy-volta-6igg2d
git pull origin claude/dreamy-volta-6igg2d
adb devices                                   # debe decir "device"
adb install -r apk\NavisMobile-debug.apk
adb shell monkey -p com.navismobile.viewer -c android.intent.category.LAUNCHER 1
adb logcat -c
adb logcat chromium:I Capacitor:I Capacitor/Console:V AndroidRuntime:E *:S > logcat_navis3.txt
```
Si `adb` falta: `winget install Google.PlatformTools`. Teléfono: Depuración USB activada y autorizada.

## Cómo automatizar sin dedos (lo que funcionó)
`adb input tap` está bloqueado en Xiaomi. Se usó el **depurador del WebView (CDP)**:
```powershell
adb shell "cat /proc/net/unix" | findstr webview_devtools_remote     # obtener el socket
adb forward tcp:9222 localabstract:webview_devtools_remote_<pid>
# luego http://localhost:9222/json  → webSocketDebuggerUrl; enviar Runtime.evaluate / Input.dispatchTouchEvent
```
Globales útiles en la página: `window.nav` (cámara/gestos), `window.visor` (mallas, fps), `window.E` (estado: escena, equipos, recorrido).
Para gestos reales sin CDP el usuario puede activar en Opciones de desarrollador «Depuración USB (ajustes de seguridad)».
No cambiar ajustes del sistema (modo avión, rotación) sin pedirlo al usuario.

## Qué entregar
Tabla OK/FALLA para los puntos 1–7, `logcat_navis3.txt` filtrado (`findstr /i "error exception webgl memory"`), capturas (`adb exec-out screencap -p > capN.png`),
y modelo/versión de Android. Si algo falla: causa probable y archivo (`src/main.js`, `src/navegacion.js`, `src/datos.js`, `src/visor.js`), **sin modificar código en esta sesión**:
el arreglo lo hace la sesión en la nube.

## Prompt para pegar en la sesión local
> Lee `docs/CONTEXTO_SESION_LOCAL.md` en la rama `claude/dreamy-volta-6igg2d` de NavisMobile. Instala `apk/NavisMobile-debug.apk` en mi teléfono por USB
> (`adb install -r`), ejecuta lo que puedas automatizar de los puntos 1–4, pídeme a mí lo que requiera dedos o cambiar ajustes, y entrégame la tabla OK/FALLA,
> el logcat filtrado y las capturas. No modifiques el código; sé breve.
