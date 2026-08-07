/**
 * OrbitalRenderer module for FALSO Living Orb V2.
 * Renders Layer 3 (Three independent orbital rings with different inclinations/speeds)
 * and Layer 8 (Reserves 40 orbital slots for backend system entities).
 */

import { MaterialFactory } from './material_factory.js';

export class OrbitalRenderer {
  constructor(THREE) {
    this.THREE = THREE;
    this.matFactory = new MaterialFactory(THREE);
    this.group = new THREE.Group();
    this.rings = [];
    this.slots = [];
    this.init();
  }

  init() {
    const THREE = this.THREE;

    // Layer 3: 3 Independent Orbital Rings with different inclinations and speeds
    const ringConfigs = [
      { radius: 2.8, color: 0x00E5FF, opacity: 0.45, rx: Math.PI / 2.3, ry: 0.25, speed: 0.0012 },
      { radius: 3.2, color: 0x448AFF, opacity: 0.35, rx: -Math.PI / 2.1, ry: -0.45, speed: -0.0018 },
      { radius: 3.6, color: 0xBA68C8, opacity: 0.30, rx: Math.PI / 1.9, ry: 0.35, speed: 0.0015 }
    ];

    ringConfigs.forEach((cfg, idx) => {
      try {
        const segments = 128;
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array((segments + 1) * 3);

        for (let i = 0; i <= segments; i++) {
          const theta = (i / segments) * Math.PI * 2;
          positions[i * 3] = Math.cos(theta) * cfg.radius;
          positions[i * 3 + 1] = 0;
          positions[i * 3 + 2] = Math.sin(theta) * cfg.radius;
        }

        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        const material = this.matFactory.getOrbitalRingMaterial(cfg.color, cfg.opacity);
        const line = new THREE.Line(geometry, material);

        line.rotation.x = cfg.rx;
        line.rotation.y = cfg.ry;

        this.group.add(line);
        this.rings.push({ line, speed: cfg.speed, radius: cfg.radius });
      } catch (e) {
        console.error(`[ORBITAL_RENDERER] Ring ${idx} creation error:`, e);
      }
    });

    // Layer 8: Reserve 40 Orbital Slots across the 3 rings
    const totalSlots = 40;
    for (let i = 0; i < totalSlots; i++) {
      const ringIdx = i % this.rings.length;
      const angle = (i / totalSlots) * Math.PI * 2;
      this.slots.push({
        slotId: i,
        ringIdx,
        radius: this.rings[ringIdx].radius,
        angle,
        occupied: false
      });
    }
  }

  animate(time) {
    if (!this.group) return;
    this.rings.forEach((r, idx) => {
      r.line.rotation.z += r.speed;
      r.line.position.y = Math.sin(time * 0.8 + idx) * 0.03;
    });
  }
}
