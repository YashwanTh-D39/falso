/**
 * EntityRenderer module for FALSO 3D Spatial OS.
 * Manages real 3D system process and app nodes along orbital paths.
 * Never creates fake entities. Shows empty orbital paths when backend data is unavailable.
 */

import { diagnosticsManager } from './diagnostics.js';

export class EntityRenderer {
  constructor(THREE, scene) {
    this.THREE = THREE;
    this.scene = scene;
    this.group = new THREE.Group();
    this.nodes = new Map();
    if (this.scene) this.scene.add(this.group);
  }

  updateEntities(backendNodes = []) {
    if (!backendNodes || backendNodes.length === 0) {
      diagnosticsManager.updateNodeCount(0);
      return;
    }

    diagnosticsManager.updateNodeCount(backendNodes.length);

    const THREE = this.THREE;
    backendNodes.forEach((data, idx) => {
      const id = data.id || `node_${idx}`;
      if (!this.nodes.has(id)) {
        try {
          const geo = new THREE.SphereGeometry(0.1, 16, 16);
          const mat = new THREE.MeshBasicMaterial({
            color: data.color || 0x00E5FF,
            wireframe: true
          });
          const mesh = new THREE.Mesh(geo, mat);
          this.group.add(mesh);
          this.nodes.set(id, {
            mesh,
            radius: 2.2 + (idx % 3) * 1.6,
            angle: (idx / backendNodes.length) * Math.PI * 2,
            speed: 0.005
          });
        } catch (e) {
          console.error(`[ENTITY_RENDERER] Node ${id} creation error:`, e);
        }
      }
    });
  }

  animate(time) {
    if (!this.group) return;
    this.nodes.forEach((node) => {
      node.angle += node.speed;
      node.mesh.position.x = Math.cos(node.angle) * node.radius;
      node.mesh.position.z = Math.sin(node.angle) * node.radius;
      node.mesh.position.y = Math.sin(time + node.angle) * 0.15;
    });
  }
}
