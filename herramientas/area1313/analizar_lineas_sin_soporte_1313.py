# Lineas de tuberia sin soporte (solo lectura). Cabecera = lector FBX de analizar_huecos_tuberia_1313.py
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
modelos = {}; geoms = {}; mats = {}; mat_de = {}
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
    elif nm == 'Material':
        pr = props(p, n); mats[pr[0]] = None
        for h2 in hijos(h):
            if cab(h2)[3] != 'Properties70': continue
            for h3 in hijos(h2):
                _, n3, _, _, p3 = cab(h3); q = props(p3, n3)
                if q and q[0] in (b'DiffuseColor', b'Diffuse'): mats[pr[0]] = tuple(q[-3:])
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
    elif x in mats and y in modelos: mat_de[y] = x
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

# ================= ANALISIS DE LINEAS SIN SOPORTE (solo lectura) =================
# Uso: py analizar_lineas_sin_soporte_1313.py <Capas area 1313.fbx> <salida.json> --glb <area1313_web_v2.glb> [--relleno huecos_relleno.json] [--tol 0.05]
# Tuberias = piezas del FBX de Capas con color de Piping (sin "Insulation Volume"); linea = componente conexo (extremos a < 4 cm, + rellenos de hueco).
# Soportes = estructura/mecanico/rejillas/terreno del GLB v2 (marco Blender) + miembros de Piping (FF8000, 0080FF). Contacto = puntos a <= TOL (5 cm).
import DracoPy
from scipy.spatial import cKDTree
from scipy.interpolate import LinearNDInterpolator
GLB = opt('--glb', None); REL = opt('--relleno', None); TOL = float(opt('--tol', '0.05'))
ORI = np.array([184800.0, 4448600.0, 2250.0])
def hx(s): return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
PIPE_COL = [hx(s) for s in ('BFBFBF', 'FF0000', '00F200', '3A5484', 'F27F00', '00F2F2', '8E9DBF', '828CA0')]
SUP_COL = [hx(s) for s in ('FF8000', '0080FF')]
def en(col, lista): return col is not None and any(max(abs(a - b) for a, b in zip(col, c)) <= 3 for c in lista)
piezas = []; mids = []; sup_fbx = []; ends = []; ends_p = []; samp = []; samp_p = []; omit = collections.Counter()
for mid, gid in geo_de.items():
    d = modelos[mid]
    if d['n'] == 'Insulation Volume': continue
    m_ = mid; col = None
    while m_ in modelos and col is None:
        cm = mats.get(mat_de.get(m_))
        if cm: col = tuple(int(round(min(max(x, 0), 1) * 255)) for x in cm[:3])
        m_ = padre.get(m_)
    es_p = en(col, PIPE_COL); es_s = en(col, SUP_COL)
    if not (es_p or es_s): continue
    v = arr(geoms[gid]).reshape(-1, 3)
    if len(v) < 4: continue
    G = M(d['GT'], d['GR'], d['GS']); W4 = mundo(mid) @ G
    w = (v @ W4[:3, :3].T + W4[:3, 3]) * (unit / 100.0) - ORI
    w = np.array([40.0, 30.0, 0.0]) + w * np.array([-1.0, -1.0, 1.0])     # real-ORI -> Blender de Capas (xb=184840-real_x; yb=4448630-real_y; zb=real_z-2250)
    if es_s:
        sup_fbx.append(w[np.linspace(0, len(w) - 1, min(len(w), 400)).astype(int)]); continue
    i = len(piezas); c = w.mean(0)
    _, _, vt = np.linalg.svd(w[::max(1, len(w) // 2000)] - c, full_matrices=False)
    ln = float(np.ptp((w - c) @ vt[0]))
    piezas.append(ln); mids.append(mid)
    s = w[np.linspace(0, len(w) - 1, min(len(w), 120)).astype(int)]; samp.append(s); samp_p.append(np.full(len(s), i))
    pts = []
    for dr in np.vstack([vt, np.eye(3)]):
        pr = w @ dr
        for sg in (1, -1):
            k = np.argpartition(-sg * pr, min(3, len(w) - 1))[:3]; pts.append(w[k])
    e = np.vstack(pts); e = e[np.unique(np.round(e / 0.02), axis=0, return_index=True)[1]]
    ends.append(e); ends_p.append(np.full(len(e), i))
NP_ = len(piezas); log('piezas de tuberia:', NP_, '| puntos de miembros Piping (soporte):', sum(len(x) for x in sup_fbx))
S = np.vstack(samp); SP = np.concatenate(samp_p); E = np.vstack(ends); EP = np.concatenate(ends_p)
log('puntos muestra:', len(S), 'extremos:', len(E))
# ---- conectividad (union-find) ----
par = np.arange(NP_)
def fnd(x):
    while par[x] != x: par[x] = par[par[x]]; x = par[x]
    return x
def uni(a, b):
    ra, rb = fnd(a), fnd(b)
    if ra != rb: par[rb] = ra
te = cKDTree(E); pr_ = te.query_pairs(0.04, output_type='ndarray')
pr_ = pr_[EP[pr_[:, 0]] != EP[pr_[:, 1]]]
for a_, b_ in pr_: uni(int(EP[a_]), int(EP[b_]))
n_rel = 0
if REL:
    for t in json.load(open(REL))['tramos']:
        ids = []
        for p in (t['p0'], t['p1']):
            dd, ii = te.query(np.array([40.0, 30.0, 0.0]) + np.array(p) * np.array([-1.0, -1.0, 1.0]), distance_upper_bound=0.1)
            if np.isfinite(dd): ids.append(int(EP[ii]))
        if len(ids) == 2: uni(ids[0], ids[1]); n_rel += 1
log('pares de extremos unidos:', len(pr_), '| rellenos aplicados:', n_rel)
comp = np.array([fnd(i) for i in range(NP_)]); ucomp, cid = np.unique(comp, return_inverse=True); NC = len(ucomp)
log('lineas (componentes conexos):', NC)
# ---- soportes del GLB ----
d_ = open(GLB, 'rb').read(); Lj, _ = struct.unpack_from('<II', d_, 12); J = json.loads(d_[20:20 + Lj]); BIN = d_[20 + Lj + 8:]
def cuat(q):
    x, y, z, w_ = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w_), 2 * (x * z + y * w_)],
                     [2 * (x * y + z * w_), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w_)],
                     [2 * (x * z - y * w_), 2 * (y * z + x * w_), 1 - 2 * (x * x + y * y)]])
def malla_glb(nodo):
    n = J['nodes'][nodo]; p = J['meshes'][n['mesh']]['primitives'][0]
    bv = J['bufferViews'][p['extensions']['KHR_draco_mesh_compression']['bufferView']]; o = bv.get('byteOffset', 0)
    dm = DracoPy.decode(BIN[o:o + bv['byteLength']]); pts = np.array(dm.points, dtype=np.float64).reshape(-1, 3)
    fc = np.array(dm.faces).reshape(-1, 3)
    R = cuat(n.get('rotation', [0, 0, 0, 1])) @ np.diag(n.get('scale', [1, 1, 1])); t = np.array(n.get('translation', [0, 0, 0]))
    th = pts @ R.T + t; bl = np.stack([th[:, 0], -th[:, 2], th[:, 1]], 1)   # Three -> Blender
    return bl, fc
CAT = {}
for i_, n in enumerate(J['nodes']):
    nm = n.get('name', '')
    if nm.startswith('V4_Structural_FFFF00'): CAT.setdefault('barandas', []).append(i_)
    elif nm.startswith('V4_Structural_00FF00'): CAT.setdefault('rejillas_pisos', []).append(i_)
    elif nm.startswith('V4_Structural_'): CAT.setdefault('estructura', []).append(i_)
    elif nm.startswith('V4_Mechanical_'): CAT.setdefault('mecanico', []).append(i_)
    elif nm == 'UNION_MAT_C6B88D': CAT.setdefault('terreno', []).append(i_)
log('categorias GLB:', {k: len(v) for k, v in CAT.items()})
# comprobacion de marco: tuberias del GLB (BFBFBF) vs. muestras del FBX
nb = [i_ for i_, n in enumerate(J['nodes']) if n.get('name') == 'UNION_MAT_BFBFBF'][0]
pb, _ = malla_glb(nb); ch = pb[::max(1, len(pb) // 20000)]; dd, _ = cKDTree(S).query(ch)
log('MARCO GLB vs FBX (tuberias BFBFBF): distancia mediana %.3f m, p90 %.3f m (esperado: pocos cm)' % (np.median(dd), np.percentile(dd, 90)))
cont = {}
def marca(nombre, tree=None, interp=None):
    if tree is not None:
        dd, _ = tree.query(S, distance_upper_bound=TOL, workers=-1); ok = np.isfinite(dd)
    else:
        h = interp(S[:, 0], S[:, 1]); ok = np.isfinite(h) & (S[:, 2] <= h + TOL) & (S[:, 2] >= h - 3.0)
    cont[nombre] = np.bincount(cid[SP[ok]], minlength=NC)
    log('contacto', nombre, ': piezas-muestra tocando', int(ok.sum()), '| lineas con contacto', int((cont[nombre] > 0).sum()))
for cat, nodos in CAT.items():
    if cat == 'terreno':
        bl, _ = malla_glb(nodos[0]); marca(cat, interp=LinearNDInterpolator(bl[:, :2], bl[:, 2])); continue
    P_ = []
    for nd in nodos:
        bl, fc = malla_glb(nd); P_.append(bl); P_.append(bl[fc].mean(1))
    P_ = np.vstack(P_); log(cat, 'puntos de soporte:', len(P_)); marca(cat, tree=cKDTree(P_)); del P_
if sup_fbx: marca('miembros_piping', tree=cKDTree(np.vstack(sup_fbx)))
sop = np.zeros(NC, bool)
for k, v in cont.items():
    if k != 'barandas': sop |= v > 0
# ---- resultado ----
npz = np.bincount(cid, minlength=NC); lg = np.bincount(cid, weights=np.array(piezas), minlength=NC)
mn = np.full((NC, 3), 1e9); mx = np.full((NC, 3), -1e9)
np.minimum.at(mn, cid[SP], S); np.maximum.at(mx, cid[SP], S)
sin = np.where(~sop)[0]
log(f'LINEAS: {NC} | con soporte: {int(sop.sum())} | SIN SOPORTE (candidatas): {len(sin)}')
log('candidatas por n.o de piezas: 1:', int((npz[sin] == 1).sum()), '| 2-5:', int(((npz[sin] >= 2) & (npz[sin] <= 5)).sum()), '| 6-20:', int(((npz[sin] >= 6) & (npz[sin] <= 20)).sum()), '| >20:', int((npz[sin] > 20).sum()))
sal = []
for c in sin[np.argsort(-lg[sin])]:
    sal.append({'id': int(c), 'piezas': int(npz[c]), 'largo_m': round(float(lg[c]), 2), 'min': mn[c].round(2).tolist(), 'max': mx[c].round(2).tolist(),
                'toca_barandas': int(cont.get('barandas', np.zeros(NC))[c]), 'mids': [int(mids[i]) for i in np.where(cid == c)[0]]})
json.dump({'tol': TOL, 'lineas': NC, 'con_soporte': int(sop.sum()), 'candidatas': sal}, open(salida, 'w'))
for s_ in sal[:25]: log('  cand', s_['id'], 'piezas', s_['piezas'], 'largo', s_['largo_m'], 'm  bbox', s_['min'], s_['max'], 'baranda' if s_['toca_barandas'] else '')
log('listo ->', salida)
