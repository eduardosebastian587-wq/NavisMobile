# Detecta elementos "sueltos" (piping, escalerillas, conduit, instrumentos) del FBX de Capas: piezas a mas de D m de toda
# estructura/equipo (mallas V4_* del GLB del visor, sin terreno) y agrupadas por contacto (cajas a < 5 cm) en conjuntos flotantes.
# Solo lectura. Uso: py -I detectar_sueltos_1313.py "<Capas area 1313.fbx>" <salida.json> --glb <visor.glb> [--cruce cruce.json]
import sys, os
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'analizar_huecos_tuberia_1313.py'), encoding='utf-8').read()
exec(_src.split('# ---- analisis de huecos')[0])
from scipy.spatial import cKDTree
import DracoPy
ORI = np.array([184800.0, 4448600.0, 2250.0]); rng = np.random.default_rng(0)
# ---------- 1) puntos de superficie de estructura/equipos (GLB, marco local glTF) ----------
g = open(opt('--glb', ''), 'rb').read(); jl = struct.unpack_from('<I', g, 12)[0]; J = json.loads(g[20:20 + jl]); BIN = g[20 + jl + 8:]
def acc(i):
    A = J['accessors'][i]; bv = J['bufferViews'][A['bufferView']]; n = {'SCALAR': 1, 'VEC3': 3}[A['type']]
    dt = {5126: '<f4', 5125: '<u4', 5123: '<u2', 5121: 'u1'}[A['componentType']]; o = bv.get('byteOffset', 0) + A.get('byteOffset', 0)
    st = bv.get('byteStride', 0); it = np.dtype(dt).itemsize
    if st and st != n * it: return np.lib.stride_tricks.as_strided(np.frombuffer(BIN, dt, offset=o), (A['count'], n), (st, it)).copy()
    return np.frombuffer(BIN, dt, count=A['count'] * n, offset=o).reshape(-1, n)
def nmat(nd):
    if 'matrix' in nd: return np.array(nd['matrix']).reshape(4, 4).T
    m = np.eye(4); x, y, zq, w = nd.get('rotation', [0, 0, 0, 1])
    R = np.array([[1-2*(y*y+zq*zq), 2*(x*y-zq*w), 2*(x*zq+y*w)], [2*(x*y+zq*w), 1-2*(x*x+zq*zq), 2*(y*zq-x*w)], [2*(x*zq-y*w), 2*(y*zq+x*w), 1-2*(x*x+y*y)]])
    m[:3, :3] = R * np.array(nd.get('scale', [1, 1, 1])); m[:3, 3] = nd.get('translation', [0, 0, 0]); return m
pts = []; usados = collections.Counter()
def recorrer(ni, P):
    nd = J['nodes'][ni]; Mw = P @ nmat(nd)
    if 'mesh' in nd:
        nm = J['meshes'][nd['mesh']].get('name') or nd.get('name', '')
        if nm.startswith('V4_') and 'C6B88D' not in nm.upper():
            for pr in J['meshes'][nd['mesh']]['primitives']:
                bv = J['bufferViews'][pr['extensions']['KHR_draco_mesh_compression']['bufferView']]; o = bv.get('byteOffset', 0)
                dm = DracoPy.decode(BIN[o:o + bv['byteLength']]); v = np.asarray(dm.points, np.float64).reshape(-1, 3); f = np.asarray(dm.faces).reshape(-1, 3)
                v = v @ Mw[:3, :3].T + Mw[:3, 3]
                a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]; ar = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
                k = np.minimum(np.ceil(ar / 0.09).astype(int), 3000); rep = np.repeat(np.arange(len(f)), k)
                u, w2 = rng.random(len(rep)), rng.random(len(rep)); s = u + w2 > 1; u[s], w2[s] = 1 - u[s], 1 - w2[s]
                pts.append(a[rep] + (b[rep] - a[rep]) * u[:, None] + (c[rep] - a[rep]) * w2[:, None]); pts.append(v)
                usados[nm.split('#')[0]] += len(rep)
    for c2 in nd.get('children', []): recorrer(c2, Mw)
for r in J['scenes'][J.get('scene', 0)]['nodes']: recorrer(r, np.eye(4))
P = np.concatenate(pts); arbol = cKDTree(P); log('estructura: puntos', len(P), dict(usados.most_common(12)))
# ---------- 2) piezas objetivo del FBX de Capas: distancia minima a estructura ----------
def cadena(mid):
    out = []
    while mid in modelos: out.append(modelos[mid]['n']); mid = padre.get(mid)
    return out[::-1]
DISC = ('Piping', 'Electrical', 'Control Systems')
pz = []
for mid, gid in geo_de.items():
    cad = cadena(mid)
    if len(cad) < 7 or cad[5] not in DISC: continue
    v = arr(geoms[gid]).reshape(-1, 3)
    if len(v) < 3: continue
    d = modelos[mid]; G = M(d['GT'], d['GR'], d['GS']); W4 = mundo(mid) @ G
    w = (v @ W4[:3, :3].T + W4[:3, 3]) * (unit / 100.0) - ORI
    q = np.c_[40 - w[:, 0], w[:, 2], -(30 - w[:, 1])]
    if len(q) > 400: q = q[rng.choice(len(q), 400, replace=False)]
    c = q.mean(0); _, _, vt = np.linalg.svd(q - c, full_matrices=False); t = (q - c) @ vt[0]; L = float(t.max() - t.min())
    s = q
    if L > 0.6: s = np.r_[q, c + np.outer(np.arange(t.min(), t.max(), 0.4), vt[0])]
    dist = float(arbol.query(s, k=1, distance_upper_bound=50)[0].min())
    pz.append({'mid': int(mid), 'cad': cad[5:-1] if cad[-1] == 'Geometry' else cad[5:], 'caja': np.r_[q.min(0), q.max(0)], 'L': L, 'd': min(dist, 50.0)})
log('piezas objetivo', len(pz))
# ---------- 3) conjuntos flotantes por umbral D (contacto entre cajas < 5 cm) ----------
CJ = np.array([p['caja'] for p in pz]); dd = np.array([p['d'] for p in pz])
def conjuntos(D, tol=0.05):
    idx = np.nonzero(dd > D)[0]; pa = {i: i for i in idx}
    def raiz(i):
        while pa[i] != i: pa[i] = pa[pa[i]]; i = pa[i]
        return i
    lo, hi = CJ[idx, :3] - tol, CJ[idx, 3:] + tol
    for k, i in enumerate(idx):
        m = np.all((lo[k + 1:] <= hi[k]) & (hi[k + 1:] >= lo[k]), axis=1)
        for j in idx[k + 1:][m]: pa[raiz(j)] = raiz(i)
    G = collections.defaultdict(list)
    for i in idx: G[raiz(i)].append(int(i))
    out = []
    for mi in G.values():
        b = np.r_[CJ[mi, :3].min(0), CJ[mi, 3:].max(0)]
        out.append({'m': mi, 'ext': float(np.linalg.norm(b[3:] - b[:3])), 'caja': b.round(2).tolist()})
    return out
# piezas encerradas por Eduardo (cruce del picado), sin terreno/plataformas
enc = {}
if opt('--cruce', ''):
    inv = np.load(opt('--inv', '_trabajo/insp/piezas_1313.npz'))['ids']; cr = json.load(open(opt('--cruce', ''), encoding='utf-8'))
    pos = {p['mid']: k for k, p in enumerate(pz)}
    for e, L2 in cr.items():
        enc[e] = [pos[int(inv[x['i']])] for x in L2 if int(inv[x['i']]) in pos]
res = {'piezas': [{'mid': p['mid'], 'cad': p['cad'], 'd': round(p['d'], 2), 'L': round(p['L'], 2), 'caja': p['caja'].round(2).tolist()} for p in pz], 'enc': enc, 'D': {}}
for D in (0.5, 1.0, 1.5, 2.0):
    cs = conjuntos(D); de = {i: c['ext'] for c in cs for i in c['m']}
    rec = {e: f"{sum(1 for i in L2 if i in de)}/{len(L2)} (ext min {min([de[i] for i in L2 if i in de] or [0]):.1f})" for e, L2 in enc.items()}
    for X in (0, 2, 4):
        sel = [c for c in cs if c['ext'] >= X]
        log(f'D={D} ext>={X} m: conjuntos {len(sel)}, piezas {sum(len(c["m"]) for c in sel)}')
    log(f'  D={D} encerradas marcadas: {rec}')
    res['D'][str(D)] = cs
json.dump(res, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False); log('guardado', sys.argv[2])
