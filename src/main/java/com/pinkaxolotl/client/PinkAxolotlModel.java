package com.pinkaxolotl.client;

import com.pinkaxolotl.core.AnimState;
import com.pinkaxolotl.core.AxmModel;
import com.pinkaxolotl.core.Pose;
import net.minecraft.client.render.VertexConsumer;
import net.minecraft.client.render.entity.model.EntityModel;
import net.minecraft.client.util.math.MatrixStack;
import net.minecraft.entity.passive.AxolotlEntity;
import org.joml.Matrix3f;
import org.joml.Matrix4f;

import java.util.WeakHashMap;

/**
 * Skinned, baked-animation model. All geometry is CPU-skinned each frame from the AXM1 file and
 * emitted as quads (each triangle is a degenerate quad) with baked vertex colours.
 */
public class PinkAxolotlModel extends EntityModel<AxolotlEntity> {
    /** Vanilla LivingEntityRenderer applies scale(-1,-1,1) + translate(0,-1.501,0) before render(). */
    private static final float OFFSET_Y = 1.501f;

    private static final class State {
        final AnimState anim;
        float lastProgress = Float.NaN;
        State(AxmModel m) { anim = new AnimState(m); }
    }

    private final AxmModel model;
    private final Pose pose;
    private final float[] pos, nrm;
    private final WeakHashMap<AxolotlEntity, State> states = new WeakHashMap<>();
    private State current;

    public PinkAxolotlModel(AxmModel model) {
        this.model = model;
        this.pose = new Pose(model);
        this.pos = new float[model.vertexCount * 3];
        this.nrm = new float[model.vertexCount * 3];
    }

    @Override
    public void setAngles(AxolotlEntity entity, float limbAngle, float limbDistance, float animationProgress,
                          float headYaw, float headPitch) {
        State st = states.computeIfAbsent(entity, e -> new State(model));
        float dt = 0f;
        if (!Float.isNaN(st.lastProgress)) {
            dt = (animationProgress - st.lastProgress) / 20f; // ticks -> seconds (frozen while paused)
            if (dt < 0f || dt > 0.5f) dt = 0f;
        }
        st.lastProgress = animationProgress;

        boolean inWater = entity.isTouchingWater();
        boolean onGround = entity.isOnGround();
        boolean moving = limbDistance > 0.04f;
        AnimState.Mode mode = AnimState.Mode.IDLE;
        float speed = 1f;
        if (moving) {
            if (inWater && !onGround) {
                mode = AnimState.Mode.SWIM;
                speed = Math.min(1.6f, 0.7f + limbDistance * 3f);
            } else if (onGround) {
                mode = AnimState.Mode.WALK;
                speed = Math.min(1.8f, 0.6f + limbDistance * 2.5f);
            }
        }
        st.anim.update(dt, mode, speed, entity.handSwinging);
        current = st;
    }

    @Override
    public void render(MatrixStack matrices, VertexConsumer vertices, int light, int overlay,
                       float red, float green, float blue, float alpha) {
        if (current == null) return;
        current.anim.apply(pose);
        pose.skinMesh(pos, nrm);

        MatrixStack.Entry entry = matrices.peek();
        Matrix4f pm = entry.getPositionMatrix();
        Matrix3f nm = entry.getNormalMatrix();
        final byte[] col = model.color;
        final int[] idx = model.indices;
        final int a = Math.round(alpha * 255f);
        for (int t = 0; t < idx.length; t += 3) {
            for (int k = 0; k < 4; k++) {
                int v = idx[t + (k == 3 ? 2 : k)];
                int p = v * 3, c = v * 4;
                vertices.vertex(pm, pos[p], OFFSET_Y - pos[p + 1], -pos[p + 2])
                        .color(Math.round((col[c] & 0xFF) * red), Math.round((col[c + 1] & 0xFF) * green),
                                Math.round((col[c + 2] & 0xFF) * blue), a)
                        .texture(0.5f, 0.5f)
                        .overlay(overlay)
                        .light(light)
                        .normal(nm, nrm[p], -nrm[p + 1], -nrm[p + 2])
                        .next();
            }
        }
    }
}
