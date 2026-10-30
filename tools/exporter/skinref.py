"""Reference (numpy) skeletal animation + skinning, mirrors the Java runtime."""
import numpy as np
import axextract as ax

def local_mats(T, Q, S):
    N = len(T); M = np.zeros((N, 4, 4)); M[:, 3, 3] = 1
    x, y, z, w = Q[:, 0], Q[:, 1], Q[:, 2], Q[:, 3]
    R = np.stack([
        np.stack([1 - 2*(y*y+z*z), 2*(x*y - z*w), 2*(x*z + y*w)], 1),
        np.stack([2*(x*y + z*w), 1 - 2*(x*x+z*z), 2*(y*z - x*w)], 1),
        np.stack([2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x+y*y)], 1)], 1)
    M[:, :3, :3] = R * S[:, None, :]
    M[:, :3, 3] = T
    return M

def world_mats(parent, L):
    W = np.zeros_like(L)
    for i in range(len(parent)):
        W[i] = L[i] if parent[i] < 0 else W[parent[i]] @ L[i]
    return W

def skin_positions(W, invbind, pos, joints, weights):
    """invbind: (N,4,4) (identity where unused)"""
    K = W @ invbind                       # (N,4,4)
    out = np.zeros_like(pos)
    for k in range(4):
        Mk = K[joints[:, k]]               # (V,4,4)
        p = np.einsum('vij,vj->vi', Mk[:, :3, :3], pos) + Mk[:, :3, 3]
        out += weights[:, k:k+1] * p
    return out

def sample_clip(clip, t):
    f = (t % clip['duration']) * clip['fps'] if clip['duration'] > 0 else 0
    f0 = int(np.floor(f)); f1 = min(f0 + 1, len(clip['T']) - 1); a = f - f0
    T = clip['T'][f0] * (1 - a) + clip['T'][f1] * a
    S = clip['S'][f0] * (1 - a) + clip['S'][f1] * a
    q0, q1 = clip['Q'][f0], clip['Q'][f1]
    d = (q0 * q1).sum(1, keepdims=True)
    q1 = np.where(d < 0, -q1, q1)
    Q = q0 * (1 - a) + q1 * a
    Q /= np.linalg.norm(Q, axis=1, keepdims=True)
    return T, Q, S
