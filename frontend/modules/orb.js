/**
 * Original FALSO Living Orb implementation restored from project history (commit 7154029).
 * Features:
 * - Layer 1: Outer sphere lines shell (2.0)
 * - Layer 2: 30 Holographic grid panel planes (2.01)
 * - Layer 3: Secondary sphere lines shell (2.12)
 * - Layer 4: Inner glowing core shell (0.9)
 * - Layer 5: Innermost icosahedron core (0.25) & solid glow core (0.20)
 * - 5 Thin Neon Orbital Rings (1.8, 3.0, 4.2, 5.4, 6.6)
 * - Additive blending neon materials & multi-state animations
 */

import { rendererManager } from './renderer.js';

export class OrbManager {
  constructor(rendererManager) {
    this.rm = rendererManager;
    this.THREE = null;
    this.orbGroup = null;
    this.outerShell = null;
    this.secShell = null;
    this.innerCore = null;
    this.innerMost = null;
    this.glowCore = null;
    this.glowMat = null;
    this.rings = [];
    this.clock = null;
    this.orbState = 'idle';
  }

  addOrb() {
    if (!this.orbGroup) {
      this.init();
    }
  }

  init() {
    this.THREE = this.rm.THREE;
    const THREE = this.THREE;
    if (!THREE) throw new Error('Three.js instance missing in OrbManager');

    this.clock = new THREE.Clock();
    const scene = this.rm.scene;
    if (!scene) throw new Error('Scene missing in OrbManager.init()');

    // Ambient & Directional Lights
    const ambientLight = new THREE.AmbientLight(0x00E5FF, 0.6);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0x7DF9FF, 1.2);
    dirLight1.position.set(5, 10, 7);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0xFFB74D, 0.4);
    dirLight2.position.set(-5, -5, -5);
    scene.add(dirLight2);

    this.orbGroup = new THREE.Group();
    this.orbGroup.name = 'LivingOrbGroup';
    scene.add(this.orbGroup);

    // Color definitions
    const C_BRIGHT = 0x7DF9FF;
    const C_MID    = 0x00E5FF;
    const C_DIM    = 0x0080FF;
    const C_HOT    = 0x00FFFF;

    function lineMat(color, opacity = 1) {
      return new THREE.LineBasicMaterial({
        color,
        transparent: true,
        opacity,
        blending: THREE.AdditiveBlending,
        depthWrite: false
      });
    }

    const matBright = lineMat(C_BRIGHT, 0.8);
    const matMid = lineMat(C_MID, 0.5);
    const matDim = lineMat(C_DIM, 0.3);

    function createSphereLines(radius, wSeg, hSeg, material) {
      const geo = new THREE.SphereGeometry(radius, wSeg, hSeg);
      const edges = new THREE.EdgesGeometry(geo);
      return new THREE.LineSegments(edges, material);
    }

    // LAYER 1: Outer shell
    this.outerShell = createSphereLines(2.0, 24, 30, matDim);
    this.orbGroup.add(this.outerShell);

    // LAYER 2: Grid panels
    const panelMat = new THREE.MeshBasicMaterial({
      color: C_DIM,
      wireframe: true,
      transparent: true,
      opacity: 0.2
    });
    for (let i = 0; i < 30; i++) {
      const pGeo = new THREE.PlaneGeometry(0.3, 0.3);
      const pMesh = new THREE.Mesh(pGeo, panelMat);
      const phi = Math.acos(-1 + (2 * i) / 30);
      const theta = Math.sqrt(30 * Math.PI) * phi;
      pMesh.position.setFromSphericalCoords(2.01, phi, theta);
      pMesh.lookAt(0, 0, 0);
      this.orbGroup.add(pMesh);
    }

    // LAYER 3: Secondary shell
    this.secShell = createSphereLines(2.12, 12, 16, matMid);
    this.orbGroup.add(this.secShell);

    // LAYER 4: Inner core
    this.innerCore = createSphereLines(0.9, 16, 16, matBright);
    this.orbGroup.add(this.innerCore);

    // LAYER 5: Innermost core (Icosahedron)
    const icoGeo = new THREE.IcosahedronGeometry(0.25, 0);
    const icoEdges = new THREE.EdgesGeometry(icoGeo);
    this.innerMost = new THREE.LineSegments(icoEdges, new THREE.LineBasicMaterial({ color: C_HOT }));
    this.orbGroup.add(this.innerMost);

    const glowGeo = new THREE.SphereGeometry(0.2, 16, 16);
    this.glowMat = new THREE.MeshBasicMaterial({ color: C_HOT, transparent: true, opacity: 0.4 });
    this.glowCore = new THREE.Mesh(glowGeo, this.glowMat);
    this.orbGroup.add(this.glowCore);

    // 5 Thin Neon Orbital Rings
    const ringColors = [0x00E5FF, 0x81C784, 0xFF7043, 0xFFB74D, 0x42A5F5];
    [1.8, 3.0, 4.2, 5.4, 6.6].forEach((radius, idx) => {
      const points = [];
      const segments = 64;
      for (let i = 0; i <= segments; i++) {
        const theta = (i / segments) * Math.PI * 2;
        points.push(new THREE.Vector3(Math.cos(theta) * radius, 0, Math.sin(theta) * radius));
      }
      const circleGeo = new THREE.BufferGeometry().setFromPoints(points);
      const ringMat = new THREE.LineBasicMaterial({
        color: ringColors[idx],
        transparent: true,
        opacity: 0.28 - (idx * 0.04),
        blending: THREE.AdditiveBlending
      });
      const ringLine = new THREE.LineLoop(circleGeo, ringMat);
      ringLine.rotation.x = Math.PI * 0.04 * (idx % 2 === 0 ? 1 : -1);
      scene.add(ringLine);
      this.rings.push(ringLine);
    });
  }

  updateState(newState) {
    this.orbState = newState;
    window.orbState = newState;
  }

  animate(micLevel = 0) {
    if (!this.clock || !this.orbGroup) return;

    const dt = this.clock.getDelta();
    const time = this.clock.getElapsedTime();

    const bloomPass = this.rm.bloomPass;
    const caPass = this.rm.caPass;

    // State visual adjustments for all 8 states
    if (this.orbState === 'thinking') {
      this.orbGroup.rotation.y += 0.025;
      if (bloomPass) bloomPass.strength = 1.2 + Math.sin(time * 10) * 0.2;
      if (caPass && caPass.uniforms) caPass.uniforms.amount.value = 0.003;
      if (this.glowMat) this.glowMat.opacity = 0.85;
    } else if (this.orbState === 'listening') {
      this.orbGroup.rotation.y += 0.006;
      let m = (micLevel / 128.0) * 0.6;
      if (bloomPass) bloomPass.strength = 0.9 + m;
      if (this.innerCore) this.innerCore.scale.setScalar(1 + m);
      if (this.glowMat) this.glowMat.opacity = 0.6 + m * 0.4;
    } else if (this.orbState === 'speaking') {
      this.orbGroup.rotation.y += 0.012;
      if (bloomPass) bloomPass.strength = 1.0 + Math.sin(time * 6) * 0.2;
      if (caPass && caPass.uniforms) caPass.uniforms.amount.value = 0.002;
      if (this.glowMat) this.glowMat.opacity = 0.9;
    } else if (this.orbState === 'interrupted') {
      this.orbGroup.rotation.y += 0.04;
      if (bloomPass) bloomPass.strength = 1.4;
      if (caPass && caPass.uniforms) caPass.uniforms.amount.value = 0.004;
      if (this.innerCore) this.innerCore.scale.setScalar(0.7);
      if (this.glowMat) this.glowMat.opacity = 1.0;
    } else if (this.orbState === 'searching') {
      this.orbGroup.rotation.y += 0.035;
      if (this.outerShell) this.outerShell.rotation.z += 0.015;
      if (bloomPass) bloomPass.strength = 1.2;
      if (caPass && caPass.uniforms) caPass.uniforms.amount.value = 0.003;
      if (this.glowMat) this.glowMat.opacity = 0.95;
    } else if (this.orbState === 'sleeping') {
      this.orbGroup.rotation.y += 0.0008;
      if (bloomPass) bloomPass.strength = 0.4;
      if (caPass && caPass.uniforms) caPass.uniforms.amount.value = 0.001;
      if (this.innerCore) this.innerCore.scale.setScalar(0.95);
      if (this.glowMat) this.glowMat.opacity = 0.2;
    } else if (this.orbState === 'booting') {
      this.orbGroup.rotation.y += 0.015;
      if (bloomPass) bloomPass.strength = 0.6;
      if (caPass && caPass.uniforms) caPass.uniforms.amount.value = 0.001;
      if (this.glowMat) this.glowMat.opacity = 0.5;
    } else if (this.orbState === 'error') {
      this.orbGroup.rotation.y += 0.03;
      if (bloomPass) bloomPass.strength = 1.1 + Math.sin(time * 15) * 0.3;
      if (caPass && caPass.uniforms) caPass.uniforms.amount.value = 0.005;
      if (this.glowMat) this.glowMat.opacity = 0.9;
    } else { // idle
      this.orbGroup.rotation.y += 0.003;
      if (bloomPass) bloomPass.strength = 0.7;
      if (caPass && caPass.uniforms) caPass.uniforms.amount.value = 0.001;
      if (this.innerCore) this.innerCore.scale.setScalar(1);
      if (this.glowMat) this.glowMat.opacity = 0.4;
    }

    if (this.outerShell) {
      this.outerShell.rotation.y += 0.001;
      this.outerShell.rotation.z += 0.0005;
    }
    if (this.innerCore) this.innerCore.rotation.x -= 0.005;
    if (this.innerMost) this.innerMost.rotation.y += 0.02;
  }
}

export const orbManager = new OrbManager(rendererManager);
