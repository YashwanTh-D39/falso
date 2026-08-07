/**
 * AnimationController module for FALSO 3D Spatial OS.
 * Manages frame delta, elapsed time, and smooth animation ticks.
 */

export class AnimationController {
  constructor(THREE) {
    this.THREE = THREE;
    this.clock = THREE ? new THREE.Clock() : null;
    this.elapsedTime = 0;
  }

  tick() {
    if (!this.clock) return { dt: 0.016, time: performance.now() / 1000 };
    const dt = this.clock.getDelta();
    this.elapsedTime += dt;
    return { dt, time: this.elapsedTime };
  }
}
