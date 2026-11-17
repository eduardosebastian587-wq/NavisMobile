# Separa los elementos sueltos (mascaras de detectar_sueltos_hito.py) de hito_realista.blend:
#   - se mueven (no se borran) a la coleccion "_SUELTOS_EXCLUIDOS", excluida del render y de la exportacion;
#   - se guarda hito_realista_limpio.blend (el .blend del video queda intacto);
#   - opcional: renders de control (Workbench) con los sueltos en rojo.
# Uso: blender -b hito_realista.blend --python separar_sueltos_hito.py -- <mascaras.npz> <salida.blend> [carpeta_renders]
import bpy, bmesh, sys, os, time
import numpy as np
from mathutils import Vector
a = sys.argv[sys.argv.index('--')+1:]
masc = np.load(a[0]); salida = a[1]; carp_r = a[2] if len(a) > 2 else None
S = bpy.context.scene; t0 = time.time()
def log(*x): print(f'[separar {time.time()-t0:5.0f} s]', *x, flush=True)
col = bpy.data.collections.new('_SUELTOS_EXCLUIDOS'); S.collection.children.link(col)
quitados = 0; nuevos = []
for nombre in masc.files:
    o = bpy.data.objects.get(nombre)
    if o is None: continue
    m = masc[nombre]
    if not m.any(): continue
    me = o.data; me.calc_loop_triangles()
    nt = len(me.loop_triangles)
    assert nt == m.size, (nombre, nt, m.size)
    pidx = np.empty(nt, np.int32); me.loop_triangles.foreach_get('polygon_index', pidx)
    sel = np.zeros(len(me.polygons), bool); sel[pidx[m]] = True
    me.polygons.foreach_set('select', sel)
    for x in bpy.data.objects: x.select_set(False)
    bpy.context.view_layer.objects.active = o; o.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_mode(type='FACE')
    bpy.ops.object.mode_set(mode='OBJECT'); me.polygons.foreach_set('select', sel)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.separate(type='SELECTED'); bpy.ops.object.mode_set(mode='OBJECT')
    for x in bpy.context.selected_objects:
        if x != o:
            x.name = 'SUELTO_' + nombre
            for c in list(x.users_collection): c.objects.unlink(x)
            col.objects.link(x); nuevos.append(x)
    quitados += int(m.sum()); log(f'{nombre}: {int(m.sum()):,} triangulos separados')
log(f'total separado: {quitados:,} triangulos en {len(nuevos)} objetos')

if carp_r:
    os.makedirs(carp_r, exist_ok=True)
    rojo = bpy.data.materials.new('CONTROL_ROJO'); rojo.diffuse_color = (1, 0.02, 0.02, 1)
    S.render.engine = 'BLENDER_WORKBENCH'
    sh = S.display.shading; sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_shadows = False
    sh.show_cavity = True
    S.render.resolution_x, S.render.resolution_y = 1600, 900
    for x in nuevos:
        x.data.materials.clear(); x.data.materials.append(rojo)
    camd = bpy.data.cameras.new('cam_control'); cam = bpy.data.objects.new('cam_control', camd); S.collection.objects.link(cam); S.camera = cam
    terr = bpy.data.objects.get('SUELO_EXTENSO')
    if terr: terr.hide_render = True
    import json
    vistas = [('general_planta', 'ORTHO', (20, -20, 400), (20, -20, -40), 600)]
    rs = json.load(open(os.path.join(os.path.dirname(a[0]), 'sueltos.json'), encoding='utf-8'))['grupos_detalle']
    for k, g in enumerate(rs[:8]):                     # acercamiento a los 8 grupos sueltos mas grandes
        c = Vector([(p + q) / 2 for p, q in zip(g['min'], g['max'])])
        r = max(max(g['tam']), 2.0) * 1.6 + 6
        vistas.append((f'grupo_{k+1:02d}', 'PERSP', tuple(c + Vector((-0.75, -0.55, 0.55)).normalized() * r), tuple(c), 0))
    ocultos = []
    for o in bpy.data.objects:                         # el domo y los translucidos no tapan la evidencia
        if o.type == 'MESH' and ('_A' in o.name.split('UNION_MAT_')[-1] or o.name == 'SUELO_EXTENSO'):
            if not o.name.startswith('SUELTO_') and not o.hide_render: o.hide_render = True; ocultos.append(o)
    for nom, tipo, p, mira, esc in vistas:
        camd.type = tipo
        if tipo == 'ORTHO': camd.ortho_scale = esc
        else: camd.lens = 24
        cam.location = p
        cam.rotation_euler = (Vector(mira) - Vector(p)).to_track_quat('-Z', 'Y').to_euler()
        camd.clip_end = 5000
        S.render.filepath = os.path.join(carp_r, nom + '.png'); bpy.ops.render.render(write_still=True)
        log('render', nom)
    for x in nuevos:                      # se devuelven los materiales originales en el archivo guardado
        x.data.materials.clear()
        base = bpy.data.objects.get(x.name.replace('SUELTO_', '').split('.')[0])
        if base and base.data.materials: x.data.materials.append(base.data.materials[0])
    for o in ocultos: o.hide_render = False
    bpy.data.objects.remove(cam); bpy.data.cameras.remove(camd)
    if terr: terr.hide_render = False
    S.render.engine = 'BLENDER_EEVEE'
for vl in S.view_layers:
    lc = vl.layer_collection.children.get(col.name)
    if lc: lc.exclude = True
bpy.ops.wm.save_as_mainfile(filepath=salida)
log('guardado', salida)
