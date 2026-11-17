# NavisMobile — Tareas pendientes (secuenciales) para Sonnet 5.5

Fuente de verdad: `PLAN_EJECUCION.md` (§ = sección). Leer solo la § indicada en cada tarea.
Reglas: ejecutar en orden; 1 commit por tarea (`git commit -m "Tarea N: …"`); no re-investigar lo de §2;
no leer el `.glb` ni `node_modules`; respuestas breves.
Rama de trabajo: `claude/dreamy-volta-6igg2d` (el plan dice `main`: no empujar a `main` sin permiso del usuario).

## Estado (2026-11-17) — Tareas 1-23 hechas (ver notas); falta solo la 24
Notas: iconos = los de Capacitor (base.apk no es público); PLAN_NavisBlend.md no es público (omitido); descarga real desde Drive no verificable en el Chromium de la nube (curl confirma CORS); falta prueba en teléfono.
Hecho: `index.html`, `src/estilos.css`, `src/navegacion.js` (sin probar), `modelos_movil/area1313_movil.glb`, `.gitignore`.
Pendiente: todo lo siguiente.

## Fase A — Base del proyecto
1. **Configurar build** (§6.1): en `package.json` añadir `"type":"module"`, scripts `dev`/`build`/`preview`; crear
   `vite.config.js` con `base:'./'` y plugin dev que sirva `datos_locales/` en `/datos/` (§4 datos.js).
   Hecho si: `npm run build` genera `dist/`.
2. **Decodificador Draco local** (§2.4): copiar `node_modules/three/examples/jsm/libs/draco/gltf/` a `public/draco/`.
3. **Comprobar CORS** de la URL raw de GitHub del `area1313_movil.glb` (§2.3, `curl -I`). Si no hay `access-control-allow-origin`,
   copiar el GLB a `public/modelos/` y usar ruta relativa en el catálogo.
4. **Catálogo** (§3): crear `public/catalogo.json` completo con los IDs/bytes de §2.3 (las 2 escenas, todos los archivos).
5. **Script de catálogo** (§3): `tools/sincronizar_catalogo.mjs` (embeddedfolderview → actualiza IDs/bytes por nombre).
   Probarlo una vez con `node`.

## Fase B — Módulos de la app (§4)
6. `src/datos.js` (descarga con progreso, Cache API, `comprobar`, `borrar`, `storage.persist`, ruta DEV `/datos/`).
7. `src/visor.js` (renderer, luces, RoomEnvironment, render bajo demanda, pixelRatio dinámico, carga GLTF+Draco,
   `puntoEn(x,y)` por pasada de profundidad 1×1 y selección por pasada de identidad; ayudantes en capa 1).
8. `src/recorridos.js` (§2.4 recorridos: interpolación lineal, `desfase_ciclo_s`, bloquea `nav`).
9. `src/equipos.js` (§2.4 equipos 1313 + animaciones.json; ignorar pistas no-equipo y avisarlo).
10. `src/correas.js` (§2.4 correas: ejes Blender→Three `(x,z,-y)`, cinta con textura animada ~3 m/s).
11. `src/main.js` (§4 main.js): enlazar con los `id` de `index.html` — pestañas Escenas, Capas, Propiedades, Vistas,
    Animación; barra (Aislar, Ocultar, Mostrar, Encuadrar, Corte, Medir, ↶); panel de navegación, joystick, pivote, `#info`.
    Verificar que `index.html` carga `src/main.js` como módulo.

## Fase C — Pruebas en navegador (§8.1–8.3)
12. Copiar a `datos_locales/` los archivos del Hito ligero (bajar de Drive con la URL de §2.2). `npm run dev` + Playwright:
    captura, capas listadas, consola sin errores (timeout amplio).
13. Script Playwright: orbitar/panear/zoom, `puntoEn`, medir, corte, recorrido, animación `ciclo-completo` del 1313.
    Revisar sentido de giros y que el zoom no atraviese el modelo (§5); corregir `navegacion.js` si falla.
14. Prueba de descarga real desde Drive (CORS) y segunda apertura desde caché.

## Fase D — APK (§6)
15. `capacitor.config.json`; `npm run build && npx cap add android && npx cap sync android`.
16. Instalar Android SDK (§6.4), `android/local.properties`, `./gradlew assembleDebug`.
17. Iconos: extraer `res/mipmap*` de `base.apk` (Drive `1-hq1HE7SQMswIZtOsZ56d0dvuaYXaeYg`) a `android/app/src/main/res/`.
18. Verificar APK con `unzip -l` (index.html, catalogo.json, draco/); copiar a `apk/NavisMobile-debug.apk`; enviar con `SendUserFile`.
19. CI: `.github/workflows/android.yml` (§6.6).

## Fase E — Contenido y documentación (§7)
20. `herramientas/hito/` y `herramientas/area1313/` desde Drive (sin `_respaldos`).
21. `datos/`: JSON pequeños de §2.3 como referencia.
22. `docs/`: `LEEME_ESTRUCTURA.md`, `PLAN_NavisBlend.md`, `.bat` de las raíces.
23. `README.md` (§7: qué es, instalación, Drive, catálogo, compilación, tabla de gestos).

## Fase F — Entrega (§9)
24. Push a la rama de trabajo; informe al usuario: hecho/probado, no probado (teléfono real), desinstalar APK anterior,
    copiar `area1313_movil.glb` a Drive. Preguntar si se fusiona a `main` / se crea PR.
