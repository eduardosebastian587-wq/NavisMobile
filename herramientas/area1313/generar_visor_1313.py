# Genera index_1313.html (visor del Área 1313, tipo Hito, aspecto del visor v4) a partir de:
#   - herramientas/plantilla_visor_1313.html            (parchar_plantilla_1313.py sobre la plantilla del Hito; marcas __VIDEO__,
#                                                        __RECORRIDOS__, __SUELTOS__, __CORREAS__, __EQUIPOS__)
#   - convertidos_blender/area1313_web.glb              (solo se leen los NOMBRES de material: MAT_<hex>[_A<op>] y V4_<disc>_<hex>)
#   - convertidos_blender/area1313_web_equipos.json     (piezas animadas, unir_capas_1313.py)
#   - animaciones.json                                  (pistas de «ciclo-completo» del visor v4.1)
#   - convertidos_blender/area1313_recorrido.json       (planificar_recorrido_1313.py)
#   - _trabajo/capas_fbx/disciplina_por_color.json      (disciplina de cada color de «Capas», leída del FBX)
#   - ../HITO_M33-1/convertidos_blender/hito_escena_video.json (cielo, soles, lente y exposición del Hito: misma iluminación)
# Materiales: perfiles PBR del visor v4 (PERFILES_POR_COLOR manda; si no, perfil de la disciplina «gris»/«color»), sobre el
# color de Navisworks de cada grupo. El HTML de salida no se edita a mano. Uso: py herramientas\generar_visor_1313.py
import json, os, sys, struct, colorsys, re
try: sys.stdout.reconfigure(errors='replace')
except Exception: pass
aqui = os.path.dirname(os.path.abspath(__file__)); raiz = os.path.dirname(aqui); cb = os.path.join(raiz, 'convertidos_blender')
arg = dict(a.split('=', 1) for a in sys.argv[1:] if '=' in a)
R_ESC = arg.get('escena', os.path.join(os.path.dirname(raiz), 'HITO_M33-1', 'convertidos_blender', 'hito_escena_video.json'))
R_GLB = arg.get('modelo', os.path.join(cb, 'area1313_web.glb'))
R_EQ = os.path.join(cb, 'area1313_web_equipos.json'); R_AN = os.path.join(raiz, 'animaciones.json')
R_REC = arg.get('recorrido', os.path.join(cb, 'area1313_recorrido.json')); R_DC = os.path.join(raiz, '_trabajo', 'capas_fbx', 'disciplina_por_color.json')
R_PLA = os.path.join(aqui, 'plantilla_visor_1313.html'); R_SAL = arg.get('salida', os.path.join(raiz, 'index_1313.html'))

# ---- perfiles del visor v4 (index_v4.html, CONFIG.PERFILES_MATERIAL y PERFILES_POR_COLOR)
PERFILES = {'Structural': {'gris': {'m': 0.30, 'r': 0.60}, 'color': {'m': 0.05, 'r': 0.55, 'cc': 0.15}},
            'Mechanical': {'gris': {'m': 0.88, 'r': 0.32}, 'color': {'m': 0.25, 'r': 0.38, 'cc': 0.60}},
            'Piping': {'gris': {'m': 0.92, 'r': 0.28}, 'color': {'m': 0.70, 'r': 0.32, 'cc': 0.25}},
            'Electrical': {'gris': {'m': 0.80, 'r': 0.40}, 'color': {'m': 0.55, 'r': 0.42, 'cc': 0.10}},
            'Control_Systems': {'gris': {'m': 0.40, 'r': 0.45}, 'color': {'m': 0.10, 'r': 0.40, 'cc': 0.50}},
            'defecto': {'gris': {'m': 0.60, 'r': 0.40}, 'color': {'m': 0.05, 'r': 0.60, 'cc': 0.20}}}
POR_COLOR = {0xa3a3a3: {'m': 0.00, 'r': 0.94}, 0xadd8e6: {'m': 0.55, 'r': 0.50, 'cc': 0.20}, 0x00ff00: {'m': 0.04, 'r': 0.64, 'cc': 0.20, 'a': 0.80},
             0xffff00: {'m': 0.18, 'r': 0.42, 'cc': 0.55, 'a': 0.88}, 0xa9a9a9: {'m': 0.52, 'r': 0.44, 'cc': 0.35},
             0x5999d9: {'m': 0.18, 'r': 0.34, 'cc': 0.65}, 0x0080c0: {'m': 0.70, 'r': 0.38, 'cc': 0.15}}
def perfil(hexs, disc):
    c = int(hexs, 16); pc = POR_COLOR.get(c)
    if pc: return pc
    r, g, b = ((c >> 16) & 255) / 255, ((c >> 8) & 255) / 255, (c & 255) / 255
    s = colorsys.rgb_to_hls(r, g, b)[2]
    return (PERFILES.get(disc) or PERFILES['defecto'])['gris' if s < 0.2 else 'color']

# ---- disciplina de cada color de «Capas» (color más cercano de la tabla leída del FBX; diferencias de redondeo de 1–2 unidades)
DC = json.load(open(R_DC, encoding='utf-8'))
def disc_capas(hexs):
    c = int(hexs, 16); rgb = lambda x: ((x >> 16) & 255, (x >> 8) & 255, x & 255)
    best = min(DC, key=lambda k: sum((a - b) ** 2 for a, b in zip(rgb(int(k[4:10], 16)), rgb(c))))
    d = max(DC[best].items(), key=lambda kv: kv[1])[0]
    return {'Control Systems': 'Control_Systems'}.get(d, d if d in PERFILES else 'defecto')

# ---- nombres de material del GLB + materiales de las piezas animadas
b = open(R_GLB, 'rb').read(24); L = struct.unpack('<I', b[12:16])[0]
J = json.loads(open(R_GLB, 'rb').read(20 + L)[20:])
nombres = {re.sub(r'\.\d+$', '', m['name']) for m in J['materials']}
EQ = json.load(open(R_EQ, encoding='utf-8'))
for p in EQ['partes']:
    for s in p['mallas']: nombres.add(f"V4_{s['disciplina']}_{s['color']:06X}")
mats = {}
for n in sorted(nombres):
    m1 = re.match(r'^MAT_([0-9A-F]{6})(?:_A(\d+))?$', n); m2 = re.match(r'^V4_(\w+?)_([0-9A-F]{6})$', n)
    if m1: hexs, alfa, disc = m1.group(1), (int(m1.group(2)) / 100 if m1.group(2) else 1.0), disc_capas(m1.group(1))
    elif m2: hexs, alfa, disc = m2.group(2), 1.0, m2.group(1)
    else: raise SystemExit('material sin formato conocido: ' + n)
    p = perfil(hexs, disc)
    mats[n] = {'color': hexs, 'metal': p['m'], 'rugosidad': p['r'], 'alfa': alfa, 'cc': p.get('cc', 0), 'a': p.get('a', 1), 'acabado': 'v4', 'disciplina': disc}

# ---- escena (iluminación y lente del Hito; terreno con el color de Navisworks)
R = json.load(open(R_ESC, encoding='utf-8')); terr = R['materiales']['MAT_C6B88D']
video = {'fps': R['vista']['fps'], 'cuadros': 0, 'lente_mm': R['camara']['lente_mm'], 'sensor_mm': R['camara']['sensor_mm'],
         'exposicion_ev': round(R['vista']['exposicion'], 4), 'suelo_y': 0.0, 'suelo_lado': R['suelo_extenso']['lado_m'],
         'soles': [{'nombre': s['nombre'], 'dir': s['hacia_sol_three'], 'energia': s['energia']} for s in R['soles']],
         'cielo': {'elevacion': round(R['cielo']['sun_elevation'], 3), 'rotacion': round(R['cielo']['sun_rotation'], 3)},
         'terreno': {'rampa': ['#C6B88D', '#C6B88D'], 'escala': round(terr['ruido'][0]['escala'], 4), 'detalle': terr['ruido'][0]['detalle'],
                     'relieve_escala': round(terr['ruido'][1]['escala'], 4), 'relieve_fuerza': round(terr['relieve'], 4), 'rugosidad': terr['rugosidad']},
         'materiales': mats}
# ---- recorrido y equipos
O = json.load(open(R_REC, encoding='utf-8'))
recorridos = [{'id': 'equipos', 'nombre': O['nombre'], 'fps': O['fps'], 'origen': O['origen'], 'verificacion': O['verificacion'],
               'desfase_ciclo_s': O.get('desfase_ciclo_s', 0),
               'distancias': O['distancias'], 'trayectoria_three': O['trayectoria_three']}]
AN = json.load(open(R_AN, encoding='utf-8')); CIC = next(a for a in AN['animaciones'] if a['id'] == 'ciclo-completo')
pistas = {}
for k in CIC['pistas']:
    if k['objetivo'] == 'camara' or k['propiedad'] not in ('posicion', 'rotacion'): continue
    pistas.setdefault(k['objetivo'], {})[k['propiedad']] = {'claves': k['claves'], 'modo': k.get('interpolacion') or 'suave'}
equipos = {'TX': EQ['TX'], 'TY': EQ['TY'], 'TZ': EQ['TZ'], 'duracion': CIC['duracion'], 'partes': EQ['partes'], 'pistas': pistas}

num = lambda v: ('%.3f' % v).rstrip('0').rstrip('.')
def compacto(o):
    if isinstance(o, list) and o and isinstance(o[0], list) and len(o[0]) == 6:
        filas = ['[' + ','.join(num(v) for v in r) + ']' for r in o]
        return '[\n' + ',\n'.join(','.join(filas[i:i + 6]) for i in range(0, len(filas), 6)) + '\n]'
    if isinstance(o, dict): return '{' + ','.join(json.dumps(k) + ':' + compacto(v) for k, v in o.items()) + '}'
    if isinstance(o, list): return '[' + ','.join(compacto(v) for v in o) + ']'
    return json.dumps(o, ensure_ascii=False)
html = open(R_PLA, encoding='utf-8').read()
for m in ('__VIDEO__', '__RECORRIDOS__', '__SUELTOS__', '__CORREAS__', '__EQUIPOS__'):
    assert m in html, 'plantilla sin la marca ' + m
html = (html.replace('__VIDEO__', json.dumps(video, ensure_ascii=False)).replace('__RECORRIDOS__', compacto(recorridos))
            .replace('__SUELTOS__', 'null').replace('__CORREAS__', 'null')
            .replace('__EQUIPOS__', json.dumps(equipos, ensure_ascii=False, separators=(',', ':'))))
open(R_SAL, 'w', encoding='utf-8', newline='\n').write(html)
print(f'Visor generado: {R_SAL} ({len(html)/1024:.0f} KB; recorrido {O["nombre"]}; {len(mats)} grupos de material; '
      f'{len(EQ["partes"])} partes animadas, {len(pistas)} con pistas, ciclo {CIC["duracion"]} s)')
for n, v in mats.items(): print(f'  {n:24s} {v["disciplina"]:16s} metal {v["metal"]:.2f} rug {v["rugosidad"]:.2f} barniz {v["cc"]:.2f} alfa {v["alfa"]}')
