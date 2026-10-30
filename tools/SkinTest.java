import com.pinkaxolotl.core.*;
import java.io.*;
import java.nio.*;
import java.nio.file.*;

public class SkinTest {
    public static void main(String[] a) throws Exception {
        AxmModel m = AxmModel.parse(Files.readAllBytes(Paths.get(a[0])));
        System.out.println("nodes=" + m.nodeCount + " verts=" + m.vertexCount + " tris=" + m.triCount + " clips=" + m.clips.keySet());
        Pose p = new Pose(m);
        float[] pos = new float[m.vertexCount * 3], nrm = new float[m.vertexCount * 3];
        ByteBuffer out = ByteBuffer.allocate(8 * m.vertexCount * 6 * 4).order(ByteOrder.LITTLE_ENDIAN);
        String[][] cases = {{"Walk", "0.37"}, {"Swim", "0.81"}, {"Eat", "1.9"}, {"Idle_Breathe", "3.3"}, {"Walk", "5.0"}};
        for (String[] c : cases) {
            p.set(m.clips.get(c[0]), Float.parseFloat(c[1]), true);
            p.update(); p.skinMesh(pos, nrm);
            for (float f : pos) out.putFloat(f);
            for (float f : nrm) out.putFloat(f);
        }
        // blend Walk@0.5 -> Swim@0.2, w=0.4
        p.setBlend(m.clips.get("Walk"), 0.5f, true, m.clips.get("Swim"), 0.2f, true, 0.4f);
        p.update(); p.skinMesh(pos, nrm);
        for (float f : pos) out.putFloat(f);
        for (float f : nrm) out.putFloat(f);
        // state machine: run a walk->swim->eat sequence just to be sure it executes
        AnimState s = new AnimState(m);
        for (int i = 0; i < 200; i++) {
            s.update(0.05f, i < 60 ? AnimState.Mode.WALK : AnimState.Mode.SWIM, 1f, i == 100);
            s.apply(p);
        }
        p.skinMesh(pos, nrm);
        for (float f : pos) if (Float.isNaN(f)) throw new RuntimeException("NaN");
        // timing
        long t0 = System.nanoTime();
        int iters = 2000;
        for (int i = 0; i < iters; i++) { s.update(0.016f, AnimState.Mode.WALK, 1f, false); s.apply(p); p.skinMesh(pos, nrm); }
        System.out.printf("avg pose+skin: %.3f ms%n", (System.nanoTime() - t0) / 1e6 / iters);
        Files.write(Paths.get(a[1]), java.util.Arrays.copyOf(out.array(), out.position()));
    }
}
