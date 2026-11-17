# Exporta la escena del Hito a GLB para el visor web.
# - Usa los materiales PBR del video (color, metal, rugosidad, alfa); el visor agrega las texturas procedurales.
# - Presupuesto de triangulos: objetos chicos (<= UMBRAL) intactos; solo se decimán los grandes, misma razon.
# - Compresion Draco (posiciones 16 bits ~1 cm en 560 m).
# - No exporta camara, luces ni SUELO_EXTENSO. Los objetos de la coleccion "_SUELTOS_EXCLUIDOS"
#   (separar_sueltos_hito.py) se exportan solo con --sueltos, a un archivo aparte.
# Uso: blender -b hito_realista_limpio.blend --python exportar_hito_visor.py -- <salida.glb> [millones=13] [--sueltos]
import bpy, sys, time, os
a = sys.argv[sys.argv.index('--')+1:]
solo_sueltos = '--sueltos' in a
a = [x for x in a if x != '--sueltos']
salida = a[0]
objetivo = float(a[1])*1e6 if len(a) > 1 else 13e6
UMBRAL = 400_000
t0 = time.time()
def log(*x): print('[hito-visor %5.0f s]' % (time.time()-t0), *x, flush=True)
excl = bpy.data.collections.get('_SUELTOS_EXCLUIDOS')
en_excl = set(excl.all_objects) if excl else set()
if excl:                                   # la coleccion esta excluida del view layer: se incluye para poder seleccionar
    for vl in bpy.context.scene.view_layers:
        lc = vl.layer_collection.children.get(excl.name)
        if lc: lc.exclude = False
mallas = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.name != 'SUELO_EXTENSO'
          and ((o in en_excl) == solo_sueltos)]
if not mallas:
    log('no hay mallas para exportar'); sys.exit(0)
tri = {}
for o in mallas:
    o.data.calc_loop_triangles(); tri[o.name] = len(o.data.loop_triangles)
total = sum(tri.values())
chicos = sum(v for v in tri.values() if v <= UMBRAL); grandes = total - chicos
ratio = 1.0 if total <= objetivo else max(0.15, min(1.0, (objetivo - chicos) / max(grandes, 1)))
log(f'{"SUELTOS " if solo_sueltos else ""}mallas={len(mallas)} triangulos={total:,} ratio_grandes={ratio:.3f}')
for o in bpy.data.objects: o.select_set(False)
for o in mallas:
    o.select_set(True)
    if tri[o.name] > UMBRAL and ratio < 1.0:
        m = o.modifiers.new('dec_visor', 'DECIMATE'); m.decimate_type = 'COLLAPSE'; m.ratio = ratio; m.use_collapse_triangulate = True
bpy.ops.export_scene.gltf(filepath=salida, export_format='GLB', use_selection=True, export_apply=True, export_yup=True,
    export_cameras=False, export_lights=False, export_extras=False, export_animations=False, export_texcoords=False,
    export_normals=True, export_materials='EXPORT',
    export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
    export_draco_position_quantization=16, export_draco_normal_quantization=10)
log(f'listo -> {salida} ({os.path.getsize(salida)/1e6:.1f} MB)')
