package com.pinkaxolotl.core;

import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

/** Skinned mesh + skeleton + baked animation clips (file format "AXM1"). No Minecraft dependencies. */
public final class AxmModel {
    public static final class Clip {
        public final String name;
        public final float duration, fps;
        public final int frames;
        /** frames * nodeCount * 10 : tx ty tz qx qy qz qw sx sy sz */
        public final float[] data;

        Clip(String name, float duration, float fps, int frames, float[] data) {
            this.name = name; this.duration = duration; this.fps = fps; this.frames = frames; this.data = data;
        }
    }

    public int nodeCount;
    public short[] parent;
    public boolean[] joint;
    /** 3x4 row-major per node */
    public float[] invBind;
    public int vertexCount;
    public float[] pos, nrm;
    public byte[] color;   // rgba
    public byte[] joints;  // 4 per vertex (node indices, unsigned)
    public float[] weights;
    public int triCount;
    public int[] indices;
    public final Map<String, Clip> clips = new LinkedHashMap<>();

    public static AxmModel load(InputStream in) throws IOException {
        return parse(in.readAllBytes());
    }

    public static AxmModel parse(byte[] bytes) throws IOException {
        ByteBuffer b = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
        byte[] magic = new byte[4];
        b.get(magic);
        if (!new String(magic, StandardCharsets.US_ASCII).equals("AXM1")) throw new IOException("Not an AXM1 file");
        AxmModel m = new AxmModel();
        int n = b.getInt();
        m.nodeCount = n;
        m.parent = new short[n];
        m.joint = new boolean[n];
        m.invBind = new float[n * 12];
        for (int i = 0; i < n; i++) {
            m.parent[i] = b.getShort();
            m.joint[i] = b.get() != 0;
            for (int k = 0; k < 12; k++) m.invBind[i * 12 + k] = b.getFloat();
            if (m.parent[i] >= i) throw new IOException("Nodes must be topologically sorted");
        }
        int v = b.getInt();
        m.vertexCount = v;
        m.pos = new float[v * 3];
        m.nrm = new float[v * 3];
        b.asFloatBuffer().get(m.pos); b.position(b.position() + v * 12);
        b.asFloatBuffer().get(m.nrm); b.position(b.position() + v * 12);
        m.color = new byte[v * 4]; b.get(m.color);
        m.joints = new byte[v * 4]; b.get(m.joints);
        m.weights = new float[v * 4];
        b.asFloatBuffer().get(m.weights); b.position(b.position() + v * 16);
        int t = b.getInt();
        m.triCount = t;
        m.indices = new int[t * 3];
        for (int i = 0; i < t * 3; i++) m.indices[i] = b.getShort() & 0xFFFF;
        int c = b.getInt();
        for (int i = 0; i < c; i++) {
            int len = b.get() & 0xFF;
            byte[] nb = new byte[len];
            b.get(nb);
            String name = new String(nb, StandardCharsets.UTF_8);
            float dur = b.getFloat(), fps = b.getFloat();
            int frames = b.getInt();
            float[] data = new float[frames * n * 10];
            b.asFloatBuffer().get(data);
            b.position(b.position() + data.length * 4);
            m.clips.put(name, new Clip(name, dur, fps, frames, data));
        }
        return m;
    }
}
