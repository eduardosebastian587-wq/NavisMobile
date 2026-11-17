# Selecciona, SIN rayos, las caras de las mallas UNION_MAT_* (piping/electrico de Capas) cuyo pixel cae en una elipse, es candidato
# (oscuro/saturado) y esta en primer plano segun un z-buffer de centros de cara (todo menos terreno). Salida: semillas en marco Blender (x,-z,y).
# Uso: py -I seleccionar_pantalla_1313.py <visor.glb> <jobs.json> <prefijo_vista> <salida_semillas.json> [--base semillas_previas.json] [--max 400]
#   jobs.json = [{"t": 90, "elipses": [{"id":.., "cx":.., "cy":.., "rx":.., "ry":..}]}, ...]; usa <prefijo>_<t>_cam.json y _cand.npy de volcar_camara_1313.py
import sys, json, struct, time, collections
import numpy as np, DracoPy
a = sys.argv[1:]; glb, fj, pref, sal = a[:4]; opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
MAXS = int(opt('--max', 400)); t0 = time.time(); log = lambda *x: print(f'[{time.time()-t0:6.1f} s]', *x, flush=True)
g = open(glb, 'rb').read(); jl = struct.unpack_from('<I', g, 12)[0]; J = json.loads(g[20:20 + jl]); BIN = g[20 + jl + 8:]
def nmat(nd):
    if 'matrix' in nd: return np.array(nd['matrix']).reshape(4, 4).T
    m = np.eye(4); x, y, z, w = nd.get('rotation', [0, 0, 0, 1])
    R = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
    m[:3, :3] = R * np.array(nd.get('scale', [1, 1, 1])); m[:3, 3] = nd.get('translation', [0, 0, 0]); return m
mallas = []     # (nombre_base, matriz)
def rec(ni, P):
    nd = J['nodes'][ni]; Mw = P @ nmat(nd)
    if 'mesh' in nd: mallas.append((nd['mesh'], Mw))
    for c in nd.get('children', []): rec(c, Mw)
for r in J['scenes'][J.get('scene', 0)]['nodes']: rec(r, np.eye(4))
def centros(mi, Mw):
    out = []
    for pr in J['meshes'][mi]['primitives']:
        bv = J['bufferViews'][pr['extensions']['KHR_draco_mesh_compression']['bufferView']]; o = bv.get('byteOffset', 0)
        dm = DracoPy.decode(BIN[o:o + bv['byteLength']]); v = np.asarray(dm.points, np.float64).reshape(-1, 3); f = np.asarray(dm.faces).reshape(-1, 3)
        v = v @ Mw[:3, :3].T + Mw[:3, 3]; out.append(v[f].mean(1))
    return np.concatenate(out) if out else np.zeros((0, 3))
jobs = json.load(open(fj, encoding='utf-8')); M = lambda e: np.array(e).reshape(4, 4).T; CEL = 3
ST = []
for J_ in jobs:
    cam = json.load(open(f"{pref}_{J_['t']:g}_cam.json")); cand = np.load(f"{pref}_{J_['t']:g}_cand.npy"); W, H = cam['W'], cam['H']
    cand = np.pad(cand, ((0, max(0, H - cand.shape[0])), (0, max(0, W - cand.shape[1]))), mode='edge')[:H, :W]
    ST.append({'PVR': M(cam['P']) @ M(cam['V']) @ M(cam['R']), 'VR': M(cam['V']) @ M(cam['R']), 'cand': cand, 'W': W, 'H': H, 'E': J_['elipses'],
               'zb': np.full((H // CEL + 1, W // CEL + 1), np.inf), 'cands': []})
    yy, xx = np.mgrid[0:H, 0:W]; m = np.zeros((H, W), bool)
    for E in J_['elipses']: m |= (((xx - E['cx']) / E['rx']) ** 2 + ((yy - E['cy']) / E['ry']) ** 2 <= 1)
    ST[-1]['zona'] = m & cand; ST[-1]['zona_any'] = m
log('mallas', len(mallas), 'trabajos', len(ST))
for k, (mi, Mw) in enumerate(mallas):
    nm = (J['meshes'][mi].get('name') or '').split('#')[0]
    if nm.upper().endswith('C6B88D'): continue
    C = centros(mi, Mw)
    if not len(C): continue
    H4 = np.c_[C, np.ones(len(C))]
    for S in ST:
        h = H4 @ S['PVR'].T; z = -(H4 @ S['VR'].T)[:, 2]; ok = (h[:, 3] > 0) & (z > 0); w_ = h[:, 3]
        px = (h[:, 0] / w_ + 1) / 2 * S['W']; py = (1 - h[:, 1] / w_) / 2 * S['H']; ok &= (px >= 0) & (px < S['W'] - 1) & (py >= 0) & (py < S['H'] - 1)
        ix = np.where(ok, px, 0).astype(int); iy = np.where(ok, py, 0).astype(int); ok &= S['zona_any'][iy, ix]
        if not ok.any(): continue
        np.minimum.at(S['zb'], (iy[ok] // CEL, ix[ok] // CEL), z[ok])
        if nm.startswith('UNION_MAT_'):
            s = ok & S['zona'][iy, ix]
            if s.any(): S['cands'].append((nm, C[s], z[s], iy[s] // CEL, ix[s] // CEL))
    if k % 6 == 0: log(f'malla {k + 1}/{len(mallas)} {nm}')
sem = json.load(open(opt('--base'), encoding='utf-8')) if opt('--base') else {}
nuevas = collections.Counter(); rng = np.random.default_rng(2)
for S in ST:
    por = collections.defaultdict(list)
    for nm, C, z, cy, cx in S['cands']:
        v = z <= S['zb'][cy, cx] + 0.25
        if v.any(): por[nm].append(C[v])
    for nm, L in por.items():
        C = np.concatenate(L); nuevas[nm] += len(C)
        if len(C) > MAXS: C = C[rng.choice(len(C), MAXS, replace=False)]
        sem.setdefault(nm, []).extend([[float(c[0]), float(-c[2]), float(c[1])] for c in C])
log('caras seleccionadas por malla:', dict(nuevas))
json.dump(sem, open(sal, 'w')); log('semillas ->', sal, {k: len(v) for k, v in sem.items()})
