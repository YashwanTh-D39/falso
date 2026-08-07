/**
 * MaterialFactory module for FALSO Living Orb.
 * Centralized material creation for exact visual recreation matching the reference screenshot.
 */

export class MaterialFactory {
  constructor(THREE) {
    this.THREE = THREE;
    this.materials = new Map();
  }

  getOuterWireframeMaterial() {
    if (!this.materials.has('outerWireframe')) {
      const mat = new this.THREE.MeshBasicMaterial({
        color: 0x2A629A,
        wireframe: true,
        transparent: true,
        opacity: 0.35,
        depthWrite: false
      });
      this.materials.set('outerWireframe', mat);
    }
    return this.materials.get('outerWireframe');
  }

  getMiddleWireframeMaterial() {
    if (!this.materials.has('middleWireframe')) {
      const mat = new this.THREE.MeshBasicMaterial({
        color: 0x00E5FF,
        wireframe: true,
        transparent: true,
        opacity: 0.85,
        depthWrite: false
      });
      this.materials.set('middleWireframe', mat);
    }
    return this.materials.get('middleWireframe');
  }

  getCoreCrystalMaterial() {
    if (!this.materials.has('coreCrystal')) {
      const mat = new this.THREE.MeshBasicMaterial({
        color: 0x7DF9FF,
        wireframe: true,
        transparent: true,
        opacity: 0.95
      });
      this.materials.set('coreCrystal', mat);
    }
    return this.materials.get('coreCrystal');
  }

  getCoreSolidMaterial() {
    if (!this.materials.has('coreSolid')) {
      const mat = new this.THREE.MeshStandardMaterial({
        color: 0xE0F7FA,
        emissive: 0x00E5FF,
        emissiveIntensity: 0.9,
        roughness: 0.1,
        metalness: 0.9
      });
      this.materials.set('coreSolid', mat);
    }
    return this.materials.get('coreSolid');
  }

  getOrbitalRingMaterial(colorHex, opacity = 0.4) {
    const key = `orbital_${colorHex}_${opacity}`;
    if (!this.materials.has(key)) {
      const mat = new this.THREE.LineBasicMaterial({
        color: colorHex,
        transparent: true,
        opacity: opacity
      });
      this.materials.set(key, mat);
    }
    return this.materials.get(key);
  }
}
