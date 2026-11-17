# Inventario de TODAS las piezas con malla del FBX de Capas: caja en el marco local del GLB del visor, color, jerarquia.
# Reutiliza el lector FBX en streaming de analizar_huecos_tuberia_1313.py (solo lectura).
# Marco: FBX real -> Blender (xb = 40-(x-ORIx), yb = 30-(y-ORIy), zb = z-ORIz) -> glTF (xb, zb, -yb).
# Uso: py -I inventario_piezas_1313.py "<Capas area 1313.fbx>" <salida_sin_ext>   -> <salida>.npz + <salida>.json
import sys, os
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'analizar_huecos_tuberia_1313.py'), encoding='utf-8').read()
exec(_src.split('# ---- analisis de huecos')[0])
ORI = np.array([184800.0, 4448600.0, 2250.0])
def hexc(m):
    c = mats.get(m) if m is not None else None
    return '%02X%02X%02X' % tuple(int(round(max(0, min(1, x)) * 255)) for x in c) if c else ''
def cadena(mid):
    out = []
    while mid in modelos: out.append(modelos[mid]['n']); mid = padre.get(mid)
    return out[::-1]
cajas, cols, nv, ids, cad = [], [], [], [], []
for mid, gid in geo_de.items():
    v = arr(geoms[gid]).reshape(-1, 3)
    if len(v) < 3: continue
    d = modelos[mid]; G = M(d['GT'], d['GR'], d['GS']); W4 = mundo(mid) @ G
    w = (v @ W4[:3, :3].T + W4[:3, 3]) * (unit / 100.0) - ORI
    g = np.c_[40 - w[:, 0], w[:, 2], -(30 - w[:, 1])]
    cajas.append(np.r_[g.min(0), g.max(0)]); cols.append(hexc(mat_de.get(mid))); nv.append(len(v)); ids.append(mid); cad.append(cadena(mid))
cajas = np.array(cajas, dtype=np.float32)
np.savez_compressed(sys.argv[2] + '.npz', cajas=cajas, nv=np.array(nv), ids=np.array(ids, dtype=np.int64))
json.dump({'cols': cols, 'cad': cad}, open(sys.argv[2] + '.json', 'w', encoding='utf-8'))
log('piezas', len(ids), 'limites', cajas[:, :3].min(0).round(1), cajas[:, 3:].max(0).round(1))
