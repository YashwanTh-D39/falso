/**
 * OrbitalRenderer module for FALSO Living Orb.
 * Renders multiple orbital paths/rings (Rings 1-5) around the Living Orb.
 * Shows empty glowing orbital paths when no backend entities are present.
 */

export class OrbitalRenderer {
  constructor(THREE) {
    this.THREE = THREE;
    this.group = new THREE.Group();
    this.rings = [];
    this.init();
  }

  init() {
    const THREE = this.THREE;
    const radii = [1.8, 3.0, 4.2, 5.4, 6.6];
    const colors = [0x00E5FF, 0x448AFF, 0xFFB74D, 0x00E676, 0xBA68C8];

    radii.forEach((r, idx) => {
      const ringGeo = new THREE.RingGeometry(r - 0.015, r + 0.015, 64);
      const ringMat = new THREE.MeshBasicMaterial({
        color: colors[idx],
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.25 - idx * 0.03
      });
      const ringMesh = new THREE.Mesh(ringGeo, ringMat);
      ringMesh.rotation.x = Math.PI / 2 + (idx * 0.1);
      ringMesh.rotation.y = idx * 0.15;
      this.group.add(ringMesh);
      this.rings.push({ mesh: ringMesh, speed: 0.001 + idx * 0.0005 });
    });
  }

  animate(time) {
    if (!this.group) return;
    this.rings.forEach((r, i) => {
      r.mesh.rotation.z += r.speed;
      r.mesh.position.y = Math.sin(time + i) * 0.05;
    });
  }
}
