# Detecta "elementos sueltos" en la geometria del Hito (volcada por volcar_geometria_hito.py).
# Criterio (medible, sin suposiciones de disciplina):
#   1) Se sueldan vertices a 2 mm y se separan las piezas conexas (componentes) de cada malla.
#   2) Dos piezas estan "en contacto" si tienen puntos de superficie en la misma celda de una rejilla de CEL m
#      (evaluada tambien desplazada media celda). Se muestrea el interior de los triangulos grandes.
#   3) Las piezas en contacto forman grupos. Un grupo esta "apoyado" si toca el terreno del modelo
#      (UNION_MAT_C6B88D) o llega al suelo extenso (z <= SUELO + 0.5 m).
#   4) Grupo NO apoyado = elemento suelto (flota sin tocar nada que llegue al suelo).
# Salida: <carpeta>/sueltos.json (resumen) y <carpeta>/sueltos_mascaras.npz (triangulos sueltos por objeto).
# Uso: python detectar_sueltos_hito.py <carpeta_geo> [CEL=0.25]
import sys, os, json, time
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

carpeta = sys.argv[1]
CEL = float(sys.argv[2]) if len(sys.argv) > 2 else 0.25
SUELO = -47.6
TERRENO = 'UNION_MAT_C6B88D'
BITS = 20
t0 = time.time()
def log(*a): print(f'[sueltos {time.time()-t0:6.1f} s]', *a, flush=True)

# ---------- 1) piezas conexas por malla
ind = json.load(open(os.path.join(carpeta, 'indice.json'), encoding='utf-8'))
objs = []
comp_tris, comp_min, comp_max, comp_obj = [], [], [], []
off = 0; gmin = np.full(3, np.inf); gmax = np.full(3, -np.inf)
for nombre in ind:
    d = np.load(os.path.join(carpeta, nombre + '.npz'))
    v, t = d['v'].astype(np.float64), d['t'].astype(np.int64)
    _, inv = np.unique(np.round(v / 0.002).astype(np.int64), axis=0, return_inverse=True)
    inv = inv.ravel(); nvw = int(inv.max()) + 1
    tw = inv[t]; vw = np.zeros((nvw, 3)); vw[inv] = v
    a = np.concatenate([tw[:, 0], tw[:, 1], tw[:, 2]]); b = np.concatenate([tw[:, 1], tw[:, 2], tw[:, 0]])
    nc, lab = connected_components(coo_matrix((np.ones(a.size, np.int8), (a, b)), shape=(nvw, nvw)), directed=False)
    tc = lab[tw[:, 0]]
    mn = np.full((nc, 3), np.inf); mx = np.full((nc, 3), -np.inf)
    for k in range(3):
        np.minimum.at(mn[:, k], lab, vw[:, k]); np.maximum.at(mx[:, k], lab, vw[:, k])
    comp_tris.append(np.bincount(tc, minlength=nc)); comp_min.append(mn); comp_max.append(mx); comp_obj.append(np.full(nc, len(objs)))
    gmin = np.minimum(gmin, vw.min(0)); gmax = np.maximum(gmax, vw.max(0))
    objs.append({'nombre': nombre, 'vw': vw, 'tw': tw, 'lab': lab, 'tc': tc, 'nc': nc, 'off': off})
    log(f'{nombre}: {t.shape[0]:,} tri, {nc:,} piezas')
    off += nc
ncomp = off
assert ncomp < (1 << BITS)
ctris = np.concatenate(comp_tris); cmin = np.concatenate(comp_min); cmax = np.concatenate(comp_max); cobj = np.concatenate(comp_obj)
D = np.floor((gmax - gmin) / CEL).astype(np.int64) + 3
log(f'piezas totales {ncomp:,}; rejilla {D.tolist()}')

# ---------- 2) codigos (celda, pieza) por bloques, deduplicados al vuelo
def codigos(P, comp, desf):
    c = np.floor((P - gmin) / CEL + desf).astype(np.int64) + 1
    return (((c[:, 0] * D[1] + c[:, 1]) * D[2] + c[:, 2]) << BITS) | comp
acum = {0.0: [], 0.5: []}
npts = 0
for o in objs:
    vw, tw, lab, tc, base = o['vw'], o['tw'], o['lab'], o['tc'], o['off']
    for desf in acum: acum[desf].append(np.unique(codigos(vw, lab + base, desf)))
    npts += vw.shape[0]
    p0, p1, p2 = vw[tw[:, 0]], vw[tw[:, 1]], vw[tw[:, 2]]
    lado = np.maximum(np.maximum(np.linalg.norm(p1-p0, axis=1), np.linalg.norm(p2-p1, axis=1)), np.linalg.norm(p0-p2, axis=1))
    nivel = np.clip(np.ceil(lado / CEL).astype(np.int64), 1, 128)
    for k in np.unique(nivel[nivel > 1]):
        sel = np.nonzero(nivel == k)[0]
        ii, jj = np.meshgrid(np.arange(k+1), np.arange(k+1), indexing='ij'); m = (ii + jj) <= k
        u = (ii[m] / k)[None, :, None]; w_ = (jj[m] / k)[None, :, None]
        paso = max(1, 3_000_000 // u.shape[1])
        for s in range(0, sel.size, paso):
            ss = sel[s:s+paso]
            P = (p0[ss][:, None, :]*(1-u-w_) + p1[ss][:, None, :]*u + p2[ss][:, None, :]*w_).reshape(-1, 3)
            comp = np.repeat(tc[ss] + base, u.shape[1])
            npts += P.shape[0]
            for desf in acum: acum[desf].append(np.unique(codigos(P, comp, desf)))
    log(f'muestreado {o["nombre"]} (puntos acumulados {npts:,})')
filas, cols = [], []
for desf, lst in acum.items():
    cod = np.unique(np.concatenate(lst)); lst.clear()
    cel = cod >> BITS; comp = cod & ((1 << BITS) - 1)
    mismo = cel[1:] == cel[:-1]
    filas.append(comp[:-1][mismo]); cols.append(comp[1:][mismo])
    log(f'desfase {desf}: {cod.size:,} pares celda-pieza, {int(mismo.sum()):,} contactos')
    del cod, cel, comp
fi = np.concatenate(filas); co = np.concatenate(cols)
ngr, grupo = connected_components(coo_matrix((np.ones(fi.size, np.int8), (fi, co)), shape=(ncomp, ncomp)), directed=False)
log(f'grupos en contacto: {ngr:,}')

# ---------- 3) apoyo y resumen
nombres = [o['nombre'] for o in objs]
apoyado = np.zeros(ngr, bool)
apoyado[np.unique(grupo[cobj == nombres.index(TERRENO)])] = True
apoyado[np.unique(grupo[cmin[:, 2] <= SUELO + 0.5])] = True
suelto_comp = ~apoyado[grupo]

# ---------- 3b) holgura bajo cada grupo no apoyado: si su punto mas bajo esta a <= HUECO m de una superficie
#                apoyada que tiene debajo (o del suelo extenso), se considera apoyado (falta la losa/radier en el modelo)
HUECO = 1.0; CXY = 1.0
pk, pz = [], []
for o in objs:
    vw, tw, lab, tc, base = o['vw'], o['tw'], o['lab'], o['tc'], o['off']
    okv = ~suelto_comp[lab + base]; okt = ~suelto_comp[tc + base]
    P = [vw[okv]]
    t2 = tw[okt]
    if t2.size:
        p0, p1, p2 = vw[t2[:, 0]], vw[t2[:, 1]], vw[t2[:, 2]]
        lado = np.maximum(np.maximum(np.linalg.norm(p1-p0, axis=1), np.linalg.norm(p2-p1, axis=1)), np.linalg.norm(p0-p2, axis=1))
        nivel = np.clip(np.ceil(lado / CXY).astype(np.int64), 1, 256)
        for k in np.unique(nivel[nivel > 1]):
            sel = np.nonzero(nivel == k)[0]
            ii, jj = np.meshgrid(np.arange(k+1), np.arange(k+1), indexing='ij'); m = (ii + jj) <= k
            u = (ii[m] / k)[None, :, None]; w_ = (jj[m] / k)[None, :, None]
            paso = max(1, 2_000_000 // u.shape[1])
            for s in range(0, sel.size, paso):
                ss = sel[s:s+paso]
                P.append((p0[ss][:, None, :]*(1-u-w_) + p1[ss][:, None, :]*u + p2[ss][:, None, :]*w_).reshape(-1, 3))
    P = np.concatenate(P)
    cx = np.floor((P[:, 0] - gmin[0]) / CXY).astype(np.int64); cy = np.floor((P[:, 1] - gmin[1]) / CXY).astype(np.int64)
    pk.append(cx * 100000 + cy); pz.append(P[:, 2].astype(np.float32))
pk = np.concatenate(pk); pz = np.concatenate(pz)
o_ = np.argsort(pk, kind='stable'); pk = pk[o_]; pz = pz[o_]
log(f'superficies apoyadas: {pk.size:,} puntos')
gl = np.unique(grupo[suelto_comp])
gmn = np.full((ngr, 3), np.inf); gmx = np.full((ngr, 3), -np.inf)
for k in range(3):
    np.minimum.at(gmn[:, k], grupo, cmin[:, k]); np.maximum.at(gmx[:, k], grupo, cmax[:, k])
rescatados = 0; huecos = {}
for gid in gl:
    zmin = gmn[gid, 2]
    x0, x1 = int(np.floor((gmn[gid, 0] - gmin[0]) / CXY)), int(np.floor((gmx[gid, 0] - gmin[0]) / CXY))
    y0, y1 = int(np.floor((gmn[gid, 1] - gmin[1]) / CXY)), int(np.floor((gmx[gid, 1] - gmin[1]) / CXY))
    soporte = SUELO
    for xx in range(x0, x1 + 1):
        a_ = np.searchsorted(pk, xx * 100000 + y0); b_ = np.searchsorted(pk, xx * 100000 + y1, side='right')
        if b_ > a_:
            zz = pz[a_:b_]; zz = zz[zz <= zmin + 0.05]
            if zz.size: soporte = max(soporte, float(zz.max()))
    huecos[int(gid)] = round(zmin - soporte, 2)
    if zmin - soporte <= HUECO:
        apoyado[gid] = True; rescatados += 1
suelto_comp = ~apoyado[grupo]
log(f'grupos a <= {HUECO} m de una superficie apoyada (se conservan): {rescatados:,}')
orden = np.argsort(grupo, kind='stable'); g_ord = grupo[orden]
cortes = np.flatnonzero(np.diff(g_ord)) + 1
res = []
for blq in np.split(orden, cortes):
    gid = grupo[blq[0]]
    if apoyado[gid]: continue
    mn = cmin[blq].min(0); mx = cmax[blq].max(0); mats = {}
    for oi, nt in zip(cobj[blq], ctris[blq]): mats[nombres[oi]] = mats.get(nombres[oi], 0) + int(nt)
    res.append({'grupo': int(gid), 'piezas': int(blq.size), 'triangulos': int(ctris[blq].sum()),
                'min': [round(float(x), 2) for x in mn], 'max': [round(float(x), 2) for x in mx],
                'tam': [round(float(x), 2) for x in (mx - mn)], 'hueco_bajo_m': huecos.get(int(gid)), 'objetos': mats})
res.sort(key=lambda r: -r['triangulos'])
tot = int(ctris[suelto_comp].sum()); porobj = {}
for r in res:
    for k, v in r['objetos'].items(): porobj[k] = porobj.get(k, 0) + v
resumen = {'criterio': {'soldadura_m': 0.002, 'contacto_celda_m': CEL, 'suelo_z_blender': SUELO, 'terreno': TERRENO,
                        'hueco_max_bajo_pieza_m': HUECO, 'descripcion': 'grupo de piezas que no toca nada apoyado y queda a mas de 1 m sobre la superficie apoyada que tiene debajo'},
           'piezas_totales': int(ncomp), 'grupos': int(ngr), 'grupos_sueltos': len(res),
           'triangulos_sueltos': tot, 'triangulos_totales': int(ctris.sum()), 'por_objeto': porobj, 'grupos_detalle': res[:500]}
json.dump(resumen, open(os.path.join(carpeta, 'sueltos.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
np.savez_compressed(os.path.join(carpeta, 'sueltos_mascaras.npz'),
                    **{o['nombre']: suelto_comp[o['off']:o['off'] + o['nc']][o['tc']] for o in objs})
log(f'SUELTOS: {len(res):,} grupos, {tot:,} triangulos de {int(ctris.sum()):,}')
for k, v in sorted(porobj.items(), key=lambda x: -x[1]): log(f'   {k}: {v:,}')
for r in res[:30]: log('  ', r['triangulos'], r['piezas'], r['tam'], r['min'], 'hueco', r['hueco_bajo_m'], list(r['objetos'])[:3])
# ids de grupo por triangulo (solo sueltos; -1 = conservado) para los renders de control
np.savez_compressed(os.path.join(carpeta, 'sueltos_grupos.npz'),
                    **{o['nombre']: np.where(suelto_comp[o['off']:o['off'] + o['nc']], grupo[o['off']:o['off'] + o['nc']], -1)[o['tc']].astype(np.int32) for o in objs})
