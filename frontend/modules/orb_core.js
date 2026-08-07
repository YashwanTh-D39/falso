/**
 * OrbCore module for FALSO Living Orb.
 * Recreates the exact nested wireframe globes and crystal core from the reference screenshot.
 */

import { MaterialFactory } from './material_factory.js';

export class OrbCore {
  constructor(THREE) {
    this.THREE = THREE;
    this.matFactory = new MaterialFactory(THREE);
    this.group = new THREE.Group();

    this.outerGlobe = null;
    this.middleGlobe = null;
    this.innerCrystal = null;
    this.innerCoreSolid = null;

    this.init();
  }

  init() {
    const THREE = this.THREE;

    // Layer 1: Outer Large Dark Blue Wireframe Containment Globe (Radius ~3.5)
    try {
      const outerGeo = new THREE.SphereGeometry(3.5, 32, 24);
      const outerMat = this.matFactory.getOuterWireframeMaterial();
      this.outerGlobe = new THREE.Mesh(outerGeo, outerMat);
      this.group.add(this.outerGlobe);
    } catch (e) {
      console.error('[ORB_CORE] Outer globe creation error:', e);
    }

    // Layer 2: Middle Electric Cyan Wireframe Globe (Radius ~1.25)
    try {
      const middleGeo = new THREE.SphereGeometry(1.25, 24, 18);
      const middleMat = this.matFactory.getMiddleWireframeMaterial();
      this.middleGlobe = new THREE.Mesh(middleGeo, middleMat);
      this.group.add(this.middleGlobe);
    } catch (e) {
      console.error('[ORB_CORE] Middle globe creation error:', e);
    }

    // Layer 3: Innermost Polyhedron Crystal Core (Radius ~0.35)
    try {
      const crystalGeo = new THREE.IcosahedronGeometry(0.35, 0);
      const crystalMat = this.matFactory.getCoreCrystalMaterial();
      this.innerCrystal = new THREE.Mesh(crystalGeo, crystalMat);
      this.group.add(this.innerCrystal);

      // Solid glowing inner center
      const solidGeo = new THREE.IcosahedronGeometry(0.18, 1);
      const solidMat = this.matFactory.getCoreSolidMaterial();
      this.innerCoreSolid = new THREE.Mesh(solidGeo, solidMat);
      this.group.add(this.innerCoreSolid);
    } catch (e) {
      console.error('[ORB_CORE] Crystal core creation error:', e);
    }
  }

  animate(time, orbState, micLevel = 0) {
    if (!this.group) return;

    // Smooth counter-rotations matching reference
    if (this.outerGlobe) {
      this.outerGlobe.rotation.y += 0.0008;
      this.outerGlobe.rotation.x += 0.0003;
    }

    if (this.middleGlobe) {
      this.middleGlobe.rotation.y -= 0.003;
      this.middleGlobe.rotation.z += 0.001;
    }

    if (this.innerCrystal) {
      this.innerCrystal.rotation.x += 0.008;
      this.innerCrystal.rotation.y += 0.012;
    }

    if (this.innerCoreSolid) {
      this.innerCoreSolid.rotation.y -= 0.015;
    }

    // Animated breathing glow
    const breath = Math.sin(time * 2.0) * 0.04;
    if (this.innerCrystal) this.innerCrystal.scale.setScalar(1.0 + breath);
    if (this.middleGlobe) this.middleGlobe.scale.setScalar(1.0 - breath * 0.2);

    // State adjustments
    if (orbState === 'thinking') {
      if (this.middleGlobe) this.middleGlobe.rotation.y -= 0.015;
      if (this.innerCrystal) this.innerCrystal.rotation.y += 0.03;
    } else if (orbState === 'listening') {
      let m = (micLevel / 128.0) * 0.3;
      if (this.middleGlobe) this.middleGlobe.scale.setScalar(1.0 + m);
      if (this.innerCoreSolid) this.innerCoreSolid.scale.setScalar(1.0 + m * 0.8);
    } else if (orbState === 'speaking') {
      if (this.middleGlobe) this.middleGlobe.rotation.y -= 0.008;
    }
  }
}
