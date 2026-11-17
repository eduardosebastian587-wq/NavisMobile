# Campo de distancias (celdas de 0,75 m, ejes Blender) del Área 1313 para planificar/verificar el recorrido de cámara.
#   Ocupado = geometría de area1313_web.glb (Draco) + VOLUMEN BARRIDO por las piezas animadas durante todo el ciclo
#   (equipos animados del v4.1 evaluados cada 0,25 s con las pistas de «ciclo-completo») + todo lo que queda bajo el terreno.
# Salida: <dist.npy> (float16, m) y <dist>.json (origen, celda, dims).
# Uso: py campo_distancias_1313.py <area1313_web.glb> <area1313_web_equipos.json> <animaciones.json> <dist.npy>
# Requiere numpy, scipy, DracoPy.
import sys, json, struct, time, math, numpy as np, DracoPy
from scipy import ndimage
glb, r_eq, r_an, salida = sys.argv[1:5]
t0 = time.time(); CEL = 0.75
log = lambda *a: print(f'[campo {time.time()-t0:5.0f} s]', *a, flush=True)
b = open(glb, 'rb').read(); L = struct.unpack('<I', b[12:16])[0]; J = json.loads(b[20:20 + L]); bin0 = 20 + L + 8; BV = J['bufferViews']
def qrot(q, v):
    x, y, z, w = q; u = np.array([x, y, z]); return v + 2 * np.cross(u, np.cross(u, v) + w * v)
mallas = []                                   # (vertices Blender, triángulos, material)
for nd in J['nodes']:
    if 'mesh' not in nd: continue
    for pr in J['meshes'][nd['mesh']]['primitives']:
        bv = BV[pr['extensions']['KHR_draco_mesh_compression']['bufferView']]
        o = bin0 + bv.get('byteOffset', 0); m = DracoPy.decode(b[o:o + bv['byteLength']])
        v = np.asarray(m.points, np.float64); t = np.asarray(m.faces, np.int64).reshape(-1, 3)
        v = v * np.array(nd.get('scale', [1, 1, 1])); v = qrot(nd.get('rotation', [0, 0, 0, 1]), v) + np.array(nd.get('translation', [0, 0, 0]))
        mallas.append((np.stack([v[:, 0], -v[:, 2], v[:, 1]], 1), t, J['materials'][pr['material']]['name']))
# ---- piezas animadas: vértices en coordenadas v4 y su movimiento
EQ = json.load(open(r_eq, encoding='utf-8')); eqb = open(r_eq[:-5] + '.bin', 'rb').read()
AN = json.load(open(r_an, encoding='utf-8')); CICLO = next(a for a in AN['animaciones'] if a['id'] == 'ciclo-completo')
TX, TY, TZ = EQ['TX'], EQ['TY'], EQ['TZ']
P = {p['id']: p for p in EQ['partes']}
for p in EQ['partes']:
    p['piv'] = np.array(p.get('pivote') or (P[p['padre']].get('pivote') if p.get('padre') else None) or [0, 0, 0], float)
    tri = [np.frombuffer(eqb, np.float32, s['vert'] * 3, s['pos']).reshape(-1, 3, 3).astype(np.float64) for s in p['mallas']]
    pts = []
    for T3 in tri:                            # muestreo del interior de cada triángulo cada ≤ 0,375 m (sin huecos en vigas largas)
        p0, p1, p2 = T3[:, 0], T3[:, 1], T3[:, 2]
        lado = np.maximum(np.maximum(np.linalg.norm(p1 - p0, axis=1), np.linalg.norm(p2 - p1, axis=1)), np.linalg.norm(p0 - p2, axis=1))
        nivel = np.clip(np.ceil(lado / (CEL * 0.5)).astype(int), 1, 512); pts.append(T3.reshape(-1, 3))
        for k in np.unique(nivel[nivel > 1]):
            sel = np.nonzero(nivel == k)[0]; ii, jj = np.meshgrid(np.arange(k + 1), np.arange(k + 1), indexing='ij'); mm = (ii + jj) <= k
            u = (ii[mm] / k)[None, :, None]; w = (jj[mm] / k)[None, :, None]
            pts.append((p0[sel][:, None] * (1 - u - w) + p1[sel][:, None] * u + p2[sel][:, None] * w).reshape(-1, 3))
    p['v'] = np.unique(np.round(np.concatenate(pts) / 0.3).astype(np.int32), axis=0) * 0.3 if pts else np.zeros((0, 3))
pistas = {}
for k in CICLO['pistas']:
    if k['objetivo'] == 'camara': continue
    pistas.setdefault(k['objetivo'], {})[k['propiedad']] = (k['claves'], k.get('interpolacion') or 'suave')
def ev(ks, modo, t):
    if t <= ks[0][0]: return np.array(ks[0][1], float)
    if t >= ks[-1][0]: return np.array(ks[-1][1], float)
    i = max(j for j in range(len(ks) - 1) if ks[j][0] <= t); (t0_, a), (t1_, c) = ks[i], ks[i + 1]
    u = (t - t0_) / (t1_ - t0_) if t1_ > t0_ else 1.0
    if modo == 'suave': u = u * u * (3 - 2 * u)
    elif modo == 'escalon': u = 0.0
    return np.array(a, float) + (np.array(c, float) - np.array(a, float)) * u
def rot(e):
    x, y, z = [math.radians(a) for a in e]
    Rx = np.array([[1, 0, 0], [0, math.cos(x), -math.sin(x)], [0, math.sin(x), math.cos(x)]])
    Ry = np.array([[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]])
    Rz = np.array([[math.cos(z), -math.sin(z), 0], [math.sin(z), math.cos(z), 0], [0, 0, 1]])
    return Rx @ Ry @ Rz                       # Euler 'XYZ' de Three.js
def mundo(pid, t, cache):                     # matriz 4x4 del nodo de la parte (coordenadas v4)
    if pid in cache: return cache[pid]
    p = P[pid]; pa = p.get('padre'); off = P[pa]['piv'] if pa else np.zeros(3)
    M = np.eye(4); M[:3, 3] = p['piv'] - off
    pk = pistas.get(pid, {})
    if 'posicion' in pk and not p.get('estirable'): M[:3, 3] += ev(*pk['posicion'], t)
    if 'rotacion' in pk: M[:3, :3] = rot(ev(*pk['rotacion'], t))
    M = (mundo(pa, t, cache) if pa else np.eye(4)) @ M
    cache[pid] = M; return M
def piezas_en(t):
    cache = {}; out = []
    for p in EQ['partes']:
        if not len(p['v']): continue
        v = p['v'].astype(np.float64)
        if p.get('estirable'):                # gancho + cable: deformación vertical (rígido < y1, anclado > y2)
            e = p['estirable']; dy = ev(*pistas[p['id']]['posicion'], t)[1] if 'posicion' in pistas.get(p['id'], {}) else 0.0
            y = v[:, 1]; w = np.where(y <= e['y1'], 1.0, np.where(y >= e['y2'], 0.0, (e['y2'] - y) / max(1e-6, e['y2'] - e['y1'])))
            v = v.copy(); v[:, 1] += dy * w
            pa = p.get('padre'); M = mundo(pa, t, cache) if pa else np.eye(4); off = P[pa]['piv'] if pa else np.zeros(3)
            w4 = (v - off) @ M[:3, :3].T + M[:3, 3]
        else:
            M = mundo(p['id'], t, cache); w4 = (v - p['piv']) @ M[:3, :3].T + M[:3, 3]
        out.append(np.stack([TX - w4[:, 0], w4[:, 2] + TY, w4[:, 1] + TZ], 1))
    return np.concatenate(out)
# ---- rejilla
todo = np.concatenate([m[0] for m in mallas])
lo = np.floor(todo.min(0) - 25); hi = np.ceil(todo.max(0) + 25); hi[2] = todo[:, 2].max() + 60
dims = np.ceil((hi - lo) / CEL).astype(int) + 1
occ = np.zeros(dims, bool)
def marcar(Pt):
    c = np.floor((Pt - lo) / CEL).astype(np.int32); ok = np.all((c >= 0) & (c < dims), 1); c = c[ok]; occ[c[:, 0], c[:, 1], c[:, 2]] = True
def marcar_tri(v, t):
    marcar(v)
    p0, p1, p2 = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    lado = np.maximum(np.maximum(np.linalg.norm(p1 - p0, axis=1), np.linalg.norm(p2 - p1, axis=1)), np.linalg.norm(p0 - p2, axis=1))
    nivel = np.clip(np.ceil(lado / (CEL * 0.5)).astype(int), 1, 512)
    for k in np.unique(nivel[nivel > 1]):
        sel = np.nonzero(nivel == k)[0]; ii, jj = np.meshgrid(np.arange(k + 1), np.arange(k + 1), indexing='ij'); mm = (ii + jj) <= k
        u = (ii[mm] / k)[None, :, None]; w = (jj[mm] / k)[None, :, None]; paso = max(1, 2_000_000 // u.shape[1])
        for s in range(0, sel.size, paso):
            ss = sel[s:s + paso]; marcar((p0[ss][:, None] * (1 - u - w) + p1[ss][:, None] * u + p2[ss][:, None] * w).reshape(-1, 3))
ntri = 0
for v, t, nombre in mallas: marcar_tri(v, t); ntri += len(t)
log(f'rejilla {dims.tolist()} desde {lo.tolist()}; {ntri:,} tri del modelo marcados')
# bajo el terreno: en cada columna, todo lo que está por debajo de la superficie más alta del terreno es «macizo»
terr = np.zeros(dims, bool)
for v, t, nombre in mallas:
    if nombre.startswith('MAT_C6B88D'):
        occ_b = occ; occ = terr; marcar_tri(v, t); occ = occ_b
alto = np.where(terr.any(2), dims[2] - 1 - np.argmax(terr[:, :, ::-1], axis=2), -1)
kz = np.arange(dims[2])[None, None, :]
occ |= kz <= alto[:, :, None]
zmin_t = min(v[:, 2].min() for v, t, n in mallas if n.startswith('MAT_C6B88D'))
occ[:, :, :int((zmin_t - lo[2]) / CEL) + 1] = True        # fuera de la huella del terreno: suelo al nivel más bajo del terreno
del terr
# volumen barrido por las piezas animadas (ciclo de CICLO['duracion'] s, cada 0,25 s)
nb = 0
for tt in np.arange(0, CICLO['duracion'] + 1e-6, 0.25):
    pts = piezas_en(tt); marcar(pts); nb += 1
log(f'volumen barrido: {nb} instantes; {sum(len(p["v"]) for p in EQ["partes"]):,} vértices por instante')
d = ndimage.distance_transform_edt(~occ, sampling=CEL); del occ
np.save(salida, d.astype(np.float16))
json.dump({'origen': lo.tolist(), 'celda_m': CEL, 'dims': dims.tolist(), 'ejes': 'blender (x, y, z) = three (x, -z, y)',
           'suelo_min_terreno_z': float(zmin_t), 'nota': 'incluye volumen barrido de las piezas animadas (ciclo-completo)'},
          open(salida[:-4] + '.json', 'w'), indent=1)
log(f'listo; distancia máx {float(d.max()):.1f} m')
