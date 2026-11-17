import sys, json, struct, time, numpy as np, DracoPy
glb = sys.argv[1]; b = open(glb, 'rb').read(); L = struct.unpack('<I', b[12:16])[0]; J = json.loads(b[20:20+L]); bin0 = 20 + L + 8; BV = J['bufferViews']
tot = dup = deg = 0; t0 = time.time()
for nd in J['nodes']:
    if 'mesh' not in nd: continue
    for pr in J['meshes'][nd['mesh']]['primitives']:
        bv = BV[pr['extensions']['KHR_draco_mesh_compression']['bufferView']]; o = bin0 + bv.get('byteOffset', 0)
        m = DracoPy.decode(b[o:o+bv['byteLength']]); v = np.asarray(m.points, np.float64); t = np.asarray(m.faces, np.int64).reshape(-1, 3)
        q = np.round(v * 500).astype(np.int64)                       # rejilla de 2 mm
        _, inv = np.unique(q, axis=0, return_inverse=True); inv = inv.reshape(-1); tt = inv[t]
        d0 = (tt[:, 0] == tt[:, 1]) | (tt[:, 1] == tt[:, 2]) | (tt[:, 0] == tt[:, 2])
        s = np.sort(tt[~d0], axis=1); k = s[:, 0] * (inv.max() + 1) ** 2 + s[:, 1] * (inv.max() + 1) + s[:, 2] if inv.max() < 2e6 else None
        if k is None: u = np.unique(s, axis=0).shape[0]
        else: u = np.unique(k).shape[0]
        n = len(t); dd = (~d0).sum() - u; tot += n; dup += dd; deg += d0.sum()
        print(f'{nd["name"][:26]:26s} tri {n:>9,} degenerados {d0.sum()/n:5.1%} duplicados(extra) {dd/n:5.1%}  {time.time()-t0:4.0f}s', flush=True)
print(f'TOTAL tri {tot:,}  degenerados {deg:,} ({deg/tot:.1%})  duplicados extra {dup:,} ({dup/tot:.1%})')