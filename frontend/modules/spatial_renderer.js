/**
 * SpatialRenderer module for FALSO 3D Spatial OS.
 * Handles 3D spatial node positioning, raycasting, and visual layout.
 */

export class SpatialRenderer {
  constructor(THREE, camera, scene) {
    this.THREE = THREE;
    this.camera = camera;
    this.scene = scene;
    this.raycaster = THREE ? new THREE.Raycaster() : null;
    this.mouse = THREE ? new THREE.Vector2() : null;
  }

  raycast(event, objects) {
    if (!this.raycaster || !this.camera || !objects) return [];
    this.mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
    this.mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
    this.raycaster.setFromCamera(this.mouse, this.camera);
    return this.raycaster.intersectObjects(objects, true);
  }
}
