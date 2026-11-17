# Exporta hito.blend -> GLB liviano para el visor web (decima por objeto).
# Uso: blender -b hito.blend --python exportar_hito_glb.py -- <salida.glb> [triangulos_objetivo_millones=4.5]
import bpy, sys, time
a = sys.argv[sys.argv.index('--')+1:]
salida = a[0]; objetivo = float(a[1])*1e6 if len(a) > 1 else 4.5e6
t0 = time.time()
mallas = [o for o in bpy.data.objects if o.type == 'MESH']
for o in bpy.data.objects:
    o.select_set(False)
total = sum(len(o.data.polygons) for o in mallas)   # aprox. triángulos (caras)
ratio = min(1.0, objetivo/max(total, 1))
print(f'[hito] mallas={len(mallas)} caras={total:,} ratio={ratio:.3f}', flush=True)
for o in mallas:
    o.select_set(True)
    if ratio < 1.0:
        m = o.modifiers.new('dec', 'DECIMATE'); m.decimate_type = 'COLLAPSE'; m.ratio = ratio
bpy.ops.export_scene.gltf(filepath=salida, export_format='GLB', use_selection=True,
    export_apply=True, export_yup=True, export_cameras=False, export_lights=False,
    export_extras=False, export_animations=False)
print(f'[hito] listo en {time.time()-t0:.0f} s -> {salida}', flush=True)
