/**
 * OrbCore module for FALSO Living Orb.
 * Renders the animated energy core, electric cyan shell, outer glow mesh, and smooth breathing animation.
 */

export class OrbCore {
  constructor(THREE) {
    this.THREE = THREE;
    this.group = new THREE.Group();
    this.innerCore = null;
    this.outerShell = null;
    this.glowMat = null;
    this.init();
  }

  init() {
    const THREE = this.THREE;

    // Layer 1: Energy Core - Bright white-blue energy
    const coreGeo = new THREE.IcosahedronGeometry(0.85, 4);
    const coreMat = new THREE.MeshStandardMaterial({
      color: 0xF0F8FF,
      emissive: 0x80D8FF,
      emissiveIntensity: 0.6,
      roughness: 0.1,
      metalness: 0.9,
      wireframe: false
    });
    this.innerCore = new THREE.Mesh(coreGeo, coreMat);
    this.group.add(this.innerCore);

    // Layer 2: Inner Shell - Electric cyan
    const shellGeo = new THREE.IcosahedronGeometry(1.2, 3);
    const shellMat = new THREE.MeshStandardMaterial({
      color: 0x00E5FF,
      emissive: 0x00E5FF,
      emissiveIntensity: 0.3,
      roughness: 0.15,
      metalness: 0.85,
      wireframe: true,
      transparent: true,
      opacity: 0.45
    });
    this.outerShell = new THREE.Mesh(shellGeo, shellMat);
    this.group.add(this.outerShell);

    // Layer 3: Outer Shell Glow
    const glowGeo = new THREE.SphereGeometry(1.4, 32, 32);
    this.glowMat = new THREE.MeshBasicMaterial({
      color: 0x00E5FF,
      transparent: true,
      opacity: 0.35,
      side: THREE.BackSide
    });
    const glowMesh = new THREE.Mesh(glowGeo, this.glowMat);
    this.group.add(glowMesh);
  }

  animate(time, orbState, micLevel = 0, bloomPass, caPass) {
    if (!this.group || !this.innerCore) return;

    // Continuous rotation
    this.outerShell.rotation.y += 0.001;
    this.outerShell.rotation.x += 0.0005;

    // Smooth breathing animation
    const breath = Math.sin(time * 2.0) * 0.04;
    this.innerCore.scale.setScalar(1.0 + breath);

    // State-driven visuals
    if (orbState === 'thinking') {
      this.group.rotation.y += 0.025;
      if (bloomPass) bloomPass.strength = 1.1 + Math.sin(time * 10) * 0.2;
      if (caPass && caPass.uniforms) caPass.uniforms.amount.value = 0.003;
      this.glowMat.opacity = 0.65;
    } else if (orbState === 'listening') {
      this.group.rotation.y += 0.006;
      let m = (micLevel / 128.0) * 0.4;
      if (bloomPass) bloomPass.strength = 0.8 + m;
      this.innerCore.scale.setScalar(1 + m * 0.5);
      this.glowMat.opacity = 0.5 + m * 0.3;
    } else if (orbState === 'speaking') {
      this.group.rotation.y += 0.012;
      if (bloomPass) bloomPass.strength = 0.9 + Math.sin(time * 6) * 0.2;
      if (caPass && caPass.uniforms) caPass.uniforms.amount.value = 0.002;
      this.glowMat.opacity = 0.7;
    } else if (orbState === 'interrupted') {
      this.group.rotation.y += 0.04;
      if (bloomPass) bloomPass.strength = 1.2;
      if (caPass && caPass.uniforms) caPass.uniforms.amount.value = 0.004;
      this.innerCore.scale.setScalar(0.85);
      this.glowMat.opacity = 0.8;
    } else if (orbState === 'searching') {
      this.group.rotation.y += 0.035;
      this.outerShell.rotation.z += 0.015;
      if (bloomPass) bloomPass.strength = 1.1;
      if (caPass && caPass.uniforms) caPass.uniforms.amount.value = 0.003;
      this.glowMat.opacity = 0.75;
    } else if (orbState === 'sleeping') {
      this.group.rotation.y += 0.0008;
      if (bloomPass) bloomPass.strength = 0.4;
      if (caPass && caPass.uniforms) caPass.uniforms.amount.value = 0.001;
      this.innerCore.scale.setScalar(0.95);
      this.glowMat.opacity = 0.2;
    } else if (orbState === 'booting') {
      this.group.rotation.y += 0.015;
      if (bloomPass) bloomPass.strength = 0.6;
      if (caPass && caPass.uniforms) caPass.uniforms.amount.value = 0.001;
      this.glowMat.opacity = 0.4;
    } else if (orbState === 'error') {
      this.group.rotation.y += 0.03;
      if (bloomPass) bloomPass.strength = 1.0 + Math.sin(time * 15) * 0.3;
      if (caPass && caPass.uniforms) caPass.uniforms.amount.value = 0.005;
      this.glowMat.opacity = 0.8;
    } else { // idle
      this.group.rotation.y += 0.003;
      if (bloomPass) bloomPass.strength = 0.7;
      if (caPass && caPass.uniforms) caPass.uniforms.amount.value = 0.001;
      this.glowMat.opacity = 0.35;
    }
  }
}
