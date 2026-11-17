# Lamina en planta de los conjuntos sueltos (detectar_sueltos_1313.py) + CSV de conjuntos.
# Uso: py -I lamina_sueltos_1313.py <sueltos.json> <visor.glb> <D> <ext_min> <salida_png> <salida_csv>
import sys, json, struct, csv, collections, numpy as np, DracoPy
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
fs, fg, D, X, png, fcsv = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), sys.argv[5], sys.argv[6]
R = json.load(open(fs, encoding='utf-8')); PZ = R['piezas']; sets = [c for c in R['D'][D] if c['ext'] >= X]
sets.sort(key=lambda c: -c['ext'])
g = open(fg, 'rb').read(); jl = struct.unpack_from('<I', g, 12)[0]; J = json.loads(g[20:20 + jl]); B = g[20 + jl + 8:]
fondo = []
for m in J['meshes']:
    if not m.get('name', '').startswith('V4_') or 'C6B88D' in m['name'].upper(): continue
    for pr in m['primitives']:
        bv = J['bufferViews'][pr['extensions']['KHR_draco_mesh_compression']['bufferView']]; o = bv.get('byteOffset', 0)
        p = np.asarray(DracoPy.decode(B[o:o + bv['byteLength']]).points).reshape(-1, 3); fondo.append(p[::7])
F = np.concatenate(fondo)
COL = {'Piping': '#e53935', 'Electrical': '#fb8c00', 'Control Systems': '#8e24aa'}
fig, ax = plt.subplots(figsize=(16.5, 11.7), dpi=110); fig.patch.set_facecolor('#0f172a'); ax.set_facecolor('#111827')
ax.scatter(F[:, 0], F[:, 2], s=0.05, c='#64748b', alpha=0.35, lw=0)
todos = [p for p in PZ]; rect = lambda b: [(b[0], b[2]), (b[3], b[2]), (b[3], b[5]), (b[0], b[5])]
ax.add_collection(PolyCollection([rect(p['caja']) for p in todos], facecolors='none', edgecolors='#334155', lw=0.15))
filas = []; cnt = collections.Counter()
for k, c in enumerate(sets, 1):
    disc = collections.Counter(PZ[i]['cad'][0] for i in c['m']); d0 = disc.most_common(1)[0][0]; cnt[d0] += len(c['m'])
    ax.add_collection(PolyCollection([rect(PZ[i]['caja']) for i in c['m']], facecolors=COL.get(d0, 'r'), edgecolors=COL.get(d0, 'r'), lw=0.6, alpha=0.9))
    b = c['caja']; ax.text(b[3] + 0.3, (b[2] + b[5]) / 2, str(k), color='white', fontsize=6.5, weight='bold')
    nodos = collections.Counter(PZ[i]['cad'][2] if len(PZ[i]['cad']) > 2 else '?' for i in c['m'])
    filas.append([k, d0, len(c['m']), round(c['ext'], 1), round((b[1] + b[4]) / 2, 1), '; '.join(f'{n} ({v})' for n, v in nodos.most_common(6))])
ax.set_aspect('equal'); ax.invert_yaxis(); ax.tick_params(colors='#94a3b8', labelsize=7)
for s in ax.spines.values(): s.set_color('#334155')
ax.set_title(f'Área 1313 – Elementos sueltos candidatos a ocultar (v4)  ·  {len(sets)} conjuntos, {sum(len(c["m"]) for c in sets)} piezas  ·  '
             f'criterio: > {D} m de estructura/equipos y conjunto ≥ {X:g} m', color='white', fontsize=12, loc='left')
for k2, cc in COL.items(): ax.plot([], [], 's', color=cc, label=f'{k2}: {cnt[k2]} piezas')
ax.legend(loc='lower left', facecolor='#1e293b', labelcolor='white', fontsize=9, edgecolor='#334155')
fig.text(0.5, 0.01, 'Vista en planta (x, z del visor) · gris = estructura/equipos · contorno = todas las piezas de piping/eléctrico/control · número = conjunto (ver CSV)', color='#94a3b8', ha='center', fontsize=8)
fig.savefig(png, facecolor=fig.get_facecolor(), bbox_inches='tight')
with open(fcsv, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f, delimiter=';'); w.writerow(['Conjunto', 'Disciplina', 'Piezas', 'Extension_m', 'Altura_media_m', 'Lineas/escalerillas (piezas)']); w.writerows(filas)
print('lamina', png, 'conjuntos', len(sets), dict(cnt))
