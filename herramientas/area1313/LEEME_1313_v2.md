# Área 1313 – pasos nuevos (barandas y decimación selectiva)

Todo corre en el PC. Ejecutar en este orden. Los originales (`unir_capas_1313.py`, etc.) quedan intactos.

## 1) Cajas de las barandas (solo lectura del FBX)
```
py extraer_barandas_1313.py ___area_1313.fbx barandas_cajas.json --desf 0,0,0
```
Esperado: ~41 cajas "Handrail". `--desf` es el desfase mundo→real del FBX v4 y NO está verificado
(cuando se tenga, pasarlo; por defecto 0). El paso 2 imprime los límites de las cajas y del modelo para detectar un desfase malo.

## 2) Unir capas con barandas amarillas (una corrida de Blender)
```
blender -b "Capas area 1313 completo.blend" --python unir_capas_1313_v2.py -- ___area_1313.visor.glb animaciones.json area1313_web_v2.glb --barandas barandas_cajas.json
```
Revisar en el log: (a) «limites cajas v4» vs «limites del modelo v4» del mismo orden; (b) línea REPINTADO con conteos por lote
(verdes 00FF00 / StrSteel ADD8E6 / amarillo). Si dice AVISO → no usar. Los triángulos repintados salen como mallas `V4_<disc>_FFFF00_baranda`.
Riesgo: se repinta por centroide dentro de la caja; si una caja Handrail encierra otra geometría, ésta también se pintaría.
Mostrar captura de la zona verde (imagen 02) antes de aceptar.

## 3) Decimación selectiva (rejillas/escaleras) – opcional, para calidad alta
Añadir al comando anterior, por ejemplo: `--decimar V4_Structural_00FF00=0.5` (conserva 50 % de triángulos).
Subir la razón/ajustar hasta que calidad alta fluya en Chrome sin perder el aspecto; medir FPS en alta y media.

## No hecho (necesita el PC)
- Unión de huecos de tubería y líneas sin soporte: requieren la geometría pieza por pieza del FBX (Capas area 1313.fbx, 507 MB) y medir conectividad; no se pueden verificar desde la nube.
- Recorrido de 90 s: las nuevas VISTAS salen de buscar_vistas_1313.py sobre el campo de distancias (PC).
