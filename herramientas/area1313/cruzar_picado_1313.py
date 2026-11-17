# Cruza los impactos de picar_visor_1313.py con el inventario de piezas (inventario_piezas_1313.py).
# Cada impacto -> pieza de menor volumen cuya caja (+tol) lo contiene. Resumen por elipse y por nodo padre.
# Uso: py -I cruzar_picado_1313.py <pick.json> <piezas_sin_ext> <salida.json> [--tol 0.03]
import sys, json, collections
import numpy as np
a = sys.argv[1:]; tol = float(a[a.index('--tol') + 1]) if '--tol' in a else 0.03
hits = json.load(open(a[0], encoding='utf-8')); z = np.load(a[1] + '.npz'); inf = json.load(open(a[1] + '.json', encoding='utf-8'))
C = z['cajas']; lo, hi = C[:, :3] - tol, C[:, 3:] + tol
vol = np.prod(np.maximum(C[:, 3:] - C[:, :3], 0.02), axis=1)
asig = collections.defaultdict(lambda: collections.Counter()); sin = collections.Counter(); col_glb = collections.defaultdict(collections.Counter)
for h in hits:
    p = np.array(h['p']); m = np.all((lo <= p) & (p <= hi), axis=1); idx = np.nonzero(m)[0]
    col_glb[h['e']][h['c']] += 1
    if len(idx) == 0: sin[h['e']] += 1; continue
    asig[h['e']][int(idx[np.argmin(vol[idx])])] += 1
out = {}
for e in sorted(set(h['e'] for h in hits)):
    tot = sum(asig[e].values()) + sin[e]
    print(f'\n=== Elipse {e}: impactos {tot}, sin pieza {sin[e]}, colores GLB {dict(col_glb[e].most_common(5))}')
    padres = collections.Counter()
    for i, n in asig[e].items(): padres[' / '.join(inf['cad'][i][-4:-1])] += n
    for pp, n in padres.most_common(12): print(f'  {n:4d}  {pp[:150]}')
    out[e] = [{'i': i, 'n': n, 'col': inf['cols'][i], 'cad': inf['cad'][i], 'caja': C[i].round(2).tolist()} for i, n in asig[e].most_common()]
json.dump(out, open(a[2], 'w', encoding='utf-8'), ensure_ascii=False)
