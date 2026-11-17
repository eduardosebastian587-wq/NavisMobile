# Recorrido de camara del Hito SIN INTERFERENCIAS (planificacion en espacio libre).
#   1) Mapa de ocupacion de la planta (sin elementos sueltos) en celdas de CEL m + suelo extenso -> campo de
#      distancias (EDT): distancia libre en metros desde cada punto al elemento mas cercano.
#   2) Puntos de paso = posiciones de la camara del video en sus 5 claves (0; 4; 6; 9,5; 12 s), llevados a la
#      celda libre mas cercana con holgura >= HOLG.
#   3) Entre puntos de paso: camino de costo minimo (Dijkstra) por celdas con holgura >= HOLG, dentro de un tubo
#      de TUBO m alrededor del recorrido del video; el costo premia seguir el recorrido original y alejarse de los
#      elementos.
#   4) Suavizado con restriccion (ningun punto baja de HOLG) y reparto en el tiempo con el mismo ritmo
#      (aceleracion/frenado) del video, estirado a DUR s. El objetivo (punto al que mira) es el del video.
#   5) Verificacion: holgura en cada cuadro y en los tramos entre cuadros (muestreo fino).
# Salidas: <salida.json> (trayectoria en ejes Three, Y arriba) y <salida>_distancias.bin (campo de distancias
#          reducido para que el visor verifique/corrija recorridos creados por el usuario).
# Uso: python optimizar_recorrido_hito.py <carpeta_geo> <hito_escena_video.json> <salida.json> [DUR=25] [HOLG=3.0]
import sys, os, json, time
import numpy as np
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

geo, ruta_esc, salida = sys.argv[1:4]
DUR = float(sys.argv[4]) if len(sys.argv) > 4 else 25.0
HOLG = float(sys.argv[5]) if len(sys.argv) > 5 else 3.0
CEL = 0.75; CP = 1.5; TUBO = 30.0; SUELO = -47.6; FPS = 30
CLAVES_S = [0.0, 4.0, 6.0, 9.5, 12.0]          # claves de camara del video (hito_p2.py)
t0 = time.time()
def log(*a): print(f'[recorrido {time.time()-t0:6.1f} s]', *a, flush=True)

R = json.load(open(ruta_esc, encoding='utf-8'))
T = np.array([r[1:7] for r in R['trayectoria_three']], np.float64)
b = lambda a: np.stack([a[:, 0], -a[:, 2], a[:, 1]], 1)               # Three -> Blender
t3 = lambda a: np.stack([a[:, 0], a[:, 2], -a[:, 1]], 1)              # Blender -> Three
cam0, obj0 = b(T[:, :3]), b(T[:, 3:6]); n0 = len(T)

# ---------- 1) ocupacion y distancias
masc = np.load(os.path.join(geo, 'sueltos_mascaras.npz'))
ind = json.load(open(os.path.join(geo, 'indice.json'), encoding='utf-8'))
gmin = np.full(3, np.inf); gmax = np.full(3, -np.inf)
for nombre in ind:
    v = np.load(os.path.join(geo, nombre + '.npz'))['v']; gmin = np.minimum(gmin, v.min(0)); gmax = np.maximum(gmax, v.max(0))
lo = np.minimum(np.minimum(cam0.min(0), obj0.min(0)), gmin) - 20; hi = np.maximum(np.maximum(cam0.max(0), obj0.max(0)), gmax) + 20
lo[2] = SUELO - 3; hi[2] = max(hi[2], cam0[:, 2].max() + 30)
dims = np.ceil((hi - lo) / CEL).astype(int) + 1
occ = np.zeros(dims, bool)
def marcar(P):
    c = np.floor((P - lo) / CEL).astype(int); ok = np.all((c >= 0) & (c < dims), 1); c = c[ok]
    occ[c[:, 0], c[:, 1], c[:, 2]] = True
for nombre in ind:
    d = np.load(os.path.join(geo, nombre + '.npz')); v = d['v'].astype(np.float64); t = d['t']
    if nombre in masc.files: t = t[~masc[nombre]]
    if not t.size: continue
    marcar(v[np.unique(t)])
    p0, p1, p2 = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    lado = np.maximum(np.maximum(np.linalg.norm(p1-p0, axis=1), np.linalg.norm(p2-p1, axis=1)), np.linalg.norm(p0-p2, axis=1))
    nivel = np.clip(np.ceil(lado / (CEL * 0.5)).astype(int), 1, 512)
    for k in np.unique(nivel[nivel > 1]):
        sel = np.nonzero(nivel == k)[0]
        ii, jj = np.meshgrid(np.arange(k+1), np.arange(k+1), indexing='ij'); m = (ii + jj) <= k
        u = (ii[m] / k)[None, :, None]; w = (jj[m] / k)[None, :, None]
        paso = max(1, 2_000_000 // u.shape[1])
        for s in range(0, sel.size, paso):
            ss = sel[s:s+paso]
            marcar((p0[ss][:, None]*(1-u-w) + p1[ss][:, None]*u + p2[ss][:, None]*w).reshape(-1, 3))
occ[:, :, :int(np.floor((SUELO - lo[2]) / CEL)) + 1] = True
dist = ndimage.distance_transform_edt(~occ, sampling=CEL).astype(np.float32); del occ
log(f'rejilla {dims.tolist()} ({CEL} m); campo de distancias listo')
def holgura(P):
    return ndimage.map_coordinates(dist, ((P - lo) / CEL).T, order=1, mode='nearest')

d_ini = holgura(cam0)
log(f'VIDEO: holgura minima {d_ini.min():.2f} m; cuadros con holgura < {HOLG} m: {(d_ini < HOLG).sum()} de {n0}')

# ---------- 2-3) planificacion en rejilla gruesa (CP m) dentro del tubo
f = int(round(CP / CEL))
nd = np.array(dist.shape) // f
dg = dist[:nd[0]*f, :nd[1]*f, :nd[2]*f].reshape(nd[0], f, nd[1], f, nd[2], f).min(axis=(1, 3, 5))   # holgura conservadora
centros = lambda idx: lo + (np.array(idx) * f + (f - 1) / 2.0) * CEL
dens = np.concatenate([cam0[:-1] + (cam0[1:] - cam0[:-1]) * s for s in np.linspace(0, 1, 8)])
arbol = cKDTree(dens)
gi = np.stack(np.meshgrid(*[np.arange(n) for n in nd], indexing='ij'), -1).reshape(-1, 3)
cc = centros(gi)
dtub, _ = arbol.query(cc, distance_upper_bound=TUBO)
libre = (dg.reshape(-1) >= HOLG) & np.isfinite(dtub)
nodos = np.flatnonzero(libre); log(f'celdas libres en el tubo: {nodos.size:,}')
idx_nodo = -np.ones(gi.shape[0], np.int64); idx_nodo[nodos] = np.arange(nodos.size)
lin = lambda g: (g[:, 0] * nd[1] + g[:, 1]) * nd[2] + g[:, 2]
filas, cols, pesos = [], [], []
dev = dtub[nodos]; hol = dg.reshape(-1)[nodos]
for dx in (-1, 0, 1):
    for dy in (-1, 0, 1):
        for dz in (-1, 0, 1):
            if (dx, dy, dz) <= (0, 0, 0): continue
            g2 = gi[nodos] + (dx, dy, dz)
            ok = np.all((g2 >= 0) & (g2 < nd), 1)
            j = idx_nodo[lin(g2[ok])]; okj = j >= 0
            a = np.flatnonzero(ok)[okj]; j = j[okj]
            L = CP * np.sqrt(dx*dx + dy*dy + dz*dz)
            # costo: largo + desvio del recorrido del video + preferencia por pasar a >= HOLG+6 m de los elementos
            c = L * (1 + 0.5 * (dev[a] + dev[j]) / 6.0 + 5.0 * np.clip((HOLG + 6 - 0.5 * (hol[a] + hol[j])) / 6, 0, 1))
            filas.append(a); cols.append(j); pesos.append(c)
G = coo_matrix((np.concatenate(pesos), (np.concatenate(filas), np.concatenate(cols))), shape=(nodos.size, nodos.size)).tocsr()
log(f'grafo: {G.nnz:,} aristas')
cl_idx = [min(int(round(s * FPS)), n0 - 1) for s in CLAVES_S]
# solo el espacio libre conectado al exterior (componente mas grande): evita "encerrar" la camara en un recinto
from scipy.sparse.csgraph import connected_components
ncc, etq = connected_components(G, directed=False)
mayor = np.bincount(etq).argmax()
log(f'regiones libres separadas: {ncc}; se usa la exterior ({(etq == mayor).sum():,} celdas)')
validos = np.flatnonzero(etq == mayor)
arbol_v = cKDTree(cc[nodos[validos]])
class _A:                                    # vecino mas cercano restringido a la region exterior
    def query(self, p): d, k = arbol_v.query(p); return d, validos[k]
arbol_n = _A()
def nodo_cercano(p):
    _, k = arbol_n.query(p); return int(k)
wps = [nodo_cercano(cam0[i]) for i in cl_idx]
camino = [wps[0]]
for a_, b_ in zip(wps[:-1], wps[1:]):
    _, pred = dijkstra(G, directed=False, indices=a_, return_predecessors=True)
    if pred[b_] < 0 and a_ != b_: raise SystemExit(f'No hay camino libre entre claves (nodos {a_}->{b_}); aumente TUBO o baje HOLG')
    tramo = [b_]
    while tramo[-1] != a_: tramo.append(pred[tramo[-1]])
    camino += tramo[::-1][1:]
Pg = cc[nodos[camino]]
log(f'camino grueso: {len(Pg)} celdas, largo {np.linalg.norm(np.diff(Pg, axis=0), axis=1).sum():.0f} m')

# ---------- 4) densificar + suavizado con restriccion (fino, CEL)
def remuestrear(P, paso):
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    q = np.linspace(0, s[-1], max(int(s[-1] / paso), 2))
    return np.stack([np.interp(q, s, P[:, k]) for k in range(3)], 1)
P = remuestrear(Pg, 0.5)
for it in range(400):
    Q = P.copy(); Q[1:-1] = 0.5 * P[1:-1] + 0.25 * (P[:-2] + P[2:])
    ok = holgura(Q) >= HOLG
    P = np.where(ok[:, None], Q, P)
P = remuestrear(P, 0.25)
s_n = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]); s_n /= s_n[-1]

# ritmo: velocidad proporcional a la holgura (lento junto a las estructuras, rapido en espacio abierto),
#        suavizada a lo largo de ~40 m, con arranque y llegada suaves; duracion total DUR s.
from scipy.ndimage import gaussian_filter1d
ds = np.linalg.norm(np.diff(P, axis=0), axis=1)
hP = holgura(P)
w = gaussian_filter1d(np.clip(hP, HOLG, 25.0) ** 0.6, sigma=40.0 / 0.25, mode='nearest')
tiempo = np.concatenate([[0], np.cumsum(ds / (0.5 * (w[1:] + w[:-1])))]); tiempo /= tiempo[-1]
N = int(round(DUR * FPS)); u = np.arange(N) / (N - 1)
K_EASE = 0.30; u2 = (1 - K_EASE) * u + K_EASE * (0.5 - 0.5 * np.cos(np.pi * u))
sig = np.interp(u2, tiempo, s_n)                                       # fraccion de recorrido en cada cuadro
cam = np.stack([np.interp(sig, s_n, P[:, k]) for k in range(3)], 1)
# objetivo: el del video en el punto equivalente del recorrido (por fraccion de largo), suavizado
s_o = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(cam0, axis=0), axis=1))]); s_o /= s_o[-1]
t_o = np.interp(sig, s_o, np.arange(n0))
i = np.clip(np.floor(t_o).astype(int), 0, n0 - 2); s = (t_o - i)[:, None]
obj = gaussian_filter1d(obj0[i] * (1 - s) + obj0[i + 1] * s, sigma=8, axis=0, mode='nearest')

# ---------- 5) verificacion
d_fin = holgura(cam)
seg = np.concatenate([cam[:-1] + (cam[1:] - cam[:-1]) * q for q in np.linspace(0, 1, 9)])
d_seg = holgura(seg)
vel = np.linalg.norm(np.diff(cam, axis=0), axis=1) * FPS
acc = np.abs(np.diff(vel)) * FPS
desv = arbol.query(cam)[0]
ver = {'holgura_min_m': round(float(d_fin.min()), 2), 'holgura_min_tramos_m': round(float(d_seg.min()), 2),
       'holgura_objetivo_m': HOLG, 'cuadros_bajo_holgura': int((d_fin < HOLG - 0.05).sum()),
       'video_holgura_min_m': round(float(d_ini.min()), 2), 'video_cuadros_bajo_holgura_12s': int((d_ini < HOLG).sum()),
       'largo_m': round(float(np.linalg.norm(np.diff(cam, axis=0), axis=1).sum()), 1),
       'velocidad_max_m_s': round(float(vel.max()), 2), 'velocidad_media_m_s': round(float(vel.mean()), 2),
       'aceleracion_max_m_s2': round(float(acc.max()), 2),
       'desvio_medio_m': round(float(desv.mean()), 2), 'desvio_max_m': round(float(desv.max()), 2)}
log('VERIFICACION:', json.dumps(ver, ensure_ascii=False))
tray = np.round(np.concatenate([t3(cam), t3(obj)], 1), 3).tolist()
# campo de distancias reducido para el visor (uint8, decimetros, tope 25,5 m) en celdas de CP m (minimo por bloque)
db = np.clip(np.floor(dg * 10), 0, 255).astype(np.uint8)
ruta_bin = os.path.splitext(salida)[0] + '_distancias.bin'
db.tofile(ruta_bin)
json.dump({'formato': 'recorrido-hito-v1', 'nombre': f'Recorrido optimizado {DUR:g} s (sin interferencias)',
           'fps': FPS, 'cuadros': N, 'duracion_s': DUR,
           'origen': 'recorrido de camara del video (hito_realista.blend), replanificado en espacio libre',
           'verificacion': ver,
           'distancias': {'archivo': os.path.basename(ruta_bin), 'ejes': 'blender (x, y, z)', 'origen': lo.round(4).tolist(),
                          'celda_m': CP * 1.0, 'dims': nd.tolist(), 'unidad': 'decimetros (uint8, tope 25,5 m)', 'orden': 'x mayor, z menor (C)'},
           'trayectoria_three': tray}, open(salida, 'w', encoding='utf-8'), ensure_ascii=False)
log('guardado', salida, 'y', ruta_bin)
