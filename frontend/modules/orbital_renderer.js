/**
 * OrbitalRenderer module for FALSO Living Orb.
 * Recreates thin intersecting orbital rings matching the reference screenshot.
 * Reserves orbital paths for backend system entities (Chrome, VS Code, Explorer, CPU, RAM, etc.).
 */

import { MaterialFactory } from './material_factory.js';

export class OrbitalRenderer {
  constructor(THREE) {
    this.THREE = THREE;
    this.matFactory = new MaterialFactory(THREE);
    this.group = new THREE.Group();
    this.rings = [];
    this.init();
  }

  init() {
    const THREE = this.THREE;
    const ringConfigs = [
      { radius: 2.2, color: 0x00E5FF, opacity: 0.5, rx: Math.PI / 2.2, ry: 0.1, speed: 0.001 },
      { radius: 3.8, color: 0xFFB74D, opacity: 0.35, rx: Math.PI / 2.0, ry: -0.2, speed: -0.0008 },
      { radius: 4.8, color: 0xFF5252, opacity: 0.25, rx: Math.PI / 1.8, ry: 0.3, speed: 0.0006 },
      { radius: 5.8, color: 0x00E676, opacity: 0.2, rx: Math.PI / 2.1, ry: -0.4, speed: -0.0005 }
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
        this.rings.push({ line, speed: cfg.speed });
      } catch (e) {
        console.error(`[ORBITAL_RENDERER] Ring ${idx} creation error:`, e);
      }
    });
  }

  animate(time) {
    if (!this.group) return;
    this.rings.forEach((r, idx) => {
      r.line.rotation.z += r.speed;
      r.line.position.y = Math.sin(time * 0.8 + idx) * 0.03;
    });
  }
}
