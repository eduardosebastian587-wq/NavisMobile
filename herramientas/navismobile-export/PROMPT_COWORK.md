# Prompt para Cowork (PC con Navisworks)

Copia todo lo que está debajo de la línea en una sesión de Cowork que tenga acceso a este PC.

---

Eres mi asistente en mi PC con Windows (usuario `Lenovo`, 16 GB de RAM, Navisworks Manage 2027). Trabaja en español. Necesito que pruebes y uses la extracción "oculta" de NavisMobile, que ya está preparada en mi repositorio. Avísame en una línea antes de cada paso largo y deténte a preguntarme cuando este texto lo indique.

## Contexto
- NavisMobile es una app Android (Capacitor + three.js) que muestra áreas de la planta descargadas desde GitHub. Repositorio: `https://github.com/eduardosebastian587-wq/NavisMobile`, rama `main`.
- Antes, extraer un área bloqueaba Navisworks y saturaba el PC durante ~1 h. Ahora la cadena está partida en dos:
  1. **En el PC:** `herramientas\navismobile-export\extraer_area_oculto.ps1` abre el NWD en una instancia **oculta** de Navisworks (Automation API), con prioridad baja y la mitad de los núcleos. Ejecuta la entrada sin ventanas del plugin, `NwMobileExport.Lote`, y deja `<id>.nmraw` + `<id>.nmraw.piezas.json` en la carpeta de Google Drive `proyecto animación\NavisMobile\entrada`.
  2. **En la nube:** GitHub Actions › «Procesar área» convierte, comprime y publica. Esto ya está probado y funciona.
- **Falta lo único que solo se puede hacer en este PC:** compilar e instalar el plugin y comprobar que la entrada `Lote` funciona en la instancia oculta. Se compiló sin errores contra una réplica de la API, nunca contra las DLL reales.
- Guía completa: `herramientas\navismobile-export\LEEME_NUBE.md`.

## Reglas
- **No cierres ni mates Navisworks sin preguntarme.** Puede haber trabajo sin guardar o un guardado en curso: un reinicio a mitad de un guardado ya dañó un NWD.
- **No abras el modelo completo de 1,3 GB en dos Navisworks a la vez:** no cabe en 16 GB. Usa NWD por área cuando existan.
- **No borres archivos.** Si algo estorba, renómbralo (por ejemplo, agrégale `.viejo`) y avísame.
- **No subas nada a GitHub** salvo que te lo pida.
- Ante un error, copia el mensaje exacto. No improvises cambios de código sin mostrármelos primero.

## Pasos

### 0. Preparar
1. Busca el repositorio local. La configuración del plugin apunta a `C:\Users\Lenovo\NavisMobile_app`; mira también `%LOCALAPPDATA%\NwMobileExport\config.json` (clave `repo_app`).
   - Si existe: `git status` (no pierdas cambios locales) y `git pull origin main`.
   - Si no existe: clónalo ahí.
2. Comprueba que existen `herramientas\navismobile-export\extraer_area_oculto.ps1` y `plugin\PluginLote.cs`.
3. Comprueba que hay .NET SDK (`dotnet --version`); `Install.ps1` lo usa para compilar. Si falta, **pregúntame** antes de instalarlo.
4. Ubica la carpeta de Drive «proyecto animación». Suele estar en `C:\Users\Lenovo\Streaming de Google Drive\Mi unidad\proyecto animación`; hay copias antiguas en `F:\proyecto animación`.

### 1. Compilar e instalar el plugin
1. Si `Roamer.exe` (Navisworks) está abierto, **pregúntame** si puedo cerrarlo. Espera mi respuesta.
2. Ejecuta:
   ```
   powershell -ExecutionPolicy Bypass -File herramientas\navismobile-export\Install.ps1
   ```
3. Si falla la compilación, muéstrame los errores exactos y para.

### 2. Prueba de la extracción oculta (la prueba clave)
1. Con un NWD de área pequeño (~100 MB), **no** con el modelo completo:
   ```
   powershell -ExecutionPolicy Bypass -File herramientas\navismobile-export\extraer_area_oculto.ps1 -Nwd "<ruta>\AREA_1313_MOLINOS\modelo_fuente\area 1313.nwd" -Id area1313 -Prueba
   ```
2. Mientras corre, mide cada ~30 s la RAM libre, la CPU total y la del proceso `Roamer` oculto. Comprueba también que el PC sigue usable.
3. Resultado esperado: una línea `LISTO:` y, en `%LOCALAPPDATA%\NwMobileExport\lote\area1313\`, los archivos `area1313.nmraw` (cientos de MB) y `area1313.nmraw.piezas.json`.
4. Revisa `%LOCALAPPDATA%\NwMobileExport\export.log` (líneas `Lote:`).
5. **Si falla con «no ejecutó NwMobileExport.Lote»** o no aparece el `.nmraw`, prueba el plan B y anota el error del primer intento:
   ```
   ... extraer_area_oculto.ps1 -Nwd "<mismo NWD>" -Id area1313 -Formato fbx -Prueba
   ```

### 3. Área 1251 (solo si el paso 2 funcionó)
El FBX del 1251 que hay en Drive está truncado, así que hay que volver a extraerla.
1. Busca los ids de nodo de la exportación anterior en `F:\proyecto animación\NavisMobile\trabajo\area1251\area1251.nmraw.piezas.json`, campo `"raices"`.
2. Busca el NWD que contiene el área 1251. Probablemente es el modelo completo `MODELO_FLUOR_RAPIDO_2025-12-17.nwd` en `F:\`. **No lo abras si ya hay otro Navisworks con un modelo grande abierto**: pregúntame.
3. Ejecuta **sin** `-Prueba`:
   ```
   ... extraer_area_oculto.ps1 -Nwd "<NWD>" -Id area1251 -Raices "<raices separadas por coma>"
   ```
4. Espera a que Google Drive termine de subir `area1251.nmraw` a `proyecto animación\NavisMobile\entrada`. Después avísame: yo lanzo «Procesar área» en GitHub con `archivo = area1251.nmraw` e `id = area1251`.

### 4. Recuperar el modelo dañado (pregúntame antes)
- `F:\proyecto animación\MODELO_FLUOR_RAPIDO_2026-08-30.nwd` quedó dañado (934 MB, no abre).
- En Drive hay una copia sana de 1 260 MB en `proyecto animación\_MODELO_ORIGINAL_PLANTA\`.
- Propón renombrar el dañado a `.dañado.nwd` y copiar el sano en su lugar. **Hazlo solo si te lo confirmo.**

## Informe final
Dame un resumen corto con:
- **Paso 1:** compiló o no (errores exactos si no).
- **Paso 2:** funcionó o no. Incluye el tiempo total, el tamaño del `.nmraw`, el pico de RAM y CPU de `Roamer` oculto, si el PC siguió usable y las últimas líneas de `export.log`.
- **Plan B:** si hizo falta, si funcionó.
- **Paso 3:** estado del área 1251 y nombre exacto del archivo subido a Drive.
- **Paso 4:** lo que quedó pendiente de mi confirmación.
