# -*- coding: utf-8 -*-
"""
fbx_a_blender.py — Convierte un FBX exportado desde Navisworks en un archivo .blend
listo para trabajar (animación de despiece, recorridos, render).

Uso (lo llama CONVERTIR_FBX_A_BLENDER.bat; también se puede usar a mano):

    blender.exe -b --factory-startup --python fbx_a_blender.py -- "modelo.fbx" [opciones]

Opciones:
    --salida RUTA.blend     Archivo de salida (por defecto: convertidos_blender/<nombre>.blend
                            junto a la carpeta del proyecto).
    --jerarquia plana|mantener
                            plana (por defecto): elimina los nodos vacíos de Navisworks
                            (Model:Null) y deja cada malla suelta con su posición real.
                            Los nombres de la jerarquía se guardan en cada malla como
                            propiedades "ruta" y "tag".
                            mantener: conserva el árbol de Navisworks tal cual.
    --colecciones tag|ninguna
                            tag (por defecto): agrupa las mallas en colecciones por TAG
                            (p. ej. 1313-CV-1305). Las mallas sin TAG van a "SIN_TAG".
    --unir no|tag|material  Une mallas para aligerar Blender (por defecto: no).
                            tag: un objeto por TAG (ideal para animar equipos completos).
                            material: un objeto por color (lo más liviano, sin piezas sueltas).
    --decimar R             Reduce los triángulos al factor R (0 < R < 1), p. ej. 0.5.
                            Pierde detalle; úsalo solo en modelos muy pesados.
    --sin-recentrar         No resta el desfase de coordenadas (no recomendado: con
                            coordenadas de ~4.000.000 m la geometría queda deformada).
    --sin-comprimir         Guarda el .blend sin compresión (más grande, abre más rápido).
    --no-fusionar-materiales
                            No fusiona los materiales idénticos del FBX antes de importar
                            (por defecto sí se fusionan; ver punto 2 más abajo).

Qué corrige respecto a un "Archivo > Importar > FBX" normal:
  1. Coordenadas gigantes (≈ 4.448.000 m): Blender guarda la geometría en float32 y a esa
     distancia del origen la precisión es de ~0,5 m, así que las piezas pequeñas se
     deforman. Aquí el desfase se resta en doble precisión ANTES de crear la geometría,
     y queda guardado en la escena (propiedad "desfase_navisworks") para poder volver
     a las coordenadas reales.
  2. Un material por objeto (cientos de miles): Blender tarda un tiempo CUADRÁTICO en crearlos
     (~70 KB cada uno; 200.000 materiales = horas y > 14 GB). Aquí los materiales idénticos
     del FBX se fusionan ANTES de importar (en segundos) y después se unifican por color.
  3. Decenas de miles de nodos vacíos que vuelven lento el esquema: se eliminan
     (salvo --jerarquia mantener), conservando sus nombres como propiedades. Además los
     objetos se enlazan a la escena en bloque (el importador lo hace uno a uno y el tiempo
     crece al cuadrado: 65.000 objetos tardaban más de 10 minutos).
  4. Búsqueda de texturas desactivada (Navisworks no exporta texturas y buscarlas en
     una carpeta de Google Drive puede tardar muchísimo).
"""

import sys
import os
import re
import time
import math
import argparse
import struct
from array import array

import numpy as np

import bpy
import bmesh  # noqa: F401  (disponible para extensiones)
from mathutils import Vector, Matrix, Euler

# ---------------------------------------------------------------------------
# Utilidades de consola
# ---------------------------------------------------------------------------
T0 = time.time()
INFORME = []


def log(msg=""):
    linea = f"[{time.time() - T0:7.1f} s] {msg}"
    print(linea, flush=True)
    INFORME.append(linea)


def memoria():
    """Memoria del proceso (privada y pico) para el registro; vacío si no se puede leer."""
    try:
        import ctypes
        import ctypes.wintypes as wt

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                        ("PrivateUsage", ctypes.c_size_t)]
        k32, ps = ctypes.windll.kernel32, ctypes.windll.psapi
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        ps.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), wt.DWORD]
        c = PMC()
        c.cb = ctypes.sizeof(c)
        ps.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return f"[memoria {c.PrivateUsage / 1073741824:.1f} GB, pico {c.PeakPagefileUsage / 1073741824:.1f} GB]"
    except Exception:
        return ""


def verificar_fbx(ruta):
    """Recorre solo los nodos de primer nivel de un FBX binario (lectura de unos pocos bytes).
    Si falta 'Objects' o 'Connections' el archivo está incompleto (exportación interrumpida)."""
    with open(ruta, "rb") as f:
        cab = f.read(27)
        if not cab.startswith(b"Kaydara FBX Binary"):
            return                      # FBX ASCII u otro formato: lo valida el importador
        version = struct.unpack("<I", cab[23:27])[0]
        grande = version >= 7500
        n_cab = 25 if grande else 13
        tam = os.path.getsize(ruta)
        pos, nodos, motivo = 27, [], None
        while True:
            f.seek(pos)
            h = f.read(n_cab)
            if len(h) < n_cab:
                motivo = "el archivo se corta antes de terminar la lista de nodos"
                break
            if grande:
                fin, nl = struct.unpack("<Q", h[:8])[0], h[24]
            else:
                fin, nl = struct.unpack("<I", h[:4])[0], h[12]
            nombre = f.read(nl).decode("ascii", "replace") if nl else ""
            if fin == 0:
                if nombre:
                    nodos.append(nombre + " (sin cerrar)")
                break
            nodos.append(nombre)
            if fin <= pos or fin > tam:
                motivo = f"el nodo '{nombre}' apunta fuera del archivo"
                break
            pos = fin
    faltan = [n for n in ("Objects", "Connections") if n not in nodos]
    if faltan or motivo:
        raise SystemExit(
            "El FBX está incompleto: la exportación de Navisworks se interrumpió "
            f"({'faltan los nodos ' + ', '.join(faltan) if faltan else motivo}). "
            f"Nodos encontrados: {', '.join(nodos) or 'ninguno'}. "
            "Vuelve a exportar el modelo (o a convertir el .nwd) y usa el archivo nuevo.")


# Patrón de TAG: AREA(4 dígitos)-TIPO-NUMERO al inicio de un código (1313-CV-1305, 1241-CH-001A).
# No toma trozos de códigos más largos como 1313-TA60-C-113-TRAY-0726.
PATRON_TAG = re.compile(r"(?<![0-9A-Za-z-])(\d{4}-[A-Z]{1,4}-\d{2,5}[A-Z]?)(?![0-9A-Za-z])")

# Por encima de esta magnitud (en unidades del archivo) se considera que las
# coordenadas son "georreferenciadas" y se recentran.
UMBRAL_DESFASE = 50_000.0


# ---------------------------------------------------------------------------
# Argumentos
# ---------------------------------------------------------------------------
def leer_argumentos():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(prog="fbx_a_blender.py")
    p.add_argument("fbx")
    p.add_argument("--salida")
    p.add_argument("--jerarquia", choices=["plana", "mantener"], default="plana")
    p.add_argument("--colecciones", choices=["tag", "ninguna"], default="tag")
    p.add_argument("--unir", choices=["no", "tag", "material"], default="no")
    p.add_argument("--decimar", type=float, default=None)
    p.add_argument("--sin-recentrar", action="store_true")
    p.add_argument("--sin-comprimir", action="store_true")
    p.add_argument("--no-fusionar-materiales", action="store_true")
    a = p.parse_args(argv)
    if a.decimar is not None and not (0.0 < a.decimar < 1.0):
        p.error("--decimar debe estar entre 0 y 1 (p. ej. 0.5)")
    a.fbx = os.path.abspath(a.fbx)
    if not os.path.isfile(a.fbx):
        p.error(f"No existe el archivo: {a.fbx}")
    if not a.salida:
        carpeta_herr = os.path.dirname(os.path.abspath(__file__))
        proyecto = os.path.dirname(carpeta_herr)
        nombre = os.path.splitext(os.path.basename(a.fbx))[0].strip().lstrip(",").strip()
        a.salida = os.path.join(proyecto, "convertidos_blender", nombre + ".blend")
    a.salida = os.path.abspath(a.salida)
    return a


# ---------------------------------------------------------------------------
# 1. Recentrado en doble precisión (sobre el árbol FBX ya leído, antes de crear mallas)
# ---------------------------------------------------------------------------
class Recentrador:
    """Envuelve parse_fbx.parse del importador oficial para corregir el árbol en float64."""

    def __init__(self):
        self.desfase = (0.0, 0.0, 0.0)     # en unidades y ejes del archivo
        self.modo = "ninguno"
        self.unidad_cm = 1.0
        self.avisos = []

    # -- helpers sobre FBXElem(id, props, props_type, elems) --
    @staticmethod
    def hijo(elem, nombre):
        for e in elem.elems:
            if e.id == nombre:
                return e
        return None

    @staticmethod
    def p70(elem_modelo, nombre_prop):
        p = Recentrador.hijo(elem_modelo, b"Properties70")
        if p is None:
            return None
        for e in p.elems:
            if e.props and e.props[0] == nombre_prop:
                return e
        return None

    def aplicar(self, raiz, fase="ambos"):
        """fase: 'nodos' (desfase en traslaciones), 'vertices' (desfase en vértices) o 'ambos'."""
        objetos = self.hijo(raiz, b"Objects")
        conexiones = self.hijo(raiz, b"Connections")
        if objetos is None:
            return

        ajustes = self.hijo(raiz, b"GlobalSettings")
        if ajustes is not None:
            e = self.p70(ajustes, b"UnitScaleFactor")
            if e is not None:
                self.unidad_cm = float(e.props[4])

        geometrias = {}   # id -> elem (Mesh)
        modelos = {}      # id -> elem
        for e in objetos.elems:
            if e.id == b"Geometry" and len(e.props) > 2 and e.props[2] == b"Mesh":
                geometrias[e.props[0]] = e
            elif e.id == b"Model":
                modelos[e.props[0]] = e

        padre_de = {}         # modelo -> modelo padre (0 = raíz)
        geom_a_modelo = {}    # geometría -> modelo
        if conexiones is not None:
            for c in conexiones.elems:
                if c.id != b"C" or len(c.props) < 3 or c.props[0] != b"OO":
                    continue
                hijo_id, padre_id = c.props[1], c.props[2]
                if hijo_id in modelos and (padre_id in modelos or padre_id == 0):
                    padre_de[hijo_id] = padre_id
                elif hijo_id in geometrias and padre_id in modelos:
                    geom_a_modelo[hijo_id] = padre_id

        # --- caso A: vértices con coordenadas absolutas ---
        mn = [math.inf] * 3
        mx = [-math.inf] * 3
        for g in geometrias.values():
            v = self.hijo(g, b"Vertices")
            if v is None or not len(v.props[0]):
                continue
            d = np.frombuffer(v.props[0], dtype=np.float64).reshape(-1, 3)
            dmn, dmx = d.min(axis=0), d.max(axis=0)
            for k in range(3):
                mn[k] = min(mn[k], float(dmn[k]))
                mx[k] = max(mx[k], float(dmx[k]))
        if mn[0] != math.inf:
            centro_v = [(mn[k] + mx[k]) * 0.5 for k in range(3)]
        else:
            centro_v = [0.0, 0.0, 0.0]

        if max(abs(c) for c in centro_v) > UMBRAL_DESFASE:
            if fase == "nodos":
                return
            # Redondeo a 10 unidades: desfase "limpio", fácil de anotar.
            O = tuple(round(c / 10.0) * 10.0 for c in centro_v)
            n_rot = 0
            for gid, g in geometrias.items():
                v = self.hijo(g, b"Vertices")
                if v is None:
                    continue
                o_local = self._desfase_local(modelos.get(geom_a_modelo.get(gid)), O)
                if o_local is not O:
                    n_rot += 1
                d = np.frombuffer(v.props[0], dtype=np.float64).reshape(-1, 3)
                d = d - np.asarray(o_local, dtype=np.float64)   # resta en doble precisión
                v.props[0] = array("d", d.ravel().tobytes())
            self.desfase = O
            self.modo = "vertices"
            if n_rot:
                self.avisos.append(
                    f"{n_rot} mallas tienen rotación/escala propia; el desfase se llevó a su espacio local.")
            return

        # --- caso B: traslaciones grandes en los nodos ---
        if fase == "vertices" or self.modo != "ninguno":
            return
        hijos_de = {}
        for h, p in padre_de.items():
            hijos_de.setdefault(p, []).append(h)
        raices = [m for m in modelos if padre_de.get(m, 0) == 0]

        def tras(mid):
            e = self.p70(modelos[mid], b"Lcl Translation")
            return (float(e.props[4]), float(e.props[5]), float(e.props[6])) if e is not None else (0.0, 0.0, 0.0)

        # acumulado (ignorando rotaciones, suficiente para detectar el desfase)
        acum = {}
        pila = [(r, (0.0, 0.0, 0.0)) for r in raices]
        while pila:
            mid, base = pila.pop()
            t = tras(mid)
            a = (base[0] + t[0], base[1] + t[1], base[2] + t[2])
            acum[mid] = a
            for h in hijos_de.get(mid, ()):
                pila.append((h, a))
        con_malla = set(geom_a_modelo.values())
        pts = [acum[m] for m in con_malla if m in acum] or list(acum.values())
        if not pts:
            return
        centro_t = [(min(p[k] for p in pts) + max(p[k] for p in pts)) * 0.5 for k in range(3)]
        if max(abs(c) for c in centro_t) <= UMBRAL_DESFASE:
            return

        O = tuple(round(c / 10.0) * 10.0 for c in centro_t)
        n = 0
        # Resta O en el primer nodo de cada rama cuya posición acumulada se vuelve grande.
        pila = [(r, (0.0, 0.0, 0.0)) for r in raices]
        while pila:
            mid, base = pila.pop()
            e = self.p70(modelos[mid], b"Lcl Translation")
            t = tras(mid)
            a = (base[0] + t[0], base[1] + t[1], base[2] + t[2])
            if e is not None and max(abs(x) for x in a) > UMBRAL_DESFASE and \
                    max(abs(x) for x in base) <= UMBRAL_DESFASE:
                e.props[4] = t[0] - O[0]
                e.props[5] = t[1] - O[1]
                e.props[6] = t[2] - O[2]
                a = (a[0] - O[0], a[1] - O[1], a[2] - O[2])
                n += 1
            for h in hijos_de.get(mid, ()):
                pila.append((h, a))
        self.desfase = O
        self.modo = f"nodos ({n} ramas)"

    def _desfase_local(self, modelo, O):
        """Lleva el desfase al espacio local de la malla si el nodo tiene rotación/escala."""
        if modelo is None:
            return O
        r = self.p70(modelo, b"Lcl Rotation")
        s = self.p70(modelo, b"Lcl Scaling")
        rot = (float(r.props[4]), float(r.props[5]), float(r.props[6])) if r is not None else (0, 0, 0)
        esc = (float(s.props[4]), float(s.props[5]), float(s.props[6])) if s is not None else (1, 1, 1)
        if max(abs(x) for x in rot) < 1e-9 and max(abs(x - 1) for x in esc) < 1e-9:
            return O
        R = Euler([math.radians(x) for x in rot], "XYZ").to_matrix().to_3x3()
        v = R.inverted() @ Vector(O)
        return (v.x / (esc[0] or 1), v.y / (esc[1] or 1), v.z / (esc[2] or 1))


# ---------------------------------------------------------------------------
# Transformaciones FBX en doble precisión (misma fórmula que el importador de Blender,
# que trabaja en float32 y pierde ~0,5 m a 4.400 km del origen)
# ---------------------------------------------------------------------------
def _m_tras(v):
    M = np.eye(4)
    M[:3, 3] = v
    return M


def _m_esc(v):
    return np.diag([v[0], v[1], v[2], 1.0])


def _m_rot(grados, orden="XYZ"):
    a = np.radians(np.asarray(grados, dtype=np.float64))
    cx, cy, cz = np.cos(a)
    sx, sy, sz = np.sin(a)
    R = {"X": np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]]),
         "Y": np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]),
         "Z": np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])}
    M = np.eye(4)
    M[:3, :3] = R[orden[2]] @ R[orden[1]] @ R[orden[0]]
    return M


def matrices_fbx64(td):
    """Devuelve (base, geom) en float64 a partir de FBXTransformData."""
    inv = np.linalg.inv
    alt = np.array(td.rot_alt_mat, dtype=np.float64)
    base = (_m_tras(td.loc) @ _m_tras(td.rot_ofs) @ _m_tras(td.rot_piv) @ _m_rot(td.pre_rot) @
            (_m_rot(td.rot, td.rot_ord) @ alt) @ inv(_m_rot(td.pst_rot)) @ inv(_m_tras(td.rot_piv)) @
            _m_tras(td.sca_ofs) @ _m_tras(td.sca_piv) @ _m_esc(td.sca) @ inv(_m_tras(td.sca_piv)))
    geom = _m_tras(td.geom_loc) @ _m_rot(td.geom_rot) @ _m_esc(td.geom_sca)
    return base, geom


class PodaJerarquia:
    """Elimina del árbol FBX los nodos sin malla (Model:Null de Navisworks) ANTES de que
    Blender cree objetos. Cada malla queda colgando de la raíz con su transformación mundial
    ya calculada, y con la ruta de nombres y el TAG como propiedades personalizadas.
    Con 130 mil nodos vacíos, esto lleva la importación de decenas de minutos a segundos."""

    def __init__(self):
        self.mallas = 0
        self.eliminados = 0
        self.con_cizalle = 0
        # siempre definidos: aplicar() puede salir antes (sin nodos que podar)
        self.desfase = (0.0, 0.0, 0.0)
        self.vertices_recentrados = 0
        self.horneadas = 0
        self.desfase_activo = True
        self.renombradas = 0

    @staticmethod
    def nombre(elem_modelo):
        return elem_modelo.props[1].split(b"\x00\x01")[0].decode("utf-8", "replace")

    def aplicar(self, raiz):
        import io_scene_fbx.import_fbx as imp
        from io_scene_fbx.parse_fbx import FBXElem
        H = Recentrador.hijo
        objetos = H(raiz, b"Objects")
        conexiones = H(raiz, b"Connections")
        if objetos is None or conexiones is None:
            return

        # plantilla de propiedades de Model (valores por defecto del archivo)
        plantilla = imp.fbx_elem_nil
        defs = H(raiz, b"Definitions")
        if defs is not None:
            for ot in defs.elems:
                if ot.id == b"ObjectType" and ot.props and ot.props[0] == b"Model":
                    for pt in ot.elems:
                        if pt.id == b"PropertyTemplate":
                            p70 = H(pt, b"Properties70")
                            if p70 is not None:
                                plantilla = p70

        modelos = {e.props[0]: e for e in objetos.elems if e.id == b"Model"}
        geom_malla = {e.props[0] for e in objetos.elems
                      if e.id == b"Geometry" and len(e.props) > 2 and e.props[2] == b"Mesh"}
        padre_de, con_malla = {}, set()
        self.geoms = {e.props[0]: e for e in objetos.elems
                      if e.id == b"Geometry" and len(e.props) > 2 and e.props[2] == b"Mesh"}
        self.geom_de = {}       # modelo -> [geometrías]
        self.usos_geom = {}     # geometría -> nº de modelos que la usan
        for c in conexiones.elems:
            if c.id != b"C" or len(c.props) < 3 or c.props[0] != b"OO":
                continue
            h, pa = c.props[1], c.props[2]
            if h in modelos and (pa in modelos or pa == 0):
                padre_de[h] = pa
            elif h in geom_malla and pa in modelos:
                con_malla.add(pa)
                self.geom_de.setdefault(pa, []).append(h)
                self.usos_geom[h] = self.usos_geom.get(h, 0) + 1
        # se conservan las mallas y cualquier nodo que no sea Null/Mesh (cámaras, luces...)
        tipos_vacios = (b"Null", b"Mesh", b"Line", b"NurbsCurve", b"Nurbs", b"NurbsSurface", b"Shape")
        conservar = {m for m, e in modelos.items()
                     if m in con_malla or (len(e.props) > 2 and e.props[2] not in tipos_vacios)}
        eliminar = set(modelos) - conservar
        if not eliminar:
            return

        cache = {}

        def td_de(mid):
            e = modelos[mid]
            props = (H(e, b"Properties70") or imp.fbx_elem_nil, plantilla)
            return imp.blen_read_object_transform_preprocess(props, e, Matrix(), True)

        def base(mid):
            if mid not in cache:
                cache[mid] = matrices_fbx64(td_de(mid))
            return cache[mid]

        def mundo(mid):
            cadena = []
            m = mid
            while m in modelos:
                cadena.append(m)
                m = padre_de.get(m, 0)
            M = np.eye(4)
            for m in reversed(cadena):
                M = M @ base(m)[0]
            return M, cadena

        # mundo de cada objeto conservado (float64) y caja real de su geometría
        mundos = {}
        mn = np.full(3, np.inf)
        mx = np.full(3, -np.inf)
        desplazada = {}   # geometría -> vector restado a sus vértices
        self.vertices_recentrados = 0
        for mid in conservar:
            M, cadena = mundo(mid)
            G = base(mid)[1]
            gids = [g for g in self.geom_de.get(mid, ())
                    if Recentrador.hijo(self.geoms[g], b"Vertices") is not None]
            # Vértices en coordenadas absolutas: se recentran respecto del centro de la malla y
            # ese vector pasa a la transformación del objeto (todo en float64).
            if gids:
                arrs = [np.frombuffer(Recentrador.hijo(self.geoms[g], b"Vertices").props[0],
                                      dtype=np.float64).reshape(-1, 3) for g in gids]
                arrs = [x for x in arrs if len(x)]
                if arrs:
                    c = (np.min([x.min(axis=0) for x in arrs], axis=0) +
                         np.max([x.max(axis=0) for x in arrs], axis=0)) * 0.5
                    diag = float(np.linalg.norm(
                        np.max([x.max(axis=0) for x in arrs], axis=0) -
                        np.min([x.min(axis=0) for x in arrs], axis=0)))
                    if gids[0] in desplazada:
                        c = desplazada[gids[0]]
                    # vértices absolutos, u origen muy lejos de la pieza (típico de Navisworks):
                    # el origen pasa al centro de la pieza, útil como pivote para animar.
                    if np.abs(c).max() > UMBRAL_DESFASE or np.linalg.norm(c) > max(5.0 * diag, 1.0):
                        for g in gids:
                            if g in desplazada:
                                continue
                            v = Recentrador.hijo(self.geoms[g], b"Vertices")
                            d = np.frombuffer(v.props[0], dtype=np.float64).reshape(-1, 3) - c
                            v.props[0] = array("d", d.ravel().tobytes())
                            desplazada[g] = c
                        M = M @ G @ _m_tras(c) @ np.linalg.inv(G)
                        self.vertices_recentrados += 1
            mundos[mid] = (M, cadena)
            for gid in gids:
                v = Recentrador.hijo(self.geoms[gid], b"Vertices")
                if v is None or not len(v.props[0]):
                    continue
                d = np.frombuffer(v.props[0], dtype=np.float64).reshape(-1, 3)
                a, b = d.min(axis=0), d.max(axis=0)
                esquinas = np.array([[x, y, z, 1.0] for x in (a[0], b[0])
                                     for y in (a[1], b[1]) for z in (a[2], b[2])])
                w = (M @ G @ esquinas.T).T[:, :3]
                mn = np.minimum(mn, w.min(axis=0))
                mx = np.maximum(mx, w.max(axis=0))
        self.desfase = (0.0, 0.0, 0.0)
        if np.isfinite(mn).all():
            centro = (mn + mx) * 0.5
            if np.abs(centro).max() > UMBRAL_DESFASE and getattr(self, "desfase_activo", True):
                self.desfase = tuple(float(round(c / 10.0) * 10.0) for c in centro)

        def p_vec(nombre, v):
            return FBXElem(b"P", [nombre, nombre, b"", b"A", float(v[0]), float(v[1]), float(v[2])],
                           bytearray(b"SSSSDDD"), [])

        def p_txt(nombre, texto):
            return FBXElem(b"P", [nombre, b"KString", b"", b"U", texto.encode("utf-8")],
                           bytearray(b"SSSSS"), [])

        quitar_props = {b"Lcl Translation", b"Lcl Rotation", b"Lcl Scaling", b"RotationOffset",
                        b"RotationPivot", b"ScalingOffset", b"ScalingPivot", b"PreRotation",
                        b"PostRotation", b"RotationOrder", b"RotationActive", b"ruta", b"tag"}
        O = np.array(self.desfase)
        nombre_orig = {m: self.nombre(x) for m, x in modelos.items()}   # antes de renombrar
        for mid in conservar:
            e = modelos[mid]
            M64, cadena = mundos[mid]
            M64 = M64.copy()
            M64[:3, 3] -= O                      # recentrado exacto, en doble precisión
            M = Matrix(M64.tolist())             # ya cerca del origen: float32 basta
            loc, rot, esc = M.decompose()
            eul = rot.to_euler("XYZ")
            rehecha = Matrix.LocRotScale(loc, rot, esc)
            if max(abs(rehecha[i][j] - M[i][j]) for i in range(3) for j in range(3)) > 1e-6:
                # Cizalle: no cabe en loc/rot/esc. El resto se incorpora a los vértices.
                self.hornear_resto(mid, rehecha.inverted_safe() @ M, modelos[mid], plantilla, H, imp)
            nombres = [n for n in (nombre_orig[m] for m in reversed(cadena[1:])) if n.strip()]
            # Navisworks llama "Geometry" a cada malla: se usa el nombre del elemento padre.
            # Se hace aquí, antes de importar: renombrar 65.000 objetos después tarda ~5 min.
            if nombres and nombre_orig[mid].split(".")[0].strip().lower() in ("geometry", "mesh", "object", ""):
                e.props[1] = nombres[-1][:60].encode("utf-8") + b"\x00\x01Model"
                self.renombradas += 1
            tag = tag_de(nombre_orig[mid])
            if not tag:
                for n in reversed(nombres):
                    tag = tag_de(n)
                    if tag:
                        break
            p70 = H(e, b"Properties70")
            if p70 is None:
                p70 = FBXElem(b"Properties70", [], bytearray(), [])
                e.elems.append(p70)
            p70.elems[:] = [x for x in p70.elems if not (x.props and x.props[0] in quitar_props)]
            p70.elems.append(p_vec(b"Lcl Translation", loc))
            p70.elems.append(p_vec(b"Lcl Rotation", [math.degrees(a) for a in eul]))
            p70.elems.append(p_vec(b"Lcl Scaling", esc))
            p70.elems.append(p_txt(b"ruta", " / ".join(nombres)))
            if tag:
                p70.elems.append(p_txt(b"tag", tag))

        nuevas = []
        for c in conexiones.elems:
            if c.id == b"C" and len(c.props) >= 3:
                if c.props[1] in eliminar or c.props[2] in eliminar:
                    continue
                if c.props[0] == b"OO" and c.props[1] in conservar:
                    continue  # se vuelve a colgar de la raíz abajo
            nuevas.append(c)
        for mid in conservar:
            nuevas.append(FBXElem(b"C", [b"OO", mid, 0], bytearray(b"SLL"), []))
        conexiones.elems[:] = nuevas
        objetos.elems[:] = [e for e in objetos.elems
                            if not (e.id == b"Model" and e.props[0] in eliminar)]
        self.mallas = len(conservar)
        self.eliminados = len(eliminar)

    def hornear_resto(self, mid, resto, e, plantilla, H, imp):
        """Aplica la parte de cizalle 'resto' (4x4) directamente a vértices y normales."""
        props = (H(e, b"Properties70") or imp.fbx_elem_nil, plantilla)
        td = imp.blen_read_object_transform_preprocess(props, e, Matrix(), True)
        G = matrices_fbx64(td)[1]
        X = np.linalg.inv(G) @ np.array(resto, dtype=np.float64) @ G
        L = X[:3, :3]
        N = np.linalg.inv(L).T
        for gid in self.geom_de.get(mid, ()):
            if self.usos_geom.get(gid, 1) > 1:
                self.con_cizalle += 1   # geometría compartida: no se puede hornear por objeto
                continue
            g = self.geoms[gid]
            v = Recentrador.hijo(g, b"Vertices")
            if v is not None and len(v.props[0]):
                d = np.frombuffer(v.props[0], dtype=np.float64).reshape(-1, 3)
                v.props[0] = array("d", (d @ L.T + X[:3, 3]).ravel().tobytes())
            for capa in g.elems:
                if capa.id != b"LayerElementNormal":
                    continue
                n = Recentrador.hijo(capa, b"Normals")
                if n is not None and len(n.props[0]):
                    d = np.frombuffer(n.props[0], dtype=np.float64).reshape(-1, 3) @ N.T
                    d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-12)
                    n.props[0] = array("d", d.ravel().tobytes())
        self.horneadas = getattr(self, "horneadas", 0) + 1

MARCADORES = ("__eje_x__", "__eje_y__", "__eje_z__")


def agregar_marcadores_ejes(raiz):
    """Tres nodos a 1000 unidades sobre cada eje del archivo: tras importar, sus posiciones
    dicen cómo convierte Blender los ejes y unidades (para expresar el desfase en Blender)."""
    from io_scene_fbx.parse_fbx import FBXElem
    objetos = Recentrador.hijo(raiz, b"Objects")
    conexiones = Recentrador.hijo(raiz, b"Connections")
    if objetos is None or conexiones is None:
        return
    for i, nombre in enumerate(MARCADORES):
        uid = 9_100_000_000_000 + i
        v = [0.0, 0.0, 0.0]
        v[i] = 1000.0
        p70 = FBXElem(b"Properties70", [], bytearray(), [
            FBXElem(b"P", [b"Lcl Translation", b"Lcl Translation", b"", b"A", v[0], v[1], v[2]],
                    bytearray(b"SSSSDDD"), [])])
        objetos.elems.append(FBXElem(b"Model", [uid, nombre.encode() + b"\x00\x01Model", b"Null"],
                                     bytearray(b"LSS"), [p70]))
        conexiones.elems.append(FBXElem(b"C", [b"OO", uid, 0], bytearray(b"SLL"), []))



def instalar_enlace_rapido():
    """Acelera la creación de objetos del importador FBX de Blender (miles de objetos).

    El importador crea cada objeto, lo enlaza a la colección y lo selecciona, uno por uno:
    cada llamada obliga a Blender a re-sincronizar toda la escena, así que el tiempo crece al
    CUADRADO (20.000 objetos = 33 s; 65.000 = varios minutos; 130.000 = decenas de minutos).
    Aquí se crean todos los objetos primero y se enlazan juntos al final, sin seleccionarlos
    (65.733 objetos en ~10 s). Solo se usa si el árbol no tiene huesos ni armaduras; si los
    tuviera, se deja el comportamiento original. Devuelve la función que lo deshace."""
    try:
        import io_scene_fbx.import_fbx as imp
        nodo_cls = imp.FbxImportHelperNode
    except Exception:
        return lambda: None
    original = nodo_cls.build_hierarchy

    def con_huesos(raiz):
        pila = [raiz]
        while pila:
            n = pila.pop()
            if getattr(n, "is_armature", False) or getattr(n, "is_bone", False):
                return True
            pila.extend(n.children)
        return False

    def build_hierarchy(self, fbx_tmpl, settings, scene, view_layer):
        if not getattr(self, "is_root", False) or con_huesos(self):
            return original(self, fbx_tmpl, settings, scene, view_layer)
        objetos = []

        def construir(n):
            obj = n.build_node_obj(fbx_tmpl, settings) if n.fbx_elem else None
            for hijo in n.children:
                construir(hijo)
            if obj is not None:
                objetos.append(obj)

        t = time.time()
        construir(self)
        col = view_layer.active_layer_collection.collection
        for obj in objetos:
            col.objects.link(obj)
        log(f"Objetos creados y enlazados en bloque: {len(objetos):,} ({time.time() - t:.1f} s). {memoria()}")
        return None

    nodo_cls.build_hierarchy = build_hierarchy
    return lambda: setattr(nodo_cls, "build_hierarchy", original)


def fusionar_materiales_fbx(raiz):
    """Fusiona en el árbol FBX los Material idénticos ANTES de que Blender los cree.

    Navisworks exporta un material por pieza (200.000 en el modelo grande, casi todos iguales)
    y el importador de Blender tarda un tiempo cuadrático en crearlos (~70 KB cada uno).
    Cada conexión modelo→material se redirige al material canónico conservando el orden y la
    cantidad de conexiones, así que los índices de material de cada malla no cambian.
    Los materiales que reciben conexiones propias (texturas) no se tocan.
    Devuelve (materiales_antes, materiales_despues)."""
    H = Recentrador.hijo
    objetos = H(raiz, b"Objects")
    conexiones = H(raiz, b"Connections")
    if objetos is None or conexiones is None:
        return 0, 0
    mats = [e for e in objetos.elems if e.id == b"Material" and e.props]
    if len(mats) < 2:
        return len(mats), len(mats)
    con_hijos = {c.props[2] for c in conexiones.elems
                 if c.id == b"C" and len(c.props) >= 3}
    canon, reemplazo = {}, {}
    for m in mats:
        uid = m.props[0]
        if uid in con_hijos:
            continue
        # el nombre (props[1]) no cuenta: dos materiales con distinto nombre pero iguales se fusionan
        clave = (tuple(m.props[2:]),
                 tuple((e.id, tuple(tuple(p.props) for p in e.elems)) if e.id == b"Properties70"
                       else (e.id, tuple(e.props)) for e in m.elems))
        try:
            hash(clave)
        except TypeError:
            clave = repr(clave)
        if clave in canon:
            reemplazo[uid] = canon[clave]
        else:
            canon[clave] = uid
    if not reemplazo:
        return len(mats), len(mats)
    for c in conexiones.elems:
        if c.id == b"C" and len(c.props) >= 3 and c.props[0] == b"OO" and c.props[1] in reemplazo:
            c.props[1] = reemplazo[c.props[1]]
    objetos.elems[:] = [e for e in objetos.elems
                        if not (e.id == b"Material" and e.props and e.props[0] in reemplazo)]
    return len(mats), len(mats) - len(reemplazo)


def instalar_recentrador(rec, poda=None, fusionar_mats=True):
    import io_scene_fbx.parse_fbx as parse_fbx
    original = parse_fbx.parse

    def parse_corregido(fn, use_namedtuple=True):
        raiz, version = original(fn, use_namedtuple)
        log(f"FBX leído (versión {version}). Revisando coordenadas… {memoria()}")
        if fusionar_mats:
            t = time.time()
            antes, despues = fusionar_materiales_fbx(raiz)
            if antes > despues:
                log(f"Materiales idénticos fusionados antes de importar: {antes:,} → {despues:,} "
                    f"({time.time() - t:.1f} s). {memoria()}")
        if rec is not None:
            ajustes = Recentrador.hijo(raiz, b"GlobalSettings")
            e = Recentrador.p70(ajustes, b"UnitScaleFactor") if ajustes is not None else None
            if e is not None:
                rec.unidad_cm = float(e.props[4])
        if poda is not None:
            t = time.time()
            poda.desfase_activo = rec is not None
            poda.aplicar(raiz)
            if rec is not None and any(poda.desfase):
                rec.desfase, rec.modo = poda.desfase, "transformaciones de nodos (doble precisión)"
            log(f"Nodos vacíos podados antes de importar: {poda.eliminados:,} "
                f"(quedan {poda.mallas:,} objetos, {time.time() - t:.1f} s). {memoria()}")
            if poda.vertices_recentrados:
                log(f"  {poda.vertices_recentrados:,} mallas con el origen lejos de su geometría: "
                    "origen movido al centro de cada pieza.")
            if getattr(poda, "horneadas", 0):
                log(f"  {poda.horneadas} mallas con cizalle: deformación incorporada a sus vértices.")
        if rec is not None and rec.modo == "ninguno":
            rec.aplicar(raiz, "vertices" if poda is not None else "ambos")
        agregar_marcadores_ejes(raiz)
        return raiz, version

    parse_fbx.parse = parse_corregido
    return lambda: setattr(parse_fbx, "parse", original)


# ---------------------------------------------------------------------------
# 2. Limpieza posterior
# ---------------------------------------------------------------------------
def tag_de(nombre):
    m = PATRON_TAG.search(nombre or "")
    return m.group(1) if m else None


def ruta_y_tag(obj):
    nombres = []
    o = obj.parent
    while o is not None:
        nombres.append(o.name)
        o = o.parent
    nombres.reverse()
    tag = tag_de(obj.name)
    if not tag:
        for n in reversed(nombres):  # el ancestro más cercano manda
            tag = tag_de(n)
            if tag:
                break
    return " / ".join(nombres), tag


def fusionar_materiales(mallas):
    def clave(mat):
        if mat is None:
            return None
        col = list(mat.diffuse_color)
        rough, metal = mat.roughness, mat.metallic
        if mat.node_tree:
            bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if bsdf is not None:
                col = list(bsdf.inputs["Base Color"].default_value)
                col[3] = bsdf.inputs["Alpha"].default_value
                rough = bsdf.inputs["Roughness"].default_value
                metal = bsdf.inputs["Metallic"].default_value
        return tuple(round(x, 3) for x in col) + (round(rough, 2), round(metal, 2))

    antes = len(bpy.data.materials)
    canon = {}
    for mat in list(bpy.data.materials):
        k = clave(mat)
        if k not in canon:
            canon[k] = mat
            r, g, b, a = k[:4]
            mat.name = "MAT_{:02X}{:02X}{:02X}{}".format(
                int(r * 255), int(g * 255), int(b * 255), "" if a >= 0.999 else f"_A{int(a * 100)}")
    reemplazo = {m: canon[clave(m)] for m in bpy.data.materials}
    # user_remap sustituye todos los usos de una vez; asignar slot por slot (65.000 mallas)
    # crece al cuadrado en Blender.
    for m, destino in reemplazo.items():
        if destino is not m:
            m.user_remap(destino)
    usados = set(canon.values())
    sobran = [m for m in bpy.data.materials if m not in usados]
    bpy.data.batch_remove(sobran)
    return antes, len(bpy.data.materials)


def unir_numpy(obs, nombre):
    """Une objetos malla en un objeto nuevo copiando los arreglos con numpy (tiempo lineal).

    bpy.ops.object.join elimina los objetos uno a uno y cada eliminación cuesta O(nº de objetos
    de la escena): 4.000 objetos = 11 s, 8.000 = 70 s, 23.000 = más de 15 min. Aquí se crea
    la malla unida de una vez y los originales se eliminan en bloque (batch_remove).
    El resultado queda en el espacio local del primer objeto (como con join), conserva
    materiales, suavizado y normales personalizadas."""
    primero = obs[0]
    inv0 = np.linalg.inv(np.array(primero.matrix_world))
    cos, ixs, lss, sms, mis, nms = [], [], [], [], [], []
    materiales, mapa = [], {}
    base_v = base_l = 0
    hay_normales = any(o.data.has_custom_normals for o in obs)
    for o in obs:
        me = o.data
        nv, nl, npol = len(me.vertices), len(me.loops), len(me.polygons)
        if nv == 0 or npol == 0:
            continue
        A = inv0 @ np.array(o.matrix_world)            # espacio de este objeto -> el del primero
        co = np.empty(nv * 3, dtype=np.float32)
        me.vertices.foreach_get("co", co)
        cos.append((co.reshape(-1, 3).astype(np.float64) @ A[:3, :3].T + A[:3, 3]).astype(np.float32))
        ix = np.empty(nl, dtype=np.int32)
        me.loops.foreach_get("vertex_index", ix)
        ixs.append(ix + base_v)
        ls = np.empty(npol, dtype=np.int32)
        me.polygons.foreach_get("loop_start", ls)
        lss.append(ls + base_l)
        sm = np.empty(npol, dtype=bool)
        me.polygons.foreach_get("use_smooth", sm)
        sms.append(sm)
        mi = np.empty(npol, dtype=np.int32)
        me.polygons.foreach_get("material_index", mi)
        tabla = []
        for slot in o.material_slots:
            m = slot.material
            if m is not None and m not in mapa:
                mapa[m] = len(materiales)
                materiales.append(m)
            tabla.append(mapa.get(m, 0))
        mis.append(np.array(tabla, dtype=np.int32)[np.clip(mi, 0, len(tabla) - 1)] if tabla
                   else np.zeros(npol, dtype=np.int32))
        if hay_normales:
            cn = np.empty(nl * 3, dtype=np.float32)
            me.corner_normals.foreach_get("vector", cn)
            N = np.linalg.inv(A[:3, :3]).T
            n = cn.reshape(-1, 3).astype(np.float64) @ N.T
            n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
            nms.append(n.astype(np.float32))
        base_v += nv
        base_l += nl
    nueva = bpy.data.meshes.new(nombre)
    if cos:
        co_t, ix_t, ls_t = np.concatenate(cos), np.concatenate(ixs), np.concatenate(lss)
        nueva.vertices.add(len(co_t))
        nueva.loops.add(len(ix_t))
        nueva.polygons.add(len(ls_t))
        nueva.vertices.foreach_set("co", co_t.ravel())
        nueva.loops.foreach_set("vertex_index", ix_t)
        nueva.polygons.foreach_set("loop_start", ls_t)
        nueva.polygons.foreach_set("use_smooth", np.concatenate(sms))
        nueva.polygons.foreach_set("material_index", np.concatenate(mis))
        nueva.update(calc_edges=True)
        for m in materiales:
            nueva.materials.append(m)
        if hay_normales:
            nueva.normals_split_custom_set(np.concatenate(nms))
    nuevo = bpy.data.objects.new(nombre, nueva)
    nuevo.matrix_world = primero.matrix_world
    for c in primero.users_collection:
        c.objects.link(nuevo)
    for clave in primero.keys():
        nuevo[clave] = primero[clave]
    viejas = {o.data for o in obs}
    bpy.data.batch_remove(list(obs))
    bpy.data.batch_remove([m for m in viejas if m.users == 0])
    return nuevo


def unir(grupos, nombre_de):
    """Une cada grupo de objetos malla en uno solo. grupos: {clave: [obj, ...]}"""
    resultado = []
    total, ultimo, t_ini = len(grupos), time.time(), time.time()
    log(f"Uniendo {sum(len(v) for v in grupos.values()):,} objetos en {total:,} grupos…")
    for i, (k, obs) in enumerate(grupos.items(), 1):
        if len(obs) > 200 or time.time() - ultimo > 20:
            log(f"  grupo {i}/{total} «{str(k)[:40]}»: {len(obs):,} objetos "
                f"({time.time() - t_ini:.0f} s desde el inicio) {memoria()}")
            ultimo = time.time()
        obs = [o for o in obs if o.type == "MESH"]
        if not obs:
            continue
        if len(obs) == 1:
            obs[0].name = nombre_de(k)
            resultado.append(obs[0])
            continue
        activo = unir_numpy(obs, nombre_de(k))
        activo.name = nombre_de(k)
        activo.data.name = activo.name
        resultado.append(activo)
    return resultado


def decimar(mallas, factor):
    """Decima objeto por objeto: así solo hay una copia evaluada a la vez (con ~16 objetos de
    millones de triángulos, evaluarlos todos juntos duplicaba la memoria)."""
    total, ultimo, t_ini = len(mallas), time.time(), time.time()
    log(f"Decimando {total:,} objetos al {factor:.0%}…")
    for i, ob in enumerate(mallas, 1):
        n0 = len(ob.data.polygons)
        m = ob.modifiers.new("Decimar", "DECIMATE")
        m.ratio = factor
        m.use_collapse_triangulate = True
        ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
        nueva = bpy.data.meshes.new_from_object(ev)
        ob.modifiers.clear()
        vieja = ob.data
        ob.data = nueva
        if vieja.users == 0:
            bpy.data.meshes.remove(vieja)
        if n0 > 200_000 or time.time() - ultimo > 20 or i == total:
            log(f"  decimado {i}/{total}: {n0:,} → {len(nueva.polygons):,} polígonos "
                f"({time.time() - t_ini:.0f} s desde el inicio) {memoria()}")
            ultimo = time.time()


def contar_triangulos(mallas):
    t = 0
    vistos = set()
    for ob in mallas:
        me = ob.data
        if me in vistos:
            continue
        vistos.add(me)
        me.calc_loop_triangles()
        t += len(me.loop_triangles)
    return t


def ajustar_escena(mallas, nombre):
    esc = bpy.context.scene
    esc.unit_settings.system = "METRIC"
    esc.unit_settings.length_unit = "METERS"

    # caja envolvente global (tam_total) y caja "robusta" para encuadrar, que ignora el
    # 2 % de piezas más alejadas en cada eje (elementos sueltos lejos de la planta)
    esquinas = []
    for ob in mallas:
        w = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        esquinas.append([[min(p[k] for p in w) for k in range(3)], [max(p[k] for p in w) for k in range(3)]])
    if esquinas:
        E = np.array(esquinas)                     # (n, 2, 3)
        tam_total = float(np.linalg.norm(E[:, 1].max(axis=0) - E[:, 0].min(axis=0)))
        lo = np.percentile(E[:, 0], 2, axis=0) if len(E) > 20 else E[:, 0].min(axis=0)
        hi = np.percentile(E[:, 1], 98, axis=0) if len(E) > 20 else E[:, 1].max(axis=0)
        mn, mx = Vector(lo.tolist()), Vector(hi.tolist())
    else:
        mn, mx, tam_total = Vector((-10, -10, -10)), Vector((10, 10, 10)), 35.0
    centro = (mn + mx) * 0.5
    tam = max((mx - mn).length, 1.0)

    # mundo gris oscuro (fondo industrial) que no apaga la luz
    mundo = bpy.data.worlds.new("Mundo_Visor") if not esc.world else esc.world
    esc.world = mundo
    mundo.color = (0.05, 0.06, 0.08)
    if mundo.node_tree is None:
        try:
            mundo.use_nodes = True
        except Exception:
            pass
    bg = mundo.node_tree.nodes.get("Background") if mundo.node_tree else None
    if bg:
        bg.inputs[0].default_value = (0.067, 0.094, 0.153, 1.0)  # #111827
        bg.inputs[1].default_value = 1.0

    # sol
    sol_d = bpy.data.lights.new("Sol", "SUN")
    sol_d.energy = 3.0
    sol_d.angle = math.radians(2)
    sol = bpy.data.objects.new("Sol", sol_d)
    sol.rotation_euler = Euler((math.radians(50), 0, math.radians(35)))
    esc.collection.objects.link(sol)

    # cámara encuadrando todo el modelo (vista isométrica alta)
    cam_d = bpy.data.cameras.new("Camara")
    cam_d.clip_start = max(0.05, tam / 20000)
    cam_d.clip_end = max(tam, tam_total) * 10
    cam_d.lens = 35
    cam = bpy.data.objects.new("Camara", cam_d)
    direccion = Vector((1.0, -1.0, 0.75)).normalized()
    cam.location = centro + direccion * tam * 1.3
    cam.rotation_euler = (centro - cam.location).to_track_quat("-Z", "Y").to_euler()
    esc.collection.objects.link(cam)
    esc.camera = cam

    # ventanas 3D: recorte acorde al tamaño del modelo (si no, se "corta" a 1 km)
    for scr in bpy.data.screens:
        for area in scr.areas:
            for sp in area.spaces:
                if sp.type == "VIEW_3D":
                    sp.clip_start = cam_d.clip_start
                    sp.clip_end = cam_d.clip_end
                    sp.shading.type = "SOLID"
                    sp.shading.color_type = "MATERIAL"
                    r3d = sp.region_3d
                    if r3d is not None:
                        r3d.view_location = centro
                        r3d.view_distance = tam * 0.9
                        r3d.view_rotation = Euler(
                            (math.radians(60), 0, math.radians(45))).to_quaternion()
    return centro, max(tam, tam_total)


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------
def main():
    a = leer_argumentos()
    log(f"Blender {bpy.app.version_string}")
    log(f"FBX: {a.fbx} ({os.path.getsize(a.fbx) / 1048576:,.0f} MB)")
    log(f"Salida: {a.salida}")
    verificar_fbx(a.fbx)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    if "io_scene_fbx" not in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_enable(module="io_scene_fbx")

    rec = Recentrador()
    poda = PodaJerarquia() if a.jerarquia == "plana" else None
    restaurar = instalar_recentrador(None if a.sin_recentrar else rec, poda,
                                     fusionar_mats=not a.no_fusionar_materiales)
    antes = set(bpy.data.objects)
    deshacer_enlace = instalar_enlace_rapido()
    try:
        log("Importando FBX (en modelos grandes esto toma varios minutos)…")
        r = bpy.ops.import_scene.fbx(
            filepath=a.fbx,
            use_custom_normals=True,
            use_image_search=False,
            use_anim=False,
            use_custom_props=True,
            ignore_leaf_bones=True,
            global_scale=1.0,
        )
    finally:
        restaurar()
        deshacer_enlace()
    if "FINISHED" not in r:
        raise SystemExit("El importador FBX de Blender no pudo leer el archivo.")

    if poda is not None and poda.con_cizalle:
        log(f"Aviso: {poda.con_cizalle} mallas con cizalle comparten geometría; "
            "su forma puede variar levemente.")
    # conversión de ejes/unidades archivo -> Blender, leída de los marcadores
    conv = None
    marcas = [bpy.data.objects.get(n) for n in MARCADORES]
    if all(marcas):
        conv = [[m.matrix_world.translation[f] / 1000.0 for m in marcas] for f in range(3)]
    bpy.data.batch_remove([m for m in marcas if m is not None])
    nuevos = [o for o in bpy.data.objects if o not in antes]
    mallas = [o for o in nuevos if o.type == "MESH"]
    vacios = [o for o in nuevos if o.type == "EMPTY"]
    log(f"Importado: {len(mallas):,} mallas, {len(vacios):,} nodos vacíos, "
        f"{len(bpy.data.materials):,} materiales. {memoria()}")

    esc = bpy.context.scene
    factor_m = rec.unidad_cm / 100.0
    if rec.modo != "ninguno":
        dx, dy, dz = rec.desfase
        log(f"Recentrado ({rec.modo}): desfase restado = ({dx:,.1f}; {dy:,.1f}; {dz:,.1f}) "
            f"unidades del archivo (1 unidad = {factor_m:g} m).")
        for av in rec.avisos:
            log("  Aviso: " + av)
    else:
        log("Coordenadas cercanas al origen: no fue necesario recentrar."
            if not a.sin_recentrar else "Recentrado desactivado por el usuario.")
    if conv is not None:
        d_bl = [round(sum(conv[f][k] * rec.desfase[k] for k in range(3)), 6) for f in range(3)]
    else:
        d_bl = [rec.desfase[k] * factor_m for k in range(3)]
    esc["desfase_blender_m"] = d_bl
    esc["desfase_archivo"] = list(rec.desfase)
    esc["desfase_archivo_unidad_m"] = factor_m
    esc["desfase_nota"] = (
        "Coordenada real (ejes Blender, m) = coordenada en Blender + desfase_blender_m. "
        "desfase_archivo = el mismo desfase en ejes y unidades del FBX original.")
    if rec.modo != "ninguno":
        log("Desfase en ejes de Blender (m): ({:,.2f}; {:,.2f}; {:,.2f}) — guardado en la escena "
            "como «desfase_blender_m».".format(*d_bl))
    esc["origen_fbx"] = os.path.basename(a.fbx)

    # ruta y TAG por malla (antes de tocar la jerarquía)
    tags = {}
    for ob in mallas:
        if "ruta" in ob:            # ya viene de la poda previa
            tag = ob.get("tag") or None
        else:
            ruta, tag = ruta_y_tag(ob)
            ob["ruta"] = ruta
            if tag:
                ob["tag"] = tag
        tags[ob] = tag
    # Navisworks llama "Geometry" a todas las mallas: se usa el nombre del elemento padre
    renombradas = poda.renombradas if poda is not None else 0
    for ob in mallas:
        base = ob.name.split(".")[0].strip()
        if base.lower() in ("geometry", "mesh", "object", "") and ob.get("ruta"):
            ob.name = ob["ruta"].split(" / ")[-1][:60]
            renombradas += 1
    if renombradas:
        log(f"Mallas renombradas con el nombre de su elemento: {renombradas:,}.")
    n_tag = len({t for t in tags.values() if t})
    log(f"TAG detectados: {n_tag:,} (mallas con TAG: {sum(1 for t in tags.values() if t):,}).")

    # materiales
    m_antes, m_despues = fusionar_materiales(mallas)
    log(f"Materiales fusionados por color: {m_antes:,} → {m_despues:,}. {memoria()}")

    # jerarquía
    if a.jerarquia == "plana":
        for ob in mallas:
            if ob.parent is not None:
                mw = ob.matrix_world.copy()
                ob.parent = None
                ob.matrix_world = mw
        bpy.data.batch_remove(vacios)
        log(f"Jerarquía aplanada: {len(vacios):,} nodos vacíos eliminados.")

    # unión opcional
    if a.unir != "no":
        if a.jerarquia == "mantener":
            log("Aviso: --unir requiere jerarquía plana; se aplana para unir.")
            for ob in mallas:
                if ob.parent is not None:
                    mw = ob.matrix_world.copy()
                    ob.parent = None
                    ob.matrix_world = mw
            bpy.data.batch_remove([o for o in vacios if o.name in bpy.data.objects])
        grupos = {}
        if a.unir == "tag":
            for ob in mallas:
                grupos.setdefault(tags[ob] or "SIN_TAG", []).append(ob)
            mallas = unir(grupos, lambda k: k)
            for ob in mallas:
                ob["tag"] = ob.name if ob.name != "SIN_TAG" else ""
                tags[ob] = ob.name if ob.name != "SIN_TAG" else None
        else:
            for ob in mallas:
                mat = ob.material_slots[0].material if ob.material_slots else None
                grupos.setdefault(mat.name if mat else "SIN_MATERIAL", []).append(ob)
            mallas = unir(grupos, lambda k: "UNION_" + k)
            tags = {ob: None for ob in mallas}
        log(f"Mallas unidas por {a.unir}: {len(mallas):,} objetos. {memoria()}")

    # decimación opcional
    if a.decimar:
        t_antes = contar_triangulos(mallas)
        decimar(mallas, a.decimar)
        log(f"Decimado al {a.decimar:.0%}: {t_antes:,} → {contar_triangulos(mallas):,} triángulos. {memoria()}")

    # colecciones
    nombre = os.path.splitext(os.path.basename(a.fbx))[0].strip().lstrip(",").strip()
    col_raiz = bpy.data.collections.new(nombre[:60])
    esc.collection.children.link(col_raiz)
    if a.colecciones == "tag" and a.jerarquia == "plana":
        cols = {}
        for ob in mallas:
            k = tags.get(ob) or "SIN_TAG"
            if k not in cols:
                cols[k] = bpy.data.collections.new(k)
            for c in list(ob.users_collection):
                c.objects.unlink(ob)
            cols[k].objects.link(ob)
        for k in sorted(cols, key=lambda s: (s == "SIN_TAG", s)):
            col_raiz.children.link(cols[k])
        log(f"Colecciones por TAG: {len(cols):,}.")
    else:
        for ob in [o for o in bpy.data.objects if o in set(nuevos) or o in set(mallas)]:
            if ob.name not in bpy.data.objects:
                continue
            for c in list(ob.users_collection):
                c.objects.unlink(ob)
            col_raiz.objects.link(ob)
    # colecciones vacías que dejó el importador
    for c in list(bpy.data.collections):
        if c is not col_raiz and not c.all_objects and c.name not in [x.name for x in col_raiz.children]:
            bpy.data.collections.remove(c)

    tri = contar_triangulos(mallas)
    centro, tam = ajustar_escena(mallas, nombre)
    log(f"Escena: {len(mallas):,} objetos, {tri:,} triángulos, tamaño ≈ {tam:,.0f} m "
        f"(centro {centro.x:,.1f}; {centro.y:,.1f}; {centro.z:,.1f}).")

    os.makedirs(os.path.dirname(a.salida), exist_ok=True)
    bpy.data.orphans_purge(do_recursive=True)
    bpy.ops.wm.save_as_mainfile(filepath=a.salida, compress=not a.sin_comprimir, check_existing=False)
    log(f"Guardado: {a.salida} ({os.path.getsize(a.salida) / 1048576:,.1f} MB). {memoria()}")

    with open(os.path.splitext(a.salida)[0] + ".informe.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(INFORME) + "\n")
    log("Listo.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # mensaje claro en la ventana del .bat
        import traceback
        traceback.print_exc()
        print(f"\nERROR: {e}", flush=True)
        sys.exit(1)
