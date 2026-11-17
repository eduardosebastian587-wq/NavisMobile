#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generar_puntos_de_vista_navisworks.py
Convierte el recorrido de cámara de «ciclo-completo» (animaciones.json) en puntos de vista de Navisworks:
  · Puntos_de_vista_ciclo.xml     importable en  Puntos de vista guardados › clic derecho › Importar puntos de vista
  · Camara_ciclo_tabla.html/.csv  mismos datos como tabla (Posición y «Mirar a») para el cuadro «Editar punto de vista»
Uso:  python generar_puntos_de_vista_navisworks.py <animaciones.json> <carpeta_salida> [paso_s=3] [E N Z del desfase]
Convención de cámara de Navisworks (documentada en el blog de Autodesk APS «Load XML of Navisworks Saved Viewpoints…»):
  cuaternión a,b,c,d = x,y,z,w · la cámara mira por su eje −Z local y su «arriba» es +Y local.
"""
import sys, os, json, math, csv, uuid, datetime
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generar_capa_animacion_navisworks as G

GT_DEFECTO = [190292.989, 4454840.976, 0.0]

def catmull_centripeta(P, s, f):
    """Segmento s (0..n-2), fracción f: Catmull-Rom centrípeto con los extremos extrapolados, igual que THREE.CatmullRomCurve3."""
    n = len(P)
    p1, p2 = P[s], P[s + 1]
    p0 = P[s - 1] if s > 0 else 2 * P[0] - P[1]
    p3 = P[s + 2] if s + 2 < n else 2 * P[-1] - P[-2]
    d = lambda a, b: max(1e-8, np.linalg.norm(a - b) ** 0.5)
    t0, t1, t2, t3 = 0.0, d(p0, p1), 0, 0
    t2 = t1 + d(p1, p2); t3 = t2 + d(p2, p3)
    t = t1 + (t2 - t1) * f
    A1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
    A2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
    A3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
    B1 = (t2 - t) / (t2 - t0) * A1 + (t - t0) / (t2 - t0) * A2
    B2 = (t3 - t) / (t3 - t1) * A2 + (t - t1) / (t3 - t1) * A3
    return (t2 - t) / (t2 - t1) * B1 + (t - t1) / (t2 - t1) * B2

def muestrear(claves_pos, claves_mira, t):
    ts = [c[0] for c in claves_pos]; P = [np.array(c[1], float) for c in claves_pos]
    s = 0
    while s < len(ts) - 2 and t > ts[s + 1]: s += 1
    f = min(1, max(0, (t - ts[s]) / (ts[s + 1] - ts[s])))
    pos = catmull_centripeta(P, s, f)
    tm = [c[0] for c in claves_mira]; M = [np.array(c[1], float) for c in claves_mira]
    k = 0
    while k < len(tm) - 2 and t > tm[k + 1]: k += 1
    g = min(1, max(0, (t - tm[k]) / (tm[k + 1] - tm[k])))
    return pos, M[k] + (M[k + 1] - M[k]) * g            # «mira» es lineal en el visor

def cuaternion(pos, objetivo, arriba=(0, 0, 1)):
    f = objetivo - pos; f /= np.linalg.norm(f)
    r = np.cross(f, np.array(arriba, float)); r /= np.linalg.norm(r)
    u = np.cross(r, f)
    R = np.stack([r, u, -f], 1)                           # columnas = ejes locales (X der., Y arriba, −Z adelante)
    t = np.trace(R)
    if t > 0:
        S = math.sqrt(t + 1) * 2; w = S / 4; x = (R[2, 1] - R[1, 2]) / S; y = (R[0, 2] - R[2, 0]) / S; z = (R[1, 0] - R[0, 1]) / S
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        S = math.sqrt(1 + R[0, 0] - R[1, 1] - R[2, 2]) * 2; w = (R[2, 1] - R[1, 2]) / S; x = S / 4; y = (R[0, 1] + R[1, 0]) / S; z = (R[0, 2] + R[2, 0]) / S
    elif R[1, 1] > R[2, 2]:
        S = math.sqrt(1 + R[1, 1] - R[0, 0] - R[2, 2]) * 2; w = (R[0, 2] - R[2, 0]) / S; x = (R[0, 1] + R[1, 0]) / S; y = S / 4; z = (R[1, 2] + R[2, 1]) / S
    else:
        S = math.sqrt(1 + R[2, 2] - R[0, 0] - R[1, 1]) * 2; w = (R[1, 0] - R[0, 1]) / S; x = (R[0, 2] + R[2, 0]) / S; y = (R[1, 2] + R[2, 1]) / S; z = S / 4
    q = np.array([x, y, z, w]); return q / np.linalg.norm(q)

def adelante_desde_q(q):
    x, y, z, w = q
    return np.array([-2 * (x * z + w * y), -2 * (y * z - w * x), -1 + 2 * (x * x + y * y)])   # fórmulas del blog de Autodesk

def main():
    if len(sys.argv) < 3: print(__doc__); sys.exit(1)
    ruta_json, carpeta = sys.argv[1:3]; paso = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
    gt = [float(x) for x in sys.argv[4:7]] if len(sys.argv) >= 7 else GT_DEFECTO
    os.makedirs(carpeta, exist_ok=True)
    anim = json.load(open(ruta_json, encoding='utf-8'))
    ciclo = next(a for a in anim['animaciones'] if a['id'] == 'ciclo-completo')
    pp = next(p for p in ciclo['pistas'] if p['objetivo'] == 'camara' and p['propiedad'] == 'posicion')['claves']
    pm = next(p for p in ciclo['pistas'] if p['objetivo'] == 'camara' and p['propiedad'] == 'mira')['claves']
    dur = float(ciclo['duracion'])
    tiempos = sorted(set([round(i * paso, 3) for i in range(int(dur / paso) + 1)] + [float(c[0]) for c in pp] + [dur]))
    filas, vistas = [], []
    for k, t in enumerate(tiempos):
        pos_v, mira_v = muestrear(pp, pm, t)
        pa = np.array(G.abs_nav(pos_v, gt)); ma = np.array(G.abs_nav(mira_v, gt))
        q = cuaternion(pa, ma); fw = adelante_desde_q(q); fw_ok = (ma - pa) / np.linalg.norm(ma - pa)
        assert np.allclose(fw, fw_ok, atol=1e-6), 'La cámara no mira hacia el objetivo'
        clave = any(abs(t - float(c[0])) < 1e-6 for c in pp)
        nombre = f'Ciclo {k+1:02d} · t={t:g} s' + (' ◆' if clave else '')
        filas.append(dict(n=k + 1, t=t, clave=clave, nombre=nombre, pos=pa.tolist(), mira=ma.tolist(), q=q.tolist(), dist=float(np.linalg.norm(ma - pa))))
        vistas.append((nombre, pa, q, float(np.linalg.norm(ma - pa))))
    def view(nombre, pa, q, dist):
        # Estructura y valores de enumeración tomados de un XML real de Navisworks (blog Autodesk APS) y del mensaje de validación del esquema.
        return (f'<view name="{nombre}" guid="{uuid.uuid4()}"><viewpoint tool="navigator_examine" render="shaded" lighting="user" focal="{dist:.10f}" linear="4.0000000000" angular="0.7853981634">'
                f'<camera projection="persp" near="0.5000000000" far="3000.0000000000" aspect="1.9101796407" height="0.7853981634"><position><pos3f x="{pa[0]:.10f}" y="{pa[1]:.10f}" z="{pa[2]:.10f}"/></position>'
                f'<rotation><quaternion a="{q[0]:.10f}" b="{q[1]:.10f}" c="{q[2]:.10f}" d="{q[3]:.10f}"/></rotation></camera>'
                f'<viewer radius="0.2500000000" height="1.7000000000" actual_height="1.7000000000" eye_height="0.1500000000" avatar="dummy" camera_mode="first" first_to_third_angle="0.2617993878" first_to_third_distance="4.0000000000" first_to_third_param="1.0000000000" first_to_third_correction="1" collision_detection="0" auto_crouch="0" gravity="0" gravity_value="9.8000000000" terminal_velocity="50.0000000000"/>'
                f'<up><vec3f x="0.0000000000" y="0.0000000000" z="1.0000000000"/></up></viewpoint></view>')
    xml = ('<?xml version="1.0" encoding="UTF-8" ?>\n<exchange xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
           'xsi:noNamespaceSchemaLocation="http://download.autodesk.com/us/navisworks/schemas/nw-exchange-12.0.xsd" units="m" filename="" filepath="">'
           f'<viewpoints><viewfolder name="CAMARA CICLO AREA 1313" guid="{uuid.uuid4()}">' + ''.join(view(*v) for v in vistas) + '</viewfolder></viewpoints></exchange>')
    open(os.path.join(carpeta, 'Puntos_de_vista_ciclo.xml'), 'w', encoding='utf-8').write(xml)
    with open(os.path.join(carpeta, 'Camara_ciclo_tabla.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f, delimiter=';'); w.writerow(['N', 'Nombre', 't (s)', 'Clave', 'Pos E', 'Pos N', 'Pos Z', 'Mirar E', 'Mirar N', 'Mirar Z'])
        for r in filas: w.writerow([r['n'], r['nombre'], r['t'], 'sí' if r['clave'] else '', *[f'{x:.3f}'.replace('.', ',') for x in r['pos']], *[f'{x:.3f}'.replace('.', ',') for x in r['mira']]])
    json.dump(filas, open(os.path.join(carpeta, 'camara_ciclo.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(len(filas), 'puntos de vista;', sum(r['clave'] for r in filas), 'son claves del recorrido')

if __name__ == '__main__': main()
