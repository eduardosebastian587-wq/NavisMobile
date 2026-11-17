# proyecto animación — estructura (reorganizada 2026-10-30)

Cada subproyecto es autónomo: sus .bat y scripts usan rutas relativas a su propia carpeta.
Registro de todos los movimientos (origen → destino): `_registro_reorganizacion_2026-10-30.csv`.

## HITO_M33-1/  (área seca: correas, alimentadores, domo, harneros, puente grúa)
- `INICIAR_VISOR_HITO.bat` → abre el visor (puerto 8050). `EXPORTAR_HITO_GLB.bat` → regenera toda la cadena.
- `index_hito.html` (generado, no editar) · `servidor_visor.py` (copia)
- `herramientas/` scripts + `plantilla_visor_hito.html` (molde del visor) · `herramientas/_respaldos/`
- `convertidos_blender/` hito_web.glb, recorridos JSON, terreno relleno, hito.blend
- `modelo_fuente/` hito M33-1.nwd, hito.fbx
- `videos/` video vigente · `videos/versiones_anteriores/`
- `navisworks_hito/` puntos de vista XML · `capturas_prueba/` · `_trabajo/`

## AREA_1313_MOLINOS/  (molinos ML-1401/1402, pórtico CN-1406, pescantes CN-1404/1405)
- `INICIAR_VISOR_V4.bat` → visor v4 (puerto 8040) con `index_v4.html`, `animaciones.json`, `___area_1313.fbx` + `.visor.glb`
- `CONVERTIR_FBX_A_BLENDER.bat` + `LEEME_FBX_A_BLENDER.txt` (conversor FBX → Blender)
- `herramientas/` fbx_a_blender.py, nwd_a_fbx.ps1, generadores de la capa Navisworks
- `capa_navisworks/` capa de animación para Navisworks · `convertidos_blender/` · `convertidos_nwd/`
- `modelo_fuente/` area 1313.nwd/.nwf y FBX completos · `versiones_anteriores/` visores v1–v3 (con sus .bat)
- `documentacion/` · `videos/` · `capturas_prueba/` · `_respaldos/` · `_trabajo/`

## _MODELO_ORIGINAL_PLANTA/
- `MODELO_FLUOR_RAPIDO_2026-08-30.nwd` (modelo completo de planta, origen de ambos subproyectos)

## _por_borrar/  (revisar y eliminar a mano; ~5,2 GB)
- `fbx_truncados_o_duplicados/` FBX incompletos (sin nodo Objects) y la copia «,Area_1313…»
- `duplicados_nueva_carpeta/` copias viejas de index_v4, animaciones.json, servidor
- `carpetas_vacias/`, `__pycache__/`, y los temporales que ya estaban
