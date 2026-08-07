/**
 * EntitySystem module for FALSO 3D Spatial OS.
 * Manages dynamic 3D entity nodes orbiting the Living Orb.
 * Keeps orb alive and shows empty orbital paths when backend entities are unavailable.
 */

import { diagnosticsManager } from './diagnostics.js';

export class EntitySystem {
  constructor(THREE, scene) {
    this.THREE = THREE;
    this.scene = scene;
    this.group = new THREE.Group();
    this.entities = new Map();
    if (this.scene) this.scene.add(this.group);
  }

  updateEntities(backendNodes = []) {
    if (!backendNodes || backendNodes.length === 0) {
      diagnosticsManager.updateNodeCount(0);
      return;
    }

    diagnosticsManager.updateNodeCount(backendNodes.length);

    // Dynamic entity instantiation
    const THREE = this.THREE;
    backendNodes.forEach((nodeData, idx) => {
      const id = nodeData.id || `node_${idx}`;
      if (!this.entities.has(id)) {
        const geo = new THREE.SphereGeometry(0.12, 16, 16);
        const mat = new THREE.MeshStandardMaterial({
          color: nodeData.color || 0x00E5FF,
          emissive: nodeData.color || 0x00E5FF,
          emissiveIntensity: 0.5,
          roughness: 0.2
        });
        const mesh = new THREE.Mesh(geo, mat);
        this.group.add(mesh);
        this.entities.set(id, { mesh, angle: (idx / backendNodes.length) * Math.PI * 2, radius: 2.2 + (idx % 4) * 1.2 });
      }
    });
  }

  animate(time) {
    if (!this.group) return;
    this.entities.forEach((entity, id) => {
      entity.angle += 0.005;
      const x = Math.cos(entity.angle) * entity.radius;
      const z = Math.sin(entity.angle) * entity.radius;
      const y = Math.sin(time * 2 + entity.angle) * 0.2;
      entity.mesh.position.set(x, y, z);
    });
  }
}
