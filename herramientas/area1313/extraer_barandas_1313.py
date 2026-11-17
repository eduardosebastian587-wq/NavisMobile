# Cajas de los nodos "Handrail" del FBX del v4 (___area_1313.fbx), para repintar barandas a amarillo (FFFF00) en unir_capas_1313_v2.py.
# Lectura en streaming (mmap + zlib), misma tecnica de fbx_tags_correas.py. Solo lectura; no modifica el FBX.
# Salida: <salida>.json = {"desf": [...], "cajas": [[xmin,ymin,zmin,xmax,ymax,zmax], ...], "nombres": {...}}
#   Coordenadas = mundo del FBX en metros (Z arriba) MENOS --desf. Con --desf 0,0,0 se asume que el FBX ya esta en coordenadas reales.
#   El desfase de ESTE FBX no esta verificado: unir_capas_1313_v2.py imprime los limites de las cajas contra los del v4 para detectarlo.
# Uso: py extraer_barandas_1313.py <___area_1313.fbx> <salida.json> [--desf 0,0,0] [--regex ^Handrail$]
import sys, mmap, struct, zlib, re, json, math, time, collections
import numpy as np
a = sys.argv[1:]
ruta, salida = a[0], a[1]
def opt(k, d):
    return a[a.index(k) + 1] if k in a else d
DESF = np.array([float(x) for x in opt('--desf', '0,0,0').split(',')])
FILTRO = re.compile(opt('--regex', r'^Handrail$'))
t0 = time.time(); log = lambda *x: print(f'[{time.time()-t0:6.1f} s]', *x, flush=True)
f = open(ruta, 'rb'); mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
ver = struct.unpack_from('<I', mm, 23)[0]; W = 8 if ver >= 7500 else 4
HDR = 25 if W == 8 else 13
def cab(o):
    if W == 8: end, n, pl = struct.unpack_from('<QQQ', mm, o)
    else: end, n, pl = struct.unpack_from('<III', mm, o)
    nl = mm[o + 3 * W]; nombre = mm[o + 3 * W + 1:o + 3 * W + 1 + nl].decode('latin1')
    return end, n, pl, nombre, o + 3 * W + 1 + nl
def props(p, n):
    out = []
    for _ in range(n):
        c = chr(mm[p]); p += 1
        if c == 'Y': out.append(struct.unpack_from('<h', mm, p)[0]); p += 2
        elif c == 'C': out.append(mm[p]); p += 1
        elif c == 'I': out.append(struct.unpack_from('<i', mm, p)[0]); p += 4
        elif c == 'F': out.append(struct.unpack_from('<f', mm, p)[0]); p += 4
        elif c == 'D': out.append(struct.unpack_from('<d', mm, p)[0]); p += 8
        elif c == 'L': out.append(struct.unpack_from('<q', mm, p)[0]); p += 8
        elif c in 'SR': l = struct.unpack_from('<I', mm, p)[0]; out.append(mm[p + 4:p + 4 + l]); p += 4 + l
        elif c in 'fdlib':
            ln, enc, cl = struct.unpack_from('<III', mm, p); out.append(('ARR', c, ln, enc, cl, p + 12)); p += 12 + cl
        else: raise ValueError('tipo ' + c)
    return out
def hijos(o):
    end, n, pl, nombre, p = cab(o); q = p + pl
    while q < end - HDR:
        e2 = cab(q)[0]
        if e2 == 0: break
        yield q; q = e2
def arr(x):
    _, c, ln, enc, cl, p = x; d = mm[p:p + cl]
    if enc: d = zlib.decompress(d)
    return np.frombuffer(d, {'d': '<f8', 'f': '<f4', 'i': '<i4', 'l': '<i8', 'b': 'u1'}[c])[:ln]
o = 27; top = {}
while o < len(mm):
    end, n, pl, nombre, p = cab(o)
    if end == 0: break
    top[nombre] = o; o = end
unit = 1.0
for h in hijos(top['GlobalSettings']):
    for h2 in hijos(h):
        _, n, pl, nm, p = cab(h2); pr = props(p, n)
        if pr and pr[0] == b'UnitScaleFactor': unit = float(pr[-1])
log('version', ver, 'UnitScaleFactor', unit)
modelos = {}; geoms = {}
for h in hijos(top['Objects']):
    end, n, pl, nm, p = cab(h)
    if nm == 'Model':
        pr = props(p, n); mid = pr[0]; nombre = pr[1].split(b'\x00')[0].decode('utf-8', 'replace')
        d = {'n': nombre, 'T': (0, 0, 0), 'R': (0, 0, 0), 'S': (1, 1, 1), 'GT': (0, 0, 0), 'GR': (0, 0, 0), 'GS': (1, 1, 1), 'PR': (0, 0, 0)}
        for h2 in hijos(h):
            if cab(h2)[3] != 'Properties70': continue
            for h3 in hijos(h2):
                _, n3, _, _, p3 = cab(h3); q = props(p3, n3); k = q[0]
                m = {b'Lcl Translation': 'T', b'Lcl Rotation': 'R', b'Lcl Scaling': 'S', b'GeometricTranslation': 'GT',
                     b'GeometricRotation': 'GR', b'GeometricScaling': 'GS', b'PreRotation': 'PR'}.get(k)
                if m: d[m] = tuple(q[-3:])
        modelos[mid] = d
    elif nm == 'Geometry':
        pr = props(p, n)
        for h2 in hijos(h):
            e2, n2, _, nm2, p2 = cab(h2)
            if nm2 == 'Vertices': geoms[pr[0]] = props(p2, n2)[0]; break
padre = {}; geo_de = {}
for h in hijos(top['Connections']):
    _, n, _, _, p = cab(h); q = props(p, n)
    if q[0] != b'OO': continue
    x, y = q[1], q[2]
    if x in modelos: padre[x] = y
    elif x in geoms and y in modelos: geo_de[y] = x
log('modelos', len(modelos), 'con malla', len(geo_de))
def rot(e):
    x, y, z = [math.radians(v) for v in e]
    Rx = np.array([[1, 0, 0], [0, math.cos(x), -math.sin(x)], [0, math.sin(x), math.cos(x)]])
    Ry = np.array([[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]])
    Rz = np.array([[math.cos(z), -math.sin(z), 0], [math.sin(z), math.cos(z), 0], [0, 0, 1]])
    return Rz @ Ry @ Rx
def M(T, R, S, PR=(0, 0, 0)):
    m = np.eye(4); m[:3, :3] = rot(PR) @ rot(R) @ np.diag(S); m[:3, 3] = T; return m
cache = {}
def mundo(mid):
    if mid in cache: return cache[mid]
    d = modelos[mid]; m = M(d['T'], d['R'], d['S'], d['PR'])
    pa = padre.get(mid)
    if pa in modelos: m = mundo(pa) @ m
    cache[mid] = m; return m
sys.setrecursionlimit(100000)
# un nodo Handrail puede ser el Model con malla o un contenedor de piezas: se toma la malla propia y la de sus descendientes
def es_handrail(mid):
    while mid in modelos:
        if FILTRO.search(modelos[mid]['n']): return True
        mid = padre.get(mid)
    return False
cajas = []; nombres = collections.Counter()
VERT = []; ORI = np.array([184800.0, 4448600.0, 2250.0])   # vertices de las barandas en coordenadas reales menos ORI (float32 conserva el mm)
for mid, gid in geo_de.items():
    if not es_handrail(mid): continue
    v = arr(geoms[gid]).reshape(-1, 3)
    d = modelos[mid]; G = M(d['GT'], d['GR'], d['GS'])
    W4 = mundo(mid) @ G
    w = (v @ W4[:3, :3].T + W4[:3, 3]) * (unit / 100.0) - DESF   # unit = factor FBX (cm = 1.0 -> /100 a metros)
    cajas.append([*w.min(0).round(3).tolist(), *w.max(0).round(3).tolist()]); nombres[modelos[mid]['n']] += 1
    VERT.append(np.unique(np.round(w + DESF - ORI, 3), axis=0).astype(np.float32))
log('cajas Handrail:', len(cajas), dict(nombres))
json.dump({'desf': DESF.tolist(), 'unit': unit, 'cajas': cajas, 'nombres': dict(nombres)}, open(salida, 'w', encoding='utf-8'))
V = np.unique(np.concatenate(VERT), axis=0); np.save(salida.replace('.json', '_vertices.npy'), V)
json.dump({'desf': DESF.tolist(), 'unit': unit, 'cajas': cajas, 'nombres': dict(nombres), 'origen_vertices': ORI.tolist(), 'n_vertices': int(len(V))}, open(salida, 'w', encoding='utf-8'))
log('vertices unicos de barandas:', len(V)); log('listo ->', salida)
