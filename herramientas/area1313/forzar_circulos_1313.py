# Fuerza el ocultamiento de TODO lo que Eduardo encerro en circulos (cuadro t = 90 s), con la camara real del visor.
# Pieza forzada = pieza de Capas (piping/electrico/control) cuya caja proyectada cae >= 75 % dentro de una elipse y que no
# esta pegada a estructura/equipos (d > 0,3 m). Uso: py -I forzar_circulos_1313.py <sueltos.json> <cam.json> <elipses.json> <salida.json>
import sys, json, numpy as np
R = json.load(open(sys.argv[1], encoding='utf-8')); cam = json.load(open(sys.argv[2])); E = json.load(open(sys.argv[3]))
M = lambda e: np.array(e).reshape(4, 4).T
PVR = M(cam['P']) @ M(cam['V']) @ M(cam['R']); W, H = cam['W'], cam['H']
def pantalla(P):
    h = np.c_[P, np.ones(len(P))] @ PVR.T; ok = h[:, 3] > 0; s = h[:, :3] / h[:, 3:4]
    return np.c_[(s[:, 0] + 1) / 2 * W, (1 - s[:, 1]) / 2 * H], ok
# z-buffer de estructura/equipos (mallas V4_* del GLB, muestreadas cada ~0,3 m) para descartar piezas tapadas por edificios
import struct, DracoPy
g = open(sys.argv[5], 'rb').read(); jl = struct.unpack_from('<I', g, 12)[0]; J = json.loads(g[20:20 + jl]); BIN = g[20 + jl + 8:]; rng = np.random.default_rng(0)
CEL = 4; ZB = np.full((H // CEL + 1, W // CEL + 1), np.inf)
for m in J['meshes']:
    if not m.get('name', '').startswith('V4_') or 'C6B88D' in m['name'].upper(): continue
    for pr in m['primitives']:
        bv = J['bufferViews'][pr['extensions']['KHR_draco_mesh_compression']['bufferView']]; o = bv.get('byteOffset', 0)
        dm = DracoPy.decode(BIN[o:o + bv['byteLength']]); v = np.asarray(dm.points, float).reshape(-1, 3); f = np.asarray(dm.faces).reshape(-1, 3)
        a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]; ar = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
        k = np.minimum(np.ceil(ar / 0.09).astype(int), 3000); rep = np.repeat(np.arange(len(f)), k); u, w = rng.random(len(rep)), rng.random(len(rep))
        sw = u + w > 1; u[sw], w[sw] = 1 - u[sw], 1 - w[sw]; P = a[rep] + (b[rep] - a[rep]) * u[:, None] + (c[rep] - a[rep]) * w[:, None]
        h = np.c_[P, np.ones(len(P))] @ (M(cam['V']) @ M(cam['R'])).T; z = -h[:, 2]; s, ok = pantalla(P)
        ok &= (s[:, 0] >= 0) & (s[:, 0] < W) & (s[:, 1] >= 0) & (s[:, 1] < H) & (z > 0)
        np.minimum.at(ZB, ((s[ok, 1] // CEL).astype(int), (s[ok, 0] // CEL).astype(int)), z[ok])
def visible(P, s):
    z = -(np.c_[P, np.ones(len(P))] @ (M(cam['V']) @ M(cam['R'])).T)[:, 2]; i = np.clip((s[:, 1] // CEL).astype(int), 0, ZB.shape[0] - 1); j = np.clip((s[:, 0] // CEL).astype(int), 0, ZB.shape[1] - 1)
    return (z <= ZB[i, j] + 0.5).mean()
DMIN = float(sys.argv[6]) if len(sys.argv) > 6 else 0.3
fz = {}
for k, p in enumerate(R['piezas']):
    if p['d'] <= DMIN: continue
    b = np.array(p['caja']); C = np.array([[b[i], b[j], b[l]] for i in (0, 3) for j in (1, 4) for l in (2, 5)] + [(b[:3] + b[3:]) / 2])
    s, ok = pantalla(C)
    if not ok.all(): continue
    for e in E:
        den = ((s[:, 0] - e['cx']) / e['rx']) ** 2 + ((s[:, 1] - e['cy']) / e['ry']) ** 2
        if den[-1] <= 1 and np.linalg.norm(b[3:] - b[:3]) <= 10 and visible(C, s) >= 0.5: # centro de la caja dentro de la elipse; las esquinas de cajas de tubos curvos caen fuera
             fz[k] = e['id']; break
import collections
print('forzadas por elipse:', dict(collections.Counter(fz.values())), 'total', len(fz))
json.dump({'indices': sorted(fz)}, open(sys.argv[4], 'w'))
