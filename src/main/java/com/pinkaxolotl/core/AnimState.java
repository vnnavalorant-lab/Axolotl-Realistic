package com.pinkaxolotl.core;

/** Per-entity animation state machine with cross-fading. Pure logic, no Minecraft types. */
public final class AnimState {
    public enum Mode { IDLE, WALK, SWIM }

    public static final float FADE = 0.25f;

    private final AxmModel model;
    private final AxmModel.Clip idle, walk, swim, eat;

    private AxmModel.Clip cur, prev;
    private float curT, prevT, fade = 1f;
    private boolean eating, lastEatTrigger;

    public AnimState(AxmModel model) {
        this.model = model;
        idle = model.clips.get("Idle_Breathe");
        walk = model.clips.get("Walk");
        swim = model.clips.get("Swim");
        eat = model.clips.get("Eat");
        cur = idle;
    }

    private AxmModel.Clip clipFor(Mode m) {
        switch (m) {
            case WALK: return walk;
            case SWIM: return swim;
            default: return idle;
        }
    }

    private void switchTo(AxmModel.Clip c) {
        if (c == cur) return;
        prev = cur; prevT = curT;
        cur = c; curT = 0f; fade = 0f;
    }

    /**
     * @param dt     seconds since last update (>= 0)
     * @param mode   desired locomotion mode
     * @param speed  playback speed multiplier for looping clips
     * @param eatNow true while the entity is performing a bite/attack swing
     */
    public void update(float dt, Mode mode, float speed, boolean eatNow) {
        if (eatNow && !lastEatTrigger && !eating && eat != null) {
            eating = true;
            switchTo(eat);
        }
        lastEatTrigger = eatNow;
        if (eating) {
            curT += dt;
            if (curT >= eat.duration) eating = false;
        }
        if (!eating) {
            switchTo(clipFor(mode));
            curT += dt * speed;
        }
        if (prev != null) {
            prevT += dt * speed;
            fade += dt / FADE;
            if (fade >= 1f) { fade = 1f; prev = null; }
        }
    }

    public void apply(Pose pose) {
        boolean loopCur = cur != eat;
        if (prev != null && fade < 1f) {
            float w = fade * fade * (3f - 2f * fade); // smoothstep
            pose.setBlend(prev, prevT, prev != eat, cur, curT, loopCur, w);
        } else {
            pose.set(cur, curT, loopCur);
        }
        pose.update();
    }

    public AxmModel model() { return model; }
}
