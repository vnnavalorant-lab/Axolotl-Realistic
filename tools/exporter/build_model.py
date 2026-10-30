"""Build the runtime model file (AXM1) from extract.pkl + textures."""
import sys, pickle, struct, time
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from PIL import Image
import qem
import preview

Image.MAX_IMAGE_PIXELS = None
rng = np.random.default_rng(7)

CFG = dict(body=3600, tail=700, eye=450, shafts=1100, feathers=260)
if len(sys.argv) > 1:
    for kv in sys.argv[1:]:
        k, v = kv.split('='); CFG[k] = int(v)

d = pickle.load(open('extract.pkl', 'rb'))
tex = preview.load_tex()
meshes = {m['name']: m for m in d['meshes']}
N = len(d['nodes'])


def dense_samples(m, tri_sel, tex_img, per_tri):
    tr = m['tris'][tri_sel]
    r1 = rng.random((len(tr), per_tri)); r2 = rng.random((len(tr), per_tri))
    f = r1 + r2 > 1
    r1[f] = 1 - r1[f]; r2[f] = 1 - r2[f]
    r0 = 1 - r1 - r2
    pts = (r0[..., None] * m['pos'][tr[:, 0]][:, None] + r1[..., None] * m['pos'][tr[:, 1]][:, None]
           + r2[..., None] * m['pos'][tr[:, 2]][:, None]).reshape(-1, 3)
    uv = (r0[..., None] * m['uv'][tr[:, 0]][:, None] + r1[..., None] * m['uv'][tr[:, 1]][:, None]
          + r2[..., None] * m['uv'][tr[:, 2]][:, None]).reshape(-1, 2)
    return pts, preview.sample(tex_img, uv)


def reproject(Pd, src_pos, src_nrm, src_j, src_w, dpts, dcols):
    t = cKDTree(src_pos)
    _, i = t.query(Pd, k=1)
    nrm = src_nrm[i]
    J = src_j[i]; Wt = src_w[i]
    td = cKDTree(dpts)
    dist, ii = td.query(Pd, k=6)
    w = 1.0 / (dist + 0.5)
    col = (dcols[ii] * w[..., None]).sum(1) / w.sum(1, keepdims=True)
    return nrm, J, Wt, col


parts = []  # each: dict(P, F, nrm, J, W, col)


def add_part(name, m, tri_sel, tex_img, target, per_tri=6):
    sel_tris = m['tris'][tri_sel]
    used = np.unique(sel_tris)
    Pw, Fw = qem.weld(m['pos'][sel_tris.reshape(-1)], np.arange(len(sel_tris) * 3).reshape(-1, 3))
    t0 = time.time()
    if target and len(Fw) > target:
        Pd, Fd = qem.decimate(Pw, Fw, target)
    else:
        Pd, Fd = Pw, Fw
    nrm, J, Wt, col = reproject(Pd, m['pos'][used], m['nrm'][used], m['joints'][used], m['weights'][used],
                                *dense_samples(m, tri_sel, tex_img, per_tri))
    print(f'{name:10s} tris {len(sel_tris):6d} -> welded {len(Fw):6d} -> {len(Fd):5d}  verts {len(Pd):5d}  ({time.time()-t0:.1f}s)')
    parts.append(dict(name=name, P=Pd, F=Fd, nrm=nrm, J=J, W=Wt, col=col))


allt = lambda m: np.arange(len(m['tris']))
add_part('body', meshes['Axolotl_Body_mesh0'], allt(meshes['Axolotl_Body_mesh0']), tex['body'], CFG['body'], 8)
add_part('tail', meshes['Axolotl_Body_mesh1'], allt(meshes['Axolotl_Body_mesh1']), tex['body'], CFG['tail'], 8)
add_part('eyeL', meshes['Axolotl_EyeL_mesh0'], allt(meshes['Axolotl_EyeL_mesh0']), tex['eyeL'], CFG['eye'], 6)
add_part('eyeR', meshes['Axolotl_EyeR_mesh0'], allt(meshes['Axolotl_EyeR_mesh0']), tex['eyeR'], CFG['eye'], 6)

# gills: split into shafts (big islands) and feathers (medium islands)
g = meshes['Axolotl_Gills_mesh0']
cp = g['cp']; t = cp[g['tris']]
ncp = cp.max() + 1
r = np.r_[t[:, 0], t[:, 1], t[:, 2]]; c = np.r_[t[:, 1], t[:, 2], t[:, 0]]
k, lab = connected_components(coo_matrix((np.ones(len(r)), (r, c)), shape=(ncp, ncp)), directed=False)
tl = lab[t[:, 0]]
tc = np.bincount(tl, minlength=k)
shaft_tris = np.where(tc[tl] >= 100)[0]
feather_comps = np.where((tc >= 20) & (tc < 100))[0]
pick = rng.choice(feather_comps, size=min(CFG['feathers'], len(feather_comps)), replace=False)
feather_tris = np.where(np.isin(tl, pick))[0]
add_part('shafts', g, shaft_tris, tex['gills'], CFG['shafts'], 6)
add_part('feathers', g, feather_tris, tex['gills'], CFG['feathers']*8, 6)

# ---------------- merge ----------------
P = np.concatenate([p['P'] for p in parts])
Nn = np.concatenate([p['nrm'] for p in parts])
J = np.concatenate([p['J'] for p in parts]).astype(np.uint8)
Wt = np.concatenate([p['W'] for p in parts]).astype(np.float32)
Col = np.concatenate([p['col'] for p in parts])
Col = np.concatenate([np.clip(Col, 0, 1) * 255 + 0.5, np.full((len(Col), 1), 255)], 1).astype(np.uint8)
off = 0; F = []
for p in parts:
    F.append(p['F'] + off); off += len(p['P'])
F = np.concatenate(F)
assert len(P) < 65536
print('TOTAL verts', len(P), 'tris', len(F))

# ---------------- scale / placement baked into root nodes ----------------
body = parts[0]['P']; tail = parts[1]['P']
bt = np.concatenate([body, tail])
LEN = 0.80  # blocks, nose to tail tip
s = LEN / (bt[:, 2].max() - bt[:, 2].min())
off_x = -0.5 * (bt[:, 0].max() + bt[:, 0].min()) * s
off_z = -0.5 * (bt[:, 2].max() + bt[:, 2].min()) * s
off_y = -bt[:, 1].min() * s
print('scale', s, 'offset', off_x, off_y, off_z)

nodes = d['nodes']
parent = np.array([n['parent'] for n in nodes], np.int16)
isjoint = np.zeros(N, np.uint8)
inv = np.tile(np.eye(4), (N, 1, 1))
for i, m in d['invbind'].items():
    inv[i] = m; isjoint[i] = 1
assert J.max() < N

clips_out = {}
for name, cl in d['clips'].items():
    T = cl['T'].copy(); Q = cl['Q'].copy(); S = cl['S'].copy()
    for i, n in enumerate(nodes):
        if n['parent'] < 0:
            T[:, i] = T[:, i] * s + np.array([off_x, off_y, off_z])
            S[:, i] = S[:, i] * s
    clips_out[name] = dict(duration=cl['duration'], fps=cl['fps'], T=T, Q=Q, S=S)

with open('out/axolotl.axm', 'wb') as f:
    f.write(b'AXM1')
    f.write(struct.pack('<i', N))
    for i in range(N):
        f.write(struct.pack('<hB', int(parent[i]), int(isjoint[i])))
        f.write(inv[i][:3].astype('<f4').tobytes())
    f.write(struct.pack('<i', len(P)))
    f.write(P.astype('<f4').tobytes()); f.write(Nn.astype('<f4').tobytes())
    f.write(Col.tobytes()); f.write(J.tobytes()); f.write(Wt.astype('<f4').tobytes())
    f.write(struct.pack('<i', len(F)))
    f.write(F.astype('<u2').tobytes())
    f.write(struct.pack('<i', len(clips_out)))
    for name, cl in clips_out.items():
        nb = name.encode()
        f.write(struct.pack('<B', len(nb))); f.write(nb)
        f.write(struct.pack('<ffi', cl['duration'], cl['fps'], len(cl['T'])))
        arr = np.concatenate([cl['T'], cl['Q'], cl['S']], axis=2).astype('<f4')  # frames, N, 10
        f.write(arr.tobytes())
pickle.dump(dict(P=P, Nn=Nn, Col=Col, J=J, W=Wt, F=F, parent=parent, inv=inv, clips=clips_out,
                 parts=[(p['name'], len(p['P']), len(p['F'])) for p in parts]), open('out/built.pkl', 'wb'))
import os
print('file size', os.path.getsize('out/axolotl.axm'))
