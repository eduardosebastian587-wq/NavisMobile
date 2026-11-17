# v4 (aprobado por Eduardo 2026-10-30): prepara lo que unir_capas_1313_v4.py borra.
#  - piezas sueltas (detectar_sueltos_1313.py, D=1.0 m, conjuntos >= 2 m) + extension forzada de las lineas 40" SL-11040/11041 (circulo 2)
#  - centros de poligono (y de triangulos en abanico) de esas piezas, en el marco Blender de Capas: (40 - x, 30 - y, z) con x,y,z = real - ORI
#  - semillas de la linea verde del terreno (malla base V4_Structural_00FF00) = impactos del picado en el circulo 2, marco Blender (x, -z, y)
# Uso: py -I preparar_ocultar_v4_1313.py "<Capas area 1313.fbx>" <salida_prefijo> --sueltos sueltos.json --pick pick.json
import sys, os
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'analizar_huecos_tuberia_1313.py'), encoding='utf-8').read()
exec(_src.split('# ---- analisis de huecos')[0])
ORI = np.array([184800.0, 4448600.0, 2250.0]); pref = sys.argv[2]
R = json.load(open(opt('--sueltos', ''), encoding='utf-8')); PZ = R['piezas']
sel = {i for c in R['D']['1.0'] if c['ext'] >= 2 for i in c['m']}; n0 = len(sel)
# extension forzada: piezas de SL-11040/11041 conectadas (cajas < 5 cm) a lo ya marcado y separadas > 0,15 m de estructura
lin = [i for i, p in enumerate(PZ) if len(p['cad']) > 2 and p['cad'][2] in ('1313-SL-11040', '1313-SL-11041')]
CJ = {i: np.array(PZ[i]['caja']) for i in lin}; cambio = True
while cambio:
    cambio = False
    for i in lin:
        if i in sel or PZ[i]['d'] <= 0.15: continue
        for j in lin:
            if j in sel and np.all(CJ[i][:3] - 0.05 <= CJ[j][3:]) and np.all(CJ[j][:3] - 0.05 <= CJ[i][3:]):
                sel.add(i); cambio = True; break
n1 = len(sel)
LN = [x for x in opt('--lineas', '').split(',') if x]
for i, p in enumerate(PZ):
    if len(p['cad']) > 2 and p['cad'][2] in LN: sel.add(i)
log(f'lineas completas {LN}: +{len(sel) - n1}')
n1 = len(sel)
if opt('--forzar', ''): sel |= set(json.load(open(opt('--forzar', ''), encoding='utf-8'))['indices'])
log(f'forzadas por circulos (camara real, visibles): +{len(sel) - n1}')
log(f'piezas: {n0} sueltas + {len(sel) - n0} forzadas lineas 40" = {len(sel)}')
mids = {PZ[i]['mid'] for i in sel}; gids = {geo_de[m]: m for m in mids}
cen = []; ver = []; obb = []
for h in hijos(top['Objects']):
    end, n, pl, nm, p = cab(h)
    if nm != 'Geometry': continue
    gid = props(p, n)[0]
    if gid not in gids: continue
    pvi = None
    for h2 in hijos(h):
        e2, n2, _, nm2, p2 = cab(h2)
        if nm2 == 'PolygonVertexIndex': pvi = arr(props(p2, n2)[0]); break
    mid = gids[gid]; v = arr(geoms[gid]).reshape(-1, 3); d = modelos[mid]; G = M(d['GT'], d['GR'], d['GS']); W4 = mundo(mid) @ G
    w = (v @ W4[:3, :3].T + W4[:3, 3]) * (unit / 100.0) - ORI; b = np.c_[40 - w[:, 0], 30 - w[:, 1], w[:, 2]]; ver.append(b); c0 = b.mean(0); _, _, vt = np.linalg.svd(b - c0, full_matrices=False); pr_ = (b - c0) @ vt.T; lo_, hi_ = pr_.min(0), pr_.max(0); obb.append(np.r_[c0 + ((lo_ + hi_) / 2) @ vt, vt.ravel(), (hi_ - lo_) / 2 + 0.04])
    pol = []
    for k in pvi:
        if k < 0: pol.append(~k); P = b[pol]; cen.append(P.mean(0))
        else: pol.append(k); continue
        if len(pol) > 3: cen.extend((P[0] + P[j] + P[j + 1]) / 3 for j in range(1, len(pol) - 1))
        pol = []
cen = np.array(cen, np.float32); np.save(pref + '_centros.npy', cen); ver = np.concatenate(ver).astype(np.float32); np.save(pref + '_vertices.npy', ver); np.save(pref + '_obb.npy', np.array(obb)); log(f'cajas orientadas {len(obb)}'); log(f'vertices {len(ver):,}')
hits = json.load(open(opt('--pick', ''), encoding='utf-8'))
sem = np.zeros((0, 3), np.float32)   # la linea verde del terreno es piping de Capas (00F200): va en las forzadas; NO tocar mallas V4 (eran rejillas de la torre)
np.save(pref + '_islas.npy', sem)
json.dump(sorted(int(m) for m in mids), open(pref + '_mids.json', 'w'))
log(f'centros {len(cen):,}  semillas linea verde {len(sem)}  -> {pref}_*.npy')
