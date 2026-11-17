# Extrae del modelo web (hito_web.glb) las BANDAS de las correas transportadoras (cinta de carga y de retorno) y sus
# CUBIERTAS (capotas semicirculares). Solo mide geometría existente: las bandas son losas finas (4 cm) de 1,22–1,52 m de
# ancho dentro de la malla UNION_MAT_008000; se reconocen como componentes conexos de triángulos largos (> 4 m) cuyas
# estaciones tienen dos bordes laterales a 1,0–1,8 m y espesor < 8 cm.
# Asignación de TAG y sentido de marcha con las piezas del FBX (fbx_tags_correas.py, ejes del visor = (-x, -y, z) del FBX):
#   1241-CV-1305/1306/1307: cola bajo los alimentadores 1232-FE-1301…1306 (x -178…-139) -> cabeza en la torre (x 147, z -15)
#   1241-CV-1309/1310/1311: cola bajo los chutes 1241-CH-1359…1361 (x 157–162, z -39) -> cabeza en x -19 (chutes CH-1338…1340)
# Salida: hito_correas.json (ejes Blender: x, y, z; m). Uso: py extraer_correas_hito.py hito_web.glb hito_correas.json
import sys, json, struct, numpy as np, DracoPy
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
glb, salida = sys.argv[1], sys.argv[2]
b = open(glb, 'rb').read(); L = struct.unpack('<I', b[12:16])[0]; J = json.loads(b[20:20 + L]); bin0 = 20 + L + 8; BV = J['bufferViews']
def qrot(q, v):
    x, y, z, w = q; u = np.array([x, y, z]); return v + 2 * np.cross(u, np.cross(u, v) + w * v)
nd = next(n for n in J['nodes'] if n.get('name') == 'UNION_MAT_008000')
pr = J['meshes'][nd['mesh']]['primitives'][0]; bv = BV[pr['extensions']['KHR_draco_mesh_compression']['bufferView']]
o = bin0 + bv.get('byteOffset', 0); m = DracoPy.decode(b[o:o + bv['byteLength']])
v = np.asarray(m.points, np.float64); t = np.asarray(m.faces, np.int64).reshape(-1, 3)
v = v * np.array(nd.get('scale', [1, 1, 1])); v = qrot(nd.get('rotation', [0, 0, 0, 1]), v) + np.array(nd.get('translation', [0, 0, 0]))
v = np.stack([v[:, 0], -v[:, 2], v[:, 1]], 1)
P = v[t]; c = P.mean(1)
emax = np.stack([np.linalg.norm(P[:, 1] - P[:, 0], axis=1), np.linalg.norm(P[:, 2] - P[:, 1], axis=1), np.linalg.norm(P[:, 0] - P[:, 2], axis=1)], 1).max(1)
reg = (c[:, 0] > -170) & (c[:, 0] < 172) & (c[:, 1] > -20) & (c[:, 1] < 22) & (c[:, 2] < -12)
s = np.flatnonzero(reg & (emax > 4)); T = t[s]
q = np.round(v[T].reshape(-1, 3) / 0.02).astype(np.int64); _, inv = np.unique(q, axis=0, return_inverse=True); inv = inv.reshape(-1, 3)
n = inv.max() + 1; ed = np.concatenate([inv[:, [0, 1]], inv[:, [1, 2]]])
k, lab = connected_components(coo_matrix((np.ones(len(ed)), (ed[:, 0], ed[:, 1])), shape=(n, n)), directed=False)
tl = lab[inv[:, 0]]; orden = np.argsort(tl); lim = np.searchsorted(tl[orden], np.arange(k + 1))
tiras = []
for i in range(k):
    idx = orden[lim[i]:lim[i + 1]]; pp = np.unique(np.round(v[T[idx]].reshape(-1, 3), 3), axis=0)
    if np.linalg.norm(pp.max(0) - pp.min(0)) < 25: continue
    est = np.round(pp[:, 0] / 0.4).astype(int); ok = True; pts = []; anchos = []
    for e_ in np.unique(est):
        g = pp[est == e_]
        if np.ptp(g[:, 2]) > 0.08: ok = False; break
        w = np.ptp(g[:, 1]); anchos.append(w)
        if not 1.0 <= w <= 1.8: ok = False; break
        pts.append([g[:, 0].mean(), 0.5 * (g[:, 1].min() + g[:, 1].max()), g[:, 2].max()])
    if not ok or len(pts) < 2: continue
    pts = np.array(pts); pts = pts[np.argsort(pts[:, 0])]
    tiras.append({'pts': pts, 'ancho': float(np.median(anchos)), 'ntri': int(len(idx))})
print('tiras de banda encontradas:', len(tiras))
# --- asignación a correas (franja lateral medida en el modelo; TAG del FBX)
CORREAS = [  # tag, función de la línea central y(x) aproximada para asignar, sentido de la carga (+1 = hacia +x)
    ('1241-CV-1305', lambda x: -4.7 + 0 * x, +1), ('1241-CV-1306', lambda x: 4.7 + 0 * x, +1), ('1241-CV-1307', lambda x: 14.4 + 0 * x, +1),
    ('1241-CV-1309', lambda x: -10.78 + (x + 19.05) * (5.97 / 185.25), -1), ('1241-CV-1310', lambda x: -1.28 + (x + 19.05) * (5.97 / 185.25), -1),
    ('1241-CV-1311', lambda x: 8.22 + (x + 19.05) * (5.97 / 185.25), -1)]
salida_c = []
for tag, yf, sentido in CORREAS:
    mias = [ti for ti in tiras if np.abs(ti['pts'][:, 1] - yf(ti['pts'][:, 0])).max() < 0.6]
    if not mias: print('sin bandas:', tag); continue
    # la de carga = la más alta en la zona común; las demás (por debajo, ~0,6–0,7 m) son retorno
    mias.sort(key=lambda ti: -np.ptp(ti['pts'][:, 0]))
    carga = mias[0]; tramos = []
    for ti in mias:
        x0, x1 = ti['pts'][[0, -1], 0]
        zc = np.interp(np.clip(0.5 * (x0 + x1), *carga['pts'][[0, -1], 0]), carga['pts'][:, 0], carga['pts'][:, 2])
        zt = np.interp(0.5 * (x0 + x1), ti['pts'][:, 0], ti['pts'][:, 2])
        tipo = 'carga' if ti is carga else ('retorno' if zt < zc - 0.3 else 'carga')
        if tipo == 'carga' and ti is not carga: continue
        P_ = ti['pts'] if (sentido > 0) == (tipo == 'carga') else ti['pts'][::-1]   # puntos en el sentido de marcha
        tramos.append({'tipo': tipo, 'ancho_m': round(ti['ancho'], 3), 'triangulos': ti['ntri'],
                       'puntos': np.round(P_, 3).tolist(), 'largo_m': round(float(np.linalg.norm(np.diff(P_, axis=0), axis=1).sum()), 1)})
    salida_c.append({'tag': tag, 'sentido_carga': '+x' if sentido > 0 else '-x', 'tramos': tramos})
    print(tag, [(tr['tipo'], tr['largo_m'], len(tr['puntos'])) for tr in tramos])
json.dump({'formato': 'correas-hito-v1', 'ejes': 'blender (x, y, z), m', 'malla': 'UNION_MAT_008000',
           'nota': 'bandas medidas en hito_web.glb; TAG y sentido de marcha según piezas del FBX (fbx_tags_correas.py)',
           'correas': salida_c}, open(salida, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
