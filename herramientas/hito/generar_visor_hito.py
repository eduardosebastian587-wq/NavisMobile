# Genera index_hito.html (visor web realista del Hito M33-1) a partir de:
#   - herramientas/plantilla_visor_hito.html          (código del visor; marcas __VIDEO__, __RECORRIDOS__, __SUELTOS__)
#   - convertidos_blender/hito_escena_video.json       (escena del video: materiales, soles, cielo, cámara, recorrido 12 s)
#   - convertidos_blender/hito_recorrido_50s.json      (recorrido continuo 50 s: 25 s optimizados + continuación; opcional)
#   - convertidos_blender/hito_recorrido.json          (recorrido optimizado 25 s sin interferencias; opcional)
#   - convertidos_blender/hito_sueltos.json            (resumen de elementos sueltos eliminados; opcional)
# El HTML de salida no se edita a mano: se cambia la plantilla o los datos y se vuelve a generar.
# v3.1 (2026-10-29): agrega el recorrido continuo de 50 s como primer recorrido base (si existe el archivo).
# v3.2 (2026-10-30): correas en funcionamiento: datos de bandas (hito_correas.json, marca __CORREAS__) y recorrido
#                    «Correas en funcionamiento» (hito_recorrido_correas.json) como primer recorrido base.
# Uso: python generar_visor_hito.py   (rutas por defecto relativas a la carpeta del proyecto; solo biblioteca estándar)
import json, os, sys
try: sys.stdout.reconfigure(errors='replace')      # consola de Windows (cp1252): no fallar al imprimir símbolos como «≥»
except Exception: pass

aqui = os.path.dirname(os.path.abspath(__file__))
raiz = os.path.dirname(aqui)
cb = os.path.join(raiz, 'convertidos_blender')
arg = dict(a.split('=', 1) for a in sys.argv[1:] if '=' in a)
ruta_esc = arg.get('escena', os.path.join(cb, 'hito_escena_video.json'))
ruta_r50 = arg.get('recorrido50', os.path.join(cb, 'hito_recorrido_50s.json'))
ruta_rec = arg.get('recorrido', os.path.join(cb, 'hito_recorrido.json'))
ruta_cor = arg.get('recorrido_correas', os.path.join(cb, 'hito_recorrido_correas.json'))
ruta_ban = arg.get('correas', os.path.join(cb, 'hito_correas.json'))
ruta_sue = arg.get('sueltos', os.path.join(cb, 'hito_sueltos.json'))
ruta_pla = arg.get('plantilla', os.path.join(aqui, 'plantilla_visor_hito.html'))
ruta_sal = arg.get('salida', os.path.join(raiz, 'index_hito.html'))

R = json.load(open(ruta_esc, encoding='utf-8'))
T = R['trayectoria_three']
c0, c1 = R['vista']['cuadros']
assert len(T) == c1 - c0 + 1 and [r[0] for r in T] == list(range(c0, c1 + 1)), 'trayectoria del video incompleta'
assert all(len(r) == 7 for r in T), 'falta el objetivo de cámara (OBJETIVO) en algún cuadro'
assert R['soles'], 'la escena no tiene soles'
terr = R['materiales']['MAT_C6B88D']
video = {
    'fps': R['vista']['fps'], 'cuadros': len(T),
    'lente_mm': R['camara']['lente_mm'], 'sensor_mm': R['camara']['sensor_mm'],
    'exposicion_ev': round(R['vista']['exposicion'], 4),
    'suelo_y': round(R['suelo_extenso']['y_three'], 3), 'suelo_lado': R['suelo_extenso']['lado_m'],
    'soles': [{'nombre': s['nombre'], 'dir': s['hacia_sol_three'], 'energia': s['energia']} for s in R['soles']],
    'cielo': {'elevacion': round(R['cielo']['sun_elevation'], 3), 'rotacion': round(R['cielo']['sun_rotation'], 3)},
    'terreno': {'rampa': ['#' + h for h in terr['rampa']], 'escala': round(terr['ruido'][0]['escala'], 4),
                'detalle': terr['ruido'][0]['detalle'], 'relieve_escala': round(terr['ruido'][1]['escala'], 4),
                'relieve_fuerza': round(terr['relieve'], 4), 'rugosidad': terr['rugosidad']},
    'materiales': {k: {'color': v['color'], 'metal': v['metal'], 'rugosidad': v['rugosidad'], 'alfa': v['alfa']}
                   for k, v in R['materiales'].items() if k.startswith('MAT_') and 'color' in v},
}
num = lambda v: ('%.3f' % v).rstrip('0').rstrip('.')
recorridos = []
for ident, ruta in (('correas', ruta_cor), ('continuo_50s', ruta_r50), ('optimizado', ruta_rec)):
    if os.path.exists(ruta):
        O = json.load(open(ruta, encoding='utf-8'))
        recorridos.append({'id': ident, 'nombre': O['nombre'], 'fps': O['fps'], 'origen': O['origen'],
                           'verificacion': O['verificacion'], 'distancias': O['distancias'], 'trayectoria_three': O['trayectoria_three']})
vh = next((r['verificacion']['video_holgura_min_m'] for r in recorridos if 'video_holgura_min_m' in (r['verificacion'] or {})), None)
ver_video = {'holgura_min_m': vh} if vh is not None else None
recorridos.append({'id': 'video', 'nombre': 'Recorrido original del video', 'fps': R['vista']['fps'], 'origen': 'hito_realista.blend',
                   'verificacion': ver_video, 'trayectoria_three': [r[1:7] for r in T]})
sueltos = None
if os.path.exists(ruta_sue):
    S = json.load(open(ruta_sue, encoding='utf-8'))
    sueltos = {k: S[k] for k in ('criterio', 'grupos_sueltos', 'triangulos_sueltos', 'triangulos_totales', 'por_objeto')}

def compacto(o):              # JSON compacto con trayectorias a 3 decimales y 6 cuadros por línea
    if isinstance(o, list) and o and isinstance(o[0], list) and len(o[0]) == 6:
        filas = ['[' + ','.join(num(v) for v in r) + ']' for r in o]
        return '[\n' + ',\n'.join(','.join(filas[i:i + 6]) for i in range(0, len(filas), 6)) + '\n]'
    if isinstance(o, dict):
        return '{' + ','.join(json.dumps(k) + ':' + compacto(v) for k, v in o.items()) + '}'
    if isinstance(o, list):
        return '[' + ','.join(compacto(v) for v in o) + ']'
    return json.dumps(o, ensure_ascii=False)

html = open(ruta_pla, encoding='utf-8').read()
correas = json.load(open(ruta_ban, encoding='utf-8')) if os.path.exists(ruta_ban) else None
for m in ('__VIDEO__', '__RECORRIDOS__', '__SUELTOS__'):          # __CORREAS__ es opcional (plantillas anteriores a v3.2)
    assert m in html, 'plantilla sin la marca ' + m
html = (html.replace('__VIDEO__', json.dumps(video, ensure_ascii=False))
            .replace('__RECORRIDOS__', compacto(recorridos))
            .replace('__SUELTOS__', json.dumps(sueltos, ensure_ascii=False))
            .replace('__CORREAS__', json.dumps(correas, ensure_ascii=False, separators=(',', ':'))))
open(ruta_sal, 'w', encoding='utf-8', newline='\n').write(html)
print(f'Visor generado: {ruta_sal}  ({len(recorridos)} recorridos: ' +
      ', '.join(f"{r['nombre']} {(len(r['trayectoria_three'])-1)/r['fps']:.1f} s" for r in recorridos) +
      f'; materiales {len(video["materiales"])}; sueltos {"sí" if sueltos else "no"}; correas {len(correas["correas"]) if correas else 0}; {len(html)/1024:.0f} KB)')
