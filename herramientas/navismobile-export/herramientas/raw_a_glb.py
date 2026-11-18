"""NMRAW (plugin NwMobileExport) -> GLB + JSON de elementos para NavisMobile.

Misma salida que fbx_a_glb_stream.py (formato "navismobile-elementos-v1", atributo _FEATURE_ID_0),
pero sin FBX: lee la geometría ya transformada a mundo y las propiedades SmartPlant 3D de cada TAG.

Uso:
  python raw_a_glb.py area.nmraw salida.glb salida_elementos.json [--celda 0.15 --div 3 --min 0.06 --margen 15 --sin-filtro]
"""
import json, math, os, struct, sys, time
import numpy as np

T0 = time.time()
def log(*a): print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)

RAW, GLB, JSON_OUT = sys.argv[1:4]
def opcion(nombre, defecto):
    return float(sys.argv[sys.argv.index(nombre) + 1]) if nombre in sys.argv else defecto
CELDA_MAX = opcion("--celda", 0.15)
DIV = opcion("--div", 3.0)
MIN_DIAG = opcion("--min", 0.06)
MARGEN = opcion("--margen", 15.0)
FILTRAR = "--sin-filtro" not in sys.argv

meta = json.load(open(RAW + ".piezas.json", encoding="utf-8"))
tags, grupos, piezas = meta["tags"], meta["grupos"], meta["piezas"]
mm = np.memmap(RAW, dtype=np.uint8, mode="r")
assert bytes(mm[:8]) == b"NMRAW001", "no es un archivo NMRAW001"
desfase = np.frombuffer(mm[8:32].tobytes(), "<f8")

# índice de registros: (pieza, inicio de datos, n triángulos)
regs, off, N = [], 32, len(mm)
while off < N:
    p, n = struct.unpack_from("<ii", mm, off)
    regs.append((p, off + 8, n)); off += 8 + n * 36
log(f"{len(regs):,} piezas, {sum(r[2] for r in regs):,} triángulos, {len(tags):,} TAG; desfase {desfase}")

def leer(ini, n):
    P = np.frombuffer(mm, "<f4", n * 9, ini).reshape(-1, 3).astype(np.float64)
    return P[:, [0, 2, 1]] * np.array([1, 1, -1])            # Z arriba -> Y arriba

def simplificar(pos, nor, tri, celda):
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

# zona: celdas de planta ocupadas por piezas con TAG (+ margen); lo sin TAG fuera de ella se descarta
zona, CEL = None, max(10.0, MARGEN * 2)
if FILTRAR:
    cs = []
    for p, ini, n in regs:
        if piezas[p][0] >= 0:
            P = leer(ini, n); cs.append((P.min(0) + P.max(0)) / 2)
    if cs:
        C = np.floor(np.array(cs)[:, [0, 2]] / CEL).astype(np.int64)
        r = int(math.ceil((MARGEN + 25) / CEL))
        base = {(int(a), int(b)) for a, b in np.unique(C, axis=0)}
        zona = {(a + i, b + j) for a, b in base for i in range(-r, r + 1) for j in range(-r, r + 1)}
        log(f"Zona: {len(base):,} celdas de {CEL:.0f} m con TAG")

por_color, rasgos, rasgo_de = {}, [], {}
def rasgo(clave, datos):
    if clave not in rasgo_de:
        rasgo_de[clave] = len(rasgos)
        rasgos.append({**datos, "tri": 0, "min": [1e18] * 3, "max": [-1e18] * 3})
    return rasgo_de[clave]

fuera = pequenas = tri_orig = tri_total = 0
for k, (p, ini, n) in enumerate(regs):
    if k and k % 20000 == 0: log(f"  {k:,}/{len(regs):,}; triángulos {tri_orig:,} -> {tri_total:,}")
    ti, gi, col = piezas[p]
    P = leer(ini, n)
    pmin, pmax = P.min(0), P.max(0); c = (pmin + pmax) / 2; dim = pmax - pmin
    if ti < 0 and zona is not None and (int(math.floor(c[0] / CEL)), int(math.floor(c[2] / CEL))) not in zona:
        fuera += 1; continue
    if np.linalg.norm(dim) < MIN_DIAG:
        pequenas += 1; continue
    tri_orig += n
    a, b, cc = P[0::3], P[1::3], P[2::3]
    fn = np.cross(b - a, cc - a); ln = np.linalg.norm(fn, axis=1, keepdims=True)
    fn = np.where(ln > 1e-12, fn / np.maximum(ln, 1e-12), [0.0, 1.0, 0.0])
    pos = P.astype(np.float32); nor = np.repeat(fn, 3, 0).astype(np.float32)
    tri = np.arange(len(pos)).reshape(-1, 3)
    celda = min(CELDA_MAX, max(0.002, float(np.sort(dim)[1]) / DIV))
    pos, nor, tri = simplificar(pos, nor, tri, celda)
    if not len(tri): continue
    if ti >= 0:
        t = tags[ti]
        fid = rasgo(t["tag"], {"tag": t["tag"], "ruta": t["ruta"], **t["props"]})
    else:
        g = grupos[gi]
        fid = rasgo(f"G_{g}_{col}", {"tag": f"{g} · {col[:6]}", "ruta": f"{g} (sin TAG)", "grupo": g})
    r = rasgos[fid]; r["tri"] += len(tri)
    r["min"] = np.minimum(r["min"], pmin).tolist(); r["max"] = np.maximum(r["max"], pmax).tolist()
    por_color.setdefault(col, []).append((pos, nor, tri.astype(np.uint32), fid))
    tri_total += len(tri)
log(f"Fuera de zona {fuera:,}; pequeñas {pequenas:,}; triángulos {tri_orig:,} -> {tri_total:,}; "
    f"colores {len(por_color)}; elementos {len(rasgos):,}")

# ------------------------------------------------------------------ GLB
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

LIM = 2_000_000
def emitir(col, items):
    pos = np.concatenate([x[0] for x in items]); nor = np.concatenate([x[1] for x in items])
    fid = np.concatenate([np.full(len(x[0]), x[3], np.float32) for x in items])
    bases = np.cumsum([0] + [len(x[0]) for x in items[:-1]])
    idx = np.concatenate([x[2] + np.uint32(b) for x, b in zip(items, bases)]).reshape(-1)
    prim = {"attributes": {"POSITION": agregar(pos, 34962, "VEC3", 5126, True),
                           "NORMAL": agregar(nor, 34962, "VEC3", 5126),
                           "_FEATURE_ID_0": agregar(fid, 34962, "SCALAR", 5126)},
            "indices": agregar(idx, 34963, "SCALAR", 5125), "material": material(col)}
    nom = f"C_{col}_{len(mallas)}"
    mallas.append({"name": nom, "primitives": [prim]}); nodos.append({"name": nom, "mesh": len(mallas) - 1})

for col in sorted(por_color):
    items = por_color[col]; por_color[col] = None
    items.sort(key=lambda x: tuple(np.floor(x[0][0] / 40).astype(int)))
    acum, nv = [], 0
    for it in items:
        if acum and nv + len(it[0]) > LIM:
            emitir(col, acum); acum, nv = [], 0
        acum.append(it); nv += len(it[0])
    if acum: emitir(col, acum)

doc = {"asset": {"version": "2.0", "generator": "raw_a_glb.py"}, "scene": 0,
       "scenes": [{"nodes": list(range(len(nodos)))}], "nodes": nodos, "meshes": mallas, "materials": materiales,
       "accessors": accesores, "bufferViews": vistas, "buffers": [{"byteLength": off}],
       "extras": {"desfase_m": desfase.tolist(), "elementos": len(rasgos)}}
js = json.dumps(doc, separators=(",", ":")).encode(); js += b" " * ((-len(js)) % 4)
total = 12 + 8 + len(js) + 8 + off
if total >= 2 ** 32:
    tmp.close(); os.remove(GLB + ".bin.tmp"); sys.exit("El GLB superaría 4 GB: aumente --celda o --min")
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
log(f"GLB: {GLB} ({os.path.getsize(GLB) / 1e6:.1f} MB), {len(nodos)} mallas, {len(rasgos):,} elementos — LISTO")
