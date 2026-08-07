/**
 * DebugRenderer module for FALSO 3D Spatial OS.
 * Strictly gated behind DEBUG_MODE = true.
 * NEVER renders debug geometry in production.
 */

export class DebugRenderer {
  constructor(THREE, scene) {
    this.THREE = THREE;
    this.scene = scene;
    this.debugGroup = null;
    this.isEnabled = window.DEBUG_MODE === true;
  }

  setDebugMode(enabled) {
    this.isEnabled = enabled === true;
    window.DEBUG_MODE = this.isEnabled;

    if (!this.isEnabled && this.debugGroup && this.scene) {
      this.scene.remove(this.debugGroup);
      this.debugGroup = null;
    }
  }

  renderDebugHelpers() {
    if (!this.isEnabled) return;

    if (!this.debugGroup && this.THREE && this.scene) {
      this.debugGroup = new this.THREE.Group();
      const axesHelper = new this.THREE.AxesHelper(3);
      this.debugGroup.add(axesHelper);
      this.scene.add(this.debugGroup);
      console.log('[DEBUG_RENDERER] Debug helpers initialized');
    }
  }

  animate() {
    if (!this.isEnabled) return;
    this.renderDebugHelpers();
  }
}
