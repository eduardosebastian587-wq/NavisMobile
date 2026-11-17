"""Lector/escritor de FBX binario (v7500+/7700, offsets de 64 bits). Conserva los tipos de cada propiedad."""
import struct, zlib
import numpy as np
SC={'Y':'<h','C':'<?','I':'<i','F':'<f','D':'<d','L':'<q'}
AR={'f':'<f4','d':'<f8','l':'<i8','i':'<i4','b':'?'}
def leer(path):
    b=open(path,'rb').read()
    ver=struct.unpack_from('<I',b,23)[0]
    def nodo(pos):
        end,npr,plen,nl=struct.unpack_from('<QQQB',b,pos); pos+=25
        if end==0: return None,pos
        name=b[pos:pos+nl].decode('latin1'); p=pos+nl
        props=[]
        for _ in range(npr):
            t=chr(b[p]); p+=1
            if t in SC:
                v=struct.unpack_from(SC[t],b,p)[0]; p+=struct.calcsize(SC[t])
            elif t in AR:
                n,enc,cl=struct.unpack_from('<III',b,p); p+=12
                raw=b[p:p+cl]; p+=cl
                if enc: raw=zlib.decompress(raw)
                v=np.frombuffer(raw,dtype=AR[t],count=n).copy()
            else:
                n=struct.unpack_from('<I',b,p)[0]; p+=4; v=bytes(b[p:p+n]); p+=n
            props.append((t,v))
        pos=pos+nl+plen
        kids=[]
        while pos<end:
            k,pos=nodo(pos)
            if k is None: break
            kids.append(k)
        return [name,props,kids],end
    pos=27; top=[]
    while True:
        n,pos=nodo(pos)
        if n is None: break
        top.append(n)
    return ver,top,b[pos:]            # pos = justo después del registro nulo; el resto es el pie
def _prop(t,v):
    if t in SC: return t.encode()+struct.pack(SC[t],v)
    if t in AR:
        raw=np.ascontiguousarray(v,dtype=AR[t]).tobytes()
        if len(raw)>=128: c=zlib.compress(raw,6); return t.encode()+struct.pack('<III',len(v),1,len(c))+c
        return t.encode()+struct.pack('<III',len(v),0,len(raw))+raw
    return t.encode()+struct.pack('<I',len(v))+v
def _nodo(n,pos):
    name,props,kids=n
    nb=name.encode('latin1')
    pb=b''.join(_prop(t,v) for t,v in props)
    head=25+len(nb)
    cur=pos+head+len(pb); hijos=b''
    for k in kids:
        kb=_nodo(k,cur+len(hijos)); hijos+=kb
    if kids: hijos+=b'\0'*25
    end=pos+head+len(pb)+len(hijos)
    return struct.pack('<QQQB',end,len(props),len(pb),len(nb))+nb+pb+hijos
def escribir(path,ver,top,pie):
    out=bytearray(b'Kaydara FBX Binary  \x00\x1a\x00'+struct.pack('<I',ver))
    for n in top: out+=_nodo(n,len(out))
    out+=b'\0'*25+pie
    open(path,'wb').write(out)
