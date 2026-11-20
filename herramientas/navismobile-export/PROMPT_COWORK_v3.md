# Prompt para Cowork v3: cerrar pendientes (PC con Navisworks)

Copia todo lo que está debajo de la línea en una sesión de Cowork que tenga acceso a este PC.

---

Eres mi asistente en mi PC con Windows (usuario `Lenovo`, 16 GB de RAM, 12 hilos, Navisworks Manage 2027). Trabaja en español. Quiero cerrar los pendientes de NavisMobile. Avísame en una línea antes de cada paso largo y deténte a preguntarme donde este texto lo indique.

## Contexto (estado al 20-11-2026)
- **NavisMobile:** app Android que muestra áreas de la planta. Repositorio local `C:\Users\Lenovo\NavisMobile_app`, remoto `https://github.com/eduardosebastian587-wq/NavisMobile`, rama `main`.
- **Cadena actual:**
  1. En el PC, `herramientas\navismobile-export\extraer_area_oculto.ps1` extrae el área en un Navisworks oculto (prioridad baja, 6 núcleos) con la entrada `NwMobileExport.Lote` del plugin. Deja `<id>.nmraw` y `<id>.nmraw.piezas.json` en Drive: `...\Mi unidad\proyecto animación\NavisMobile\entrada`.
  2. En la nube, GitHub Actions «Procesar área» convierte y publica en la app. Lo lanza Claude en la nube, no tú.
- **Ya funciona y está probado:** el plugin compilado e instalado (8:32), la extracción oculta de `area 1313.nwd` (5,5 min, PC usable) y la del 1251 desde la copia sana del modelo (13 min). Las áreas 1313 y 1251 están publicadas en la app.
- **Lecciones de ayer:**
  - **No muevas, renombres ni borres archivos dentro de carpetas sincronizadas con Drive.** Mover la copia duplicada `area1251 (1).nmraw` hizo que Drive enviara `area1251.nmraw` a la papelera. Ya se restauró.
  - La subida automática de archivos de más de 1 GB puede tardar o quedar en pausa. Para saber si un archivo está realmente subido, revisa drive.google.com: el explorador de Windows muestra también archivos pendientes.
  - Las líneas `Lote:` no llegaban a `export.log` cuando Navisworks corre oculto. Ya está corregido en `main`: ahora se escribe también `<salida>.log` junto al `.nmraw`. Hay que reinstalar el plugin (paso 2).

## Reglas
- **No cierres ni mates Navisworks sin preguntarme:** un reinicio a mitad de un guardado ya dañó un NWD.
- **No abras el modelo completo (1,3 GB) en dos Navisworks a la vez:** no cabe en 16 GB.
- **No borres nada sin mi confirmación explícita.** Ante la duda, renombra *fuera* de las carpetas de Drive.
- **No subas nada a GitHub.**
- Ante un error, copia el mensaje exacto. Muéstrame cualquier cambio de código antes de hacerlo.

## Pasos

### 1. Drive para escritorio
1. Comprueba que la sincronización no esté en pausa. Si lo está, reanúdala.
2. En drive.google.com, revisa que `proyecto animación\NavisMobile\entrada` contenga `area1251.nmraw` (1 325 677 096 bytes) y su `.piezas.json`, **fuera de la papelera**.
3. Revisa si en el PC quedan copias tipo `area1251 (1).nmraw` dentro de carpetas de Drive. Repórtalas y no las toques.
   - La copia que moviste ayer a `%LOCALAPPDATA%\NwMobileExport\lote\area1251\area1251.nmraw.copia-drive` está fuera de Drive. Déjala ahí por ahora.

### 2. Reinstalar el plugin (corrección del registro)
1. `git status` y luego `git pull origin main` en `C:\Users\Lenovo\NavisMobile_app`.
2. Si Navisworks está abierto, **pregúntame** antes de cerrarlo.
3. Ejecuta:
   ```
   powershell -ExecutionPolicy Bypass -File herramientas\navismobile-export\Install.ps1
   ```
   Confirma 0 errores y la hora de la DLL instalada.
4. Haz una prueba corta para comprobar el registro nuevo:
   ```
   ... extraer_area_oculto.ps1 -Nwd "<ruta>\AREA_1313_MOLINOS\modelo_fuente\area 1313.nwd" -Id prueba_log -Prueba
   ```
   Debe aparecer `%LOCALAPPDATA%\NwMobileExport\lote\prueba_log\prueba_log.nmraw.log` con dos líneas `Lote:`. Después puedes borrar esa carpeta `prueba_log`: está fuera de Drive y es solo de prueba.

### 3. Recuperar el modelo dañado (pregúntame antes de copiar)
- **Dañado:** `F:\proyecto animación\MODELO_FLUOR_RAPIDO_2026-08-30.nwd` (891 MB, no abre).
- **Sano:** `...\Mi unidad\proyecto animación\_MODELO_ORIGINAL_PLANTA\MODELO_FLUOR_RAPIDO_2026-08-30.nwd` (1 260 MB).
1. Comprueba que la copia de Drive esté descargada completa en el PC y no sea solo un acceso en línea. Si hace falta, márcala como «Disponible sin conexión» y espera.
2. Propónme el plan y **espera mi «sí»**:
   - renombrar el dañado a `MODELO_FLUOR_RAPIDO_2026-08-30.dañado.nwd` (está en `F:`, fuera de Drive);
   - copiar el sano a `F:\proyecto animación\` con su nombre original.
3. Verifica que la copia mida exactamente lo mismo que el original (bytes). Si te lo pido, ábrelo en Navisworks para comprobar que abre y si tiene el viewpoint `exportar`.

### 4. Archivo temporal sospechoso (solo informar)
- `F:\MODELO_FLUOR_RAPIDO_2025-12-17.nwd~` (75 MB, del 19-11).
- Dime la fecha y el tamaño de `F:\MODELO_FLUOR_RAPIDO_2025-12-17.nwd` y si ese NWD abre bien. Con eso decido si borro el `~`. **No lo borres tú.**

### 5. Opcional: volver a extraer las áreas 1411 y 1300 (pregúntame antes de empezar)
Hoy están en la app con la extracción del 18-11. Con la extracción oculta salen más detalladas (pasó con 1313 y 1251).
1. Lee `F:\proyecto animación\NavisMobile\trabajo\area1411\area1411.nmraw.piezas.json`: anota los campos `"documento"` (el NWD de origen) y `"raices"`. Haz lo mismo con `area1300`.
2. Busca también las exclusiones usadas en la exportación anterior (`excluir`), por ejemplo en `publicar.log` o en archivos de la carpeta `trabajo\area1300\`. Según la app, la 1300 se exportó **sin «MecMiscellaneous» ni «Unknown»**. Si no encuentras los ids de exclusión de la 1300, **no la extraigas**: avísame.
3. Si el documento de origen es el modelo completo, usa la copia sana local (la del paso 3) o la de Drive, y nunca dos a la vez. Extrae de a una, **sin** `-Prueba`:
   ```
   ... extraer_area_oculto.ps1 -Nwd "<documento>" -Id area1411 -Raices "<raices separadas por coma>"
   ```
4. Espera a que cada `.nmraw` aparezca **completo** en drive.google.com, en `NavisMobile\entrada` y fuera de la papelera. Dime el nombre exacto y el tamaño en bytes.

## Informe final
Dame un resumen corto con:
- Paso 1: estado de la sincronización y copias duplicadas encontradas.
- Paso 2: hora de la DLL y contenido de `prueba_log.nmraw.log`.
- Paso 3: lo que hiciste (o el plan pendiente de mi «sí») y si el NWD abre.
- Paso 4: fechas y tamaños.
- Paso 5: archivos subidos (nombre y bytes) o por qué no se hizo.
- Cualquier error con su mensaje exacto.
