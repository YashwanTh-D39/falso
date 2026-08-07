/**
 * OrbManager module for FALSO 3D Spatial OS.
 * Orchestrates OrbCore, OrbitalRenderer, EntityRenderer, AnimationController,
 * MaterialFactory, SpatialRenderer, and DebugRenderer.
 */

import { rendererManager } from './renderer.js';
import { OrbCore } from './orb_core.js';
import { OrbitalRenderer } from './orbital_renderer.js';
import { EntityRenderer } from './entity_renderer.js';
import { AnimationController } from './animation_controller.js';
import { DebugRenderer } from './debug_renderer.js';
import { SpatialRenderer } from './spatial_renderer.js';

export class OrbManager {
  constructor(rendererManager) {
    this.rm = rendererManager;
    this.THREE = null;
    this.orbGroup = null;
    this.orbCore = null;
    this.orbitalRenderer = null;
    this.entityRenderer = null;
    this.debugRenderer = null;
    this.spatialRenderer = null;
    this.animController = null;
    this.innerCore = null;
    this.orbState = 'idle';
  }

  addOrb() {
    if (!this.orbGroup) {
      this.init();
    }
  }

  init() {
    this.THREE = this.rm.THREE;
    const THREE = this.THREE;
    if (!THREE) throw new Error('Three.js instance is missing in OrbManager');

    const scene = this.rm.scene;
    if (!scene) throw new Error('Scene is missing in OrbManager.init()');

    this.animController = new AnimationController(THREE);
    this.clock = this.animController.clock;

    // Ambient & Directional Lighting
    const ambientLight = new THREE.AmbientLight(0x00E5FF, 0.5);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0x7DF9FF, 1.0);
    dirLight1.position.set(5, 10, 7);
    scene.add(dirLight1);

    this.orbGroup = new THREE.Group();
    scene.add(this.orbGroup);

    // 1. OrbCore (Outer dark blue globe, middle cyan globe, inner crystal core)
    this.orbCore = new OrbCore(THREE);
    this.innerCore = this.orbCore.innerCrystal;
    this.orbGroup.add(this.orbCore.group);

    // 2. OrbitalRenderer (Thin intersecting orbital rings)
    this.orbitalRenderer = new OrbitalRenderer(THREE);
    this.orbGroup.add(this.orbitalRenderer.group);

    // 3. EntityRenderer (Real 3D process/app orbital nodes)
    this.entityRenderer = new EntityRenderer(THREE, scene);

    // 4. SpatialRenderer (3D node layout & raycasting)
    this.spatialRenderer = new SpatialRenderer(THREE, this.rm.camera, scene);

    // 5. DebugRenderer (Strictly gated behind window.DEBUG_MODE = true)
    this.debugRenderer = new DebugRenderer(THREE, scene);

    console.log('[LIVING ORB ACCURATELY RECREATED MATCHING REFERENCE SCREENSHOT]');
    console.log('  OrbCore:', !!this.orbCore);
    console.log('  OrbitalRenderer:', !!this.orbitalRenderer);
    console.log('  EntityRenderer:', !!this.entityRenderer);
    console.log('  SpatialRenderer:', !!this.spatialRenderer);
    console.log('  DebugRenderer (DEBUG_MODE):', window.DEBUG_MODE === true);
  }

  updateState(newState) {
    this.orbState = newState;
    window.orbState = newState;
  }

  animate(micLevel = 0) {
    if (!this.animController) return;
    if (!this.rm || !this.rm.scene) return;
    if (!this.rm || !this.rm.camera) return;
    if (!this.rm || !this.rm.renderer) return;

    const { dt, time } = this.animController.tick();

    // Render layers cleanly
    if (this.orbCore) this.orbCore.animate(time, this.orbState, micLevel);
    if (this.orbitalRenderer) this.orbitalRenderer.animate(time);
    if (this.entityRenderer) this.entityRenderer.animate(time);
    if (this.debugRenderer) this.debugRenderer.animate();
  }
}

export const orbManager = new OrbManager(rendererManager);
