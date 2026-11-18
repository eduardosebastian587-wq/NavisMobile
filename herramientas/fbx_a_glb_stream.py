"""FBX binario (Navisworks) -> GLB para NavisMobile, leyendo en streaming (poca RAM).

El importador de Blender carga todo el FBX en memoria y con 6 GB / 250 mil mallas se cae.
Este script lee el archivo en dos pasadas sin construir el árbol completo:
  1. Modelos (nombres, transformaciones, propiedades de los TAG), materiales y conexiones;
     las geometrías solo se registran (posición en el archivo).
  2. Geometrías, una a una: se transforman a coordenadas de mundo en doble precisión,
     se recentran y se agrupan por TAG (equipos, líneas) o por color (lo que no tiene TAG).
Las piezas sin TAG que caen fuera de la zona del área (calculada con las que sí tienen TAG)
se descartan. Resultado: GLB (+Y arriba, metros) con un nodo por TAG y uno por color,
y un JSON con la ruta y las propiedades de cada TAG.

Uso (con el Python de Blender, que trae numpy):
  python fbx_a_glb_stream.py entrada.fbx salida.glb salida_tags.json [--margen 15] [--sin-filtro]
"""
import json, math, os, pickle, re, struct, sys, time, zlib
import numpy as np

T0 = time.time()
def log(*a):
    print(f"[{time.time() - T0:8.1f} s]", *a, flush=True)

_op = {"--margen", "--celda", "--div", "--min"}
args = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith("--") and sys.argv[i - 1] not in _op]
FBX, GLB, JSON_OUT = args[0], args[1], args[2]
MARGEN = float(sys.argv[sys.argv.index("--margen") + 1]) if "--margen" in sys.argv else 15.0
FILTRAR = "--sin-filtro" not in sys.argv
CACHE = GLB + ".pasada1.pkl"
TAG_RE = re.compile(rb"(?<![\w-])(\d{4}-[A-Z]{1,5}-[A-Z0-9][\w.]*)")

# ------------------------------------------------------------------ lectura binaria
ARR = {b"f": ("<f4", 4), b"d": ("<f8", 8), b"l": ("<i8", 8), b"i": ("<i4", 4), b"b": ("<i1", 1)}

class Lector:
    def __init__(self, ruta):
        self.f = open(ruta, "rb", buffering=4 * 1024 * 1024)
        cab = self.f.read(27)
        if not cab.startswith(b"Kaydara FBX Binary"):
            sys.exit("No es un FBX binario")
        self.version = struct.unpack("<I", cab[23:27])[0]
        self.v64 = self.version >= 7500

    def cabecera(self):
        f = self.f
        if self.v64:
            fin, nprops, _ = struct.unpack("<QQQ", f.read(24))
        else:
            fin, nprops, _ = struct.unpack("<III", f.read(12))
        n = f.read(1)[0]
        return fin, nprops, f.read(n)

    def props(self, n, arrays=True):
        f, out = self.f, []
        for _ in range(n):
            t = f.read(1)
            if t == b"Y": out.append(struct.unpack("<h", f.read(2))[0])
            elif t == b"C": out.append(f.read(1)[0] != 0)
            elif t == b"I": out.append(struct.unpack("<i", f.read(4))[0])
            elif t == b"F": out.append(struct.unpack("<f", f.read(4))[0])
            elif t == b"D": out.append(struct.unpack("<d", f.read(8))[0])
            elif t == b"L": out.append(struct.unpack("<q", f.read(8))[0])
            elif t in (b"S", b"R"):
                k = struct.unpack("<I", f.read(4))[0]; out.append(f.read(k))
            elif t in ARR:
                cnt, enc, clen = struct.unpack("<III", f.read(12))
                if not arrays:
                    f.seek(clen, 1); out.append(None); continue
                d = f.read(clen)
                if enc: d = zlib.decompress(d)
                out.append(np.frombuffer(d, dtype=ARR[t][0], count=cnt))
            else:
                raise ValueError(f"Tipo de propiedad desconocido {t!r} en {f.tell()}")
        return out

    def hijos(self, fin):
        """Itera (inicio, fin, nprops, nombre) de los hijos hasta 'fin'; deja el cursor tras las props."""
        f = self.f
        while f.tell() < fin:
            ini = f.tell()
            hfin, nprops, nombre = self.cabecera()
            if hfin == 0:
                return
            yield ini, hfin, nprops, nombre
            f.seek(hfin)

def p70(L, fin):
    """Properties70 -> dict nombre -> (tipo, flags, valores)."""
    d = {}
    for _, hfin, np_, nom in L.hijos(fin):
        if nom == b"P":
            p = L.props(np_, arrays=False)
            d[p[0]] = (p[1], p[3], p[4:])
    return d

# ------------------------------------------------------------------ pasada 1
TRANSF = [b"Lcl Translation", b"Lcl Rotation", b"Lcl Scaling", b"GeometricTranslation", b"GeometricRotation",
          b"GeometricScaling", b"PreRotation", b"PostRotation", b"RotationPivot", b"ScalingPivot",
          b"RotationOffset", b"ScalingOffset", b"RotationOrder"]

def pasada1():
    L = Lector(FBX)
    nombres, tipos, transf, props_tag = {}, {}, {}, {}
    geoms, mats, padre, geo_mod, mat_mod = {}, {}, {}, {}, {}
    ajustes = {}
    vistos = {}
    f = L.f
    while True:
        fin, nprops, nombre = L.cabecera()
        if fin == 0:
            break
        L.props(nprops, arrays=False)
        if nombre == b"GlobalSettings":
            for _, hf, np_, n2 in L.hijos(fin):
                if n2 == b"Properties70":
                    for k, (t, fl, v) in p70(L, hf).items():
                        ajustes[k.decode()] = v[0] if v else None
        elif nombre == b"Objects":
            n = 0
            for ini, hf, np_, n2 in L.hijos(fin):
                n += 1
                if n % 200000 == 0:
                    log(f"  objetos leídos: {n:,} ({f.tell() / 1e9:.2f} GB)")
                if n2 == b"Model":
                    p = L.props(np_, arrays=False)
                    mid, nom = p[0], p[1].split(b"\x00\x01")[0]
                    nombres[mid] = nom; tipos[mid] = p[2]
                    for _, hf2, np2, n3 in L.hijos(hf):
                        if n3 == b"Properties70":
                            pp = p70(L, hf2)
                            t = {k: tuple(pp[k][2]) for k in TRANSF if k in pp}
                            for k in t: vistos[k] = vistos.get(k, 0) + 1
                            if t: transf[mid] = t
                            if TAG_RE.search(nom):
                                u = {}
                                for k, (ty, fl, v) in pp.items():
                                    if b"U" in (fl or b"") and v and k not in TRANSF:
                                        val = v[0].decode("utf-8", "replace") if isinstance(v[0], bytes) else v[0]
                                        if val not in ("", None):
                                            u[k.decode("utf-8", "replace")] = val
                                if u: props_tag[mid] = u
                elif n2 == b"Geometry":
                    p = L.props(np_, arrays=False)
                    if p[2] == b"Mesh":
                        geoms[p[0]] = ini
                elif n2 == b"Material":
                    p = L.props(np_, arrays=False)
                    col, opa = (0.8, 0.8, 0.8), 1.0
                    for _, hf2, np2, n3 in L.hijos(hf):
                        if n3 == b"Properties70":
                            pp = p70(L, hf2)
                            if b"DiffuseColor" in pp: col = tuple(pp[b"DiffuseColor"][2][:3])
                            if b"Opacity" in pp: opa = float(pp[b"Opacity"][2][0])
                            elif b"TransparencyFactor" in pp: opa = 1 - float(pp[b"TransparencyFactor"][2][0])
                    mats[p[0]] = (col, opa)
            log(f"Objects: {n:,} registros; modelos {len(nombres):,}, mallas {len(geoms):,}, materiales {len(mats):,}")
        elif nombre == b"Connections":
            for _, hf, np_, n2 in L.hijos(fin):
                if n2 != b"C":
                    continue
                p = L.props(np_, arrays=False)
                if p[0] != b"OO":
                    continue
                h, pa = p[1], p[2]
                if h in nombres and (pa in nombres or pa == 0):
                    padre[h] = pa
                elif h in geoms and pa in nombres:
                    geo_mod.setdefault(h, []).append(pa)
                elif h in mats and pa in nombres:
                    mat_mod.setdefault(pa, h)
            log(f"Conexiones: {len(padre):,} jerarquía, {len(geo_mod):,} geometrías usadas")
        f.seek(fin)
    log("Propiedades de transformación vistas:", {k.decode(): v for k, v in vistos.items()})
    return dict(nombres=nombres, tipos=tipos, transf=transf, props_tag=props_tag, geoms=geoms, mats=mats,
                padre=padre, geo_mod=geo_mod, mat_mod=mat_mod, ajustes=ajustes)

if os.path.exists(CACHE) and os.path.getmtime(CACHE) > os.path.getmtime(FBX):
    log("Pasada 1 desde caché"); D = pickle.load(open(CACHE, "rb"))
else:
    log(f"Pasada 1: {FBX} ({os.path.getsize(FBX) / 1e9:.2f} GB)")
    D = pasada1()
    pickle.dump(D, open(CACHE, "wb"), protocol=5)
nombres, padre, transf = D["nombres"], D["padre"], D["transf"]

# ------------------------------------------------------------------ transformaciones
def rot(v, orden=0):
    rx, ry, rz = (math.radians(a) for a in v)
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    X = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]]); Y = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Z = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    seq = {0: Z @ Y @ X, 1: Y @ Z @ X, 2: Z @ X @ Y, 3: X @ Z @ Y, 4: Y @ X @ Z, 5: X @ Y @ Z}[int(orden)]
    M = np.eye(4); M[:3, :3] = seq; return M
def tras(v): M = np.eye(4); M[:3, 3] = v; return M
def esc(v): M = np.eye(4); M[0, 0], M[1, 1], M[2, 2] = v; return M
def local(mid):
    t = transf.get(mid)
    if not t: return None
    g = lambda k, d: t.get(k, d)
    o = g(b"RotationOrder", (0,))[0]
    rp, sp = tras(g(b"RotationPivot", (0, 0, 0))), tras(g(b"ScalingPivot", (0, 0, 0)))
    M = (tras(g(b"Lcl Translation", (0, 0, 0))) @ tras(g(b"RotationOffset", (0, 0, 0))) @ rp
         @ rot(g(b"PreRotation", (0, 0, 0))) @ rot(g(b"Lcl Rotation", (0, 0, 0)), o)
         @ np.linalg.inv(rot(g(b"PostRotation", (0, 0, 0)))) @ np.linalg.inv(rp)
         @ tras(g(b"ScalingOffset", (0, 0, 0))) @ sp @ esc(g(b"Lcl Scaling", (1, 1, 1))) @ np.linalg.inv(sp))
    return M
def geometrica(mid):
    t = transf.get(mid) or {}
    if not any(k in t for k in (b"GeometricTranslation", b"GeometricRotation", b"GeometricScaling")): return None
    return (tras(t.get(b"GeometricTranslation", (0, 0, 0))) @ rot(t.get(b"GeometricRotation", (0, 0, 0)))
            @ esc(t.get(b"GeometricScaling", (1, 1, 1))))
_mundo = {}
def mundo(mid):
    cadena = []
    m = mid
    while m and m not in _mundo:
        cadena.append(m); m = padre.get(m, 0)
    M = _mundo.get(m) if m else None
    for x in reversed(cadena):
        l = local(x)
        M = l if M is None else (M if l is None else M @ l)
        _mundo[x] = M
    return _mundo.get(mid)

def tag_y_ruta(mid):
    ruta, tag, tag_mid, m = [], None, None, mid
    while m:
        n = nombres.get(m, b"")
        if tag is None:
            r = TAG_RE.search(n)
            if r: tag, tag_mid = r.group(1).decode("utf-8", "replace"), m
        if n and n not in (b"Geometry", b"Aspects"): ruta.append(n.decode("utf-8", "replace"))
        m = padre.get(m, 0)
    return tag, tag_mid, " / ".join(reversed(ruta[:8]))

eje_z = int(D["ajustes"].get("UpAxis", 2) or 2) == 2
escala = float(D["ajustes"].get("UnitScaleFactor", 100) or 100) / 100.0     # FBX: cm por unidad
log(f"Ejes: {'Z' if eje_z else 'Y'} arriba; escala a metros {escala}")

# ------------------------------------------------------------------ pasada 2
L = Lector(FBX)
def leer_malla(ini):
    f = L.f; f.seek(ini)
    fin, nprops, _ = L.cabecera(); L.props(nprops, arrays=False)
    V = I = N = NI = None; mapa = ref = b""
    for _, hf, np_, n in L.hijos(fin):
        if n == b"Vertices": V = L.props(np_)[0]
        elif n == b"PolygonVertexIndex": I = L.props(np_)[0]
        elif n == b"LayerElementNormal" and N is None:
            L.props(np_, arrays=False)
            for _, hf2, np2, n2 in L.hijos(hf):
                if n2 == b"Normals": N = L.props(np2)[0]
                elif n2 == b"NormalsIndex": NI = L.props(np2)[0]
                elif n2 == b"MappingInformationType": mapa = L.props(np2)[0]
                elif n2 == b"ReferenceInformationType": ref = L.props(np2)[0]
    return V, I, N, NI, mapa, ref

def triangular(I):
    neg = I < 0
    pv = np.where(neg, -I - 1, I).astype(np.int64)
    fins = np.flatnonzero(neg); inis = np.concatenate(([0], fins[:-1] + 1)); k = fins - inis + 1
    ok = k >= 3; inis, k = inis[ok], k[ok]
    nt = k - 2
    if nt.sum() == 0: return pv, np.zeros((0, 3), np.int64)
    pol = np.repeat(np.arange(len(inis)), nt)
    j = np.arange(nt.sum()) - np.repeat(np.cumsum(nt) - nt, nt)
    a = inis[pol]
    return pv, np.stack([a, a + j + 1, a + j + 2], 1)

def color_de(mid):
    m = D["mat_mod"].get(mid)
    col, opa = D["mats"].get(m, ((0.8, 0.8, 0.8), 1.0))
    r, g, b = (int(round(max(0, min(1, c)) * 255)) for c in col)
    return f"{r:02X}{g:02X}{b:02X}" + ("" if opa > 0.98 else f"_A{int(opa * 100):02d}")

# ------------------------------------------------------------------ simplificación por pieza
def opcion(nombre, defecto):
    return float(sys.argv[sys.argv.index(nombre) + 1]) if nombre in sys.argv else defecto
CELDA_MAX = opcion("--celda", 0.05)       # tamaño máximo de celda de agrupamiento (m)
DIV = opcion("--div", 6.0)                # celda = grosor de la pieza / DIV
MIN_DIAG = opcion("--min", 0.02)          # piezas más pequeñas que esto se descartan (m)

def simplificar(pos, nor, tri, celda):
    """Agrupamiento de vértices: une los que caen en la misma celda y tienen normal parecida."""
    mn = pos.min(0)
    q = np.floor((pos - mn) / celda).astype(np.int64)
    if q.max() >= (1 << 18):
        return pos, nor, tri
    qn = np.clip(np.round(nor * 2).astype(np.int64) + 2, 0, 4)
    clave = ((q[:, 0] << 36) | (q[:, 1] << 18) | q[:, 2]) * 125 + qn[:, 0] * 25 + qn[:, 1] * 5 + qn[:, 2]
    u, inv = np.unique(clave, return_inverse=True)
    if len(u) == len(pos):
        return pos, nor, tri
    cnt = np.bincount(inv, minlength=len(u)).astype(np.float64)[:, None]
    p2 = np.stack([np.bincount(inv, pos[:, k], len(u)) for k in range(3)], 1) / cnt
    n2 = np.stack([np.bincount(inv, nor[:, k], len(u)) for k in range(3)], 1)
    ln = np.linalg.norm(n2, axis=1, keepdims=True)
    n2 = np.where(ln > 1e-9, n2 / np.maximum(ln, 1e-12), [0.0, 1.0, 0.0])
    t2 = inv[tri]
    ok = (t2[:, 0] != t2[:, 1]) & (t2[:, 1] != t2[:, 2]) & (t2[:, 0] != t2[:, 2])
    usados = np.zeros(len(u), bool); usados[t2[ok].reshape(-1)] = True
    remap = np.cumsum(usados) - 1
    return p2[usados].astype(np.float32), n2[usados].astype(np.float32), remap[t2[ok]]

AREA4 = re.compile(r"\d{4}")
def grupo_sin_tag(mid):
    """Nombre de grupo para piezas sin TAG: disciplina (nodo bajo el número de área) o tipo en la capa Structure."""
    cad, m = [], mid
    while m:
        cad.append(nombres.get(m, b"").decode("utf-8", "replace")); m = padre.get(m, 0)
    cad.reverse()
    if "Structure" in cad[:3]:
        hoja = next((x for x in reversed(cad) if x not in ("Geometry", "Aspects", "")), "")
        return "Muros (capa Structure)" if hoja.startswith("WallPart") else "Volúmenes de reserva (capa Structure)"
    for i in range(len(cad) - 1):
        if AREA4.fullmatch(cad[i]) and not AREA4.fullmatch(cad[i + 1]):
            return f"{cad[i + 1]} sin TAG"
    return "Otros sin TAG"

# orden: primero las mallas con TAG (definen la zona), luego el resto; dentro, por posición en el archivo
trabajos = []
for gid, mids in D["geo_mod"].items():
    if gid not in D["geoms"]: continue
    for mid in mids:
        tag, tag_mid, ruta = tag_y_ruta(mid)
        trabajos.append((tag is None, D["geoms"][gid], gid, mid, tag, tag_mid, ruta))
trabajos.sort(key=lambda x: (x[0], x[1]))
log(f"Pasada 2: {len(trabajos):,} mallas ({sum(1 for t in trabajos if not t[0]):,} con TAG); "
    f"celda máx {CELDA_MAX} m, grosor/{DIV}, mínimo {MIN_DIAG} m")

desfase = None
por_color = {}               # color -> lista de (pos, nor, tri local, fid)
rasgos, rasgo_de = [], {}    # elementos seleccionables (TAG, o estructura por color)
zona = None; centros_tag = []
descartadas = pequenas = tri_orig = tri_total = 0
def rasgo(clave, datos):
    if clave not in rasgo_de:
        rasgo_de[clave] = len(rasgos)
        rasgos.append({**datos, "tri": 0, "min": [1e18] * 3, "max": [-1e18] * 3})
    return rasgo_de[clave]

for n, (sin_tag, ini, gid, mid, tag, tag_mid, ruta) in enumerate(trabajos):
    if n and n % 20000 == 0:
        log(f"  {n:,}/{len(trabajos):,} mallas; triángulos {tri_orig:,} -> {tri_total:,}; "
            f"fuera de zona {descartadas:,}; pequeñas {pequenas:,}")
    if sin_tag and zona is None and FILTRAR and centros_tag:
        # zona = celdas (planta, x-z) ocupadas por piezas con TAG, ampliadas con un margen: sirve para
        # áreas repartidas en varios sectores alejados entre sí
        CEL = max(10.0, MARGEN * 2)
        C = np.floor(np.array(centros_tag)[:, [0, 2]] / CEL).astype(np.int64)
        r = int(math.ceil((MARGEN + 25) / CEL))
        base = {(int(a), int(b)) for a, b in np.unique(C, axis=0)}
        zona = {(a + i, b + j) for a, b in base for i in range(-r, r + 1) for j in range(-r, r + 1)}
        log(f"Zona del área: {len(base):,} celdas de {CEL:.0f} m con TAG; {len(zona):,} con margen")
    V, I, N, NI, mapa, ref = leer_malla(ini)
    if V is None or I is None or len(I) < 3: continue
    V = V.reshape(-1, 3)
    M = mundo(mid); G = geometrica(mid)
    if G is not None: M = G if M is None else M @ G
    P = (V @ M[:3, :3].T + M[:3, 3]) if M is not None else V.astype(np.float64)
    P = P * escala
    if desfase is None:
        desfase = np.round(P.mean(0) / 10) * 10
        log(f"Desfase restado (m): {desfase}")
    P = P - desfase
    if eje_z: P = P[:, [0, 2, 1]] * np.array([1, 1, -1])
    pmin, pmax = P.min(0), P.max(0); c = (pmin + pmax) / 2; dim = pmax - pmin
    if sin_tag and zona is not None and (int(math.floor(c[0] / CEL)), int(math.floor(c[2] / CEL))) not in zona:
        descartadas += 1; continue
    if not sin_tag: centros_tag.append(c)
    if np.linalg.norm(dim) < MIN_DIAG:
        pequenas += 1; continue
    pv, tri = triangular(I)
    if not len(tri): continue
    tri_orig += len(tri)
    pos = P[pv].astype(np.float32)
    nor = None
    if N is not None:
        N = N.reshape(-1, 3)
        if NI is not None and ref == b"IndexToDirect": N = N[NI]
        if mapa == b"ByPolygonVertex" and len(N) == len(pv): nor = N
        elif mapa in (b"ByVertice", b"ByVertex", b"ByControlPoint") and len(N) == len(V): nor = N[pv]
    if nor is not None:
        R = M[:3, :3] if M is not None else np.eye(3)
        nor = nor @ np.linalg.inv(R).T
        if eje_z: nor = nor[:, [0, 2, 1]] * np.array([1, 1, -1])
        ln = np.linalg.norm(nor, axis=1, keepdims=True)
        nor = np.where(ln > 1e-9, nor / np.maximum(ln, 1e-12), [0.0, 1.0, 0.0]).astype(np.float32)
    else:
        a, b, cc = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
        fn = np.cross(b - a, cc - a); ln = np.linalg.norm(fn, axis=1, keepdims=True)
        fn = np.where(ln > 1e-12, fn / np.maximum(ln, 1e-12), [0.0, 1.0, 0.0])
        pos = np.stack([a, b, cc], 1).reshape(-1, 3)
        nor = np.repeat(fn, 3, 0).astype(np.float32); tri = np.arange(len(pos)).reshape(-1, 3)
    grosor = float(np.sort(dim)[1])          # 2.ª dimensión: diámetro de tubos, ancho de perfiles
    celda = min(CELDA_MAX, max(0.002, grosor / DIV))
    pos, nor, tri = simplificar(pos, nor, tri, celda)
    if not len(tri): continue
    col = color_de(mid)
    if tag:
        fid = rasgo(tag, {"tag": tag, "ruta": ruta, **{k: str(v) for k, v in D["props_tag"].get(tag_mid, {}).items()}})
    else:
        grupo = grupo_sin_tag(mid)
        fid = rasgo(f"G_{grupo}_{col}", {"tag": f"{grupo} · {col[:6]}", "ruta": f"{grupo} (sin TAG)", "grupo": grupo})
    r = rasgos[fid]; r["tri"] += len(tri)
    r["min"] = np.minimum(r["min"], pmin).tolist(); r["max"] = np.maximum(r["max"], pmax).tolist()
    por_color.setdefault(col, []).append((pos, nor, tri.astype(np.uint32), fid))
    tri_total += len(tri)

log(f"Fuera de zona: {descartadas:,}; pequeñas: {pequenas:,}; triángulos {tri_orig:,} -> {tri_total:,} "
    f"({tri_total / max(1, tri_orig):.1%}); colores {len(por_color)}; elementos {len(rasgos):,}")

# ------------------------------------------------------------------ escribir GLB
def lin(c): return (c / 255) ** 2.2
materiales, mat_idx = [], {}
def material(col):
    if col not in mat_idx:
        r, g, b = (lin(int(col[i:i + 2], 16)) for i in (0, 2, 4))
        a = int(col.split("_A")[1]) / 100 if "_A" in col else 1.0
        m = {"name": f"MAT_{col}", "pbrMetallicRoughness": {"baseColorFactor": [r, g, b, a], "metallicFactor": 0.1,
             "roughnessFactor": 0.7}, "doubleSided": True}
        if a < 1: m["alphaMode"] = "BLEND"
        mat_idx[col] = len(materiales); materiales.append(m)
    return mat_idx[col]

tmp = open(GLB + ".bin.tmp", "w+b")
vistas, accesores, mallas, nodos = [], [], [], []
off = 0
def agregar(arr, destino, tipo, comp, minmax=False):
    global off
    b = np.ascontiguousarray(arr).tobytes(); pad = (-len(b)) % 4
    vistas.append({"buffer": 0, "byteOffset": off, "byteLength": len(b), **({"target": destino} if destino else {})})
    tmp.write(b + b"\0" * pad); off += len(b) + pad
    a = {"bufferView": len(vistas) - 1, "componentType": comp, "count": int(arr.shape[0]), "type": tipo}
    if minmax: a["min"] = arr.min(0).tolist(); a["max"] = arr.max(0).tolist()
    accesores.append(a); return len(accesores) - 1

TIPO_FID = (np.float32, 5126)     # flotante: alineado a 4 bytes y exacto hasta 16 millones
LIM = 2_000_000      # vértices por malla: mallas más chicas se recortan mejor fuera de cámara
def emitir(col, items):
    pos = np.concatenate([x[0] for x in items]); nor = np.concatenate([x[1] for x in items])
    fid = np.concatenate([np.full(len(x[0]), x[3], TIPO_FID[0]) for x in items])
    bases = np.cumsum([0] + [len(x[0]) for x in items[:-1]])
    idx = np.concatenate([x[2] + np.uint32(b) for x, b in zip(items, bases)]).reshape(-1)
    prim = {"attributes": {"POSITION": agregar(pos, 34962, "VEC3", 5126, True),
                           "NORMAL": agregar(nor, 34962, "VEC3", 5126),
                           "_FEATURE_ID_0": agregar(fid, 34962, "SCALAR", TIPO_FID[1])},
            "indices": agregar(idx, 34963, "SCALAR", 5125), "material": material(col)}
    nom = f"C_{col}_{len(mallas)}"
    mallas.append({"name": nom, "primitives": [prim]}); nodos.append({"name": nom, "mesh": len(mallas) - 1})

for col in sorted(por_color):
    items = por_color[col]; por_color[col] = None
    # orden espacial grueso para que cada trozo agrupe piezas cercanas (mejor recorte)
    items.sort(key=lambda x: tuple(np.floor(x[0][0] / 40).astype(int)))
    acum, nv = [], 0
    for it in items:
        if acum and nv + len(it[0]) > LIM:
            emitir(col, acum); acum, nv = [], 0
        acum.append(it); nv += len(it[0])
    if acum: emitir(col, acum)
    items = None

doc = {"asset": {"version": "2.0", "generator": "fbx_a_glb_stream.py"}, "scene": 0,
       "scenes": [{"nodes": list(range(len(nodos)))}], "nodes": nodos, "meshes": mallas, "materials": materiales,
       "accessors": accesores, "bufferViews": vistas, "buffers": [{"byteLength": off}],
       "extras": {"desfase_m": desfase.tolist() if desfase is not None else None, "elementos": len(rasgos)}}
js = json.dumps(doc, separators=(",", ":")).encode(); js += b" " * ((-len(js)) % 4)
total = 12 + 8 + len(js) + 8 + off
if total >= 2 ** 32:
    tmp.close(); os.remove(GLB + ".bin.tmp")
    sys.exit(f"El GLB superaría 4 GB ({total / 1e9:.1f} GB): aumente --celda o --min")
with open(GLB, "wb") as f:
    f.write(struct.pack("<III", 0x46546C67, 2, total))
    f.write(struct.pack("<II", len(js), 0x4E4F534A)); f.write(js)
    f.write(struct.pack("<II", off, 0x004E4942))
    tmp.seek(0)
    while True:
        b = tmp.read(64 * 1024 * 1024)
        if not b: break
        f.write(b)
tmp.close(); os.remove(GLB + ".bin.tmp")
for r in rasgos:
    r["min"] = [round(v, 3) for v in r["min"]]; r["max"] = [round(v, 3) for v in r["max"]]
with open(JSON_OUT, "w", encoding="utf-8") as f:
    json.dump({"formato": "navismobile-elementos-v1", "elementos": rasgos}, f, ensure_ascii=False, separators=(",", ":"))
log(f"GLB: {GLB} ({os.path.getsize(GLB) / 1e6:.1f} MB), {len(nodos)} mallas, {len(rasgos):,} elementos")
log("LISTO")
