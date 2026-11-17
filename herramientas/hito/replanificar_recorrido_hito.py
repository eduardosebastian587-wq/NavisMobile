# REPLANIFICACIÓN del recorrido del Hito (v2, 50 s): conserva los primeros T0 cuadros del recorrido de 25 s y vuelve a planificar el
# resto con el edificio (torre de traspaso + puente grúa) a >= EDIF m de la cámara (antes 3 m).
# (v1: extender_recorrido_hito.py, 25 s -> 50 s.)
#   - Cuadros 0-749: idénticos al recorrido de 25 s ya entregado (no se tocan).
#   - Cuadros 750-1499: continuación planificada en espacio libre con la misma regla (holgura >= 3 m, prefiere >= 9 m),
#     Dijkstra en celdas de 1,5 m dentro de un tubo de 30 m alrededor de la ruta guía, suavizado con restricción.
#     Empalme C1: tramo de Hermite con la tangente del último cuadro y velocidad inicial = velocidad final de la ida (9,6 m/s);
#     ritmo con aceleración limitada (AMAX) y llegada en reposo.
#     Ruta guía: vuelta por el lado NORTE de las correas (espejo de la ida por el sur) -> domo -> correa de apilamiento
#     -> alejamiento en altura (cierre simétrico a la aproximación inicial). Objetivo de cámara = la misma línea de
#     objetivos del video (eje de correas y = 0, centro del domo), recorrida en sentido contrario; sobre el domo, la correa de apilamiento.
# Uso: python extender_recorrido_hito.py <dist.npy> <hito_recorrido.json> <hito_escena_video.json> <salida.json> [DUR_EXT=25] [HOLG=3] [MARGEN=1.2]
#      dist.npy = campo de distancias de 0,75 m (campo_distancias_hito.py, a partir de hito_web.glb)
import sys, json, time, numpy as np
from scipy import ndimage
from scipy.ndimage import gaussian_filter1d
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra, connected_components
from scipy.spatial import cKDTree
r_dist, r_rec, r_esc, salida = sys.argv[1:5]
DUR = None
HOLG = float(sys.argv[6]) if len(sys.argv) > 6 else 3.0
MARGEN = float(sys.argv[7]) if len(sys.argv) > 7 else 1.2
T0_ARG = int(sys.argv[8]) if len(sys.argv) > 8 else 450          # cuadros que se conservan del recorrido de 25 s (15 s)
EDIF = float(sys.argv[9]) if len(sys.argv) > 9 else 22.0       # holgura mínima al edificio (m)
TOTAL_S = 50.0
lo = np.array([-350.0, -270.0, -50.6]); CEL = 0.75; CP = 1.5; TUBO = 30.0; FPS = 30
t0 = time.time(); log = lambda *a: print(f'[ext {time.time()-t0:5.1f} s]', *a, flush=True)
b = lambda a: np.stack([a[:, 0], -a[:, 2], a[:, 1]], 1); t3 = lambda a: np.stack([a[:, 0], a[:, 2], -a[:, 1]], 1)
D = np.load(r_dist).astype(np.float32)
# holgura efectiva: >= HOLG a cualquier elemento y >= EDIF al edificio (caja x 120-172, y -46..27 m: torre de traspaso y puente grúa)
_gx, _gy, _gz = [lo[i] + np.arange(D.shape[i]) * CEL for i in range(3)]
_ed = ((D < 0.5) & ((_gx > 120) & (_gx < 172))[:, None, None] & ((_gy > -46) & (_gy < 27))[None, :, None] & (_gz > -45)[None, None, :])
DB = ndimage.distance_transform_edt(~_ed, sampling=CEL).astype(np.float32)
D0 = D.copy(); D = np.minimum(D, DB - (EDIF - HOLG)); del _ed
holgura0 = lambda P: ndimage.map_coordinates(D0, ((np.asarray(P) - lo) / CEL).T, order=1, mode='nearest')
holgura_ed = lambda P: ndimage.map_coordinates(DB, ((np.asarray(P) - lo) / CEL).T, order=1, mode='nearest')
holgura = lambda P: ndimage.map_coordinates(D, ((np.asarray(P) - lo) / CEL).T, order=1, mode='nearest')
R0 = json.load(open(r_rec, encoding='utf-8')); T0 = np.array(R0['trayectoria_three']); T0_N = T0_ARG
cam0, obj0 = b(T0[:T0_N + 1, :3]), b(T0[:T0_N + 1, 3:6]); n0 = len(cam0)
E = json.load(open(r_esc, encoding='utf-8')); TV = np.array([r[1:7] for r in E['trayectoria_three']]); objv = b(TV[:, 3:6])
v_fin = (cam0[-1] - cam0[-2]) * FPS; v0 = float(np.linalg.norm(v_fin)); dir0 = v_fin / v0
log(f'recorrido base: {n0} cuadros; velocidad final {v0:.2f} m/s; holgura final {holgura(cam0[-1:])[0]:.2f} m')

# ---------- ruta guía (ejes Blender, m)
GUIA = np.array([cam0[-1], cam0[-1] + 12 * dir0,
                 [55, -48, -26], [95, -98, -22], [155, -120, -18], [220, -100, -18], [242, -40, -18], [245, 30, -18], [226, 92, -18],
                 [160, 110, -18], [80, 98, -18], [0, 70, -18], [-60, 56, -14], [-112, 80, 18], [-190, 140, 45], [-268, 70, 62], [-300, -40, 72]], float)
# ---------- rejilla gruesa (mínimo por bloque = conservador) y grafo dentro del tubo
f = 2; nd = np.array(D.shape) // f
dg = D[:nd[0]*f, :nd[1]*f, :nd[2]*f].reshape(nd[0], f, nd[1], f, nd[2], f).min(axis=(1, 3, 5))
centros = lambda idx: lo + (np.array(idx) * f + (f - 1) / 2.0) * CEL
def densificar(P, paso=1.0):
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]); q = np.arange(0, s[-1], paso)
    return np.stack([np.interp(q, s, P[:, k]) for k in range(3)], 1)
arbol = cKDTree(densificar(GUIA))
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
            F_.append(a); C_.append(j); W_.append(L * (1 + 0.5 * (dev[a] + dev[j]) / 6.0 + 5.0 * np.clip((HOLG + 6 - 0.5 * (hol[a] + hol[j])) / 6, 0, 1)))
G = coo_matrix((np.concatenate(W_), (np.concatenate(F_), np.concatenate(C_))), shape=(nodos.size, nodos.size)).tocsr()
ncc, etq = connected_components(G, directed=False); mayor = np.bincount(etq).argmax(); validos = np.flatnonzero(etq == mayor)
arbol_v = cKDTree(cc[nodos[validos]])
log(f'celdas libres en el tubo {nodos.size:,}; regiones {ncc}; exterior {validos.size:,}')
wps = [int(validos[arbol_v.query(p)[1]]) for p in GUIA]
camino = [wps[0]]
for a_, b_ in zip(wps[:-1], wps[1:]):
    _, pred = dijkstra(G, directed=False, indices=a_, return_predecessors=True)
    if pred[b_] < 0 and a_ != b_: raise SystemExit(f'sin camino libre {a_}->{b_}')
    tr = [b_]
    while tr[-1] != a_: tr.append(pred[tr[-1]])
    camino += tr[::-1][1:]
Pg = cc[nodos[camino]]
sm = lambda x: np.clip(x, 0, 1) ** 2 * (3 - 2 * np.clip(x, 0, 1))
# ---------- suavizado multiescala con restricción; el primer punto queda fijo en el último cuadro y un punto
#            "fantasma" del recorrido base (a un paso hacia atrás) da la condición de borde -> empalme sin quiebre
def remuestrear(P, paso):
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]); q = np.linspace(0, s[-1], max(int(s[-1] / paso), 2))
    return np.stack([np.interp(q, s, P[:, k]) for k in range(3)], 1)
sb = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(cam0[::-1], axis=0), axis=1))])
atras = lambda d: np.array([np.interp(d, sb, cam0[::-1, k]) for k in range(3)])
def hermite(p0, m0, p1, m1, n=400):
    u = np.linspace(0, 1, n)[:, None]
    return (2*u**3 - 3*u**2 + 1) * p0 + (u**3 - 2*u**2 + u) * m0 + (-2*u**3 + 3*u**2) * p1 + (u**3 - u**2) * m1
# entrada inicial válida: Hermite desde el último cuadro (tangente de la ida) hasta el primer punto del camino grueso
# que se pueda alcanzar sin bajar de HOLG (el tramo recto choca a ~10 m: estructura al norte de la torre)
sg_ = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(Pg, axis=0), axis=1))]); entrada = None
for j in range(1, len(Pg) - 5):
    if sg_[j] < 6: continue
    tj = Pg[j + 2] - Pg[j - 2]; tj /= np.linalg.norm(tj); L = np.linalg.norm(Pg[j] - cam0[-1])
    for c in (0.6, 0.45, 0.3, 0.8):
        H = hermite(cam0[-1], dir0 * L * c, Pg[j], tj * L * c, 200)
        if holgura(H[1:]).min() >= HOLG: entrada = (j, H); break
    if entrada or sg_[j] > 80: break
if not entrada: raise SystemExit('sin entrada válida desde el último cuadro')
log(f'entrada: {sg_[entrada[0]]:.0f} m del camino grueso')
P = np.vstack([entrada[1], Pg[entrada[0] + 1:]])
P = remuestrear(P, 0.5)
fant = np.array([atras(0.5 * m) for m in range(1, 13)])[::-1]          # 12 puntos del recorrido base antes del empalme
for k, its in ((12, 500), (6, 500), (3, 400), (1, 400)):             # laplaciano de paso ancho -> suavizado multiescala
    for it in range(its):
        E_ = np.vstack([fant, P, np.repeat(P[-1:], 12, 0)]); i0 = 12
        Q = 0.5 * P + 0.25 * (E_[i0 - k:i0 - k + len(P)] + E_[i0 + k:i0 + k + len(P)]); Q[0] = cam0[-1]; Q[-1] = P[-1]
        hq = holgura(Q); P = np.where((hq >= np.minimum(HOLG + MARGEN, holgura(P)))[:, None], Q, P)   # margen: deja espacio al alisado final
P = remuestrear(P, 0.25)
Ps = gaussian_filter1d(P, 12, axis=0, mode='nearest'); Ps[0] = P[0]              # alisado final (sigma 3 m): quita las esquinas
wg = np.ones(len(P))                                       # peso del alisado, reducido con suavidad donde bajaría de HOLG
for _ in range(30):
    bad = holgura(P + wg[:, None] * (Ps - P)) < HOLG
    if not bad.any(): break
    wg[ndimage.binary_dilation(bad, iterations=40)] *= 0.6; wg = np.minimum(wg, gaussian_filter1d(wg, 20, mode='nearest'))
P = P + wg[:, None] * (Ps - P) * (holgura(P + wg[:, None] * (Ps - P)) >= HOLG)[:, None]
s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
# tangente exacta en el empalme: tramo de Hermite cúbico desde el último cuadro (tangente = dirección de la ida) hasta
# el punto de la ruta a LB m (tangente de la ruta); se prueba de más largo a más corto y se exige holgura >= HOLG
emp = None
for LB in (45.0, 35.0, 28.0, 22.0, 16.0, 12.0, 9.0):
    j = int(np.searchsorted(s, LB)); tj = P[min(j + 4, len(P) - 1)] - P[max(j - 4, 0)]; tj /= np.linalg.norm(tj)
    for c in (1.0, 0.8, 0.6, 0.45, 0.3):
        H = hermite(cam0[-1], dir0 * LB * c, P[j], tj * LB * c)
        if holgura(H[1:]).min() >= HOLG: emp = (LB, c); break
    if emp: P = np.vstack([H, P[j+1:]]); break
if not emp:
    raise SystemExit('no se pudo empalmar con tangente continua')
LB = emp[0]
P = remuestrear(P, 0.25); s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]); Ltot = s[-1]
log(f'ruta nueva: largo {Ltot:.0f} m; empalme recto {LB:.0f} m')
# ---------- ritmo: velocidad objetivo k·w(s) (w = holgura^0,6 suavizada, igual que la ida), con aceleración limitada a
#            AMAX hacia adelante (desde v0 = velocidad final de la ida) y hacia atrás (llegada en reposo); k por bisección
AMAX = 4.5; ds = np.diff(s)
w = gaussian_filter1d(np.clip(holgura(P), HOLG, 25.0) ** 0.6, sigma=40.0 / 0.25, mode='nearest')
def perfil(k):
    v = np.maximum(k * w, np.sqrt(np.maximum(v0**2 - 2 * AMAX * s, 0))); v[0] = v0
    for i in range(1, len(v)): v[i] = min(v[i], np.sqrt(v[i-1]**2 + 2 * AMAX * ds[i-1]))
    v[-1] = 0.3
    for i in range(len(v) - 2, 0, -1): v[i] = min(v[i], np.sqrt(v[i+1]**2 + 2 * AMAX * ds[i]))
    v = gaussian_filter1d(v, 20, mode='nearest'); v = v + (v0 - v[0]) * (1 - sm(s / 15)); v = np.maximum(v, 0.3)   # v(0) = v0 sin escalón
    return np.concatenate([[0], np.cumsum(ds / (0.5 * (v[1:] + v[:-1])))])
DUR = TOTAL_S - (n0 - 1) / FPS
N = int(round(DUR * FPS)); dt = 1.0 / FPS
a_, b_ = 0.1, 60.0
for _ in range(50):
    k = 0.5 * (a_ + b_); (a_, b_) = (k, b_) if perfil(k)[-1] > DUR else (a_, k)
tiempo = perfil(b_); tiempo *= DUR / tiempo[-1]
sg = np.interp(np.arange(1, N + 1) * dt, tiempo, s)          # N cuadros nuevos (750..1499)
cam = np.stack([np.interp(sg, s, P[:, i]) for i in range(3)], 1)
# ---------- objetivo: línea de objetivos del video (x -> y,z) como en v1; mientras la cámara rodea el edificio mira su centro
orden = np.argsort(objv[:, 0]); ox = objv[orden, 0]
linea = lambda x: np.stack([x, np.interp(x, ox, objv[orden, 1]), np.interp(x, ox, objv[orden, 2])], 1)
xr = np.clip(gaussian_filter1d(cam[:, 0] - 40, 15, mode='nearest'), ox[0], ox[-1])
cruda = gaussian_filter1d(linea(xr), 8, axis=0, mode='nearest')
tt = np.arange(1, N + 1) * dt; beta = sm(tt / 4)[:, None]
obj = (1 - beta) * obj0[-1] + beta * cruda
EDIFICIO = np.array([150.0, -8.0, -22.0])                    # centro del edificio (torre de traspaso + puente grúa)
ie = int(np.argmax(cam[:, 0])); xe = cam[ie, 0]
wb = sm(tt / 3.0) * np.where(np.arange(N) <= ie, 1.0, 1 - sm((xe - cam[:, 0]) / 70.0))
obj = (1 - wb[:, None]) * obj + wb[:, None] * EDIFICIO
# tramo del domo (≈ 36,5–45 s): la cámara mira la correa de apilamiento en vez del centro del domo
ta = (n0 - 1) / FPS + tt; APIL = np.array([-178.0, 55.0, 18.0])
wap = (sm((ta - 36.5) / 2.0) * (1 - sm((ta - 42.5) / 2.5)))[:, None]
obj = (1 - wap) * obj + wap * APIL
# ---------- verificación (cuadros y tramos entre cuadros, con el campo ORIGINAL: elementos >= 3 m; y distancia al edificio)
camT = np.vstack([cam0, cam]); objT = np.vstack([obj0, obj])
seg = np.concatenate([camT[:-1] + (camT[1:] - camT[:-1]) * q for q in np.linspace(0, 1, 9)])
dn = holgura0(camT); dseg = holgura0(seg)
vel = np.linalg.norm(np.diff(camT, axis=0), axis=1) * FPS; acc = np.abs(np.diff(vel)) * FPS
dirs = np.diff(camT, axis=0); giro = np.degrees(np.arccos(np.clip((dirs[1:] * dirs[:-1]).sum(1) / (np.linalg.norm(dirs[1:], axis=1) * np.linalg.norm(dirs[:-1], axis=1) + 1e-9), -1, 1)))
vb = R0['verificacion']; ed = holgura_ed(camT); ed = ed[ed < 1e5]
ver = {'holgura_min_m': round(float(dn.min()), 2), 'holgura_min_tramos_m': round(float(dseg.min()), 2),
       'holgura_objetivo_m': HOLG, 'cuadros_bajo_holgura': int((dn < HOLG - 0.05).sum()),
       'distancia_min_edificio_m': round(float(ed.min()), 1), 'distancia_edificio_objetivo_m': EDIF,
       'video_holgura_min_m': vb['video_holgura_min_m'], 'video_cuadros_bajo_holgura_12s': vb['video_cuadros_bajo_holgura_12s'],
       'largo_m': round(float(np.linalg.norm(np.diff(camT, axis=0), axis=1).sum()), 1), 'largo_extension_m': round(float(Ltot), 1),
       'velocidad_max_m_s': round(float(vel.max()), 2), 'velocidad_media_m_s': round(float(vel.mean()), 2),
       'aceleracion_max_m_s2': round(float(acc.max()), 2), 'aceleracion_max_empalme_m_s2': round(float(acc[n0-5:n0+5].max()), 2),
       'giro_max_empalme_grados_por_cuadro': round(float(giro[n0-5:n0+5].max()), 2),
       'cuadros_base_identicos': n0, 'verificado_en': 'nube, campo de 0,75 m reconstruido desde hito_web.glb (limpio)'}
log('VERIFICACIÓN:', json.dumps(ver, ensure_ascii=False))
tray = np.round(np.concatenate([t3(cam), t3(obj)], 1), 3).tolist()
assert n0 == T0_N + 1
json.dump({'formato': 'recorrido-hito-v1', 'nombre': f'Recorrido continuo {(n0 + N - 1) / FPS:.0f} s (edificio a ≥ {EDIF:.0f} m)',
           'fps': FPS, 'cuadros': n0 + N, 'duracion_s': round((n0 + N - 1) / FPS, 3),
           'origen': f'recorrido optimizado de 25 s (cuadros 0-{T0_N} sin cambios) + resto replanificado con el edificio a >= {EDIF:.0f} m',
           'verificacion': ver, 'distancias': R0['distancias'],
           'trayectoria_three': R0['trayectoria_three'][:T0_N + 1] + tray}, open(salida, 'w', encoding='utf-8'), ensure_ascii=False)
log('guardado', salida)
