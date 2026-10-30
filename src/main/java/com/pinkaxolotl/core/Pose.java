package com.pinkaxolotl.core;

/** Evaluates clips, builds world/skin matrices (3x4 row-major) and skins the mesh on the CPU. */
public final class Pose {
    private final AxmModel m;
    private final int n;
    private final float[] local;      // n*10 TRS
    private final float[] tmp;        // n*10 scratch for blending
    private final float[] world;      // n*12
    private final float[] skin;       // n*12

    public Pose(AxmModel m) {
        this.m = m;
        this.n = m.nodeCount;
        local = new float[n * 10];
        tmp = new float[n * 10];
        world = new float[n * 12];
        skin = new float[n * 12];
    }

    /** Sample a clip into dst (n*10). */
    static void sampleInto(AxmModel.Clip c, float t, boolean loop, int n, float[] dst) {
        float f;
        if (loop && c.duration > 0) {
            float tt = t % c.duration;
            if (tt < 0) tt += c.duration;
            f = tt * c.fps;
        } else {
            f = Math.max(0f, Math.min(t * c.fps, c.frames - 1));
        }
        int f0 = (int) f, f1;
        float a;
        if (f0 >= c.frames - 1) { f0 = c.frames - 1; f1 = f0; a = 0; }
        else { f1 = f0 + 1; a = f - f0; }
        int s = n * 10, o0 = f0 * s, o1 = f1 * s;
        float[] d = c.data;
        for (int i = 0; i < n; i++) {
            int p0 = o0 + i * 10, p1 = o1 + i * 10, q = i * 10;
            for (int k = 0; k < 3; k++) dst[q + k] = d[p0 + k] + (d[p1 + k] - d[p0 + k]) * a;
            nlerp(d, p0 + 3, d, p1 + 3, a, dst, q + 3);
            for (int k = 7; k < 10; k++) dst[q + k] = d[p0 + k] + (d[p1 + k] - d[p0 + k]) * a;
        }
    }

    private static void nlerp(float[] a, int ia, float[] b, int ib, float t, float[] out, int io) {
        float dot = a[ia] * b[ib] + a[ia + 1] * b[ib + 1] + a[ia + 2] * b[ib + 2] + a[ia + 3] * b[ib + 3];
        float sgn = dot < 0 ? -1f : 1f;
        float x = a[ia] + (sgn * b[ib] - a[ia]) * t;
        float y = a[ia + 1] + (sgn * b[ib + 1] - a[ia + 1]) * t;
        float z = a[ia + 2] + (sgn * b[ib + 2] - a[ia + 2]) * t;
        float w = a[ia + 3] + (sgn * b[ib + 3] - a[ia + 3]) * t;
        float inv = (float) (1.0 / Math.sqrt(x * x + y * y + z * z + w * w));
        out[io] = x * inv; out[io + 1] = y * inv; out[io + 2] = z * inv; out[io + 3] = w * inv;
    }

    public void set(AxmModel.Clip c, float t, boolean loop) {
        sampleInto(c, t, loop, n, local);
    }

    /** local = lerp(A@ta, B@tb, w) ; w=0 -> A, w=1 -> B */
    public void setBlend(AxmModel.Clip a, float ta, boolean la, AxmModel.Clip b, float tb, boolean lb, float w) {
        if (w <= 0f) { set(a, ta, la); return; }
        if (w >= 1f) { set(b, tb, lb); return; }
        sampleInto(a, ta, la, n, local);
        sampleInto(b, tb, lb, n, tmp);
        for (int i = 0; i < n; i++) {
            int q = i * 10;
            for (int k = 0; k < 3; k++) local[q + k] += (tmp[q + k] - local[q + k]) * w;
            nlerp(local, q + 3, tmp, q + 3, w, local, q + 3);
            for (int k = 7; k < 10; k++) local[q + k] += (tmp[q + k] - local[q + k]) * w;
        }
    }

    /** Compute world and skin matrices from the current local TRS. */
    public void update() {
        float[] r = new float[12];
        for (int i = 0; i < n; i++) {
            int q = i * 10;
            float x = local[q + 3], y = local[q + 4], z = local[q + 5], w = local[q + 6];
            float sx = local[q + 7], sy = local[q + 8], sz = local[q + 9];
            r[0] = (1 - 2 * (y * y + z * z)) * sx; r[1] = 2 * (x * y - z * w) * sy; r[2] = 2 * (x * z + y * w) * sz; r[3] = local[q];
            r[4] = 2 * (x * y + z * w) * sx; r[5] = (1 - 2 * (x * x + z * z)) * sy; r[6] = 2 * (y * z - x * w) * sz; r[7] = local[q + 1];
            r[8] = 2 * (x * z - y * w) * sx; r[9] = 2 * (y * z + x * w) * sy; r[10] = (1 - 2 * (x * x + y * y)) * sz; r[11] = local[q + 2];
            int p = m.parent[i];
            if (p < 0) System.arraycopy(r, 0, world, i * 12, 12);
            else mul(world, p * 12, r, 0, world, i * 12);
            if (m.joint[i]) mul(world, i * 12, m.invBind, i * 12, skin, i * 12);
        }
    }

    /** out = A * B for 3x4 affine matrices (row-major). out must not alias a or b. */
    private static void mul(float[] a, int ia, float[] b, int ib, float[] out, int io) {
        for (int r = 0; r < 3; r++) {
            float a0 = a[ia + r * 4], a1 = a[ia + r * 4 + 1], a2 = a[ia + r * 4 + 2], a3 = a[ia + r * 4 + 3];
            out[io + r * 4] = a0 * b[ib] + a1 * b[ib + 4] + a2 * b[ib + 8];
            out[io + r * 4 + 1] = a0 * b[ib + 1] + a1 * b[ib + 5] + a2 * b[ib + 9];
            out[io + r * 4 + 2] = a0 * b[ib + 2] + a1 * b[ib + 6] + a2 * b[ib + 10];
            out[io + r * 4 + 3] = a0 * b[ib + 3] + a1 * b[ib + 7] + a2 * b[ib + 11] + a3;
        }
    }

    /** CPU skinning; outPos/outNrm sized vertexCount*3. Normals are normalised. */
    public void skinMesh(float[] outPos, float[] outNrm) {
        final float[] pos = m.pos, nrm = m.nrm, wt = m.weights;
        final byte[] jn = m.joints;
        final float[] sk = skin;
        for (int v = 0; v < m.vertexCount; v++) {
            float px = pos[v * 3], py = pos[v * 3 + 1], pz = pos[v * 3 + 2];
            float nx = nrm[v * 3], ny = nrm[v * 3 + 1], nz = nrm[v * 3 + 2];
            float ox = 0, oy = 0, oz = 0, mx = 0, my = 0, mz = 0;
            for (int k = 0; k < 4; k++) {
                float w = wt[v * 4 + k];
                if (w <= 0f) continue;
                int j = (jn[v * 4 + k] & 0xFF) * 12;
                ox += w * (sk[j] * px + sk[j + 1] * py + sk[j + 2] * pz + sk[j + 3]);
                oy += w * (sk[j + 4] * px + sk[j + 5] * py + sk[j + 6] * pz + sk[j + 7]);
                oz += w * (sk[j + 8] * px + sk[j + 9] * py + sk[j + 10] * pz + sk[j + 11]);
                mx += w * (sk[j] * nx + sk[j + 1] * ny + sk[j + 2] * nz);
                my += w * (sk[j + 4] * nx + sk[j + 5] * ny + sk[j + 6] * nz);
                mz += w * (sk[j + 8] * nx + sk[j + 9] * ny + sk[j + 10] * nz);
            }
            float l = (float) Math.sqrt(mx * mx + my * my + mz * mz);
            if (l > 1e-8f) { mx /= l; my /= l; mz /= l; } else { mx = 0; my = 1; mz = 0; }
            outPos[v * 3] = ox; outPos[v * 3 + 1] = oy; outPos[v * 3 + 2] = oz;
            outNrm[v * 3] = mx; outNrm[v * 3 + 1] = my; outNrm[v * 3 + 2] = mz;
        }
    }
}
