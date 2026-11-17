# Extrae de hito_realista.blend (escena del video) todo lo que el visor web debe reproducir:
# materiales PBR finales, cielo, sol, exposicion/tono, camara (lente) y la trayectoria
# de camara y objetivo cuadro a cuadro (1..360), mas triangulos por objeto.
# Uso: blender -b hito_realista.blend --python extraer_escena_hito.py -- <salida.json>
import bpy, sys, json, math
a = sys.argv[sys.argv.index('--')+1:]
salida = a[0]
S = bpy.context.scene
def srgb(c):
    c = max(0.0, min(1.0, c))
    return 12.92*c if c <= 0.0031308 else 1.055*c**(1/2.4)-0.055
def hexc(v): return '%02X%02X%02X' % tuple(round(srgb(x)*255) for x in v[:3])
def b2t(v): return [v[0], v[2], -v[1]]           # Blender (x,y,z) -> glTF/Three (x, z, -y)
R = {'materiales': {}, 'objetos': [], 'camara': {}, 'sol': {}, 'cielo': {}, 'vista': {}}
for m in bpy.data.materials:
    d = {'usuarios': m.users}
    if m.use_nodes and m.node_tree:
        for n in m.node_tree.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                d['color'] = hexc(n.inputs['Base Color'].default_value)
                d['metal'] = round(n.inputs['Metallic'].default_value, 3)
                d['rugosidad'] = round(n.inputs['Roughness'].default_value, 3)
                d['alfa'] = round(n.inputs['Alpha'].default_value, 3)
                d['color_enlazado'] = n.inputs['Base Color'].is_linked
            elif n.type == 'VALTORGB':
                d['rampa'] = [hexc(e.color) for e in n.color_ramp.elements]
            elif n.type == 'TEX_NOISE':
                d.setdefault('ruido', []).append({'escala': n.inputs['Scale'].default_value, 'detalle': n.inputs['Detail'].default_value})
            elif n.type == 'BUMP':
                d['relieve'] = n.inputs['Strength'].default_value
    try: d['metodo'] = m.surface_render_method
    except Exception: pass
    R['materiales'][m.name] = d
for o in bpy.data.objects:
    e = {'nombre': o.name, 'tipo': o.type}
    if o.type == 'MESH':
        me = o.data
        me.calc_loop_triangles()
        e['triangulos'] = len(me.loop_triangles)
        e['materiales'] = [s.material.name if s.material else None for s in o.material_slots]
        e['dims'] = [round(x, 2) for x in o.dimensions]
        e['loc'] = [round(x, 2) for x in o.location]
    R['objetos'].append(e)
co = S.camera
R['camara'] = {'nombre': co.name, 'lente_mm': co.data.lens, 'sensor_mm': co.data.sensor_width,
               'ajuste_sensor': co.data.sensor_fit, 'clip': [co.data.clip_start, co.data.clip_end]}
R['vista'] = {'transformacion': S.view_settings.view_transform, 'look': S.view_settings.look,
              'exposicion': S.view_settings.exposure, 'gamma': S.view_settings.gamma,
              'resolucion': [S.render.resolution_x, S.render.resolution_y], 'fps': S.render.fps,
              'cuadros': [S.frame_start, S.frame_end], 'motor': S.render.engine}
R['soles'] = []
for o in S.objects:
    if o.type == 'LIGHT' and o.data.type == 'SUN' and not o.hide_render:
        q = o.matrix_world.to_3x3() @ __import__('mathutils').Vector((0, 0, -1))
        R['soles'].append({'nombre': o.name, 'energia': o.data.energy, 'color': hexc(o.data.color),
                           'hacia_sol_three': [round(-x, 5) for x in b2t(list(q))]})
for o in S.objects:
    if o.type == 'MESH' and o.name == 'SUELO_EXTENSO':
        R['suelo_extenso'] = {'y_three': o.location.z, 'lado_m': max(o.dimensions[0], o.dimensions[1])}
for o in bpy.data.objects:
    if o.type == 'LIGHT':
        q = o.matrix_world.to_3x3() @ __import__('mathutils').Vector((0, 0, -1))
        R['sol'] = {'nombre': o.name, 'tipo': o.data.type, 'energia': o.data.energy,
                    'color': hexc(o.data.color), 'angulo_deg': math.degrees(getattr(o.data, 'angle', 0)),
                    'direccion_luz_three': b2t(list(q))}
w = S.world
if w and w.use_nodes:
    for n in w.node_tree.nodes:
        if n.type == 'TEX_SKY':
            R['cielo'] = {k: (math.degrees(getattr(n, k)) if 'elevation' in k or 'rotation' in k else getattr(n, k))
                          for k in ('sky_type', 'sun_elevation', 'sun_rotation', 'sun_disc', 'air_density', 'aerosol_density')
                          if hasattr(n, k)}
        if n.type == 'BACKGROUND':
            R['cielo']['fuerza'] = n.inputs['Strength'].default_value
try: R['desfase_blender_m'] = list(S['desfase_blender_m'])
except Exception: pass
tg = bpy.data.objects.get('OBJETIVO')
tray = []
for f in range(S.frame_start, S.frame_end+1):
    S.frame_set(f)
    p = co.matrix_world.translation
    t = tg.matrix_world.translation if tg else None
    tray.append([f] + [round(x, 3) for x in b2t(p)] + ([round(x, 3) for x in b2t(t)] if t else []))
R['trayectoria_three'] = tray   # [cuadro, cx, cy, cz, ox, oy, oz] en ejes Three (Y arriba)
json.dump(R, open(salida, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('[extraer] listo ->', salida, flush=True)
