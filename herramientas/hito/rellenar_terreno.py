# Rellena los huecos del terreno (taludes triangulados en "pajarita", triangulos faltantes) con triangulos nuevos hechos
# con los MISMOS vertices del terreno: Delaunay en planta de sus vertices; se conservan los triangulos candidatos que
#   (1) no existen ya, (2) no solapan la malla existente (centroide y puntos interiores sin cobertura),
#   (3) tienen aristas cortas (<= LMAX m) y desnivel moderado, y (4) no tienen un lado largo "de vacio" (borde del terreno).
# Salida: JSON con posiciones (ejes Three, Y arriba) y normales (hacia arriba) del relleno.
import sys, json, numpy as np, time
sys.path.insert(0, '/home/claude/scripts')
from glb_util import cargar
from scipy.spatial import Delaunay, cKDTree
LMAX = float(sys.argv[1]) if len(sys.argv) > 1 else 14.0      # arista máxima de un triángulo «normal» (m)
LMAX_FINO = float(sys.argv[3]) if len(sys.argv) > 3 else 45.0 # arista máxima de un triángulo delgado (hueco entre triángulos largos)
AMAX_FINO = float(sys.argv[4]) if len(sys.argv) > 4 else 30.0 # área máxima (m2, en planta) de un triángulo delgado
salida = sys.argv[2] if len(sys.argv) > 2 else '/home/claude/datos/hito_terreno_relleno.json'
t0 = time.time(); J, M = cargar(); m = [x for x in M if 'C6B88D' in x['nombre']][0]; v, t = m['v'], m['t']
key = np.round(v / 0.01).astype(np.int64); _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True); inv = inv.ravel()
V = v[first]; T = inv[t]                                         # vertices unicos y triangulos reindexados
print('vertices unicos', len(V), 'triangulos', len(T))
# cobertura existente: rasterizacion a 0,25 m del plano
G = 0.25; lo = V[:, :2].min(0) - 1; n = np.ceil((V[:, :2].max(0) + 1 - lo) / G).astype(int)
cov = np.zeros(n, bool)
for tri in T:
    p = V[tri][:, :2]; mn = np.maximum(np.floor((p.min(0) - lo) / G).astype(int), 0); mx = np.minimum(np.ceil((p.max(0) - lo) / G).astype(int), n - 1)
    if (mx - mn + 1).prod() > 6_000_000: continue
    xs, ys = np.meshgrid(np.arange(mn[0], mx[0] + 1), np.arange(mn[1], mx[1] + 1), indexing='ij'); P = lo + np.stack([xs.ravel() + .5, ys.ravel() + .5], 1) * G
    a, b, c = p; d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(d) < 1e-12: continue
    l1 = ((b[1] - c[1]) * (P[:, 0] - c[0]) + (c[0] - b[0]) * (P[:, 1] - c[1])) / d; l2 = ((c[1] - a[1]) * (P[:, 0] - c[0]) + (a[0] - c[0]) * (P[:, 1] - c[1])) / d
    ins = (l1 >= 0) & (l2 >= 0) & (1 - l1 - l2 >= 0); cov[xs.ravel()[ins], ys.ravel()[ins]] = True
print(f'cobertura {time.time()-t0:.0f} s: {100*cov.mean():.1f}%')
# región «interior»: cierre morfológico de la cobertura (huecos más angostos que 2·RCIERRE m); los vacíos reales (plataformas) y el
# contorno exterior quedan fuera, así el relleno solo toca huecos rodeados de terreno
from scipy import ndimage
RC = float(sys.argv[5]) if len(sys.argv) > 5 else 4.0
rp = int(round(RC / G)); pad = rp + 3
cp = np.pad(cov, pad); dil = ndimage.distance_transform_edt(~cp) <= rp; cerr = ndimage.distance_transform_edt(dil) > rp
interior = cerr[pad:-pad, pad:-pad]
print(f'región interior (cierre {RC} m): {interior.sum()*G*G:.0f} m2 ({time.time()-t0:.0f} s)')
import shapely
from shapely.geometry import Polygon
from shapely.strtree import STRtree
polis = [Polygon(V[tri][:, :2]) for tri in T]
arbol = STRtree(polis)
def solape(p):                                                    # fracción del área del candidato ya cubierta por triángulos existentes
    pc = Polygon(p)
    if pc.area <= 0: return 1.0
    idx = arbol.query(pc)
    if len(idx) == 0: return 0.0
    cub = shapely.union_all([polis[i] for i in idx if polis[i].is_valid]); return pc.intersection(cub).area / pc.area
existentes = {tuple(sorted(x)) for x in T.tolist()}
D = Delaunay(V[:, :2]); S = D.simplices
nuevos = []
def cubierto(p):                                                  # fraccion de puntos interiores del triangulo ya cubiertos
    a, b, c = p; u = np.array([[1/3, 1/3], [.6, .2], [.2, .6], [.15, .15], [.7, .15], [.15, .7], [.45, .45], [.25, .5], [.5, .25]])
    pts = a[None] * (1 - u.sum(1))[:, None] + b[None] * u[:, :1] + c[None] * u[:, 1:]
    ij = np.floor((pts - lo) / G).astype(int); ok = (ij >= 0).all(1) & (ij < n).all(1)
    return cov[ij[ok, 0], ij[ok, 1]].mean() if ok.any() else 1.0
def en_interior(p):
    a, b, c = p; u = np.array([[1/3, 1/3], [.6, .2], [.2, .6], [.15, .15], [.7, .15], [.15, .7], [.45, .45], [.25, .5], [.5, .25]])
    pts = a[None] * (1 - u.sum(1))[:, None] + b[None] * u[:, :1] + c[None] * u[:, 1:]
    ij = np.floor((pts - lo) / G).astype(int); ok = (ij >= 0).all(1) & (ij < n).all(1)
    return interior[ij[ok, 0], ij[ok, 1]].mean() if ok.any() else 0.0
for s in S:
    if tuple(sorted(s)) in existentes: continue
    P3 = V[s]; e = [np.linalg.norm(P3[i] - P3[j]) for i, j in ((0, 1), (1, 2), (2, 0))]
    if max(e) > LMAX_FINO: continue
    u_, w_ = P3[1, :2] - P3[0, :2], P3[2, :2] - P3[0, :2]; area2 = abs(u_[0] * w_[1] - u_[1] * w_[0])
    if area2 < 1e-4: continue
    if max(e) > LMAX and area2 / 2 > AMAX_FINO: continue          # largo y ancho: sería relleno de un vacío real (plataformas), no un hueco
    if solape(P3[:, :2]) > 0.10: continue
    if en_interior(P3[:, :2]) < 0.8: continue
    nuevos.append(s)
nuevos = np.array(nuevos); print('candidatos nuevos', len(nuevos), f'{time.time()-t0:.0f} s')
np.save('/tmp/relleno_idx.npy', nuevos); np.save('/tmp/relleno_V.npy', V)
Pn = V[nuevos]                                                    # (k,3,3) Blender
# orientar hacia arriba (normal z > 0) y calcular normales
nrm = np.cross(Pn[:, 1] - Pn[:, 0], Pn[:, 2] - Pn[:, 0]); flip = nrm[:, 2] < 0; Pn[flip] = Pn[flip][:, [0, 2, 1]]; nrm[flip] *= -1
nl = np.linalg.norm(nrm, axis=1, keepdims=True); nrm = nrm / np.maximum(nl, 1e-12)
toThree = lambda a: np.stack([a[..., 0], a[..., 2], -a[..., 1]], -1)
json.dump({'tri': int(len(Pn)), 'pos': np.round(toThree(Pn), 3).reshape(-1).tolist(), 'nrm': np.round(toThree(np.repeat(nrm[:, None], 3, 1)), 3).reshape(-1).tolist()}, open(salida, 'w'))
print('guardado', salida, len(Pn), 'triangulos')
