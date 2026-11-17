# Recorrido de cámara del Área 1313 (60 s = un ciclo completo de las animaciones del v4.1, «ciclo-completo»), SIN interferencias.
#  Puntos de vista anclados en el tiempo (VISTAS): cada uno mira al equipo que se está moviendo en ese instante; sus posiciones
#  salen de buscar_vistas_1313.py (posiciones libres con línea de vista al equipo). Entre vistas: camino de costo mínimo
#  (Dijkstra, celdas de 1,5 m) por el espacio con holgura >= HOLG respecto del modelo Y del volumen barrido por las piezas
#  móviles; suavizado con restricción; avance s(t) monótono (PCHIP) que pasa por cada vista en su instante, sin detenerse.
#  Objetivo (punto al que mira): interpolación suave de los objetivos de las vistas.
# Salidas: <salida.json> (formato de recorridos del visor) y <salida>_distancias.bin (campo de 1,5 m, promedio por bloque).
# Uso: py planificar_recorrido_1313.py <dist.npy> <salida.json> [HOLG=3]
import sys, json, time, numpy as np
from scipy import ndimage
from scipy.ndimage import gaussian_filter1d
from scipy.interpolate import PchipInterpolator
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra, connected_components
from scipy.spatial import cKDTree
r_dist, salida = sys.argv[1:3]
HOLG = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
FPS = 30; DUR = 60.0; CP = 1.5
t0 = time.time(); log = lambda *a: print(f'[rec {time.time()-t0:5.1f} s]', *a, flush=True)
D = np.load(r_dist).astype(np.float32); M = json.load(open(r_dist[:-4] + '.json')); lo = np.array(M['origen']); CEL = M['celda_m']
tb = lambda p: np.stack([p[..., 0], -p[..., 2], p[..., 1]], -1); bt = lambda p: np.stack([p[..., 0], p[..., 2], -p[..., 1]], -1)
holg = lambda P: ndimage.map_coordinates(D, ((np.atleast_2d(P) - lo) / CEL).T, order=1, mode='nearest')     # P en ejes Blender
# ---- vistas (t s, cámara Three, objetivo Three). Guion = tiempos de «ciclo-completo» (animaciones.json):
#   pórtico CN-1406 se traslada 2–14 s y regresa 44–56 s; carro 14–22 / 44–52 s; ganchos del pórtico bajan 22–28 y suben 34–40 s;
#   pluma CN-1404 gira 4–12 y vuelve 30–38 s, su gancho 12–30 s; pluma CN-1405 gira 7–15 y vuelve 33–41 s, su gancho 15–33 s;
#   tambores de los molinos: 1 vuelta cada 6 s todo el ciclo.
# 90 s (decisión de Eduardo 2026-10-30): apertura aérea 0–15 s, ciclo de 60 s en detalle 15–75 s (tiempo del ciclo = t − DESF),
# cierre con vuelta general 75–90 s. El visor anima los equipos con (t − desfase_ciclo_s) mód 60, así el guion coincide.
DUR = 90.0; DESF = 15.0
_CICLO = [
    (0.0,  [80.0, 58.0, -2.0],   [32.0, 12.0, -44.0]),    # vista general (planta, pórtico en reposo, molinos)
    (4.0,  [62.4, 46.2, -21.2],  [44.0, 22.0, -44.0]),    # pórtico iniciando su traslación; pescantes al fondo
    (9.0,  [58.8, 29.4, -43.9],  [41.5, 25.5, -44.0]),    # pluma CN-1404 girando
    (15.0, [59.4, 33.8, -59.0],  [41.0, 24.5, -55.0]),    # pluma CN-1405 girando, gancho 1404 bajando
    (19.0, [59.0, 29.5, -69.2],  [40.0, 21.0, -64.0]),    # gancho 1405 abajo
    (26.0, [6.0, 32.9, -74.1],   [16.1, 20.0, -56.2]),    # carro sobre ML-1402, ganchos bajando
    (31.0, [-4.4, 30.6, -61.7],  [16.1, 14.0, -55.0]),    # ganchos abajo, tambor girando
    (37.0, [8.7, 14.7, -64.4],   [16.5, 6.0, -55.4]),     # ML-1402 de cerca (tambor con franjas), ganchos subiendo
    (42.0, [-6.2, 13.0, -49.0],  [16.5, 5.0, -43.0]),     # ambos molinos girando
    (48.0, [-5.3, 27.9, -51.6],  [26.0, 20.0, -45.0]),    # pórtico regresando por sus rieles
    (55.0, [21.2, 17.0, -21.5],  [42.0, 18.0, -45.0]),    # pórtico llegando a su posición de reposo
    (60.0, [8.0, 52.0, 2.0],     [30.0, 10.0, -45.0]),    # alejamiento (fin del ciclo)
]
VISTAS = ([
    (0.0,  [-20.0, 82.0, 60.0],  [30.0, 10.0, -45.0]),    # APERTURA aérea alta desde el suroeste
    (7.5,  [60.0, 78.0, 55.0],   [31.0, 11.0, -45.0]),    # sobrevuelo lateral descendiendo
] + [(t_ + DESF, c_, o_) for t_, c_, o_ in _CICLO] + [
    (82.5, [-45.0, 62.0, -50.0], [30.0, 10.0, -45.0]),    # CIERRE: vuelta general por el oeste
    (90.0, [5.0, 78.0, -115.0],  [30.0, 8.0, -45.0]),     # alejamiento final alto por el norte
])
T_v = np.array([v[0] for v in VISTAS]); C_v = tb(np.array([v[1] for v in VISTAS])); O_v = np.array([v[2] for v in VISTAS])
log('holgura de las vistas (m):', np.round(holg(C_v), 1).tolist())
# ---- grafo en celdas de CP m (mínimo por bloque = conservador)
f = int(round(CP / CEL)); nd = np.array(D.shape) // f
dg = D[:nd[0]*f, :nd[1]*f, :nd[2]*f].reshape(nd[0], f, nd[1], f, nd[2], f)
dmin = dg.min(axis=(1, 3, 5)); dmed = dg.mean(axis=(1, 3, 5)); del dg
centros = lambda idx: lo + (np.array(idx) * f + (f - 1) / 2.0) * CEL
gi = np.stack(np.meshgrid(*[np.arange(n) for n in nd], indexing='ij'), -1).reshape(-1, 3); cc = centros(gi)
nodos = np.flatnonzero(dmin.reshape(-1) >= HOLG)
idx_nodo = -np.ones(gi.shape[0], np.int64); idx_nodo[nodos] = np.arange(nodos.size)
lin = lambda g: (g[:, 0] * nd[1] + g[:, 1]) * nd[2] + g[:, 2]
hol = dmin.reshape(-1)[nodos]; F_, C_, W_ = [], [], []
for dx in (-1, 0, 1):
    for dy in (-1, 0, 1):
        for dz in (-1, 0, 1):
            if (dx, dy, dz) <= (0, 0, 0): continue
            g2 = gi[nodos] + (dx, dy, dz); ok = np.all((g2 >= 0) & (g2 < nd), 1)
            j = idx_nodo[lin(g2[ok])]; okj = j >= 0; a = np.flatnonzero(ok)[okj]; j = j[okj]
            L = CP * np.sqrt(dx*dx + dy*dy + dz*dz)
            F_.append(a); C_.append(j); W_.append(L * (1 + 3.0 * np.clip((HOLG + 5 - 0.5 * (hol[a] + hol[j])) / 5, 0, 1)))
G = coo_matrix((np.concatenate(W_), (np.concatenate(F_), np.concatenate(C_))), shape=(nodos.size, nodos.size)).tocsr()
ncc, etq = connected_components(G, directed=False); mayor = np.bincount(etq).argmax(); validos = np.flatnonzero(etq == mayor)
arbol = cKDTree(cc[nodos[validos]])
log(f'celdas libres {nodos.size:,}; regiones {ncc}; exterior {validos.size:,}')
wps = [int(validos[arbol.query(p)[1]]) for p in C_v]
desv = np.linalg.norm(cc[nodos[wps]] - C_v, axis=1); log('ajuste de las vistas a celdas libres (m):', np.round(desv, 1).tolist())
# ---- caminos entre vistas; se guarda el índice del punto de cada vista para anclar el tiempo
P = [C_v[0]]; ancla = [0]
for k, (a_, b_) in enumerate(zip(wps[:-1], wps[1:])):
    _, pred = dijkstra(G, directed=False, indices=a_, return_predecessors=True)
    if pred[b_] < 0 and a_ != b_: raise SystemExit(f'sin camino libre entre las vistas {k} y {k+1}')
    tr = [b_]
    while tr[-1] != a_: tr.append(pred[tr[-1]])
    seg = cc[nodos[tr[::-1]]]
    P += list(seg[1:-1]) + [C_v[k + 1]]; ancla.append(len(P) - 1)
P = np.array(P)
# densificar manteniendo los anclajes
Pd = [P[0]]; an = [0]
for i in range(1, len(P)):
    n = max(1, int(np.ceil(np.linalg.norm(P[i] - P[i-1]) / 0.5)))
    for s in np.arange(1, n + 1) / n: Pd.append(P[i-1] + (P[i] - P[i-1]) * s)
    if i in ancla: an.append(len(Pd) - 1)
P = np.array(Pd); an = np.array(an)
fijo = np.zeros(len(P), bool); fijo[an] = True
for it in range(600):                                   # suavizado con restricción (las vistas quedan fijas)
    Q = P.copy(); Q[1:-1] = 0.5 * P[1:-1] + 0.25 * (P[:-2] + P[2:]); Q[fijo] = P[fijo]
    ok = holg(Q) >= HOLG; P = np.where(ok[:, None], Q, P)
s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
# ---- tiempo: s(t) monótono que pasa por cada vista en su instante
st = PchipInterpolator(T_v, s[an])
N = int(round(DUR * FPS)) + 1; tt = np.arange(N) / FPS
sg = st(tt)
cam = np.stack([np.interp(sg, s, P[:, k]) for k in range(3)], 1)
obj = np.stack([PchipInterpolator(T_v, O_v[:, k])(tt) for k in range(3)], 1)
obj = gaussian_filter1d(obj, 6, axis=0, mode='nearest')
# ---- verificación
d_c = holg(cam); seg = np.concatenate([cam[:-1] + (cam[1:] - cam[:-1]) * q for q in np.linspace(0, 1, 9)]); d_s = holg(seg)
vel = np.linalg.norm(np.diff(cam, axis=0), axis=1) * FPS; acc = np.abs(np.diff(vel)) * FPS
objb = tb(obj)
def vista_libre(c, o):
    L = np.linalg.norm(o - c); n = int(L / 0.5) + 2; q = np.linspace(0, 1, n)[:, None]; R = c + (o - c) * q
    lejos = np.linalg.norm(R - o, axis=1) > 10.0
    return bool((holg(R[lejos]) > 0.45).all()) if lejos.any() else True
los = np.array([vista_libre(cam[i], objb[i]) for i in range(0, N, 3)])
ver = {'holgura_min_m': round(float(d_c.min()), 2), 'holgura_min_tramos_m': round(float(d_s.min()), 2), 'holgura_objetivo_m': HOLG,
       'cuadros_bajo_holgura': int((d_c < HOLG - 0.05).sum()), 'largo_m': round(float(np.linalg.norm(np.diff(cam, axis=0), axis=1).sum()), 1),
       'velocidad_max_m_s': round(float(vel.max()), 2), 'velocidad_media_m_s': round(float(vel.mean()), 2),
       'aceleracion_max_m_s2': round(float(acc.max()), 2), 'vista_libre_al_objetivo_pct': round(100 * float(los.mean()), 1),
       'incluye_volumen_barrido': True, 'verificado_en': 'PC, campo de 0,75 m (modelo + volumen barrido de las piezas móviles)'}
log('VERIFICACIÓN:', json.dumps(ver, ensure_ascii=False))
db = np.clip(np.floor(dmed * 10), 0, 255).astype(np.uint8); ruta_bin = salida[:-5] + '_distancias.bin'; db.tofile(ruta_bin)
import os
json.dump({'formato': 'recorrido-hito-v1', 'nombre': 'Recorrido profesional 90 s (apertura aérea, ciclo de equipos, vuelta general)', 'fps': FPS, 'cuadros': N, 'duracion_s': DUR,
           'desfase_ciclo_s': DESF,
           'origen': 'vistas ancladas al guion de «ciclo-completo» (animaciones.json v4.1), caminos planificados en espacio libre',
           'verificacion': ver, 'vistas': [{'t': v[0], 'camara': v[1], 'objetivo': v[2]} for v in VISTAS],
           'distancias': {'archivo': os.path.basename(ruta_bin), 'ejes': 'blender (x, y, z)', 'origen': lo.round(4).tolist(),
                          'celda_m': CP, 'dims': nd.tolist(), 'agregado': 'media', 'unidad': 'decimetros (uint8, tope 25,5 m)', 'orden': 'x mayor, z menor (C)'},
           'trayectoria_three': np.round(np.concatenate([bt(cam), obj], 1), 3).tolist()}, open(salida, 'w', encoding='utf-8'), ensure_ascii=False)
log('guardado', salida, 'y', ruta_bin)
