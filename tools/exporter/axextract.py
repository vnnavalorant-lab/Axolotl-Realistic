"""Extract skeleton, skinned meshes and animation clips from the axolotl FBX."""
import collections
import numpy as np
import fbxparse

TICKS = 46186158000.0
FPS = 30.0


def mat_from_fbx(a):
    return np.asarray(a, dtype=np.float64).reshape(4, 4).T.copy()


def euler_xyz_deg_to_mat(e):
    x, y, z = np.radians(e)
    cx, sx, cy, sy, cz, sz = np.cos(x), np.sin(x), np.cos(y), np.sin(y), np.cos(z), np.sin(z)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def quat_from_mat(R):
    t = R[0, 0] + R[1, 1] + R[2, 2]
    if t > 0:
        s = np.sqrt(t + 1.0) * 2
        q = [(R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s, 0.25 * s]
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        q = [0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s, (R[2, 1] - R[1, 2]) / s]
    elif R[1, 1] > R[2, 2]:
        s = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        q = [(R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s, (R[0, 2] - R[2, 0]) / s]
    else:
        s = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        q = [(R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s, (R[1, 0] - R[0, 1]) / s]
    q = np.array(q)
    return q / np.linalg.norm(q)  # x y z w


def quat_to_mat(q):
    x, y, z, w = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def euler_to_quat(e):
    return quat_from_mat(euler_xyz_deg_to_mat(e))


def trs_matrix(t, q, s):
    M = np.eye(4)
    M[:3, :3] = quat_to_mat(q) * np.asarray(s)[None, :]
    M[:3, 3] = t
    return M


def name_of(n):
    return n.props[1].split('\x00')[0]


def props70(node):
    d = {}
    p = node.first('Properties70')
    if p:
        for c in p.children:
            d[c.props[0]] = c.props[4:]
    return d


def extract(path):
    ver, root = fbxparse.parse(path)
    obj = root.first('Objects')
    conns = root.first('Connections')
    byid = {c.props[0]: c for c in obj.children}

    oo_parent = collections.defaultdict(list)   # child -> [parent]
    oo_children = collections.defaultdict(list)  # parent -> [child]
    op = []
    for c in conns.children:
        t, a, b = c.props[:3]
        if t == 'OO':
            oo_parent[a].append(b)
            oo_children[b].append(a)
        else:
            op.append((a, b, c.props[3]))

    # ---------------- skeleton ----------------
    model_ids = [c.props[0] for c in obj.children if c.name == 'Model']
    model_set = set(model_ids)
    parent_of = {}
    for m in model_ids:
        ps = [p for p in oo_parent[m] if p in model_set]
        parent_of[m] = ps[0] if ps else None
    order = []
    seen = set()

    def visit(m):
        if m in seen:
            return
        if parent_of[m] is not None:
            visit(parent_of[m])
        seen.add(m)
        order.append(m)
    for m in model_ids:
        visit(m)
    idx = {m: i for i, m in enumerate(order)}
    nodes = []
    for m in order:
        o = byid[m]
        pr = props70(o)
        assert 'PreRotation' not in pr and 'PostRotation' not in pr and 'RotationPivot' not in pr
        assert pr['RotationOrder'][-1] == 0
        t = np.array(pr['Lcl Translation'], float)
        e = np.array(pr['Lcl Rotation'], float)
        s = np.array(pr['Lcl Scaling'], float)
        nodes.append(dict(id=m, name=name_of(o), type=o.props[2],
                          parent=idx[parent_of[m]] if parent_of[m] is not None else -1,
                          t=t, e=e, s=s))
    N = len(nodes)

    def rest_world(nodes_local):
        W = [None] * N
        for i, nd in enumerate(nodes):
            L = trs_matrix(nodes_local[i][0], euler_to_quat(nodes_local[i][1]), nodes_local[i][2])
            W[i] = L if nd['parent'] < 0 else W[nd['parent']] @ L
        return W
    Wrest = rest_world([(n['t'], n['e'], n['s']) for n in nodes])

    # ---------------- skin + meshes ----------------
    meshes = []
    bone_invbind = {}
    max_bind_err = 0.0
    for gid, g in byid.items():
        if g.name != 'Geometry':
            continue
        gname = name_of(g)
        model = [p for p in oo_parent[gid] if p in model_set][0]
        mats = [m for m in oo_children[model] if byid.get(m) is not None and byid[m].name == 'Material']
        matname = name_of(byid[mats[0]]) if mats else ''
        skin = [d for d in oo_children[gid] if byid[d].name == 'Deformer' and byid[d].props[2] == 'Skin'][0]
        clusters = [c for c in oo_children[skin] if byid[c].name == 'Deformer']
        cp = g.first('Vertices').props[0].reshape(-1, 3).astype(np.float64)
        ncp = len(cp)
        TM = None
        trip_cp, trip_b, trip_w = [], [], []
        for cid in clusters:
            cl = byid[cid]
            bone = [b for b in oo_children[cid] if b in model_set][0]
            ind = cl.first('Indexes').props[0] if cl.first('Indexes') and cl.first('Indexes').props else np.zeros(0, int)
            wts = cl.first('Weights').props[0] if cl.first('Weights') and cl.first('Weights').props else np.zeros(0)
            tm = mat_from_fbx(cl.first('Transform').props[0])
            tl = mat_from_fbx(cl.first('TransformLink').props[0])
            if TM is None:
                TM = tm
            else:
                assert np.abs(TM - tm).max() < 1e-6
            bi = idx[bone]
            max_bind_err = max(max_bind_err, np.abs(Wrest[bi] - tl).max() / 1000.0)
            inv = np.linalg.inv(tl)
            if bi in bone_invbind:
                assert np.abs(bone_invbind[bi] - inv).max() < 1e-6, 'inconsistent bind between meshes'
            bone_invbind[bi] = inv
            trip_cp.append(np.asarray(ind, int))
            trip_b.append(np.full(len(ind), bi))
            trip_w.append(np.asarray(wts, float))
        trip_cp = np.concatenate(trip_cp)
        trip_b = np.concatenate(trip_b)
        trip_w = np.concatenate(trip_w)
        # top-4 per control point
        o = np.lexsort((-trip_w, trip_cp))
        trip_cp, trip_b, trip_w = trip_cp[o], trip_b[o], trip_w[o]
        start = np.searchsorted(trip_cp, np.arange(ncp))
        rank = np.arange(len(trip_cp)) - start[trip_cp]
        keep = rank < 4
        J = np.zeros((ncp, 4), np.int32)
        Wt = np.zeros((ncp, 4), np.float64)
        J[trip_cp[keep], rank[keep]] = trip_b[keep]
        Wt[trip_cp[keep], rank[keep]] = trip_w[keep]
        s = Wt.sum(1, keepdims=True)
        assert (s > 0).all(), f'{gname}: vertex without weights'
        Wt /= s

        pi = g.first('PolygonVertexIndex').props[0]
        tri = pi.reshape(-1, 3).copy()
        assert (tri[:, 2] < 0).all() and (tri[:, :2] >= 0).all()
        tri[:, 2] = ~tri[:, 2]
        ln = g.first('LayerElementNormal')
        nrm = ln.first('Normals').props[0].reshape(-1, 3)
        nidx = ln.first('NormalsIndex').props[0]
        lu = g.first('LayerElementUV')
        uv = lu.first('UV').props[0].reshape(-1, 2)
        uidx = lu.first('UVIndex').props[0]
        corner_cp = tri.reshape(-1)
        key = np.stack([corner_cp, nidx, uidx], 1)
        uk, inv_idx = np.unique(key, axis=0, return_inverse=True)
        inv_idx = inv_idx.reshape(-1)
        pos_bind = (TM[:3, :3] @ cp[uk[:, 0]].T).T + TM[:3, 3]
        n_bind = (TM[:3, :3] @ nrm[uk[:, 1]].T).T
        n_bind /= np.linalg.norm(n_bind, axis=1, keepdims=True) + 1e-12
        meshes.append(dict(name=gname, material=matname, pos=pos_bind, nrm=n_bind,
                           uv=uv[uk[:, 2]], joints=J[uk[:, 0]], weights=Wt[uk[:, 0]],
                           cp=uk[:, 0], tris=inv_idx.reshape(-1, 3).astype(np.int32)))

    # ---------------- animation ----------------
    stacks = [c for c in obj.children if c.name == 'AnimationStack']
    clips = {}
    for st in stacks:
        sname = name_of(st).replace('Axolotl_', '')
        layers = [l for l in oo_children[st.props[0]] if byid[l].name == 'AnimationLayer']
        curve_by_node = collections.defaultdict(dict)
        for a, b, prop in op:
            if byid.get(a) is not None and byid[a].name == 'AnimationCurve':
                curve_by_node[b][prop] = a
        target = {}
        for a, b, prop in op:
            if byid.get(a) is not None and byid[a].name == 'AnimationCurveNode' and b in model_set:
                target[a] = (idx[b], prop)
        node_curves = {}  # (nodeidx, prop) -> [3 curves or None]
        tmax = 0
        for lay in layers:
            for cn in oo_children[lay]:
                if cn not in target:
                    continue
                ni, prop = target[cn]
                pr = props70(byid[cn])
                arr = []
                for k, ax in enumerate(('d|X', 'd|Y', 'd|Z')):
                    cid = curve_by_node[cn].get(ax)
                    default = pr.get(ax, [0.0])[-1]
                    if cid is None:
                        arr.append((None, None, default))
                    else:
                        cv = byid[cid]
                        kt = cv.first('KeyTime').props[0].astype(np.float64)
                        kv = cv.first('KeyValueFloat').props[0].astype(np.float64)
                        tmax = max(tmax, kt.max())
                        arr.append((kt, kv, default))
                node_curves[(ni, prop)] = arr
        duration = tmax / TICKS
        nf = int(round(duration * FPS)) + 1
        times = np.arange(nf) / FPS
        tt = times * TICKS
        T = np.zeros((nf, N, 3)); Q = np.zeros((nf, N, 4)); S = np.ones((nf, N, 3))
        for i, nd in enumerate(nodes):
            def ev(prop, rest):
                arr = node_curves.get((i, prop))
                out = np.tile(np.asarray(rest, float), (nf, 1))
                if arr is not None:
                    for k in range(3):
                        kt, kv, d = arr[k]
                        out[:, k] = d if kt is None else np.interp(tt, kt, kv)
                return out
            T[:, i] = ev('Lcl Translation', nd['t'])
            E = ev('Lcl Rotation', nd['e'])
            S[:, i] = ev('Lcl Scaling', nd['s'])
            prev = None
            for f in range(nf):
                q = euler_to_quat(E[f])
                if prev is not None and np.dot(prev, q) < 0:
                    q = -q
                Q[f, i] = q
                prev = q
        clips[sname] = dict(duration=duration, fps=FPS, T=T, Q=Q, S=S)

    return dict(nodes=nodes, rest_world=Wrest, meshes=meshes, invbind=bone_invbind,
                clips=clips, bind_err=max_bind_err)
