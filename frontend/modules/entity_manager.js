/**
 * EntityManager module for FALSO 3D Spatial OS.
 * Tracks live system processes, applications, open folders, and hardware statistics.
 */

export class EntityManager {
  constructor() {
    this.nodes = new Map();
  }

  processSpatialPacket(payload) {
    if (!payload || !payload.nodes) return [];
    this.nodes.clear();
    payload.nodes.forEach((n) => {
      this.nodes.set(n.id, n);
    });
    return Array.from(this.nodes.values());
  }
}

export const entityManager = new EntityManager();
