package com.pinkaxolotl.client;

import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.rendering.v1.EntityRendererRegistry;
import net.minecraft.entity.EntityType;

/** Client-only: replaces the vanilla axolotl renderer. Works on vanilla servers. */
public class PinkAxolotlClient implements ClientModInitializer {
    @Override
    public void onInitializeClient() {
        EntityRendererRegistry.register(EntityType.AXOLOTL, PinkAxolotlRenderer::new);
    }
}
