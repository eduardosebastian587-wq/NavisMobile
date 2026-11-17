# Prueba de la APK en el teléfono (sesión local, Windows)

Objetivo: instalar `apk/NavisMobile-debug.apk` en el teléfono por USB, abrirla, verificar que funciona y recoger los registros.
Rama: `claude/dreamy-volta-6igg2d`. Carpeta local: `NavisMobile`.

## 0. Requisitos (una sola vez)
1. Teléfono: Ajustes → Acerca del teléfono → tocar 7 veces «Número de compilación» → activar **Depuración USB** en Opciones de desarrollador.
2. Cable USB de datos (no solo carga). Al conectar, aceptar «¿Permitir depuración USB?» en el teléfono (marcar «Permitir siempre»).
3. Computador: `git` y `adb` (Platform-Tools de Android). Si falta adb: `winget install Google.PlatformTools` y reabrir PowerShell.

## 1. Traer la APK
```powershell
cd <ruta>\NavisMobile
git fetch origin claude/dreamy-volta-6igg2d
git checkout claude/dreamy-volta-6igg2d
git pull origin claude/dreamy-volta-6igg2d
dir apk\NavisMobile-debug.apk
```
Debe existir (≈ 4,8 MB).

## 2. Verificar el teléfono
```powershell
adb devices
```
Debe salir `<serie>  device`. Si dice `unauthorized`, aceptar el aviso en el teléfono; si no sale nada, cambiar cable/puerto.

## 3. Desinstalar la versión anterior (firma distinta)
```powershell
adb uninstall com.navismobile.viewer
```
(`Failure [DELETE_FAILED_INTERNAL_ERROR]` o «Unknown package» = no había ninguna; continuar.)

## 4. Instalar y abrir
```powershell
adb install -r apk\NavisMobile-debug.apk
adb shell monkey -p com.navismobile.viewer -c android.intent.category.LAUNCHER 1
```
Esperado: `Success`. Si falla con `INSTALL_FAILED_USER_RESTRICTED`, activar «Instalar vía USB» en Opciones de desarrollador.

## 5. Capturar registros mientras se prueba
En otra ventana de PowerShell:
```powershell
adb logcat -c
adb logcat chromium:I Capacitor:I Capacitor/Console:V AndroidRuntime:E *:S > logcat_navis.txt
```
(Detener con Ctrl+C al terminar.)

## 6. Lista de comprobaciones en el teléfono
Anotar OK / FALLA / observación:
1. La app abre y se ven las pestañas y la tarjeta de cada escena (Hito, Área 1313) con su estado.
2. **Hito → Ligero (5 M) → Abrir**: aparece la barra de descarga (≈ 18 MB) y el modelo se muestra. Anotar segundos de descarga y FPS (texto inferior).
3. Pestaña **Capas**: 24 capas; marcar/desmarcar una la oculta.
4. **Orbitar** con 1 dedo; **Panear**; **Zoom**; pellizco con 2 dedos; **doble toque** fija el pivote. ¿El sentido de los giros es natural? ¿El zoom atraviesa el modelo?
5. Modo **Caminar**: palanca y ⇧/⇩ mueven; arrastrar con un dedo mira.
6. **Fino**: pasos de giro/desplazamiento, sensibilidad, lente.
7. Tocar un objeto → pestaña Propiedades con datos. **Aislar**, **Ocultar**, **Mostrar todo**, **Encuadrar**, **↶ Cámara**.
8. **Corte** (X/Y/Z, deslizador, Invertir) y **Medir** (2 toques → metros).
9. Pestaña **Animación**: recorrido ▶/⏸, barra de tiempo, velocidad; «Correas en movimiento».
10. Cerrar la app por completo (deslizar) y reabrir: Hito Ligero debe abrir **sin descargar** (desde caché) y mostrar «Descargado ✓».
11. Modo avión → abrir Hito Ligero: debe abrir igual (sin conexión).
12. **Área 1313 → Ligero (6 M)**: descarga y abre; Animación → `ciclo-completo` ▶ mueve el pórtico.
13. ☰ oculta/muestra menús. Girar el teléfono (vertical/horizontal): el visor se redimensiona bien.
14. Estabilidad: ¿se cierra o se queda en negro con alguna escena? (No probar «Alta» salvo que lo anterior vaya bien.)

## 7. Entregar resultados
Guardar capturas (`adb exec-out screencap -p > cap1.png`) y `logcat_navis.txt`, y pegar a Claude: tabla OK/FALLA, modelo del teléfono, versión de Android y errores del logcat (`grep -i -E "error|exception|webgl|out of memory" logcat_navis.txt`).
