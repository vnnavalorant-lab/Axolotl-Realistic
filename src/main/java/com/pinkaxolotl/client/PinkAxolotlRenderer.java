package com.pinkaxolotl.client;

import com.pinkaxolotl.core.AxmModel;
import net.minecraft.client.render.entity.EntityRendererFactory;
import net.minecraft.client.render.entity.LivingEntityRenderer;
import net.minecraft.client.util.math.MatrixStack;
import net.minecraft.entity.passive.AxolotlEntity;
import net.minecraft.resource.ResourceManager;
import net.minecraft.util.Identifier;

import java.io.IOException;
import java.io.InputStream;

public class PinkAxolotlRenderer extends LivingEntityRenderer<AxolotlEntity, PinkAxolotlModel> {
    private static final Identifier TEXTURE = new Identifier("pinkaxolotl", "textures/entity/white.png");
    private static final Identifier MODEL = new Identifier("pinkaxolotl", "models/axolotl.axm");

    public PinkAxolotlRenderer(EntityRendererFactory.Context ctx) {
        super(ctx, load(ctx.getResourceManager()), 0.35f);
    }

    private static PinkAxolotlModel load(ResourceManager rm) {
        try (InputStream in = rm.open(MODEL)) {
            return new PinkAxolotlModel(AxmModel.load(in));
        } catch (IOException e) {
            throw new RuntimeException("Failed to load " + MODEL, e);
        }
    }

    @Override
    public Identifier getTexture(AxolotlEntity entity) {
        return TEXTURE;
    }

    @Override
    protected void scale(AxolotlEntity entity, MatrixStack matrices, float amount) {
        if (entity.isBaby()) matrices.scale(0.5f, 0.5f, 0.5f);
    }
}
