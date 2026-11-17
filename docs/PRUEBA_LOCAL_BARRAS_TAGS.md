# Prueba local: barras del sistema + tags en Capas (APK commit 72514c7 o posterior)

Verifica en el teléfono lo corregido en `72514c7`: (1) las barras de Android ya no tapan la app, (2) Capas muestra correas y equipos con tag y buscador.
Contexto general y comandos de `adb`/CDP: `docs/CONTEXTO_SESION_LOCAL.md`. Teléfono: Xiaomi 14T Pro, Android 16. No modificar código.

## Prompt para pegar en la sesión local (Claude Code en `C:\Users\Lenovo\NavisMobile`)
> Lee `docs/PRUEBA_LOCAL_BARRAS_TAGS.md` y `docs/CONTEXTO_SESION_LOCAL.md` en la rama `claude/dreamy-volta-6igg2d`. Haz `git pull`, instala `apk/NavisMobile-debug.apk`
> con `adb install -r`, ejecuta lo que puedas automatizar de las comprobaciones A y B, pídeme a mí lo que requiera mis dedos, y entrégame la tabla OK/FALLA, el logcat filtrado
> y capturas (vertical y horizontal). No modifiques código; sé breve.

## Instalación
```powershell
cd C:\Users\Lenovo\NavisMobile
git fetch origin claude/dreamy-volta-6igg2d && git checkout claude/dreamy-volta-6igg2d && git pull origin claude/dreamy-volta-6igg2d
adb devices
adb install -r apk\NavisMobile-debug.apk
adb shell monkey -p com.navismobile.viewer -c android.intent.category.LAUNCHER 1
adb logcat -c
adb logcat chromium:I Capacitor:I Capacitor/Console:V AndroidRuntime:E *:S > logcat_navis4.txt
```

## A. Barras del sistema (el usuario toca; capturar con `adb exec-out screencap -p > capA1.png`)
| # | Comprobación | Esperado |
|---|---|---|
| A1 | Vertical: barra de estado (hora, batería) arriba y botones de Android abajo | La app queda **entre** las barras; ninguna zona naranja/translúcida tapa botones |
| A2 | Tocar «Aislar», «Ocultar», «Mostrar todo», «Corte», «Medir», «↶ Cámara» y la pestaña «Escenas» | Todos responden |
| A3 | Horizontal (girar el teléfono, con permiso del usuario) | Nada queda bajo la cámara frontal/recorte ni bajo la barra de gestos; botones tocables |
| A4 | Botón ☰ | Oculta/muestra menús y sigue tocable |
| A5 | Fondo bajo las barras | Oscuro/negro, sin franja blanca |
Si algo sigue tapado: adjuntar captura y `adb shell wm size` + `adb shell dumpsys window | findstr /i "InsetsSource"`.

## B. Tags en Capas (abrir Hito → Ligero (5 M); luego Área 1313 → Ligero (6 M))
| # | Comprobación | Esperado |
|---|---|---|
| B1 | Pestaña Capas del Hito | Cuadro «Buscar capa o tag…»; sección «Correas (tag)» con `1241-CV-1305`…`1241-CV-1311` y «Sentido de carga»; sección «Capas del modelo» con 24 filas |
| B2 | Buscar `1306` | Solo queda `1241-CV-1306` |
| B3 | Tocar una correa | La cámara se encuadra sobre esa correa |
| B4 | Desmarcar la casilla de una correa | Esa correa (cinta animada) se oculta; marcarla la devuelve |
| B5 | Pestaña Capas del Área 1313 | Sección «Equipos (tag)» con ~19 partes (`portico`, `molino_1401`, `pluma_1404`…) |
| B6 | Tocar `portico` | Encuadra el pórtico; desmarcar su casilla lo oculta |
| B7 | Tocar un objeto en 3D → pestaña Propiedades | Muestra nombre, material, triángulos y, en el 1313, `tag`/`ruta`/`disciplina` si existen |
| B8 | Reabrir la app (cerrar por completo) | Capas igual; modelos siguen «Descargado ✓» (sin nueva descarga) |
| B9 | Estabilidad | Sin cierres; `logcat` sin `error|exception|webgl|memory` salvo `Error injecting safe area CSS` (conocido) |

## Entrega
Tabla A1–A5 y B1–B9 (OK/FALLA/observación), `logcat_navis4.txt` filtrado (`findstr /i "error exception webgl memory"`), capturas y modelo/Android del teléfono.
