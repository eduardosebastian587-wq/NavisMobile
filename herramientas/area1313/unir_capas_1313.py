# Une las dos capas del Área 1313 en una escena para el visor tipo Hito (2026-10-30):
#   - Capa «Capas area 1313» (Piping, Control Systems, Electrical, terreno): .blend del conversor (mallas UNION_MAT_<hex>).
#   - Capa v4 (Mechanical + Structural): ___area_1313.visor.glb (lotes por disciplina+color, rangos por objeto).
# Las piezas animadas se separan con las MISMAS reglas de particion del visor v4.1 (animaciones.json: cajas de
# centroide, gana la primera regla, «oculto» elimina, sin cajas = elemento completo) y se guardan aparte, en
# coordenadas del visor v4, para animarlas con las pistas originales: <salida>_equipos.json + _equipos.bin.
# El resto del v4 se agrega a la escena como mallas V4_<Disciplina>_<hex> (vertices soldados a 1 mm, bordes vivos > 30°).
# Marco comun = el del .blend de Capas: real = (184840 - xb, 4448630 - yb, zb + 2250) m.
#   v4 -> Blender: xb = 8.13234 - vx ; yb = vz + 38.73396 ; zb = vy + 4.80603   (derivado de aReal del .visor.glb)
# Uso: blender -b "Capas area 1313 completo.blend" --python unir_capas_1313.py -- <visor.glb> <animaciones.json> <salida.glb>
import bpy, sys, json, struct, re, os, time, math
import numpy as np
a = sys.argv[sys.argv.index('--') + 1:]
ruta_glb, ruta_anim, salida = a[0], a[1], a[2]
t0 = time.time()
def log(*x): print('[unir %6.1f s]' % (time.time() - t0), *x, flush=True)

# ---------------------------------------------------------------- 1) leer el .visor.glb del v4
f = open(ruta_glb, 'rb'); h = f.read(20); L = struct.unpack('<I', h[12:16])[0]; J = json.loads(f.read(L)); f.read(8); B = f.read(); f.close()
V = J['scenes'][0]['extras']['visor']; O = V['objetos']
A = np.array(V['aReal'], float).reshape(4, 4).T
ORIG = np.array([184840.0, 4448630.0, 2250.0])
# comprobacion del marco: v4 -> real -> Blender de Capas debe ser la formula de la cabecera
tv = A[:3, 3] - ORIG
assert abs(A[0, 0] - 1) < 1e-9 and abs(A[1, 2] + 1) < 1e-9 and abs(A[2, 1] - 1) < 1e-9, 'aReal inesperado'
TX, TY, TZ = -tv[0], -tv[1], tv[2]          # xb = TX - vx ; yb = vz + TY ; zb = vy + TZ
log(f'marco v4->Blender: xb = {TX:.5f} - vx ; yb = vz + {TY:.5f} ; zb = vy + {TZ:.5f}')
def acc(i, comp, dt=np.float32):
    ac = J['accessors'][i]; bv = J['bufferViews'][ac['bufferView']]; o = bv.get('byteOffset', 0) + ac.get('byteOffset', 0)
    return np.frombuffer(B, dt, ac['count'] * comp, o).reshape(-1, comp)
lotes = []
for nd in J['nodes']:
    ex = nd.get('extras', {})
    if ex.get('paquete') != 'lote': continue
    p = J['meshes'][nd['mesh']]['primitives'][0]
    assert p.get('mode', 4) == 4
    lotes.append({'nombre': nd['name'], 'disc': ex['disciplina'], 'color': ex['color'], 'op': ex.get('opacidad', 1),
                  'pos': acc(p['attributes']['POSITION'], 3), 'nor': acc(p['attributes']['NORMAL'], 3),
                  'rangos': np.array(ex['rangos'], np.int64).reshape(-1, 3)})
aislados = set(V.get('aislados') or [])
log(f'v4: {len(O)} objetos, {len(lotes)} lotes, aislados {sorted(aislados)}')

# ---------------------------------------------------------------- 2) particiones (reglas del v4.1)
AN = json.load(open(ruta_anim, encoding='utf-8'))
reglas = []
for r in AN['particiones']:
    t = r['tag']
    m = re.match(r'^/(.*)/([a-z]*)$', t)
    rx = re.compile(m.group(1), re.I if 'i' in m.group(2) else 0) if m else None
    cajas = None
    if r.get('cajas'):
        cajas = [[(-np.inf if v is None else v) if k < 3 else (np.inf if v is None else v) for k, v in enumerate(c)] for c in r['cajas']]
    reglas.append(dict(r, rx=rx, cajasN=cajas))
def coincide(regla, tag):
    return bool(regla['rx'].search(tag)) if regla['rx'] else tag == regla['tag']
# triangulos asignados: por lote, arreglo de indice de regla (-1 = fijo, -2 = eliminado)
partes = {r['id']: {'pos': [], 'nor': []} for r in reglas}
for lo in lotes:
    ntri = len(lo['pos']) // 3
    asig = np.full(ntri, -1, np.int32)
    for ini, cnt, oi in lo['rangos']:
        if oi in aislados: asig[ini // 3:(ini + cnt) // 3] = -2; continue
        tag = O[oi]['tag']
        rs = [k for k, r in enumerate(reglas) if not r.get('vacio') and coincide(r, tag)]
        if not rs: continue
        t0_, t1_ = ini // 3, (ini + cnt) // 3
        cen = lo['pos'][ini:ini + cnt].reshape(-1, 3, 3).mean(1)
        sub = asig[t0_:t1_]
        for k in rs:
            libre = sub == -1
            if not libre.any(): break
            if reglas[k]['cajasN'] is None: sel = libre
            else:
                sel = np.zeros(len(sub), bool)
                for c in reglas[k]['cajasN']:
                    sel |= np.all((cen >= c[:3]) & (cen <= c[3:]), 1)
                sel &= libre
            sub[sel] = -2 if reglas[k].get('oculto') else k
        asig[t0_:t1_] = sub
    lo['asig'] = asig
    for k, r in enumerate(reglas):
        s = np.flatnonzero(asig == k)
        if s.size:
            idx = (s[:, None] * 3 + np.arange(3)).ravel()
            partes[r['id']]['pos'].append((lo['pos'][idx], lo['color'], lo['disc']))
            partes[r['id']]['nor'].append(lo['nor'][idx])
# salida de equipos animados (coordenadas del visor v4)
bloques = []; meta = []; off = 0
for r in reglas:
    p = partes[r['id']]
    grupos = {}
    for (pp, col, disc), nn in zip(p['pos'], p['nor']):
        if re.match(r'^molino_', r['id']): col = 0xa9a9a9          # v4.1: molinos del mismo color (unificarColorMolinos)
        grupos.setdefault((col, disc), ([], []))
        grupos[(col, disc)][0].append(pp); grupos[(col, disc)][1].append(nn)
    sub = []
    for (col, disc), (pl, nl) in grupos.items():
        P = np.concatenate(pl).astype(np.float32); N = np.clip(np.round(np.concatenate(nl) * 127), -127, 127).astype(np.int8)
        bloques.append(P.tobytes()); nb = len(P)
        sub.append({'color': int(col), 'disciplina': disc, 'vert': nb, 'pos': off, 'nor': None}); off += P.nbytes
        bloques.append(N.tobytes() + b'\0' * ((-N.nbytes) % 4)); sub[-1]['nor'] = off; off += N.nbytes + ((-N.nbytes) % 4)
    meta.append({k: r[k] for k in ('id', 'tag', 'padre', 'pivote', 'estirable', 'vacio', 'oculto') if k in r} | {'mallas': sub,
                 'tri': sum(s['vert'] for s in sub) // 3})
base_eq = os.path.splitext(salida)[0] + '_equipos'
open(base_eq + '.bin', 'wb').write(b''.join(bloques))
json.dump({'formato': 'equipos-1313-v1', 'marco': 'coordenadas del visor v4 (Y arriba); a Three: (TX - x, y + TZ, -z - TY)',
           'TX': TX, 'TY': TY, 'TZ': TZ, 'partes': meta}, open(base_eq + '.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
log('equipos animados:', ', '.join(f"{m['id']} {m['tri']:,}" for m in meta), f'-> {off/1e6:.1f} MB')

# ---------------------------------------------------------------- 3) escena: Capas + v4 fijo
for o in list(bpy.data.objects):
    if o.type != 'MESH': bpy.data.objects.remove(o, do_unlink=True)
col = bpy.context.scene.collection
def malla(nombre, P, color_hex, disc):
    q = np.round(P * 1000).astype(np.int64)
    u, inv = np.unique(q, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    me = bpy.data.meshes.new(nombre)
    me.vertices.add(len(u)); me.vertices.foreach_set('co', (u / 1000.0).astype(np.float32).ravel())
    nt = len(inv) // 3
    me.loops.add(len(inv)); me.loops.foreach_set('vertex_index', inv.astype(np.int32))
    me.polygons.add(nt); me.polygons.foreach_set('loop_start', np.arange(0, len(inv), 3, dtype=np.int32))
    me.update(calc_edges=True)
    me.polygons.foreach_set('use_smooth', np.ones(nt, bool))
    me.set_sharp_from_angle(angle=math.radians(30))
    mat = bpy.data.materials.get(nombre) or bpy.data.materials.new(nombre)
    c = [((color_hex >> s) & 255) / 255 for s in (16, 8, 0)]
    mat.diffuse_color = (*[x ** 2.2 for x in c], 1)
    mat.use_nodes = True; bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf: bsdf.inputs['Base Color'].default_value = (*[x ** 2.2 for x in c], 1)
    me.materials.append(mat)
    ob = bpy.data.objects.new(nombre, me); ob['disciplina'] = disc; col.objects.link(ob)
    return nt, len(u)
for lo in lotes:
    s = np.flatnonzero(lo['asig'] == -1)
    if not s.size: continue
    idx = (s[:, None] * 3 + np.arange(3)).ravel(); P = lo['pos'][idx].astype(np.float64)
    Pb = np.stack([TX - P[:, 0], P[:, 2] + TY, P[:, 1] + TZ], 1)
    nombre = f"V4_{lo['disc']}_{lo['color']:06X}"
    nt, nv = malla(nombre, Pb, lo['color'], lo['disc'])
    log(f'{nombre}: {nt:,} tri, {nv:,} vert soldados')
    lo['pos'] = lo['nor'] = None
del B, J
tot = 0
for o in bpy.data.objects:
    if o.type == 'MESH':
        o.data.calc_loop_triangles(); tot += len(o.data.loop_triangles)
        if o.name.startswith('UNION_MAT_'): o['disciplina'] = 'Capas'
log(f'escena: {len([o for o in bpy.data.objects if o.type == "MESH"])} mallas, {tot:,} tri')

# ---------------------------------------------------------------- 4) exportar GLB Draco (como el Hito)
for o in bpy.data.objects: o.select_set(o.type == 'MESH')
bpy.ops.export_scene.gltf(filepath=salida, export_format='GLB', use_selection=True, export_apply=True, export_yup=True,
    export_cameras=False, export_lights=False, export_extras=True, export_animations=False, export_texcoords=False,
    export_normals=True, export_materials='EXPORT',
    export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
    export_draco_position_quantization=16, export_draco_normal_quantization=10)
log(f'listo -> {salida} ({os.path.getsize(salida)/1e6:.1f} MB)')
