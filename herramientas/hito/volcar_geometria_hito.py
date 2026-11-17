# Vuelca la geometria de hito_realista.blend (coordenadas de mundo, ejes Blender) a archivos .npz por objeto,
# para analizarla con Python (componentes sueltos, holguras de camara).
# Uso: blender -b hito_realista.blend --python volcar_geometria_hito.py -- <carpeta_salida>
import bpy, sys, os, json, time
import numpy as np
sal = sys.argv[sys.argv.index('--')+1:][0]
os.makedirs(sal, exist_ok=True)
t0 = time.time(); ind = {}
for o in bpy.context.scene.objects:
    if o.type != 'MESH' or o.name == 'SUELO_EXTENSO':
        continue
    me = o.data
    me.calc_loop_triangles()
    nv, nt = len(me.vertices), len(me.loop_triangles)
    co = np.empty(nv*3, np.float64); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    M = np.array(o.matrix_world, np.float64)
    w = co @ M[:3, :3].T + M[:3, 3]
    tri = np.empty(nt*3, np.int32); me.loop_triangles.foreach_get('vertices', tri)
    mat = o.material_slots[0].material.name if o.material_slots and o.material_slots[0].material else ''
    np.savez(os.path.join(sal, o.name + '.npz'), v=w.astype(np.float32), t=tri.reshape(-1, 3))
    ind[o.name] = {'material': mat, 'vertices': nv, 'triangulos': nt}
    print(f'[volcar {time.time()-t0:5.0f} s] {o.name}: {nv:,} v, {nt:,} tri', flush=True)
json.dump(ind, open(os.path.join(sal, 'indice.json'), 'w'), indent=1)
print('[volcar] listo', flush=True)
