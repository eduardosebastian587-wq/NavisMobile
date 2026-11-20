# Prompt para Cowork v5: reintentar el área 1300

Copia todo lo que está debajo de la línea en una sesión de Cowork que tenga acceso a este PC.

---

Eres mi asistente en mi PC con Windows (usuario `Lenovo`, 16 GB de RAM, Navisworks Manage 2027). Trabaja en español. Ya autoricé todo lo de este texto: no hace falta que me preguntes salvo donde se indica.

## Contexto
- **Qué falló:** en la sesión anterior, la extracción oculta del área 1300 terminó en 7 s con
  `ERROR:No se generó …\AppData\Local\NwMobileExport\lote\area1300\area1300.nmraw`,
  sin dejar registro ni estado.
- **Causa probable:** este Cowork ejecuta los comandos desde una app empaquetada, y Windows virtualiza `AppData` para ella. La carpeta `lote\area1300` que creó el script no existía para el Navisworks oculto, así que el plugin no pudo escribir el error (seguramente un nombre de ruta que no coincidía).
  - Lo mismo explica que siempre faltara la primera línea `Lote:` del registro.
- **Corregido en `main`** (commit 7f1a8e3 «Extracción oculta: carpeta de trabajo fuera de AppData…»):
  - el script ahora trabaja en `%USERPROFILE%\NwMobileExport\lote\<id>`;
  - el plugin crea la carpeta antes de escribir;
  - si no se genera el `.nmraw`, el script muestra el código devuelto y el registro del plugin.
- **Repositorio:** `C:\Users\Lenovo\NavisMobile_app`.
- **Modelo sano:** `F:\proyecto animación\MODELO_FLUOR_RAPIDO_2026-08-30.nwd` (copiado y verificado ayer, SHA-256 `BED77543…`).

## Reglas
- **No cierres ni mates Navisworks sin preguntarme.** Si al cerrar pide guardar, detente y pregúntame.
- **No abras el modelo completo en dos Navisworks a la vez.**
- **No muevas, renombres ni borres nada dentro de carpetas de Drive.** No subas nada a GitHub.
- Si una llamada a mi PC no responde en 80 s, no la relances: comprueba si el proceso sigue corriendo.
- Ante un error, copia el mensaje exacto.

## Pasos
1. En el repositorio: `git status` y luego `git pull origin main`. Debe quedar en 7f1a8e3 o posterior.
2. Si Navisworks está abierto, pregúntame antes de cerrarlo. Después ejecuta:
   ```
   powershell -ExecutionPolicy Bypass -File herramientas\navismobile-export\Install.ps1
   ```
   Confirma 0 errores y la hora de la DLL.
3. Extrae el área 1300:
   ```
   powershell -ExecutionPolicy Bypass -File herramientas\navismobile-export\extraer_area_oculto.ps1 -Nwd "F:\proyecto animación\MODELO_FLUOR_RAPIDO_2026-08-30.nwd" -Id area1300 -Rutas "TOTAL_PROYECTO_2.vue/AMSA_DMC/1300|TOTAL_PROYECTO_4.vue/AMSA_DMC/1300" -ExcluirNombres "MecMiscellaneous,Unknown"
   ```
   - Busca el proceso oculto por su PID (puede no llamarse «Roamer»). Mide la RAM libre cada ~30 s.
4. **Si falla con «Ruta …: no existe "X". Disponibles: …»:**
   - corrige ese tramo con el nombre más parecido de la lista;
   - reintenta **una vez**;
   - si vuelve a fallar, dame el mensaje completo y para.
5. **Si falla con otro error:** dame la salida completa del script y el contenido de `%USERPROFILE%\NwMobileExport\lote\area1300\area1300.nmraw.log`.
6. **Si termina con `LISTO:`:** espera a que `area1300.nmraw` y `area1300.nmraw.piezas.json` aparezcan **completos y fuera de la papelera** en drive.google.com, en `proyecto animación\NavisMobile\entrada`. Compruébalo en la web, no en el explorador.
7. **Limpieza:** borra la carpeta vacía del intento anterior, `%LOCALAPPDATA%\NwMobileExport\lote\area1300`, si sigue vacía. No toques nada más.

## Informe final
Dame un resumen corto con:
- Commit y hora de la DLL.
- El comando exacto que funcionó (con las rutas, si las corregiste).
- Tiempo, piezas, triángulos y TAG (de `area1300.nmraw.log`), pico de RAM y si el PC siguió usable.
- Nombre y bytes de los archivos en Drive.
- El contenido completo de `area1300.nmraw.log`. Debe tener ahora **dos o más** líneas `Lote:`: confírmalo.
