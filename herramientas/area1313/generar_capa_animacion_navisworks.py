#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generar_capa_animacion_navisworks.py
=====================================
Genera, a partir del FBX parcial exportado desde Navisworks y de animaciones.json (las mismas particiones del visor v4):

  1. ANIM_Area1313_capa.fbx          Capa de piezas SEPARADAS (tambor del molino, pórtico, carro, ganchos, plumas...)
                                     georreferenciada igual que el original, con las propiedades (SmartPlant 3D) copiadas.
  2. animator_claves.json            Claves por conjunto de animación, ya convertidas a los ejes de Navisworks.
  3. Conjuntos_Navisworks.xml        Conjuntos de búsqueda importables (Sets > Import Searches).
  4. Guia_Animator_Navisworks.html   Guía paso a paso con las tablas de claves.
  5. reporte_verificacion.txt        Conciliación de triángulos y alineación.

Uso:  python generar_capa_animacion_navisworks.py <fbx_parcial> <animaciones.json> <carpeta_salida>
Requiere solo numpy.  El FBX de entrada es el exportado con «Ocultar no seleccionados» (molinos, pórtico, pescantes).
"""
import sys, os, re, json, copy, math, uuid, datetime
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fbxio

# ------------------------------------------------------------------------------------------------
# 1) Marco de coordenadas: visor (X este, Y arriba, Z sur) ↔ FBX local (X este, Y norte, Z arriba)
#    visor = (fx, fz, -fy) + OFFSET_VISOR   |   absoluto Navisworks = FBX local + GeometricTranslation
#    OFFSET_VISOR se verificó contra el .visor.glb: caja del molino x −18,373…1,587; y −5,236…4,424; z −13,12…−3,46.
# ------------------------------------------------------------------------------------------------
OFFSET_VISOR = np.array([5461.12, -2254.806, -6249.71])
def a_visor(v):  return np.stack([v[:, 0], v[:, 2], -v[:, 1]], 1) + OFFSET_VISOR
def visor_a_fbx(p):   # (x,y,z visor) → (fx,fy,fz)
    p = np.asarray(p, float) - OFFSET_VISOR
    return np.array([p[0], -p[2], p[1]])

def sin_acentos(s): 
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', str(s).lower()) if unicodedata.category(c) != 'Mn')
def coincide_tag(patron, tag):
    m = re.match(r'^/(.+)/([a-z]*)$', str(patron), re.I)
    return bool(re.search(m.group(1), tag, re.I)) if m else sin_acentos(patron) == sin_acentos(tag)

def nombre_nodo(n):   return n[1][1][1].split(b'\x00')[0].decode('utf8', 'replace')
def id_nodo(n):       return n[1][0][1]
def es_modelo(n):     return n[0] == 'Model'

# ------------------------------------------------------------------------------------------------
# 2) Lectura del FBX parcial
# ------------------------------------------------------------------------------------------------
def cargar_fbx(ruta):
    ver, top, pie = fbxio.leer(ruta)
    obj = next(t for t in top if t[0] == 'Objects'); con = next(t for t in top if t[0] == 'Connections')
    por_id = {id_nodo(n): n for n in obj[2]}
    padre, hijos_de, geo_de, mat_de, attr_de = {}, {}, {}, {}, {}
    for c in con[2]:
        tipo, a, b = c[1][0][1], c[1][1][1], c[1][2][1]
        if tipo != b'OO': continue
        na = por_id.get(a)
        if na is None: continue
        if na[0] == 'Model': padre[a] = b; hijos_de.setdefault(b, []).append(a)
        elif na[0] == 'Geometry': geo_de[b] = a
        elif na[0] == 'Material': mat_de.setdefault(b, []).append(a)
        elif na[0] == 'NodeAttribute': attr_de[b] = a
    piezas = {}
    for mid, gid in geo_de.items():
        g = por_id[gid]; d = {x[0]: x for x in g[2]}
        if 'Vertices' not in d or len(d['Vertices'][1][0][1]) == 0: continue
        v = d['Vertices'][1][0][1].reshape(-1, 3); idx = d['PolygonVertexIndex'][1][0][1]
        nor = None
        if 'LayerElementNormal' in d:
            nor = next(x for x in d['LayerElementNormal'][2] if x[0] == 'Normals')[1][0][1].reshape(-1, 3)
        cadena, x = [], mid
        while x in por_id: cadena.append(por_id[x]); x = padre.get(x)
        tag = next((nombre_nodo(c) for c in cadena if nombre_nodo(c).startswith('1313-')), None)
        piezas[mid] = dict(modelo=por_id[mid], cadena=cadena, tag=tag, v=v, idx=idx, nor=nor,
                           mats=[por_id[m] for m in mat_de.get(mid, [])], nombre_modelo=nombre_nodo(por_id[mid]))
    return dict(ver=ver, top=top, pie=pie, por_id=por_id, padre=padre, attr_de=attr_de, piezas=piezas)

def triangulos(p):
    idx = p['idx'].copy(); idx[2::3] = -idx[2::3] - 1
    return idx.reshape(-1, 3)

# ------------------------------------------------------------------------------------------------
# 3) Particiones (réplica de particionarRango() del visor): gana la primera regla; lo no reclamado queda fijo
# ------------------------------------------------------------------------------------------------
def cajas_a_arrays(cajas):
    out = []
    for b in cajas:
        lo = [(-np.inf if b[i] is None else b[i]) for i in range(3)]; hi = [(np.inf if b[i + 3] is None else b[i + 3]) for i in range(3)]
        out.append((np.array(lo), np.array(hi)))
    return out

def particionar(C, reglas):
    asig = np.full(len(C), len(reglas), np.int16)
    libre = np.ones(len(C), bool)
    for r, rg in enumerate(reglas):
        m = np.zeros(len(C), bool)
        for lo, hi in cajas_a_arrays(rg['cajas']): m |= np.all((C >= lo) & (C <= hi), 1)
        m &= libre; asig[m] = r; libre &= ~m
    return asig

# ------------------------------------------------------------------------------------------------
# 4) Construcción de las piezas de la capa
# ------------------------------------------------------------------------------------------------
def construir_partes(F, anim):
    reglas_def = anim['particiones']
    partes = []        # dicts: nombre, tag, rol, regla, tri(mask), pieza
    resumen = []
    for mid, p in F['piezas'].items():
        tag = p['tag']
        if not tag: continue
        rs = [r for r in reglas_def if r.get('cajas') and coincide_tag(r['tag'], tag)]
        if not rs: continue
        V = a_visor(p['v']); T = triangulos(p); C = V[T].mean(1)
        asig = particionar(C, rs)
        usados = np.zeros(len(T), bool)
        def añadir(nombre, rol, regla, mask):
            if mask.sum() == 0: return
            partes.append(dict(nombre=nombre, tag=tag, rol=rol, regla=regla, mask=mask, mid=mid, tri=int(mask.sum())))
        fijo = (asig == len(rs)).copy()
        for k, r in enumerate(rs):
            mk = asig == k
            if all(x is None for b in r['cajas'] for x in b):
                añadir(f"ANIM_{tag}_fijo", 'fijo', r['id'], mk)          # regla «todo el elemento»: lo que no gira ni se mueve
            elif r.get('oculto') :
                # Los ganchos del 2.º par se eliminaron del visor; aquí se CONSERVAN como piezas propias (no se pierde información)
                añadir(f"ANIM_{tag}_{r['id']}", 'pieza', r['id'], mk)
            elif r.get('estirable'):
                e = r['estirable']; cy = C[:, 1]
                añadir(f"ANIM_{tag}_{r['id']}_cuerpo",  'gancho_cuerpo', r['id'], mk & (cy < e['y1']))
                añadir(f"ANIM_{tag}_{r['id']}_cable",   'gancho_cable',  r['id'], mk & (cy >= e['y1']) & (cy < e['y2']))
                añadir(f"ANIM_{tag}_{r['id']}_anclaje", 'gancho_anclaje', r['id'], mk & (cy >= e['y2']))
            else:
                añadir(f"ANIM_{tag}_{r['id']}", 'pieza', r['id'], mk)
        # 'molino_14xx' (regla con caja total) queda como pieza fija 'cuerpo': se llama igual que la regla
        if fijo.sum(): añadir(f"ANIM_{tag}_fijo", 'fijo', None, fijo)
        resumen.append((tag, len(T), sum(x['tri'] for x in partes if x['tag'] == tag)))
    return partes, resumen

# ------------------------------------------------------------------------------------------------
# 5) Escritura del FBX de la capa
# ------------------------------------------------------------------------------------------------
def S(t, s): return ('S', s if isinstance(s, bytes) else s.encode('utf8'))
def nodo(nombre, props=(), hijos=()): return [nombre, list(props), list(hijos)]

_next = [2_000_000_000_000]
def nuevo_id(): _next[0] += 1; return _next[0]

def reemplazar_prop(modelo, clave, valor):
    P = next(x for x in modelo[2] if x[0] == 'Properties70')
    for q in P[2]:
        if q[1][0][1].decode('utf8', 'replace') == clave and len(q[1]) >= 5:
            q[1][-1] = ('S', valor.encode('utf8')); return True
    return False

def clonar_modelo(orig, nombre, mid):
    m = copy.deepcopy(orig)
    m[1][0] = ('L', mid)
    tipo = orig[1][2][1]
    m[1][1] = ('S', nombre.encode('utf8') + b'\x00\x01Model')
    reemplazar_prop(m, 'Elemento - Nombre', nombre)
    return m

def escribir_capa(F, partes, ruta_salida, anim):
    top_o = F['top']; por_id = F['por_id']
    obj_o = next(t for t in top_o if t[0] == 'Objects')
    nuevo_obj, nuevas_con = [], []
    n_model = n_geo = n_mat = n_attr = 0
    # raíz de la capa
    raiz_id = nuevo_id()
    base_modelo = next(n for n in obj_o[2] if es_modelo(n))
    raiz = clonar_modelo(base_modelo, 'ANIM_AREA_1313', raiz_id)
    raiz[1][2] = ('S', b'Null')
    # raíz sin propiedades heredadas
    P = next(x for x in raiz[2] if x[0] == 'Properties70'); P[2] = [q for q in P[2] if not q[1][0][1].startswith(b'Elemento') and not q[1][0][1].startswith(b'GeometricTranslation') and not q[1][0][1].startswith(b'SmartPlant')]
    for q in P[2]:
        pass
    nuevo_obj.append(raiz); n_model += 1
    nuevas_con.append(('C', [('S', b'OO'), ('L', raiz_id), ('L', 0)]))
    por_tag = {}
    for pt in partes: por_tag.setdefault(pt['tag'], []).append(pt)
    ids_partes = {}
    for tag, lista in por_tag.items():
        p0 = F['piezas'][lista[0]['mid']]
        cadena = p0['cadena']                      # [Geometry, Aspects, TAG, ...]
        nodo_tag = next(c for c in cadena if nombre_nodo(c) == tag)
        nodo_asp = next((c for c in cadena if nombre_nodo(c) == 'Aspects'), None)
        tid = nuevo_id(); mt = clonar_modelo(nodo_tag, f'ANIM_{tag}', tid); nuevo_obj.append(mt); n_model += 1
        nuevas_con.append(('C', [('S', b'OO'), ('L', tid), ('L', raiz_id)]))
        at = F['attr_de'].get(id_nodo(nodo_tag))
        if at:
            na = copy.deepcopy(por_id[at]); naid = nuevo_id(); na[1][0] = ('L', naid); nuevo_obj.append(na); n_attr += 1
            nuevas_con.append(('C', [('S', b'OO'), ('L', naid), ('L', tid)]))
        padre_mesh = tid
        if nodo_asp is not None:
            aid = nuevo_id(); ma = clonar_modelo(nodo_asp, f'ANIM_{tag}_Aspects', aid); nuevo_obj.append(ma); n_model += 1
            nuevas_con.append(('C', [('S', b'OO'), ('L', aid), ('L', tid)]))
            at2 = F['attr_de'].get(id_nodo(nodo_asp))
            if at2:
                na = copy.deepcopy(por_id[at2]); naid = nuevo_id(); na[1][0] = ('L', naid); nuevo_obj.append(na); n_attr += 1
                nuevas_con.append(('C', [('S', b'OO'), ('L', naid), ('L', aid)]))
            padre_mesh = aid
        for pt in lista:
            p = F['piezas'][pt['mid']]; T = triangulos(p)[pt['mask']]
            usados, inv = np.unique(T.ravel(), return_inverse=True)
            v = p['v'][usados]; T2 = inv.reshape(-1, 3).astype(np.int32)
            pidx = T2.copy(); pidx[:, 2] = -pidx[:, 2] - 1
            filas = (np.nonzero(pt['mask'])[0][:, None] * 3 + np.arange(3)).ravel()
            gid, mid2, matid = nuevo_id(), nuevo_id(), nuevo_id()
            hijos = [nodo('Vertices', [('d', v.ravel())]), nodo('PolygonVertexIndex', [('i', pidx.ravel())]), nodo('GeometryVersion', [('I', 124)])]
            if p['nor'] is not None:
                hijos.append(nodo('LayerElementNormal', [('I', 0)], [nodo('Version', [('I', 102)]), nodo('Name', [S('S', '')]),
                    nodo('MappingInformationType', [S('S', 'ByPolygonVertex')]), nodo('ReferenceInformationType', [S('S', 'Direct')]),
                    nodo('Normals', [('d', p['nor'][filas].ravel())]), nodo('NormalsW', [('d', np.ones(len(filas)))])]))
            hijos.append(nodo('LayerElementMaterial', [('I', 0)], [nodo('Version', [('I', 101)]), nodo('Name', [S('S', '')]),
                nodo('MappingInformationType', [S('S', 'ByPolygon')]), nodo('ReferenceInformationType', [S('S', 'IndexToDirect')]),
                nodo('Materials', [('i', np.zeros(len(T2), np.int32))])]))
            le = [nodo('LayerElement', [], [nodo('Type', [S('S', 'LayerElementNormal')]), nodo('TypedIndex', [('I', 0)])])] if p['nor'] is not None else []
            le.append(nodo('LayerElement', [], [nodo('Type', [S('S', 'LayerElementMaterial')]), nodo('TypedIndex', [('I', 0)])]))
            hijos.append(nodo('Layer', [('I', 0)], [nodo('Version', [('I', 100)])] + le))
            nuevo_obj.append(nodo('Geometry', [('L', gid), ('S', pt['nombre'].encode() + b'\x00\x01Geometry'), ('S', b'Mesh')], hijos)); n_geo += 1
            mm = clonar_modelo(p['modelo'], pt['nombre'], mid2); nuevo_obj.append(mm); n_model += 1
            reemplazar_prop(mm, 'Elemento - Tipo', 'Geometry')
            mt = copy.deepcopy(p['mats'][0]); mt[1][0] = ('L', matid); nuevo_obj.append(mt); n_mat += 1
            nuevas_con += [('C', [('S', b'OO'), ('L', mid2), ('L', padre_mesh)]), ('C', [('S', b'OO'), ('L', gid), ('L', mid2)]),
                           ('C', [('S', b'OO'), ('L', matid), ('L', mid2)])]
            ids_partes[pt['nombre']] = mid2
    # Definitions con contadores nuevos
    defs = copy.deepcopy(next(t for t in top_o if t[0] == 'Definitions'))
    cuentas = {'Model': n_model, 'NodeAttribute': n_attr, 'Geometry': n_geo, 'Material': n_mat, 'GlobalSettings': 1}
    for h in defs[2]:
        if h[0] == 'ObjectType':
            nm = h[1][0][1].decode()
            for c in h[2]:
                if c[0] == 'Count' and nm in cuentas: c[1][0] = ('I', cuentas[nm])
    for h in defs[2]:
        if h[0] == 'Count': h[1][0] = ('I', sum(cuentas.values()))
    defs[2] = [h for h in defs[2] if not (h[0] == 'ObjectType' and h[1][0][1].decode() not in cuentas) or True]
    # El resto de ObjectType (si los hubiera) se conserva con su conteo original; en este archivo solo existen los de arriba.
    objects = ['Objects', [], nuevo_obj]
    conexiones = ['Connections', [], [nodo(c[0], c[1]) for c in nuevas_con]]
    top = []
    for t in top_o:
        if t[0] == 'Definitions': top.append(defs)
        elif t[0] == 'Objects': top.append(objects)
        elif t[0] == 'Connections': top.append(conexiones)
        else: top.append(t)
    # Marca de origen en el encabezado
    for t in top:
        if t[0] == 'FBXHeaderExtension':
            for h in t[2]:
                if h[0] == 'SceneInfo':
                    for pp in h[2]:
                        if pp[0] == 'Properties70':
                            for q in pp[2]:
                                if q[1][0][1] in (b'DocumentUrl', b'SrcDocumentUrl'): q[1][-1] = ('S', os.path.abspath(ruta_salida).encode('utf8'))
    fbxio.escribir(ruta_salida, F['ver'], top, F['pie'])
    return dict(modelos=n_model, geometrias=n_geo, materiales=n_mat, ids=ids_partes)

# ------------------------------------------------------------------------------------------------
# 6) Claves de Animator (relativas, ejes de Navisworks: X este, Y norte, Z elevación)
# ------------------------------------------------------------------------------------------------
def suave(k): return k * k * k * (k * (k * 6 - 15) + 10)       # igual que el visor
def interp(claves, t, modo='suave'):
    ts = [c[0] for c in claves]; vs = [np.array(c[1], float) for c in claves]
    if t <= ts[0]: return vs[0]
    if t >= ts[-1]: return vs[-1]
    for i in range(len(ts) - 1):
        if ts[i] <= t <= ts[i + 1]:
            k = (t - ts[i]) / (ts[i + 1] - ts[i]); k = suave(k) if modo == 'suave' else k
            return vs[i] + (vs[i + 1] - vs[i]) * k

def claves_anim(pista, modo):
    """Claves principales (las del JSON) + 3 claves de suavizado por tramo con movimiento (25/50/75 %, curva del visor)."""
    ks = pista['claves']; out = []
    for i, (t, v) in enumerate(ks):
        out.append((float(t), np.array(v, float), 'principal'))
        if i < len(ks) - 1 and modo == 'suave' and not np.allclose(np.array(v, float), np.array(ks[i + 1][1], float)):
            t1 = ks[i + 1][0]
            for f in (0.25, 0.5, 0.75):
                tt = t + (t1 - t) * f; out.append((float(tt), interp(ks, tt, 'suave'), 'suavizado'))
    return out

def a_nav_delta(d):  return [float(d[0]), float(-d[2]), float(d[1])]     # visor (x,y,z) → Navisworks (E,N,U)
def abs_nav(pv, gt):                                                      # punto visor → coordenadas absolutas
    f = visor_a_fbx(pv); return [float(f[0] + gt[0]), float(f[1] + gt[1]), float(f[2] + gt[2])]

# ------------------------------------------------------------------------------------------------
# 7) Definición de conjuntos de animación (qué piezas lleva cada uno) y escenas
# ------------------------------------------------------------------------------------------------
def definir_conjuntos(anim, partes, F, gt):
    reglas = {r['id']: r for r in anim['particiones']}
    hijos = {}
    for r in anim['particiones']:
        if r.get('padre'): hijos.setdefault(r['padre'], []).append(r['id'])
    def descendientes(i):
        out = [i]
        for h in hijos.get(i, []): out += descendientes(h)
        return out
    nombres_originales = {nombre_nodo(p['modelo']) for p in F['piezas'].values()}
    todos_nombres = {nombre_nodo(n) for n in F['por_id'].values() if es_modelo(n)}
    def piezas_de_regla(rid):
        r = reglas[rid]; res = []
        if r.get('cajas'):
            res += [p['nombre'] for p in partes if p['regla'] == rid]
        elif not r.get('vacio'):
            # elemento completo (TAG o /regex/) que cuelga de la parte → ítem ORIGINAL de Navisworks (p. ej. 1313-CN-1404-M1)
            res += sorted(n for n in todos_nombres if coincide_tag(r['tag'], n))
        return res
    def miembros(rid):
        res = []
        for d in descendientes(rid): res += piezas_de_regla(d)
        return list(dict.fromkeys(res))
    return reglas, miembros

def construir_escenas(anim, partes, F, gt):
    ciclo = next(a for a in anim['animaciones'] if a['id'] == 'ciclo-completo')
    giro = next(a for a in anim['animaciones'] if a['id'] == 'molinos-giro')
    reglas, miembros = definir_conjuntos(anim, partes, F, gt)
    pistas = {p['objetivo']: p for p in ciclo['pistas'] if p['objetivo'] != 'camara'}
    pivote = lambda rid: reglas[rid].get('pivote')
    escenas = []
    def conjunto(nombre, regla_id, pista, tipo, piezas, notas='', pivote_abs=None, escala=None, modo='suave', claves=None):
        ks = claves if claves is not None else claves_anim(pista, modo)
        filas = []
        for t, v, kind in ks:
            f = dict(t=round(t, 3), tipo=kind, pos=None, rot=None, esc=None)
            if tipo == 'traslacion': f['pos'] = [round(x, 4) for x in a_nav_delta(v)]
            elif tipo == 'rotacion':
                # rotación Δ en grados sobre el eje visor (X,Y,Z) → Navisworks (X, -Z, Y→Z)
                f['rot'] = [round(float(v[0]), 4), round(float(-v[2]), 4), round(float(v[1]), 4)]
            elif tipo == 'escala_cable':
                e = escala; s = 1.0 + (-float(v[1])) / (e['y2'] - e['y1'])
                f['esc'] = [1.0, 1.0, round(s, 5)]
            filas.append(f)
        return dict(nombre=nombre, regla=regla_id, tipo=tipo, piezas=piezas, claves=filas, pivote=pivote_abs, notas=notas)
    def pv_abs(rid, y=None):
        p = list(pivote(rid)); 
        if y is not None: p[1] = y
        return abs_nav(p, gt)
    # --- Molinos
    for n in ('1401', '1402'):
        rid = f'molino_{n}_giro'
        ks = [(float(t), np.array(v, float), 'principal') for t, v in next(p for p in giro['pistas'] if p['objetivo'] == rid)['claves']]
        c = conjunto(f'ML-{n} · giro del tambor', rid, None, 'rotacion', miembros(rid), pivote_abs=pv_abs(rid), claves=ks,
                     notas='Una vuelta cada 6 s; activar «Bucle» en la escena. Gira solo el tambor: cabezales y apoyos quedan fijos.')
        escenas.append(dict(nombre=f'ML-{n} — giro del tambor', equipo=f'1313-ML-{n}', duracion=6.0, bucle=True, conjuntos=[c],
                            detalle='Escena en bucle: 5 claves a 90° (ver tabla). La escena completa del ciclo de 60 s usa 41 claves; en Animator basta con bucle.'))
    # --- Pórtico CN-1406
    P, C1, C2 = 'portico', 'carro_1', 'carro_2'
    cs = [
        conjunto('CN-1406 · Pórtico (traslación sobre rieles)', P, pistas[P], 'traslacion', miembros(P)),
        conjunto('CN-1406 · Carro 1 (traslación transversal)', C1, pistas[C1], 'traslacion', miembros(C1)),
        conjunto('CN-1406 · Carro 2 / ganchos del 2.º par', C2, pistas[C2], 'traslacion', miembros(C2),
                 notas='Piezas conservadas del modelo original. El visor las oculta; aquí pueden animarse o dejarse fijas.'),
    ]
    for gid_ in ('gancho_1p', 'gancho_1a'):
        e = reglas[gid_]['estirable']
        pz = [p['nombre'] for p in partes if p['regla'] == gid_]
        cuerpo = [n for n in pz if n.endswith('_cuerpo')]; cable = [n for n in pz if n.endswith('_cable')]
        cs.append(conjunto(f'CN-1406 · {gid_} bajada (cuerpo del gancho)', gid_, pistas[gid_], 'traslacion', cuerpo))
        cs.append(conjunto(f'CN-1406 · {gid_} cable (estiramiento)', gid_, pistas[gid_], 'escala_cable', cable,
                           pivote_abs=pv_abs(gid_, e['y2']), escala=e, modo='suave',
                           notas='Escala solo en Z (elevación) con pivote en el anclaje superior del cable: reproduce el cable que se alarga.'))
    escenas.append(dict(nombre='CN-1406 — Pórtico, carro y ganchos', equipo='1313-CN-1406', duracion=56.0, bucle=False, conjuntos=cs,
                        detalle='Tiempos idénticos al ciclo completo del visor (pórtico 2→14 s y 44→56 s; carro 14→22 s y 44→52 s; ganchos 22→40 s).'))
    # --- Pescantes
    for n in ('1404', '1405'):
        R, H = f'pluma_{n}', f'gancho_{n}'
        e = reglas[H]['estirable']; pz = [p['nombre'] for p in partes if p['regla'] == H]
        cs = [conjunto(f'CN-{n} · Pluma (giro sobre eje vertical)', R, pistas[R], 'rotacion', miembros(R), pivote_abs=pv_abs(R), modo='suave',
                       notas='Giro alrededor del eje vertical (Z) en el pivote indicado; el gancho y los ítems M1… siguen a la pluma.'),
              conjunto(f'CN-{n} · Gancho bajada (cuerpo)', H, pistas[H], 'traslacion', [x for x in pz if x.endswith('_cuerpo')]),
              conjunto(f'CN-{n} · Gancho cable (estiramiento)', H, pistas[H], 'escala_cable', [x for x in pz if x.endswith('_cable')],
                       pivote_abs=pv_abs(H, e['y2']), escala=e, notas='Escala solo en Z con pivote en el anclaje superior. Tramo de cable muy corto (0,24 m): el factor es grande (≈ 42×) y es lo esperado.')]
        escenas.append(dict(nombre=f'CN-{n} — Pescante', equipo=f'1313-CN-{n}', duracion=44.0, bucle=False, conjuntos=cs,
                            detalle='Pluma gira ±70° y el gancho baja 10 m, igual que el ciclo completo del visor.'))
    return escenas

# ------------------------------------------------------------------------------------------------
# 8) Conjuntos de búsqueda de Navisworks (XML importable) y guía HTML
# ------------------------------------------------------------------------------------------------
def xml_escape(s): return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
def xml_conjuntos(escenas, ocultar):
    def cond(valor): return f'<condition test="equals" flags="10"><category><name internal="LcOaNode">Elemento</name></category><property><name internal="LcOaNodeName">Nombre</name></property><value><data type="wstring">{xml_escape(valor)}</data></value></condition>'
    def ss(nombre, valores):
        return (f'<selectionset name="{xml_escape(nombre)}" guid="{uuid.uuid4()}"><findspec mode="all" disjoint="1"><conditions>' +
                ''.join(cond(v) for v in valores) + '</conditions><locator>/</locator></findspec></selectionset>')
    items = [ss('ANIM · OCULTAR originales', ocultar)]
    for e in escenas:
        for c in e['conjuntos']:
            if c['piezas']: items.append(ss('ANIM · ' + c['nombre'], c['piezas']))
    return ('<?xml version="1.0" encoding="UTF-8" ?>\n<exchange xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xsi:noNamespaceSchemaLocation="http://download.autodesk.com/us/navisworks/schemas/nw-exchange-12.0.xsd" units="m" filename="" filepath="">'
            '<selectionsets><viewfolder name="ANIMACION AREA 1313" guid="' + str(uuid.uuid4()) + '">' + ''.join(items) + '</viewfolder></selectionsets></exchange>')

def fmt(x): 
    s = f'{x:.4f}'.rstrip('0').rstrip('.'); return s if s not in ('', '-0') else '0'
def html_guia(escenas, gt, ocultar, partes, resumen, capa_nombre, medidas):
    fecha = datetime.date.today().strftime('%d-%m-%Y')
    css = """:root{--bg:#0b1220;--panel:#111a2e;--borde:#1f2d4a;--azul:#3b82f6;--cian:#22d3ee;--txt:#e5edf8;--suave:#94a3b8;--ok:#34d399;--aviso:#fbbf24}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:14px/1.55 'Segoe UI',system-ui,sans-serif}
.pag{max-width:1180px;margin:0 auto;padding:22px 26px 10px}
.cab{border-top:1px solid var(--borde);padding-top:14px;display:flex;justify-content:space-between;align-items:center;gap:20px}
h1{margin:0;font-size:24px;letter-spacing:.3px}.insignia{background:#fff;color:#0b1220;font-weight:800;padding:6px 14px;border-radius:4px;letter-spacing:1px;font-size:13px;white-space:nowrap}
.sub{color:var(--suave);font-size:12px;margin:6px 0 18px}h2{margin:30px 0 8px;font-size:18px;color:var(--cian);border-bottom:1px solid var(--borde);padding-bottom:6px}
h3{margin:22px 0 6px;font-size:15px;color:#fff}.caja{background:var(--panel);border:1px solid var(--borde);border-radius:8px;padding:14px 16px;margin:10px 0}
.aviso{border-left:3px solid var(--aviso)}.ok{border-left:3px solid var(--ok)}ol,ul{margin:6px 0 6px 20px;padding:0}li{margin:3px 0}
table{border-collapse:collapse;width:100%;margin:8px 0;font-size:12.5px}th,td{border:1px solid var(--borde);padding:5px 8px;text-align:right;font-variant-numeric:tabular-nums}
th{background:#16223b;color:var(--cian);text-align:center}td.l,th.l{text-align:left}tr.suav td{color:var(--suave)}
code{background:#16223b;padding:1px 6px;border-radius:4px;font-family:Consolas,monospace;font-size:12px}
.tag{display:inline-block;background:#16223b;border:1px solid var(--borde);border-radius:999px;padding:1px 10px;margin:2px 3px 2px 0;font-size:12px;font-family:Consolas,monospace}
label.sw{font-size:12px;color:var(--suave);cursor:pointer;margin-left:10px}.pie{margin-top:36px}.pie .barra{height:4px;background:linear-gradient(90deg,#22d3ee,#ec4899);border-radius:2px}
.pie p{text-align:center;color:var(--suave);font-size:11.5px;margin:10px 0 24px}details summary{cursor:pointer;color:var(--cian)}"""
    h = [f'<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>Guía Animator — Área 1313</title><style>{css}</style></head><body><div class="pag">']
    h.append('<div class="cab"><h1>Animación del Área 1313 en Navisworks Manage 2027</h1><span class="insignia">FLUOR | SALFA</span></div>')
    h.append(f'<div class="sub">Nueva Centinela · Precomisionamiento Mecánico · Guía de montaje en Animator (escenas por equipo) · {fecha}</div>')
    h.append(f'''<div class="caja ok"><b>Qué se hizo.</b> El FBX original trae cada equipo como <b>una sola geometría</b> (p. ej. el pórtico: 552.780 triángulos entre rieles, patas, carro y ganchos), y Navisworks solo mueve objetos completos.
Por eso se generó la capa <code>{capa_nombre}</code>: las mismas piezas, <b>cortadas con las particiones del visor</b>, con la misma georreferencia (<code>{gt[0]:.3f} ; {gt[1]:.3f} ; {gt[2]:.0f}</code>) y con las propiedades SmartPlant 3D copiadas.
Los ítems originales no se borran: se ocultan. Si se quita la capa y se muestran de nuevo, el modelo queda como estaba.</div>''')
    h.append('<h2>1 · Preparación (una sola vez)</h2><ol>')
    h.append(f'<li>Abre en Navisworks el <code>.nwd</code>/<code>.nwf</code> de trabajo. <b>Guarda una copia</b> antes de anexar.</li>')
    h.append(f'<li><b>Inicio › Anexar</b> → <code>{capa_nombre}</code>. Debe quedar encima del original, sin desplazamiento. Si pide unidades: <b>metros</b>. (Comprobación: la pieza <code>ANIM_1313-ML-1401_fijo</code> debe coincidir con el molino; centro esperado E {medidas["ML1401"][0]:.2f} · N {medidas["ML1401"][1]:.2f} · Z {medidas["ML1401"][2]:.2f}.)</li>')
    h.append('<li><b>Conjuntos › Importar búsquedas</b> → <code>Conjuntos_Navisworks.xml</code> (crea la carpeta «ANIMACION AREA 1313» con un conjunto por animación). Si el importador lo rechaza, crea los conjuntos con <i>Buscar elementos</i> (Elemento › Nombre = el nombre de la pieza, condiciones con «O»).</li>')
    h.append('<li>Con la capa anexada ya visible, <b>verifica visualmente</b> que no hay desfase (parpadeo entre copia y original) y recién entonces <b>oculta los originales</b>: selecciónalos (conjunto «ANIM · OCULTAR originales») → clic derecho › <b>Ocultar</b> (Ctrl+H). Guarda un punto de vista con los atributos Ocultar/Requerido.</li></ol>')
    h.append('<div class="caja aviso"><b>Originales a ocultar:</b> ' + ' '.join(f'<span class="tag">{o}</span>' for o in ocultar) + '<br>Los ítems <code>1313-CN-1404-M1</code>, <code>1313-CN-1405-M1…M4</code> (y <code>1313-CN-1406-M1…M12</code>, si existen en el original) <b>no</b> se ocultan: son objetos independientes y se animan directamente.</div>')
    h.append('<h2>2 · Construir las escenas en Animator</h2><ol><li><b>Animación › Animator</b>. Crea una escena por cada bloque de la sección 3 (botón <b>Agregar escena</b>) y nómbrala igual.</li>'
             '<li>Dentro de la escena: <b>Agregar conjunto de animación › Desde conjunto de selección</b> y elige el conjunto importado.</li>'
             '<li>Para cada fila de la tabla: mueve el deslizador de tiempo, activa <b>Capturar fotograma clave</b> y <b>edita el fotograma</b> (clic derecho › Editar) escribiendo los valores de la tabla (posición/rotación/escala y pivote).</li>'
             '<li><b>Las traslaciones/rotaciones son acumulativas entre conjuntos</b> (así lo documenta Navisworks): una pieza que está en el conjunto del pórtico y en el del carro recibe ambos movimientos. Por eso las piezas aparecen repetidas en varios conjuntos: es intencional.</li>'
             '<li>Escena de molino: marca <b>Bucle</b>. Las demás: reproducir una vez.</li></ol>')
    h.append('<div class="caja aviso"><b>Verifica en la primera prueba (no se pudo comprobar sin Navisworks):</b><ul>'
             '<li>Sentido de giro: los valores usan la regla de la mano derecha sobre los ejes de Navisworks. Si un molino o pluma gira al revés, cambia el signo del ángulo.</li>'
             '<li>Que el cuadro «Editar fotograma clave» acepte el <b>pivote</b> escrito. Si no, mueve el pivote con la herramienta de rotación/escala antes de capturar.</li>'
             '<li>Que Animator acepte 90° por fotograma sin tomar el camino corto (la tabla del giro usa tramos de 90° justamente para evitarlo).</li>'
             '<li>Animator interpola en línea recta entre fotogramas. El visor usa una curva suave (arranque y frenado graduales): las filas <i>suavizado</i> reproducen esa curva con 3 fotogramas extra por tramo. Son opcionales.</li></ul></div>')
    h.append('<h2>3 · Escenas y tablas de fotogramas</h2><p class="sub">Valores <b>relativos a la posición inicial</b> (como los guarda Animator). Ejes de Navisworks: X = este · Y = norte · Z = elevación. Unidades: m y grados. Pivotes: coordenadas absolutas.</p>')
    h.append('<label class="sw"><input type="checkbox" id="ver_suav" checked onchange="document.querySelectorAll(\'tr.suav\').forEach(r=>r.style.display=this.checked?\'\':\'none\')"> mostrar fotogramas de suavizado</label>')
    for e in escenas:
        h.append(f'<h3>Escena · {e["nombre"]} <span class="tag">{e["duracion"]:.0f} s{" · bucle" if e["bucle"] else ""}</span></h3><div class="sub">{e["detalle"]}</div>')
        for c in e['conjuntos']:
            h.append(f'<div class="caja"><b>{c["nombre"]}</b> — {"traslación" if c["tipo"]=="traslacion" else "rotación" if c["tipo"]=="rotacion" else "escala"}<br>')
            h.append('<span class="sub">Piezas del conjunto:</span> ' + (' '.join(f'<span class="tag">{p}</span>' for p in c['piezas']) or '<i>ninguna en esta capa</i>') + '<br>')
            if c['pivote']: h.append(f'<span class="sub">Pivote (E ; N ; Z):</span> <code>{c["pivote"][0]:.3f} ; {c["pivote"][1]:.3f} ; {c["pivote"][2]:.3f}</code><br>')
            if c['notas']: h.append(f'<span class="sub">{c["notas"]}</span>')
            if c['tipo'] == 'traslacion': cab = '<th>Tiempo (s)</th><th>ΔX (m)</th><th>ΔY (m)</th><th>ΔZ (m)</th><th class="l">Tipo</th>'
            elif c['tipo'] == 'rotacion': cab = '<th>Tiempo (s)</th><th>Rot X (°)</th><th>Rot Y (°)</th><th>Rot Z (°)</th><th class="l">Tipo</th>'
            else: cab = '<th>Tiempo (s)</th><th>Esc X</th><th>Esc Y</th><th>Esc Z</th><th class="l">Tipo</th>'
            h.append(f'<table><tr>{cab}</tr>')
            for f in c['claves']:
                v = f['pos'] or f['rot'] or f['esc']
                h.append(f'<tr class="{"suav" if f["tipo"]=="suavizado" else ""}"><td>{fmt(f["t"])}</td><td>{fmt(v[0])}</td><td>{fmt(v[1])}</td><td>{fmt(v[2])}</td><td class="l">{f["tipo"]}</td></tr>')
            h.append('</table></div>')
    h.append('<h2>4 · Qué contiene la capa</h2><table><tr><th class="l">Pieza</th><th>Triángulos</th><th class="l">Función</th></tr>')
    rol = {'fijo': 'Resto fijo (rieles, estructura, apoyos) — reemplaza a lo no móvil del original', 'pieza': 'Pieza móvil', 'gancho_cuerpo': 'Gancho (rígido)', 'gancho_cable': 'Tramo de cable que se estira', 'gancho_anclaje': 'Cable fijo al carro/pluma'}
    for pt in partes: h.append(f'<tr><td class="l">{pt["nombre"]}</td><td>{pt["tri"]:,}</td><td class="l">{rol.get(pt["rol"],"")}</td></tr>'.replace(',', '.'))
    h.append('</table><details><summary>Conciliación de triángulos (capa vs. original)</summary><table><tr><th class="l">Ítem original</th><th>Triángulos original</th><th>Triángulos en la capa</th></tr>')
    for tag, a, b in resumen: h.append(f'<tr><td class="l">{tag}</td><td>{a:,}</td><td>{b:,}</td></tr>'.replace(',', '.'))
    h.append('</table></details>')
    h.append('<div class="pie"><div class="barra"></div><p>Informe generado por Eduardo Regla • Especialista en Puesta en Marcha Mecánico • Fluor-Salfa JV • Nueva Centinela</p></div></div></body></html>')
    return '\n'.join(h)

# ------------------------------------------------------------------------------------------------
def main():
    if len(sys.argv) < 4: print(__doc__); sys.exit(1)
    ruta_fbx, ruta_json, carpeta = sys.argv[1:4]
    os.makedirs(carpeta, exist_ok=True)
    anim = json.load(open(ruta_json, encoding='utf-8'))
    F = cargar_fbx(ruta_fbx)
    pm = next(iter(F['piezas'].values()))
    gt = [q[1][4:7] for q in [next(q for q in next(x for x in pm['modelo'][2] if x[0] == 'Properties70')[2] if q[1][0][1] == b'GeometricTranslation')]][0]
    gt = [float(g[1]) if isinstance(g, tuple) else float(g) for g in gt]
    partes, resumen = construir_partes(F, anim)
    capa = 'ANIM_Area1313_capa.fbx'
    info = escribir_capa(F, partes, os.path.join(carpeta, capa), anim)
    escenas = construir_escenas(anim, partes, F, gt)
    ocultar = sorted({p['tag'] for p in partes})
    # centro absoluto del molino 1401 (control de alineación)
    p = next(p for p in F['piezas'].values() if p['tag'] == '1313-ML-1401')
    c = (p['v'].min(0) + p['v'].max(0)) / 2 + np.array(gt)
    medidas = {'ML1401': c.tolist()}
    open(os.path.join(carpeta, 'Conjuntos_Navisworks.xml'), 'w', encoding='utf-8').write(xml_conjuntos(escenas, ocultar))
    json.dump([{k: v for k, v in e.items()} for e in escenas], open(os.path.join(carpeta, 'animator_claves.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(os.path.join(carpeta, 'Guia_Animator_Navisworks.html'), 'w', encoding='utf-8').write(html_guia(escenas, gt, ocultar, partes, resumen, capa, medidas))
    with open(os.path.join(carpeta, 'reporte_verificacion.txt'), 'w', encoding='utf-8') as f:
        f.write('GeometricTranslation = %s\nCentro absoluto ML-1401 = %s\n' % (gt, c.round(3).tolist()))
        for tag, a, b in resumen: f.write(f'{tag}: original {a} triángulos · capa {b} {"OK" if a == b else "DIFERENCIA"}\n')
        f.write(json.dumps({k: v for k, v in info.items() if k != 'ids'}) + '\n')
    print('Capa:', capa, info['modelos'], 'modelos', info['geometrias'], 'geometrías')
    for tag, a, b in resumen: print(tag, a, b, 'OK' if a == b else 'DIFERENCIA')
if __name__ == '__main__': main()
