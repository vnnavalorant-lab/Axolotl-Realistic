"""Quadric error metric edge-collapse decimation (positions only, boundary-preserving)."""
import heapq
import numpy as np


def weld(P, F, decimals=4):
    """Merge vertices with identical positions, drop degenerate / duplicate triangles."""
    key = np.round(P, decimals)
    uk, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    # use the first original position of each cluster to avoid rounding drift
    first = np.zeros(len(uk), int)
    first[inv[::-1]] = np.arange(len(P))[::-1]
    Pw = P[first]
    Fw = inv[F]
    ok = (Fw[:, 0] != Fw[:, 1]) & (Fw[:, 1] != Fw[:, 2]) & (Fw[:, 0] != Fw[:, 2])
    Fw = Fw[ok]
    s = np.sort(Fw, axis=1)
    _, u = np.unique(s, axis=0, return_index=True)
    Fw = Fw[np.sort(u)]
    return Pw, Fw


def decimate(P, F, target_faces, boundary_weight=20.0, flip_dot=0.25):
    P = np.asarray(P, np.float64).copy()
    n = len(P)
    faces = [tuple(int(x) for x in f) for f in F]
    alive = [True] * len(faces)
    vfaces = [set() for _ in range(n)]
    for fi, f in enumerate(faces):
        for v in f:
            vfaces[v].add(fi)
    nbrs = [set() for _ in range(n)]
    for f in faces:
        a, b, c = f
        nbrs[a].update((b, c)); nbrs[b].update((a, c)); nbrs[c].update((a, b))

    Q = np.zeros((n, 4, 4))
    edge_faces = {}
    for fi, (a, b, c) in enumerate(faces):
        pa, pb, pc = P[a], P[b], P[c]
        nrm = np.cross(pb - pa, pc - pa)
        l = np.linalg.norm(nrm)
        if l < 1e-14:
            continue
        area = l / 2
        nrm /= l
        pl = np.append(nrm, -nrm @ pa)
        K = np.outer(pl, pl) * area
        Q[a] += K; Q[b] += K; Q[c] += K
        for e in ((a, b), (b, c), (c, a)):
            edge_faces.setdefault((min(e), max(e)), []).append(fi)
    for (a, b), fl in edge_faces.items():
        if len(fl) == 1:
            f = faces[fl[0]]
            pa, pb, pc = P[f[0]], P[f[1]], P[f[2]]
            fn = np.cross(pb - pa, pc - pa); fn /= (np.linalg.norm(fn) + 1e-20)
            e = P[b] - P[a]; el = np.linalg.norm(e)
            bn = np.cross(e, fn)
            l = np.linalg.norm(bn)
            if l < 1e-14:
                continue
            bn /= l
            pl = np.append(bn, -bn @ P[a])
            K = np.outer(pl, pl) * boundary_weight * el * el
            Q[a] += K; Q[b] += K

    ver = [0] * n
    dead = [False] * n

    def best_pos(a, b):
        Qs = Q[a] + Q[b]
        A = Qs[:3, :3]
        cands = [P[a], P[b], (P[a] + P[b]) * 0.5]
        if abs(np.linalg.det(A)) > 1e-9 * (np.abs(A).max() ** 3 + 1e-30):
            try:
                cands.append(np.linalg.solve(A, -Qs[:3, 3]))
            except np.linalg.LinAlgError:
                pass
        best = None
        for x in cands:
            v = np.append(x, 1.0)
            c = v @ Qs @ v
            if best is None or c < best[0]:
                best = (c, x)
        return best

    heap = []
    cnt = 0

    def push(a, b):
        nonlocal cnt
        c, x = best_pos(a, b)
        heapq.heappush(heap, (c, cnt, a, b, ver[a], ver[b], x))
        cnt += 1

    for a in range(n):
        for b in nbrs[a]:
            if a < b:
                push(a, b)

    nfaces = len(faces)

    def is_boundary_vertex(v):
        for w in nbrs[v]:
            if len(vfaces[v] & vfaces[w]) == 1:
                return True
        return False

    while heap and nfaces > target_faces:
        c, _, a, b, va, vb, x = heapq.heappop(heap)
        if dead[a] or dead[b] or ver[a] != va or ver[b] != vb:
            continue
        shared = vfaces[a] & vfaces[b]
        common = nbrs[a] & nbrs[b]
        if len(common) != len(shared) or len(shared) == 0 or len(shared) > 2:
            continue
        if len(shared) == 2 and is_boundary_vertex(a) and is_boundary_vertex(b):
            continue
        # flip / degeneracy check
        ok = True
        for v, other in ((a, b), (b, a)):
            for fi in vfaces[v]:
                if fi in shared:
                    continue
                f = faces[fi]
                p0 = [P[k] for k in f]
                p1 = [x if k == v else P[k] for k in f]
                n0 = np.cross(p0[1] - p0[0], p0[2] - p0[0])
                n1 = np.cross(p1[1] - p1[0], p1[2] - p1[0])
                l0, l1 = np.linalg.norm(n0), np.linalg.norm(n1)
                if l1 < 1e-12 or (l0 > 1e-12 and (n0 @ n1) / (l0 * l1) < flip_dot):
                    ok = False
                    break
            if not ok:
                break
        if not ok:
            continue
        # apply collapse b -> a
        for fi in list(shared):
            alive[fi] = False
            nfaces -= 1
            for v in faces[fi]:
                vfaces[v].discard(fi)
        for fi in list(vfaces[b]):
            faces[fi] = tuple(a if k == b else k for k in faces[fi])
            vfaces[a].add(fi)
        vfaces[b].clear()
        for w in nbrs[b]:
            nbrs[w].discard(b)
            if w != a:
                nbrs[w].add(a)
                nbrs[a].add(w)
        nbrs[a].discard(b)
        nbrs[b] = set()
        dead[b] = True
        P[a] = x
        Q[a] = Q[a] + Q[b]
        ver[a] += 1
        for w in list(nbrs[a]):
            push(a, w)

    keep = [fi for fi in range(len(faces)) if alive[fi]]
    Fo = np.array([faces[i] for i in keep], int)
    used = np.unique(Fo)
    remap = -np.ones(n, int)
    remap[used] = np.arange(len(used))
    return P[used], remap[Fo]
