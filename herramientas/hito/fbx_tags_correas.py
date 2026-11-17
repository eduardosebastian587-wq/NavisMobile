# Lee hito.fbx (binario 7.x) en modo streaming (mmap, sin cargar todo) y obtiene, para cada pieza (Model con malla)
# cuyo TAG (propio o de un ancestro) coincida con el filtro, su caja en coordenadas Blender del visor
# (= mundo - desfase (185330; 4448630; 2300) m). Salida: CSV por pieza + JSON resumen por TAG.
# Uso: py fbx_tags_correas.py <hito.fbx> <salida_prefijo> [regex_tag]
import sys, mmap, struct, zlib, re, json, math, time, collections
import numpy as np
ruta, salida = sys.argv[1], sys.argv[2]
FILTRO = re.compile(sys.argv[3] if len(sys.argv) > 3 else r'-(CV|FE|BC|CH|SC|DC|CK|BK|MC|BL)-')
TAGRE = re.compile(r'(?<![0-9A-Za-z-])\d{4}-[A-Z]{1,4}-\d{2,5}[A-Z]?')
DESF = np.array([185330.0, 4448630.0, 2300.0])
t0 = time.time(); log = lambda *a: print(f'[{time.time()-t0:6.1f} s]', *a, flush=True)
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
def arr(a):
    _, c, ln, enc, cl, p = a; d = mm[p:p + cl]
    if enc: d = zlib.decompress(d)
    return np.frombuffer(d, {'d': '<f8', 'f': '<f4', 'i': '<i4', 'l': '<i8', 'b': 'u1'}[c])[:ln]
# ---- nodos de primer nivel
o = 27; top = {}
while o < len(mm):
    end, n, pl, nombre, p = cab(o)
    if end == 0: break
    top[nombre] = o; o = end
log('version', ver, 'nodos', list(top))
unit = 1.0
for h in hijos(top['GlobalSettings']):
    for h2 in hijos(h):
        _, n, pl, nm, p = cab(h2); pr = props(p, n)
        if pr and pr[0] == b'UnitScaleFactor': unit = float(pr[-1])
log('UnitScaleFactor', unit)
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
log('modelos', len(modelos), 'geometrias', len(geoms))
padre = {}; geo_de = {}
for h in hijos(top['Connections']):
    _, n, _, _, p = cab(h); q = props(p, n)
    if q[0] != b'OO': continue
    a, b = q[1], q[2]
    if a in modelos: padre[a] = b
    elif a in geoms and b in modelos: geo_de[b] = a
log('conexiones listas; modelos con malla', len(geo_de))
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
def tag_de(mid):
    while mid in modelos:
        t = TAGRE.search(modelos[mid]['n'])
        if t: return t.group(0), mid
        mid = padre.get(mid)
    return None, None
filas = []; res = collections.defaultdict(lambda: {'min': [1e18] * 3, 'max': [-1e18] * 3, 'piezas': 0, 'vert': 0, 'nombres': collections.Counter()})
for mid, gid in geo_de.items():
    tg, tmid = tag_de(mid)
    if not tg or not FILTRO.search(tg): continue
    v = arr(geoms[gid]).reshape(-1, 3)
    d = modelos[mid]; G = M(d['GT'], d['GR'], d['GS'])
    W4 = mundo(mid) @ G
    w = v @ W4[:3, :3].T + W4[:3, 3]
    w = w * (unit / 100.0) - DESF if unit != 100.0 else w - DESF
    lo, hi = w.min(0), w.max(0)
    pa = padre.get(mid); cad = []
    x = mid
    while x in modelos and x != tmid: cad.append(modelos[x]['n']); x = padre.get(x)
    nombre = ' / '.join(reversed(cad[:3]))
    filas.append((tg, nombre, len(v), *lo.round(3), *hi.round(3)))
    r = res[tg]; r['min'] = np.minimum(r['min'], lo).tolist(); r['max'] = np.maximum(r['max'], hi).tolist(); r['piezas'] += 1; r['vert'] += len(v)
    r['nombres'][nombre.split(' / ')[-1][:40]] += 1
log('piezas filtradas', len(filas))
with open(salida + '_piezas.csv', 'w', encoding='utf-8') as o:
    o.write('tag;pieza;vertices;xmin;ymin;zmin;xmax;ymax;zmax\n')
    for fl in sorted(filas): o.write(';'.join(str(x) for x in fl) + '\n')
json.dump({k: {'min': [round(a, 2) for a in r['min']], 'max': [round(a, 2) for a in r['max']], 'piezas': r['piezas'], 'vert': r['vert'],
               'nombres': r['nombres'].most_common(12)} for k, r in sorted(res.items())},
          open(salida + '_tags.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
log('listo')
