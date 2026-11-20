# Prompt para Cowork v4: últimos pendientes (PC con Navisworks)

Copia todo lo que está debajo de la línea en una sesión de Cowork que tenga acceso a este PC.

---

Eres mi asistente en mi PC con Windows (usuario `Lenovo`, 16 GB de RAM, Navisworks Manage 2027). Trabaja en español y avísame en una línea antes de cada paso largo.

## Contexto (20-11-2026, tarde)
- **NavisMobile:** app Android que muestra áreas de la planta. Repositorio local `C:\Users\Lenovo\NavisMobile_app` (rama `main`).
- **Drive:** la unidad está en `C:\Users\Lenovo\Streaming de Google Drive\Mi unidad`. La carpeta del proyecto es `proyecto animación`; si la «ó» da problemas en la consola, usa comodines.
- **Extracción oculta:** `herramientas\navismobile-export\extraer_area_oculto.ps1` abre un NWD en un Navisworks oculto con prioridad baja, extrae el área y deja `<id>.nmraw` + `.piezas.json` en `proyecto animación\NavisMobile\entrada`. Ya funciona: se usó para las áreas 1313, 1251 y 1411, que Claude en la nube ya publicó en la app.
- **Novedad en `main`:** el script ahora acepta
  - `-Rutas "A/B/C|D/E/F"`: nodos por nombre, sin ids. Si un nombre no existe, el error lista los nombres disponibles en ese nivel.
  - `-ExcluirNombres "X,Y"`: omite en todo el subárbol los nodos con esos nombres.
  Requiere reinstalar el plugin (paso 1).
- **Estado en F:**
  - El modelo dañado ya está renombrado a `F:\proyecto animación\MODELO_FLUOR_RAPIDO_2026-08-30.dañado.nwd`.
  - En F: no hay ninguna copia del modelo 2026-08-30 que abra.
  - La copia sana está en Drive: `proyecto animación\_MODELO_ORIGINAL_PLANTA\MODELO_FLUOR_RAPIDO_2026-08-30.nwd` (1 321 320 793 bytes).

## Antes de empezar
**Pregúntame una sola vez** qué autorizo de esta lista y espera mi respuesta:
- (a) Copiar el modelo sano de Drive a `F:\proyecto animación\` (paso 2).
- (b) Borrar `F:\MODELO_FLUOR_RAPIDO_2025-12-17.nwd~` (78 MB, del 29-08-2026; el NWD principal abre bien).
- (c) Borrar la carpeta de prueba `%LOCALAPPDATA%\NwMobileExport\lote\prueba_log` (1,2 GB, fuera de Drive).
- (d) Extraer el área 1300 (paso 4; unos 15–25 min).

## Reglas
- **No cierres ni mates Navisworks sin preguntarme.** Si al cerrar pide guardar, detente y pregúntame.
- **No abras el modelo completo en dos Navisworks a la vez:** no cabe en 16 GB.
- **No muevas, renombres ni borres nada dentro de carpetas de Drive.** Ayer eso mandó un `.nmraw` a la papelera.
- **Borra solo lo autorizado en (b) y (c).** No subas nada a GitHub.
- Si una llamada a mi PC no responde en 80 s, no la relances: el proceso suele seguir corriendo. Comprueba su estado.
- Ante un error, copia el mensaje exacto.

## Pasos

### 1. Actualizar e instalar el plugin
1. En `C:\Users\Lenovo\NavisMobile_app`: `git status` y luego `git pull origin main`. Debe traer el commit «Extracción oculta: nodos por nombre…».
2. Si Navisworks está abierto, pregúntame antes de cerrarlo.
3. Ejecuta:
   ```
   powershell -ExecutionPolicy Bypass -File herramientas\navismobile-export\Install.ps1
   ```
   Confirma 0 errores y anota la hora de la DLL.

### 2. Copiar el modelo sano (solo si autoricé (a))
1. Asegúrate de que la copia de Drive esté completa en el PC (clic derecho › «Disponible sin conexión» si hace falta) y espera a que termine.
2. **Copia** (no muevas) el archivo a `F:\proyecto animación\MODELO_FLUOR_RAPIDO_2026-08-30.nwd`.
3. Comprueba que la copia mida 1 321 320 793 bytes y que su SHA-256 sea igual al del original.

### 3. Limpieza (solo lo autorizado en (b) y (c))

### 4. Extraer el área 1300 (solo si autoricé (d))
La 1300 son las áreas 1313–1345 de `TOTAL_PROYECTO_2.vue` y `TOTAL_PROYECTO_4.vue`, sin los nodos «MecMiscellaneous» ni «Unknown».
1. Usa como NWD la copia sana de F: (paso 2). Si no se copió, usa la de Drive.
2. Ejecuta, sin `-Prueba`:
   ```
   powershell -ExecutionPolicy Bypass -File herramientas\navismobile-export\extraer_area_oculto.ps1 -Nwd "F:\proyecto animación\MODELO_FLUOR_RAPIDO_2026-08-30.nwd" -Id area1300 -Rutas "TOTAL_PROYECTO_2.vue/AMSA_DMC/1300|TOTAL_PROYECTO_4.vue/AMSA_DMC/1300" -ExcluirNombres "MecMiscellaneous,Unknown"
   ```
3. Si falla con «Ruta …: no existe …. Disponibles: …», ajusta el nombre con lo que lista el mensaje y reintenta **una vez**. Si vuelve a fallar, dame el mensaje completo.
4. Vigila la RAM libre cada ~30 s. Si baja de 1 GB, avísame.
5. Al terminar, lee `%LOCALAPPDATA%\NwMobileExport\lote\area1300\area1300.nmraw.log` y `area1300.nmraw.estado.json`.
6. Espera a que `area1300.nmraw` y `area1300.nmraw.piezas.json` aparezcan **completos y fuera de la papelera** en drive.google.com, en `proyecto animación\NavisMobile\entrada`. Compruébalo en Drive web, no en el explorador de Windows.

## Informe final
Dame un resumen corto con:
- Qué autoricé y qué hiciste.
- Paso 1: hora de la DLL y si hubo errores.
- Paso 2: bytes y SHA-256 del original y de la copia.
- Paso 3: qué se borró y cuánto espacio se liberó.
- Paso 4: tiempo, piezas, triángulos y TAG (de `area1300.nmraw.log` o `estado.json`), pico de RAM de Roamer, y nombre y bytes de los archivos en Drive.
- Cualquier error con su mensaje exacto.
