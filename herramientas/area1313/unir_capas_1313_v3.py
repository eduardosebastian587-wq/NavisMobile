# unir_capas_1313.py + (1) repintado de barandas "Handrail" a amarillo FFFF00 y (4) decimacion selectiva opcional. Original intacto como respaldo.
# Une las dos capas del Area 1313 en una escena para el visor tipo Hito:
#  - Capa "Capas area 1313" (Piping, Control Systems, Electrical, terreno): .blend del conversor (mallas UNION_MAT_<hex>).
#  - Capa v4 (Mechanical + Structural): ___area_1313.visor.glb (lotes por disciplina+color, rangos por objeto).
# Piezas animadas: mismas reglas de particion del visor v4.1 (animaciones.json); se guardan aparte: <salida>_equipos.json + .bin.
# Marco comun = el del .blend de Capas: real = (184840 - xb, 4448630 - yb, zb + 2250) m.  v4 -> Blender: xb = TX - vx ; yb = vz + TY ; zb = vy + TZ
# Uso: blender -b "Capas area 1313 completo.blend" --python unir_capas_1313_v2.py -- <visor.glb> <animaciones.json> <salida.glb> [--barandas cajas.json] [--decimar V4_Structural_00FF00=0.5,...]
#   --barandas : salida de extraer_barandas_1313.py. Triangulos fijos (no animados) con centroide dentro de una caja -> malla V4_<disc>_FFFF00_baranda.
#   --decimar  : nombre de malla = razon (0-1) de triangulos que se CONSERVAN (Decimate colapso). Solo para las mallas nombradas.
import bpy, sys, json, struct, re, os, time, math
import numpy as np
a = sys.argv[sys.argv.index('--') + 1:]
ruta_glb, ruta_anim, salida = a[0], a[1], a[2]
def opt(k, d=None):
    return a[a.index(k) + 1] if k in a else d
ruta_bar = opt('--barandas')
DECIMAR = {}
if opt('--decimar'):
    for par in opt('--decimar').split(','):
        n, r = par.split('='); DECIMAR[n.strip()] = float(r)
t0 = time.time()
def log(*x): print('[unir %6.1f s]' % (time.time() - t0), *x, flush=True)

# ---------------------------------------------------------------- 1) leer el .visor.glb del v4
f = open(ruta_glb, 'rb'); h = f.read(20); L = struct.unpack('<I', h[12:16])[0]; J = json.loads(f.read(L)); f.read(8); B = f.read(); f.close()
V = J['scenes'][0]['extras']['visor']; O = V['objetos']
A = np.array(V['aReal'], float).reshape(4, 4).T
ORIG = np.array([184840.0, 4448630.0, 2250.0])
tv = A[:3, 3] - ORIG
assert abs(A[0, 0] - 1) < 1e-9 and abs(A[1, 2] + 1) < 1e-9 and abs(A[2, 1] - 1) < 1e-9, 'aReal inesperado'
TX, TY, TZ = -tv[0], -tv[1], tv[2]   # xb = TX - vx ; yb = vz + TY ; zb = vy + TZ
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
partes = {r['id']: {'pos': [], 'nor': []} for r in reglas}
for lo in lotes:
    ntri = len(lo['pos']) // 3
    asig = np.full(ntri, -1, np.int32)   # -1 = fijo, -2 = eliminado, k>=0 = regla k
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
bloques = []; meta = []; off = 0
for r in reglas:
    p = partes[r['id']]
    grupos = {}
    for (pp, col, disc), nn in zip(p['pos'], p['nor']):
        if re.match(r'^molino_', r['id']): col = 0xa9a9a9   # v4.1: molinos del mismo color (unificarColorMolinos)
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

# ---------------------------------------------------------------- 2b) barandas: cajas Handrail (mundo real) -> marco v4
cajas_v4 = None
if ruta_bar:
    CB = json.load(open(ruta_bar, encoding='utf-8'))
    cr = np.array(CB['cajas'], float).reshape(-1, 6) + np.tile(CB['desf'], 2)   # a coordenadas reales
    # real = A @ (vx, vy, vz, 1)  ->  v4 = A^-1 @ real ; se transforman las 8 esquinas y se toma la caja envolvente
    Ai = np.linalg.inv(A)
    esq = np.array([[c[i], c[j], c[k]] for c in cr for i in (0, 3) for j in (1, 4) for k in (2, 5)]).reshape(-1, 8, 3)
    ev = esq @ Ai[:3, :3].T + Ai[:3, 3]
    cajas_v4 = np.concatenate([ev.min(1), ev.max(1)], 1)
    allp = np.concatenate([lo['pos'] for lo in lotes if lo['pos'] is not None])
    log(f'barandas: {len(cajas_v4)} cajas. Limites cajas v4: {cajas_v4[:, :3].min(0).round(1)} .. {cajas_v4[:, 3:].max(0).round(1)}')
    log(f'          limites del modelo v4:        {allp.min(0).round(1)} .. {allp.max(0).round(1)}   (deben coincidir en orden de magnitud; si no, revisar --desf)')
    del allp

# ---------------------------------------------------------------- 3) escena: Capas + v4 fijo
for o in list(bpy.data.objects):
    if o.type != 'MESH': bpy.data.objects.remove(o, do_unlink=True)
col = bpy.context.scene.collection
def malla(nombre, P, color_hex, disc, mat_nombre=None):
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
    mn = mat_nombre or nombre                                   # el material debe llamarse MAT_<hex> o V4_<disc>_<hex> (lo exige generar_visor_1313.py)
    mat = bpy.data.materials.get(mn) or bpy.data.materials.new(mn)
    c = [((color_hex >> s) & 255) / 255 for s in (16, 8, 0)]
    mat.diffuse_color = (*[x ** 2.2 for x in c], 1)
    mat.use_nodes = True; bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf: bsdf.inputs['Base Color'].default_value = (*[x ** 2.2 for x in c], 1)
    me.materials.append(mat)
    ob = bpy.data.objects.new(nombre, me); ob['disciplina'] = disc; col.objects.link(ob)
    return nt, len(u)
ruta_vert = opt('--barandas_vert')   # npy de extraer_barandas_1313.py: vertices exactos de las barandas (real - origen)
claves_h = None
CELDA = 0.02; TOL = 0.01
def _claves(Q):
    i = np.floor(Q / CELDA).astype(np.int64) + 30000
    return (i[:, 0] << 32) | (i[:, 1] << 16) | i[:, 2]
if ruta_vert:
    H = np.load(ruta_vert).astype(np.float64) + np.array(CB['origen_vertices'])
    Hv = H @ Ai[:3, :3].T + Ai[:3, 3]; del H                      # real -> marco v4
    ks = []
    for sx in (-TOL, TOL):
        for sy in (-TOL, TOL):
            for sz in (-TOL, TOL): ks.append(_claves(Hv + np.array([sx, sy, sz])))
    claves_h = np.unique(np.concatenate(ks)); del ks, Hv
    log(f'barandas por vertice: {len(claves_h):,} celdas de {CELDA} m (tolerancia {TOL} m)')
def tri_por_vertices(P3):          # P3 = (n,3,3) vertices v4 por triangulo; baranda si >= 2 vertices coinciden
    k = _claves(P3.reshape(-1, 3)); pos = np.searchsorted(claves_h, k); pos[pos >= len(claves_h)] = 0
    ok = (claves_h[pos] == k).reshape(-1, 3)
    return ok.sum(1) >= 2, ok.all(1)
def tri_en_cajas(cen, cajas):
    sel = np.zeros(len(cen), bool)
    for c in cajas:
        sel |= np.all((cen >= c[:3]) & (cen <= c[3:]), 1)
    return sel
repintados = {}
for lo in lotes:
    s = np.flatnonzero(lo['asig'] == -1)
    if not s.size: continue
    idx = (s[:, None] * 3 + np.arange(3)).ravel(); P = lo['pos'][idx].astype(np.float64)
    bar = np.zeros(len(s), bool)
    if cajas_v4 is not None and lo['color'] != 0xFFFF00:
        bar = tri_en_cajas(P.reshape(-1, 3, 3).mean(1), cajas_v4)
        if claves_h is not None:
            b2, b3 = tri_por_vertices(P.reshape(-1, 3, 3))
            log(f"  {lo['nombre']}: caja {int(bar.sum()):,} | vertices>=2 {int(b2.sum()):,} | vertices=3 {int(b3.sum()):,} | ambos {int((bar & b2).sum()):,}")
            bar = b2
    grupos = [(lo['color'], '', ~bar)]
    if bar.any():
        grupos.append((0xFFFF00, '_baranda', bar)); repintados[lo['nombre']] = (int(bar.sum()), lo['color'])
    for color, suf, m in grupos:
        if not m.any(): continue
        Pm = P.reshape(-1, 3, 3)[m].reshape(-1, 3)
        Pb = np.stack([TX - Pm[:, 0], Pm[:, 2] + TY, Pm[:, 1] + TZ], 1)
        nombre = f"V4_{lo['disc']}_{color:06X}{suf}"
        nt, nv = malla(nombre, Pb, color, lo['disc'], mat_nombre=f"V4_{lo['disc']}_{color:06X}")
        log(f'{nombre}: {nt:,} tri, {nv:,} vert soldados')
    lo['pos'] = lo['nor'] = None
if ruta_bar:
    log('REPINTADO a amarillo por lote de origen (triangulos, color original):', {k: (n, f'{c:06X}') for k, (n, c) in repintados.items()})
    if not repintados: log('AVISO: ningun triangulo cayo en las cajas Handrail -> marco/desfase incorrecto, NO usar este resultado')
del B, J
# relleno de huecos de tuberia (--huecos huecos_relleno.json de analizar_huecos_tuberia_1313.py): tubos rectos del mismo radio y color
if opt('--huecos'):
    HJ = json.load(open(opt('--huecos'), encoding='utf-8')); ORI_H = np.array(HJ['origen']); NS = 16
    por_color = {}
    for t in HJ['tramos']: por_color.setdefault(t['color'], []).append(t)
    for hexc, lst in por_color.items():
        a0 = np.array([t['p0'] for t in lst]) + ORI_H; a1 = np.array([t['p1'] for t in lst]) + ORI_H; rad = np.array([t['radio'] for t in lst])
        u = a1 - a0; u /= np.linalg.norm(u, axis=1)[:, None]
        ref = np.where(np.abs(u[:, 2:3]) < 0.9, np.array([[0, 0, 1.0]]), np.array([[1.0, 0, 0]]))
        e1 = np.cross(u, ref); e1 /= np.linalg.norm(e1, axis=1)[:, None]; e2 = np.cross(u, e1)
        ang = np.linspace(0, 2 * np.pi, NS, endpoint=False); cs, sn = np.cos(ang), np.sin(ang)
        ring = (e1[:, None, :] * cs[None, :, None] + e2[:, None, :] * sn[None, :, None]) * rad[:, None, None]     # (n,NS,3)
        A = a0[:, None, :] + ring; B = a1[:, None, :] + ring; Ak = np.roll(A, -1, 1); Bk = np.roll(B, -1, 1)
        tri = np.concatenate([np.stack([A, B, Bk], 2), np.stack([A, Bk, Ak], 2)], 1).reshape(-1, 3)             # sopa de triangulos (real)
        Pb = np.stack([184840.0 - tri[:, 0], 4448630.0 - tri[:, 1], tri[:, 2] - 2250.0], 1)                      # real -> Blender de Capas
        nt, nv = malla(f'UNION_MAT_{hexc}_relleno', Pb, int(hexc, 16), 'Capas', mat_nombre=f'MAT_{hexc}')
        log(f'relleno tuberia {hexc}: {len(lst)} tramos, {nt:,} tri')
        ob0 = bpy.data.objects.get(f'UNION_MAT_{hexc}')               # verificacion de marco: el relleno debe quedar pegado a la tuberia real
        if ob0 is None: log(f'  AVISO: no existe la malla UNION_MAT_{hexc} en Capas -> color/marco sin verificar')
        else:
            co = np.empty(len(ob0.data.vertices) * 3, np.float32); ob0.data.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
            mw = np.array(ob0.matrix_world); co = co @ mw[:3, :3].T + mw[:3, 3]
            ms = np.array(bpy.data.objects[f'UNION_MAT_{hexc}_relleno'].data.vertices[0].co)
            sm = Pb[np.linspace(0, len(Pb) - 1, 40).astype(int)]
            dd = [float(np.sqrt(((co - s) ** 2).sum(1)).min()) for s in sm]
            log(f'  distancia relleno -> tuberia real {hexc}: mediana {np.median(dd):.3f} m, max {max(dd):.3f} m (debe ser < ~0,3 m)')
# v3: ocultar piezas de tuberia a ambos lados de huecos 0,2-3 m (--ocultar huecos3_ocultar.json, decision de Eduardo 2026-10-30)
# Se borran de las mallas Capas UNION_MAT_* (no de los rellenos) las caras cuyo centro cae dentro del cilindro de la pieza
# (radio 1,1 r + 1,5 cm, largo +/- 1 cm). Las piezas borradas se guardan aparte en <salida>_ocultas.glb (recuperables).
if opt('--ocultar'):
    import bmesh
    from mathutils import kdtree, Vector
    OJ = json.load(open(opt('--ocultar'), encoding='utf-8')); ORI_O = np.array(OJ['origen'])
    cil = []
    for p in OJ['piezas']:
        w0 = np.array(p['p0']); w1 = np.array(p['p1'])                 # real - ORI_O ; Blender de Capas: (40 - x, 30 - y, z)
        b0 = np.array([40.0 - w0[0], 30.0 - w0[1], w0[2]]); b1 = np.array([40.0 - w1[0], 30.0 - w1[1], w1[2]])
        L_ = float(np.linalg.norm(b1 - b0)); u_ = (b1 - b0) / L_
        cil.append((b0, u_, L_, 1.1 * p['radio'] + 0.015))
    assert np.allclose(ORI_O, [184800.0, 4448600.0, 2250.0]), 'origen inesperado en --ocultar'
    borradas_obj = []; tot_b = 0
    for ob in [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('UNION_MAT_') and not o.name.endswith('_relleno')]:
        me = ob.data; n = len(me.polygons)
        if not n: continue
        C = np.empty(n * 3, np.float32); me.polygons.foreach_get('center', C); C = C.reshape(-1, 3).astype(np.float64)
        mw = np.array(ob.matrix_world); C = C @ mw[:3, :3].T + mw[:3, 3]
        kd = kdtree.KDTree(n)
        for i, c in enumerate(C): kd.insert(c, i)
        kd.balance()
        sel = set()
        for b0, u_, L_, R_ in cil:
            m_ = b0 + u_ * (L_ / 2)
            idx = [j for (_, j, _) in kd.find_range(Vector(m_), math.hypot(L_ / 2 + 0.01, R_))]
            if not idx: continue
            d = C[idx] - b0; t = d @ u_; r = np.linalg.norm(d - np.outer(t, u_), axis=1)
            ok = (t >= -0.01) & (t <= L_ + 0.01) & (r <= R_)
            sel.update(np.array(idx)[ok].tolist())
        if not sel: continue
        bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
        # copia de lo borrado (recuperable) en un objeto aparte, no exportado con el modelo
        bm2 = bm.copy(); bm2.faces.ensure_lookup_table()
        bmesh.ops.delete(bm2, geom=[f for f in bm2.faces if f.index not in sel], context='FACES')
        me2 = bpy.data.meshes.new(ob.name + '_oculta'); bm2.to_mesh(me2); bm2.free()
        for mt in me.materials: me2.materials.append(mt)
        ob2 = bpy.data.objects.new(ob.name + '_oculta', me2); ob2.matrix_world = ob.matrix_world; col.objects.link(ob2); borradas_obj.append(ob2)
        bmesh.ops.delete(bm, geom=[bm.faces[j] for j in sel], context='FACES')
        bm.to_mesh(me); bm.free(); me.update()
        tot_b += len(sel); log(f'ocultar tuberia {ob.name}: {len(sel):,} de {n:,} caras')
    log(f'OCULTAR: {len(cil)} piezas, {tot_b:,} caras borradas en total')
    if borradas_obj:
        for o in bpy.data.objects: o.select_set(o in borradas_obj)
        bpy.ops.export_scene.gltf(filepath=os.path.splitext(salida)[0] + '_ocultas.glb', export_format='GLB', use_selection=True,
                                  export_apply=True, export_yup=True, export_cameras=False, export_lights=False, export_animations=False,
                                  export_texcoords=False, export_materials='EXPORT')
        for o in borradas_obj: bpy.data.objects.remove(o, do_unlink=True)
        log('piezas ocultas guardadas aparte ->', os.path.splitext(salida)[0] + '_ocultas.glb')
# decimacion selectiva (solo mallas nombradas en --decimar)
for n, r in DECIMAR.items():
    ob = bpy.data.objects.get(n)
    if not ob: log(f'AVISO decimar: no existe la malla {n}'); continue
    antes = len(ob.data.polygons)
    md = ob.modifiers.new('decim', 'DECIMATE'); md.decimate_type = 'COLLAPSE'; md.ratio = r; md.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier='decim')
    log(f'decimar {n}: {antes:,} -> {len(ob.data.polygons):,} tri (razon {r})')
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
