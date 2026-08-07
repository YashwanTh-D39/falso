/**
 * OrbManager module for FALSO 3D Spatial OS.
 * Orchestrates OrbCore, OrbitalRenderer, EntitySystem, and DebugRenderer.
 */

import { rendererManager } from './renderer.js';
import { OrbCore } from './orb_core.js';
import { OrbitalRenderer } from './orbital_renderer.js';
import { EntitySystem } from './entity_system.js';
import { DebugRenderer } from './debug_renderer.js';

export class OrbManager {
  constructor(rendererManager) {
    this.rm = rendererManager;
    this.THREE = null;
    this.orbGroup = null;
    this.orbCore = null;
    this.orbitalRenderer = null;
    this.entitySystem = null;
    this.debugRenderer = null;
    this.clock = null;
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

    this.clock = new THREE.Clock();
    const scene = this.rm.scene;
    if (!scene) throw new Error('Scene is missing in OrbManager.init()');

    // Lighting
    const ambientLight = new THREE.AmbientLight(0x00E5FF, 0.6);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0x7DF9FF, 1.2);
    dirLight1.position.set(5, 10, 7);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0xFFB74D, 0.4);
    dirLight2.position.set(-5, -5, -5);
    scene.add(dirLight2);

    this.orbGroup = new THREE.Group();
    scene.add(this.orbGroup);

    // 1. OrbCore (Energy core & breathing)
    this.orbCore = new OrbCore(THREE);
    this.innerCore = this.orbCore.innerCore;
    this.orbGroup.add(this.orbCore.group);

    // 2. OrbitalRenderer (5 Orbital Rings)
    this.orbitalRenderer = new OrbitalRenderer(THREE);
    this.orbGroup.add(this.orbitalRenderer.group);

    // 3. EntitySystem (3D orbiting nodes)
    this.entitySystem = new EntitySystem(THREE, scene);

    // 4. DebugRenderer (strictly gated behind window.DEBUG_MODE = true)
    this.debugRenderer = new DebugRenderer(THREE, scene);

    console.log('[ORB ARCHITECTURE RESTORED]');
    console.log('  OrbCore:', !!this.orbCore);
    console.log('  OrbitalRenderer:', !!this.orbitalRenderer);
    console.log('  EntitySystem:', !!this.entitySystem);
    console.log('  DebugRenderer (DEBUG_MODE):', window.DEBUG_MODE === true);
  }

  updateState(newState) {
    this.orbState = newState;
    window.orbState = newState;
  }

  animate(micLevel = 0) {
    if (!this.clock) return;
    if (!this.rm || !this.rm.scene) return;
    if (!this.rm || !this.rm.camera) return;
    if (!this.rm || !this.rm.renderer) return;
    if (!this.orbCore || !this.orbCore.group) return;

    const dt = this.clock.getDelta();
    const time = this.clock.getElapsedTime();

    // Animate Core, Orbital Rings, Entity System, and Debug (if enabled)
    this.orbCore.animate(time, this.orbState, micLevel, this.rm.bloomPass, this.rm.caPass);
    if (this.orbitalRenderer) this.orbitalRenderer.animate(time);
    if (this.entitySystem) this.entitySystem.animate(time);
    if (this.debugRenderer) this.debugRenderer.animate();
  }
}

export const orbManager = new OrbManager(rendererManager);
