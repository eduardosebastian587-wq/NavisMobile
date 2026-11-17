import sys, json, struct, time, numpy as np, DracoPy
from scipy import ndimage
glb, salida = sys.argv[1], sys.argv[2]
t0=time.time(); CEL=0.75; SUELO=float(sys.argv[3]) if len(sys.argv)>3 else -47.6
lo=np.array([-350.0,-270.0,-50.6]); dims=np.array([810,570,180])
b=open(glb,'rb').read(); L=struct.unpack('<I',b[12:16])[0]; J=json.loads(b[20:20+L])
bin0=20+L+8; BV=J['bufferViews']
def qrot(q,v):
    x,y,z,w=q; u=np.array([x,y,z]); return v+2*np.cross(u, np.cross(u,v)+w*v)
occ=np.zeros(dims,bool)
def marcar(P):
    c=np.floor((P-lo)/CEL).astype(np.int32); ok=np.all((c>=0)&(c<dims),1); c=c[ok]; occ[c[:,0],c[:,1],c[:,2]]=True
ntri=0
for nd in J['nodes']:
    if 'mesh' not in nd: continue
    for pr in J['meshes'][nd['mesh']]['primitives']:
        bv=BV[pr['extensions']['KHR_draco_mesh_compression']['bufferView']]
        o=bin0+bv.get('byteOffset',0); m=DracoPy.decode(b[o:o+bv['byteLength']])
        v=np.asarray(m.points,np.float64); t=np.asarray(m.faces,np.int64).reshape(-1,3)
        v=v*np.array(nd.get('scale',[1,1,1])); v=qrot(nd.get('rotation',[0,0,0,1]),v)+np.array(nd.get('translation',[0,0,0]))
        v=np.stack([v[:,0],-v[:,2],v[:,1]],1)
        ntri+=len(t); marcar(v)
        p0,p1,p2=v[t[:,0]],v[t[:,1]],v[t[:,2]]
        lado=np.maximum(np.maximum(np.linalg.norm(p1-p0,axis=1),np.linalg.norm(p2-p1,axis=1)),np.linalg.norm(p0-p2,axis=1))
        nivel=np.clip(np.ceil(lado/(CEL*0.5)).astype(int),1,512)
        for k in np.unique(nivel[nivel>1]):
            sel=np.nonzero(nivel==k)[0]; ii,jj=np.meshgrid(np.arange(k+1),np.arange(k+1),indexing='ij'); mm=(ii+jj)<=k
            u=(ii[mm]/k)[None,:,None]; w=(jj[mm]/k)[None,:,None]; paso=max(1,2_000_000//u.shape[1])
            for s in range(0,sel.size,paso):
                ss=sel[s:s+paso]; marcar((p0[ss][:,None]*(1-u-w)+p1[ss][:,None]*u+p2[ss][:,None]*w).reshape(-1,3))
        del v,t,p0,p1,p2
occ[:,:,:int(np.floor((SUELO-lo[2])/CEL))+1]=True
d=ndimage.distance_transform_edt(~occ,sampling=CEL); del occ
np.save(salida,d.astype(np.float16)); print(f'listo {time.time()-t0:.0f} s; tri {ntri:,}; max {d.max():.1f} m')
