import struct, zlib, sys
import numpy as np

class Node:
    __slots__=('name','props','children')
    def __init__(s,n): s.name=n; s.props=[]; s.children=[]
    def find(s,n): return [c for c in s.children if c.name==n]
    def first(s,n):
        r=s.find(n); return r[0] if r else None

def parse(path):
    data=open(path,'rb').read()
    assert data[:20]==b'Kaydara FBX Binary  '
    ver=struct.unpack_from('<I',data,23)[0]
    wide = ver>=7500
    pos=27
    def read_prop(p):
        t=chr(data[p]); p+=1
        if t=='Y': return struct.unpack_from('<h',data,p)[0],p+2
        if t=='C': return bool(data[p]),p+1
        if t=='I': return struct.unpack_from('<i',data,p)[0],p+4
        if t=='F': return struct.unpack_from('<f',data,p)[0],p+4
        if t=='D': return struct.unpack_from('<d',data,p)[0],p+8
        if t=='L': return struct.unpack_from('<q',data,p)[0],p+8
        if t in 'SR':
            n=struct.unpack_from('<I',data,p)[0]; p+=4
            b=data[p:p+n]; p+=n
            return (b.decode('utf8','replace') if t=='S' else b),p
        if t in 'fdilb':
            cnt,enc,clen=struct.unpack_from('<III',data,p); p+=12
            raw=data[p:p+clen]; p+=clen
            if enc==1: raw=zlib.decompress(raw)
            dt={'f':'<f4','d':'<f8','i':'<i4','l':'<i8','b':'u1'}[t]
            return np.frombuffer(raw,dtype=dt,count=cnt),p
        raise ValueError(t)
    def read_node(p):
        if wide:
            end,np_,pl,nl=struct.unpack_from('<QQQB',data,p); p+=25
        else:
            end,np_,pl,nl=struct.unpack_from('<IIIB',data,p); p+=13
        if end==0: return None,p
        name=data[p:p+nl].decode('utf8','replace'); p+=nl
        n=Node(name)
        for _ in range(np_):
            v,p=read_prop(p); n.props.append(v)
        while p<end:
            c,p=read_node(p)
            if c is None: break
            n.children.append(c)
        return n,end
    root=Node('root')
    while pos<len(data)-200:
        n,pos2=read_node(pos)
        if n is None: break
        root.children.append(n); pos=pos2
    return ver,root
