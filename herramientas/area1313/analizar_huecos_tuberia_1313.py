# Cajas de los nodos "Handrail" del FBX del v4 (___area_1313.fbx), para repintar barandas a amarillo (FFFF00) en unir_capas_1313_v2.py.
# Lectura en streaming (mmap + zlib), misma tecnica de fbx_tags_correas.py. Solo lectura; no modifica el FBX.
# Salida: <salida>.json = {"desf": [...], "cajas": [[xmin,ymin,zmin,xmax,ymax,zmax], ...], "nombres": {...}}
#   Coordenadas = mundo del FBX en metros (Z arriba) MENOS --desf. Con --desf 0,0,0 se asume que el FBX ya esta en coordenadas reales.
#   El desfase de ESTE FBX no esta verificado: unir_capas_1313_v2.py imprime los limites de las cajas contra los del v4 para detectarlo.
# Uso: py extraer_barandas_1313.py <___area_1313.fbx> <salida.json> [--desf 0,0,0] [--regex ^Handrail$]
import sys, mmap, struct, zlib, re, json, math, time, collections
import numpy as np
a = sys.argv[1:]
ruta, salida = a[0], a[1]
def opt(k, d):
    return a[a.index(k) + 1] if k in a else d
DESF = np.array([float(x) for x in opt('--desf', '0,0,0').split(',')])
FILTRO = re.compile(opt('--regex', r'^Handrail$'))
t0 = time.time(); log = lambda *x: print(f'[{time.time()-t0:6.1f} s]', *x, flush=True)
f = open(ruta, 'rb'); mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
ver = struct.unpack_from('<I', mm, 23)[0]; W = 8 if ver >= 7500 else 4
HDR = 25 if W == 8 else 13
def cab(o):
    if W == 8: end, n, pl = struct.unpack_from('<QQQ', mm, o)
    else: end, n, pl = struct.unpack_from('<III', mm, o)
    nl = mm[o + 3 * W]; nombre = mm[o + 3 * W + 1:o + 3 * W + 1 + nl].decode('latin1')
    return end, n, pl, nombre, o + 3 * W + 1 + nl
def props(p, n):
    out = []
    for _ in range(n):
        c = chr(mm[p]); p += 1
        if c == 'Y': out.append(struct.unpack_from('<h', mm, p)[0]); p += 2
        elif c == 'C': out.append(mm[p]); p += 1
        elif c == 'I': out.append(struct.unpack_from('<i', mm, p)[0]); p += 4
        elif c == 'F': out.append(struct.unpack_from('<f', mm, p)[0]); p += 4
        elif c == 'D': out.append(struct.unpack_from('<d', mm, p)[0]); p += 8
        elif c == 'L': out.append(struct.unpack_from('<q', mm, p)[0]); p += 8
        elif c in 'SR': l = struct.unpack_from('<I', mm, p)[0]; out.append(mm[p + 4:p + 4 + l]); p += 4 + l
        elif c in 'fdlib':
            ln, enc, cl = struct.unpack_from('<III', mm, p); out.append(('ARR', c, ln, enc, cl, p + 12)); p += 12 + cl
        else: raise ValueError('tipo ' + c)
    return out
def hijos(o):
    end, n, pl, nombre, p = cab(o); q = p + pl
    while q < end - HDR:
        e2 = cab(q)[0]
        if e2 == 0: break
        yield q; q = e2
def arr(x):
    _, c, ln, enc, cl, p = x; d = mm[p:p + cl]
    if enc: d = zlib.decompress(d)
    return np.frombuffer(d, {'d': '<f8', 'f': '<f4', 'i': '<i4', 'l': '<i8', 'b': 'u1'}[c])[:ln]
o = 27; top = {}
while o < len(mm):
    end, n, pl, nombre, p = cab(o)
    if end == 0: break
    top[nombre] = o; o = end
unit = 1.0
for h in hijos(top['GlobalSettings']):
    for h2 in hijos(h):
        _, n, pl, nm, p = cab(h2); pr = props(p, n)
        if pr and pr[0] == b'UnitScaleFactor': unit = float(pr[-1])
log('version', ver, 'UnitScaleFactor', unit)
modelos = {}; geoms = {}; mats = {}; mat_de = {}
for h in hijos(top['Objects']):
    end, n, pl, nm, p = cab(h)
    if nm == 'Model':
        pr = props(p, n); mid = pr[0]; nombre = pr[1].split(b'\x00')[0].decode('utf-8', 'replace')
        d = {'n': nombre, 'T': (0, 0, 0), 'R': (0, 0, 0), 'S': (1, 1, 1), 'GT': (0, 0, 0), 'GR': (0, 0, 0), 'GS': (1, 1, 1), 'PR': (0, 0, 0)}
        for h2 in hijos(h):
            if cab(h2)[3] != 'Properties70': continue
            for h3 in hijos(h2):
                _, n3, _, _, p3 = cab(h3); q = props(p3, n3); k = q[0]
                m = {b'Lcl Translation': 'T', b'Lcl Rotation': 'R', b'Lcl Scaling': 'S', b'GeometricTranslation': 'GT',
                     b'GeometricRotation': 'GR', b'GeometricScaling': 'GS', b'PreRotation': 'PR'}.get(k)
                if m: d[m] = tuple(q[-3:])
        modelos[mid] = d
    elif nm == 'Material':
        pr = props(p, n); mats[pr[0]] = None
        for h2 in hijos(h):
            if cab(h2)[3] != 'Properties70': continue
            for h3 in hijos(h2):
                _, n3, _, _, p3 = cab(h3); q = props(p3, n3)
                if q and q[0] in (b'DiffuseColor', b'Diffuse'): mats[pr[0]] = tuple(q[-3:])
    elif nm == 'Geometry':
        pr = props(p, n)
        for h2 in hijos(h):
            e2, n2, _, nm2, p2 = cab(h2)
            if nm2 == 'Vertices': geoms[pr[0]] = props(p2, n2)[0]; break
padre = {}; geo_de = {}
for h in hijos(top['Connections']):
    _, n, _, _, p = cab(h); q = props(p, n)
    if q[0] != b'OO': continue
    x, y = q[1], q[2]
    if x in modelos: padre[x] = y
    elif x in geoms and y in modelos: geo_de[y] = x
    elif x in mats and y in modelos: mat_de[y] = x
log('modelos', len(modelos), 'con malla', len(geo_de))
def rot(e):
    x, y, z = [math.radians(v) for v in e]
    Rx = np.array([[1, 0, 0], [0, math.cos(x), -math.sin(x)], [0, math.sin(x), math.cos(x)]])
    Ry = np.array([[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]])
    Rz = np.array([[math.cos(z), -math.sin(z), 0], [math.sin(z), math.cos(z), 0], [0, 0, 1]])
    return Rz @ Ry @ Rx
def M(T, R, S, PR=(0, 0, 0)):
    m = np.eye(4); m[:3, :3] = rot(PR) @ rot(R) @ np.diag(S); m[:3, 3] = T; return m
cache = {}
def mundo(mid):
    if mid in cache: return cache[mid]
    d = modelos[mid]; m = M(d['T'], d['R'], d['S'], d['PR'])
    pa = padre.get(mid)
    if pa in modelos: m = mundo(pa) @ m
    cache[mid] = m; return m
sys.setrecursionlimit(100000)
# un nodo Handrail puede ser el Model con malla o un contenedor de piezas: se toma la malla propia y la de sus descendientes
def es_handrail(mid):
    while mid in modelos:
        if FILTRO.search(modelos[mid]['n']): return True
        mid = padre.get(mid)
    return False

# ---- analisis de huecos entre tuberias RECTAS (solo lectura) ----
from scipy.spatial import cKDTree
GMAX = float(opt('--gmax', '3.0'))
FILTRO = re.compile(opt('--regex', r'^Pipe$'))
ORI = np.array([184800.0, 4448600.0, 2250.0])
piezas = []; n_tot = 0; n_rec = 0
for mid, gid in geo_de.items():
    if not es_handrail(mid): continue          # es_handrail() sube por los ancestros buscando FILTRO (aqui ^Pipe$)
    n_tot += 1
    v = arr(geoms[gid]).reshape(-1, 3)
    if len(v) < 8: continue
    d = modelos[mid]; G = M(d['GT'], d['GR'], d['GS']); W4 = mundo(mid) @ G
    w = (v @ W4[:3, :3].T + W4[:3, 3]) * (unit / 100.0) - ORI
    c = w.mean(0); _, _, vt = np.linalg.svd(w - c, full_matrices=False); ax = vt[0]
    t = (w - c) @ ax; r = np.linalg.norm((w - c) - np.outer(t, ax), axis=1)
    rad = float(np.median(r)); L = float(t.max() - t.min())
    if rad < 0.005 or L < 0.02: continue
    if (np.percentile(r, 97) - np.percentile(r, 3)) > 0.08 * rad: continue      # no es cilindro recto
    n_rec += 1
    m_ = mid; col_ = None
    while m_ in modelos and col_ is None:                       # color = material de la pieza (o de su ancestro)
        cm = mats.get(mat_de.get(m_))
        if cm: col_ = '%02X%02X%02X' % tuple(int(round(min(max(x, 0), 1) * 255)) for x in cm[:3])
        m_ = padre.get(m_)
    piezas.append((c + ax * t.min(), c + ax * t.max(), ax, rad, L, mid, col_))
log(f'piezas Pipe: {n_tot}; rectas (cilindro): {n_rec}')
E = []   # extremos: (pos, direccion hacia afuera, radio, indice pieza)
for i, (p0, p1, ax, rad, L, mid, col_) in enumerate(piezas):
    E.append((p0, -ax, rad, i)); E.append((p1, ax, rad, i))
P_ = np.array([e[0] for e in E]); D_ = np.array([e[1] for e in E]); R_ = np.array([e[2] for e in E]); I_ = np.array([e[3] for e in E])
arbol = cKDTree(P_); pares = arbol.query_pairs(GMAX, output_type='ndarray')
cand = []
for a_, b_ in pares:
    if I_[a_] == I_[b_]: continue
    g = P_[b_] - P_[a_]; gl = float(np.linalg.norm(g))
    if gl < 0.001: continue
    u = g / gl
    if D_[a_] @ u < 0.995 or D_[b_] @ (-u) < 0.995: continue                     # ejes alineados (< ~5.7 grados) y enfrentados
    if abs(R_[a_] - R_[b_]) > max(0.003, 0.05 * R_[a_]): continue               # mismo diametro
    cand.append((gl, float(R_[a_]), P_[a_].tolist(), P_[b_].tolist(), int(I_[a_]), int(I_[b_])))
cand.sort()
g = np.array([c[0] for c in cand]) if cand else np.zeros(0)
bins = [0.001, 0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 3.0]
h = np.histogram(g, bins)[0]
log('candidatos de hueco (extremos enfrentados, alineados, mismo diametro):', len(cand))
for lo_, hi_, n_ in zip(bins[:-1], bins[1:], h): log(f'   hueco {lo_:5.3f}-{hi_:5.3f} m: {n_}')
log('radios (m) de los candidatos, percentiles 10/50/90:', np.percentile([c[1] for c in cand], [10, 50, 90]).round(3).tolist() if cand else '-')
json.dump({'origen': ORI.tolist(), 'gmax': GMAX, 'candidatos': cand}, open(salida, 'w'))
# ---- seleccion para rellenar: hueco <= RMAX, un extremo se usa una sola vez (primero los huecos mas cortos) ----
RMAX = float(opt('--rellenar', '0.20'))
EN_I = {}                                    # (pieza, extremo) -> indice de extremo, para marcar usados
usados = set(); seg = []; sin_color = 0; colores = collections.Counter()
ext_de = {}
for k_, (a_, b_) in enumerate(pares): pass
for gl, rad, pa, pb, ia, ib in cand:
    if gl > RMAX: break
    ka = (ia, tuple(np.round(pa, 4))); kb = (ib, tuple(np.round(pb, 4)))
    if ka in usados or kb in usados: continue
    ca, cb = piezas[ia][6], piezas[ib][6]
    if ca != cb:
        sin_color += 1; continue                                # colores distintos: no se rellena (no inventar)
    usados.add(ka); usados.add(kb); seg.append({'p0': pa, 'p1': pb, 'radio': rad, 'color': ca, 'hueco': gl}); colores[ca] += 1
log(f'RELLENO <= {RMAX} m: {len(seg)} tramos (omitidos por color distinto: {sin_color}); largo total {sum(s["hueco"] for s in seg):.1f} m')
log('colores del relleno:', dict(colores))
json.dump({'origen': ORI.tolist(), 'rellenar_max_m': RMAX, 'tramos': seg}, open(salida.replace('.json', '_relleno.json'), 'w'))
log('tramos ->', salida.replace('.json', '_relleno.json'))
# ---- (v3, decision de Eduardo 2026-10-30) ocultar las piezas a ambos lados de huecos > OMIN y <= GMAX ----
# Escribe <salida>_ocultar.json (cilindros p0/p1/radio/color de cada pieza a ocultar) y <salida>_relleno_v3.json
# (el relleno <= RMAX sin los tramos que tocan una pieza oculta, para que no queden rellenos flotando).
if opt('--ocultar_min', None) is not None:
    OMIN = float(opt('--ocultar_min', '0.20'))
    ocultas = set()
    for gl, rad, pa, pb, ia, ib in cand:
        if OMIN < gl <= GMAX: ocultas.update((ia, ib))
    lst = [{'p0': piezas[i][0].tolist(), 'p1': piezas[i][1].tolist(), 'radio': float(piezas[i][3]), 'largo': float(piezas[i][4]),
            'color': piezas[i][6]} for i in sorted(ocultas)]
    json.dump({'origen': ORI.tolist(), 'hueco_min': OMIN, 'hueco_max': GMAX, 'piezas': lst}, open(salida.replace('.json', '_ocultar.json'), 'w'))
    usados = set(); seg3 = []
    for gl, rad, pa, pb, ia, ib in cand:
        if gl > RMAX: break
        ka = (ia, tuple(np.round(pa, 4))); kb = (ib, tuple(np.round(pb, 4)))
        if ka in usados or kb in usados: continue
        if piezas[ia][6] != piezas[ib][6]: continue
        usados.add(ka); usados.add(kb)
        if ia in ocultas or ib in ocultas: continue
        seg3.append({'p0': pa, 'p1': pb, 'radio': rad, 'color': piezas[ia][6], 'hueco': gl})
    json.dump({'origen': ORI.tolist(), 'rellenar_max_m': RMAX, 'tramos': seg3}, open(salida.replace('.json', '_relleno_v3.json'), 'w'))
    log(f'OCULTAR huecos {OMIN}-{GMAX} m: {len(ocultas)} piezas, largo {sum(p["largo"] for p in lst):.1f} m | relleno v3: {len(seg3)} tramos (de {len(seg)})')
    log('colores ocultos:', dict(collections.Counter(p['color'] for p in lst)))
log('listo ->', salida)
