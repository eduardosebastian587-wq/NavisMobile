# Busca puntos de vista libres para cada equipo animado (Área 1313): posiciones de cámara a distancia R del objetivo,
# con holgura >= HOLG m (campo de distancias, incluye volumen barrido) y línea de vista libre (sin geometría en el
# segmento, salvo los últimos m metros junto al objetivo). Imprime los mejores por equipo (ejes Three: x, y arriba, z).
# Uso: py buscar_vistas_1313.py <dist.npy> <equipos.json> [HOLG=4]
import sys, json, numpy as np
from scipy import ndimage
D = np.load(sys.argv[1]).astype(np.float32); M = json.load(open(sys.argv[1][:-4] + '.json'))
EQ = json.load(open(sys.argv[2], encoding='utf-8')); HOLG = float(sys.argv[3]) if len(sys.argv) > 3 else 4.0
lo = np.array(M['origen']); C = M['celda_m']
TX, TY, TZ = EQ['TX'], EQ['TY'], EQ['TZ']
v4t = lambda v: np.array([TX - v[0], v[1] + TZ, -v[2] - TY])          # v4 -> Three
tb = lambda p: np.stack([p[..., 0], -p[..., 2], p[..., 1]], -1)         # Three -> Blender
hol = lambda p: ndimage.map_coordinates(D, ((tb(np.atleast_2d(p)) - lo) / C).T, order=1, mode='nearest')
def los(c, o, libre_fin):
    n = int(np.linalg.norm(o - c) / 0.4) + 2; s = np.linspace(0, 1, n)[:, None]; P = c + (o - c) * s
    lejos = np.linalg.norm(P - o, axis=1) > libre_fin
    return bool((hol(P[lejos]) > 0.45).all())
P = {p['id']: p for p in EQ['partes']}
# objetivos (coordenadas v4 del visor; las del pórtico en su posición de trabajo sobre los molinos: +32 m en X del v4)
OBJ = {
  'molinos (ambos)':        (v4t([-8.39, -0.406, 4.21]), 8, (25, 60), (12, 45)),
  'ML-1401':                (v4t([-8.39, -0.406, -8.29]), 6, (14, 35), (10, 40)),
  'pescantes 1404/1405':    (v4t([-36.5, 20.0, 15.3]), 10, (18, 45), (8, 40)),
  'portico en reposo':      (v4t([-38.0, 19.0, 4.0]), 14, (35, 80), (12, 40)),
  'carro sobre molinos':    (v4t([-8.0, 20.0, 17.5]), 12, (22, 50), (5, 35)),
}
if len(sys.argv) > 4:                     # objetivos a medida (JSON): {"nombre": [[x,y,z Three], libre_fin, [R0,R1], [el0,el1]], ...}
    OBJ = {k: (np.array(v[0], float), v[1], tuple(v[2]), tuple(v[3])) for k, v in json.load(open(sys.argv[4], encoding='utf-8-sig')).items()}
rng = np.random.default_rng(0)
for nom, (o, lf, (r0, r1), (e0, e1)) in OBJ.items():
    az = rng.uniform(0, 360, 6000); el = rng.uniform(e0, e1, 6000); r = rng.uniform(r0, r1, 6000)
    d = np.stack([np.cos(np.radians(el)) * np.sin(np.radians(az)), np.sin(np.radians(el)), np.cos(np.radians(el)) * np.cos(np.radians(az))], 1)
    c = o + d * r[:, None]; h = hol(c); ok = h >= HOLG
    cand = [(r[i], az[i], el[i], h[i], c[i]) for i in np.flatnonzero(ok) if los(c[i], o, lf)]
    cand.sort(key=lambda x: x[0])
    sect = {}
    for x in cand:                                      # el más cercano por sector de 45° de azimut
        k = int(x[1] // 45)
        if k not in sect: sect[k] = x
    print(f'== {nom}: objetivo Three {np.round(o, 1).tolist()}; {len(cand)} vistas libres de {len(c)}')
    for k in sorted(sect):
        r_, a_, e_, h_, c_ = sect[k]
        print(f'   az {a_:5.0f}°  el {e_:4.0f}°  R {r_:5.1f} m  holgura {h_:4.1f} m  cam {np.round(c_, 1).tolist()}')
