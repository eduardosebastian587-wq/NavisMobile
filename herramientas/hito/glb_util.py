import json, struct, numpy as np, DracoPy
def cargar(ruta='/home/claude/datos/hito_web.glb'):
    b=open(ruta,'rb').read(); L=struct.unpack('<I',b[12:16])[0]; J=json.loads(b[20:20+L]); bin0=20+L+8; BV=J['bufferViews']
    def qrot(q,v):
        x,y,z,w=q; u=np.array([x,y,z]); return v+2*np.cross(u,np.cross(u,v)+w*v)
    out=[]
    for k,nd in enumerate(J['nodes']):
        if 'mesh' not in nd: continue
        for pr in J['meshes'][nd['mesh']]['primitives']:
            bv=BV[pr['extensions']['KHR_draco_mesh_compression']['bufferView']]; o=bin0+bv.get('byteOffset',0)
            m=DracoPy.decode(b[o:o+bv['byteLength']]); v=np.asarray(m.points,np.float64); t=np.asarray(m.faces,np.int64).reshape(-1,3)
            v=v*np.array(nd.get('scale',[1,1,1])); v=qrot(nd.get('rotation',[0,0,0,1]),v)+np.array(nd.get('translation',[0,0,0]))
            v=np.stack([v[:,0],-v[:,2],v[:,1]],1)      # Blender
            out.append(dict(nodo=k,nombre=nd['name'],mat=pr.get('material'),v=v,t=t))
    return J,out
