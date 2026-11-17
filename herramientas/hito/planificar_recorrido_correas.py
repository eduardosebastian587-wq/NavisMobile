# Recorrido de cámara «Correas en funcionamiento» (Hito M33-1): acompaña las correas 1241-CV-1305/1306/1307 y
# 1241-CV-1309/1310/1311 desde la salida del domo hasta la torre, sin interferencias.
#   Ruta guía (puntos de paso por el lado sur de las correas, fuera de la torre) -> camino de costo mínimo (Dijkstra) en el
#   espacio libre con holgura >= HOLG (celdas de 1,5 m, tubo de TUBO m alrededor de la guía) -> suavizado con restricción ->
#   ritmo con aceleración limitada (arranque y llegada en reposo) -> objetivo de cámara interpolado entre los objetivos de la guía.
# Entradas: dist.npy (campo de distancias 0,75 m de hito_web.glb con el suelo plano a -41,6: campo_distancias_hito.py).
# Uso: python planificar_recorrido_correas.py dist.npy salida.json [DUR=45] [HOLG=3]
import sys, json, time, numpy as np
from scipy import ndimage
from scipy.ndimage import gaussian_filter1d
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra, connected_components
from scipy.spatial import cKDTree
r_dist, salida = sys.argv[1:3]
DUR = float(sys.argv[3]) if len(sys.argv) > 3 else 45.0
HOLG = float(sys.argv[4]) if len(sys.argv) > 4 else 3.0
lo = np.array([-350.0, -270.0, -50.6]); CEL = 0.75; CP = 1.5; TUBO = 12.0; FPS = 30; AMAX = 2.0
t0 = time.time(); log = lambda *a: print(f'[correas {time.time()-t0:5.1f} s]', *a, flush=True)
t3 = lambda a: np.stack([a[:, 0], a[:, 2], -a[:, 1]], 1)           # Blender -> Three
D = np.load(r_dist).astype(np.float32)
holgura = lambda P: ndimage.map_coordinates(D, ((np.asarray(P) - lo) / CEL).T, order=1, mode='nearest')
# ---------- guía: (posición de cámara, punto al que mira), ejes Blender (m)
GUIA = np.array([
    [[-95, -32, -24], [-50, 2, -39]],      # salida de las correas del domo (CV-1305/06/07, x > -70 fuera del túnel)
    [[-55, -24, -30], [-20, 0, -34]],
    [[-25, -28, -24], [-17, -6, -31]],     # cabezas de CV-1309/10/11 y chutes CH-1338…1340 (x ≈ -20)
    [[15, -22, -30], [40, -2, -37]],
    [[55, -20, -30], [80, 2, -33]],        # tramo cóncavo: las correas CV-1305/06/07 empiezan a subir
    [[95, -22, -22], [125, 5, -21]],
    [[112, -30, -10], [146, 4, -15]],      # llegada de CV-1305/06/07 a la torre (poleas de cabeza x ≈ 147, z ≈ -15)
    [[100, -62, 8], [40, 2, -37]]], float) # cierre: se aleja y mira las correas hacia atrás
cam_g, obj_g = GUIA[:, 0], GUIA[:, 1]
log('holgura en los puntos de la guía:', np.round(holgura(cam_g), 1).tolist())
f = 2; nd = np.array(D.shape) // f
dg = D[:nd[0]*f, :nd[1]*f, :nd[2]*f].reshape(nd[0], f, nd[1], f, nd[2], f).min(axis=(1, 3, 5))
centros = lambda idx: lo + (np.array(idx) * f + (f - 1) / 2.0) * CEL
def densificar(P, paso=1.0):
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]); q = np.arange(0, s[-1], paso)
    return np.stack([np.interp(q, s, P[:, k]) for k in range(3)], 1)
arbol = cKDTree(densificar(cam_g))
gi = np.stack(np.meshgrid(*[np.arange(n) for n in nd], indexing='ij'), -1).reshape(-1, 3); cc = centros(gi)
dtub, _ = arbol.query(cc, distance_upper_bound=TUBO)
libre = (dg.reshape(-1) >= HOLG) & np.isfinite(dtub); nodos = np.flatnonzero(libre)
idx_nodo = -np.ones(gi.shape[0], np.int64); idx_nodo[nodos] = np.arange(nodos.size)
lin = lambda g: (g[:, 0] * nd[1] + g[:, 1]) * nd[2] + g[:, 2]
dev = dtub[nodos]; hol = dg.reshape(-1)[nodos]; F_, C_, W_ = [], [], []
for dx in (-1, 0, 1):
    for dy in (-1, 0, 1):
        for dz in (-1, 0, 1):
            if (dx, dy, dz) <= (0, 0, 0): continue
            g2 = gi[nodos] + (dx, dy, dz); ok = np.all((g2 >= 0) & (g2 < nd), 1)
            j = idx_nodo[lin(g2[ok])]; okj = j >= 0; a = np.flatnonzero(ok)[okj]; j = j[okj]
            L = CP * np.sqrt(dx*dx + dy*dy + dz*dz)
            F_.append(a); C_.append(j); W_.append(L * (1 + 1.0 * (dev[a] + dev[j]) / 6.0 + 2.0 * np.clip((HOLG + 3 - 0.5 * (hol[a] + hol[j])) / 3, 0, 1)))
G = coo_matrix((np.concatenate(W_), (np.concatenate(F_), np.concatenate(C_))), shape=(nodos.size, nodos.size)).tocsr()
ncc, etq = connected_components(G, directed=False); mayor = np.bincount(etq).argmax(); validos = np.flatnonzero(etq == mayor)
arbol_v = cKDTree(cc[nodos[validos]])
wps = [int(validos[arbol_v.query(p)[1]]) for p in cam_g]
camino = [wps[0]]
for a_, b_ in zip(wps[:-1], wps[1:]):
    _, pred = dijkstra(G, directed=False, indices=a_, return_predecessors=True)
    if pred[b_] < 0 and a_ != b_: raise SystemExit(f'sin camino libre {a_}->{b_}')
    tr = [b_]
    while tr[-1] != a_: tr.append(pred[tr[-1]])
    camino += tr[::-1][1:]
Pg = cc[nodos[camino]]
log(f'camino grueso {len(Pg)} celdas; desvío máx. de la guía {arbol.query(Pg)[0].max():.1f} m')
def remuestrear(P, paso):
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]); q = np.linspace(0, s[-1], max(int(s[-1] / paso), 2))
    return np.stack([np.interp(q, s, P[:, k]) for k in range(3)], 1)
P = remuestrear(Pg, 0.5); arbol_g = cKDTree(remuestrear(Pg, 0.25)); DESV = 3.0          # el suavizado no se aleja más de DESV m del camino
for k, its in ((16, 500), (8, 500), (3, 400), (1, 400)):                 # suavizado multiescala con restricción de holgura
    for it in range(its):
        E_ = np.vstack([np.repeat(P[:1], 16, 0), P, np.repeat(P[-1:], 16, 0)])
        Q = 0.5 * P + 0.25 * (E_[16 - k:16 - k + len(P)] + E_[16 + k:16 + k + len(P)]); Q[0] = P[0]; Q[-1] = P[-1]
        P = np.where(((holgura(Q) >= np.minimum(HOLG + 1.0, holgura(P))) & (arbol_g.query(Q)[0] <= DESV))[:, None], Q, P)
P = remuestrear(P, 0.25); s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]); Ltot = s[-1]; ds = np.diff(s)
# ritmo: velocidad ∝ holgura^0,5 (más lento junto a las correas), aceleración <= AMAX, arranque y llegada en reposo
w = gaussian_filter1d(np.clip(holgura(P), HOLG, 25.0) ** 0.5, sigma=30.0 / 0.25, mode='nearest')
def perfil(kv):
    v = kv * w; v[0] = 0.3
    for i in range(1, len(v)): v[i] = min(v[i], np.sqrt(v[i-1]**2 + 2 * AMAX * ds[i-1]))
    v[-1] = 0.3
    for i in range(len(v) - 2, -1, -1): v[i] = min(v[i], np.sqrt(v[i+1]**2 + 2 * AMAX * ds[i]))
    v = np.maximum(gaussian_filter1d(v, 20, mode='nearest'), 0.3)
    return np.concatenate([[0], np.cumsum(ds / (0.5 * (v[1:] + v[:-1])))])
a_, b_ = 0.05, 40.0
for _ in range(50):
    kv = 0.5 * (a_ + b_); (a_, b_) = (kv, b_) if perfil(kv)[-1] > DUR else (a_, kv)
tiempo = perfil(b_); tiempo *= DUR / tiempo[-1]
N = int(round(DUR * FPS)) + 1
sg = np.interp(np.arange(N) / FPS, tiempo, s)
cam = np.stack([np.interp(sg, s, P[:, i]) for i in range(3)], 1)
# objetivo: fracción de avance a lo largo de la guía -> interpolación entre los objetivos de la guía
sgu = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(cam_g, axis=0), axis=1))])
dens = densificar(cam_g, 0.5); sd = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(dens, axis=0), axis=1))])
fr = sd[cKDTree(dens).query(cam)[1]]; fr = np.maximum.accumulate(gaussian_filter1d(fr, 15, mode='nearest'))
obj = np.stack([np.interp(fr, sgu, obj_g[:, k]) for k in range(3)], 1)
obj = gaussian_filter1d(obj, 20, axis=0, mode='nearest')
# verificación
seg = np.concatenate([cam[:-1] + (cam[1:] - cam[:-1]) * q for q in np.linspace(0, 1, 9)])
dn = holgura(cam); dseg = holgura(seg)
vel = np.linalg.norm(np.diff(cam, axis=0), axis=1) * FPS; acc = np.abs(np.diff(vel)) * FPS
ver = {'holgura_min_m': round(float(dn.min()), 2), 'holgura_min_tramos_m': round(float(dseg.min()), 2), 'holgura_objetivo_m': HOLG,
       'cuadros_bajo_holgura': int((dn < HOLG - 0.05).sum()), 'largo_m': round(float(Ltot), 1),
       'velocidad_max_m_s': round(float(vel.max()), 2), 'velocidad_media_m_s': round(float(vel.mean()), 2), 'aceleracion_max_m_s2': round(float(acc.max()), 2),
       'verificado_en': 'nube, campo de 0,75 m reconstruido desde hito_web.glb (suelo plano a -41,6 m)'}
log('VERIFICACIÓN:', json.dumps(ver, ensure_ascii=False))
dist_meta = json.load(open(sys.argv[5], encoding='utf-8'))['distancias'] if len(sys.argv) > 5 else None
json.dump({'formato': 'recorrido-hito-v1', 'nombre': f'Correas en funcionamiento {DUR:g} s', 'fps': FPS, 'cuadros': N, 'duracion_s': DUR,
           'origen': 'recorrido a lo largo de las correas 1241-CV-1305/1306/1307 y 1241-CV-1309/1310/1311, planificado en espacio libre',
           'verificacion': ver, 'distancias': dist_meta, 'guia_blender': GUIA.tolist(),
           'trayectoria_three': np.round(np.concatenate([t3(cam), t3(obj)], 1), 3).tolist()}, open(salida, 'w', encoding='utf-8'), ensure_ascii=False)
log('guardado', salida)
