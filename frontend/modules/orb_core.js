/**
 * OrbCore module for FALSO Living Orb.
 * Jarvis / DeepMind inspired holographic energy core.
 * Features central glowing energy core, animated plasma shell, dynamic bloom,
 * pulsating energy, breathing animation, and energy particles.
 */

export class OrbCore {
  constructor(THREE) {
    this.THREE = THREE;
    this.group = new THREE.Group();
    this.innerCore = null;
    this.outerShell = null;
    this.plasmaMesh = null;
    this.particles = null;
    this.glowMat = null;
    this.init();
  }

  init() {
    const THREE = this.THREE;

    // Layer 1: Core Energy Sphere - Bright white-cyan energy
    const coreGeo = new THREE.IcosahedronGeometry(0.85, 4);
    const coreMat = new THREE.MeshStandardMaterial({
      color: 0xF0F8FF,
      emissive: 0x00E5FF,
      emissiveIntensity: 0.8,
      roughness: 0.1,
      metalness: 0.9,
      wireframe: false
    });
    this.innerCore = new THREE.Mesh(coreGeo, coreMat);
    this.group.add(this.innerCore);

    // Layer 2: Animated Plasma Wireframe Shell
    const shellGeo = new THREE.IcosahedronGeometry(1.25, 3);
    const shellMat = new THREE.MeshStandardMaterial({
      color: 0x00E5FF,
      emissive: 0x00E5FF,
      emissiveIntensity: 0.4,
      roughness: 0.15,
      metalness: 0.85,
      wireframe: true,
      transparent: true,
      opacity: 0.5
    });
    this.outerShell = new THREE.Mesh(shellGeo, shellMat);
    this.group.add(this.outerShell);

    // Layer 3: Plasma Aura Sphere
    const plasmaGeo = new THREE.IcosahedronGeometry(1.45, 2);
    const plasmaMat = new THREE.MeshBasicMaterial({
      color: 0x7DF9FF,
      wireframe: true,
      transparent: true,
      opacity: 0.25
    });
    this.plasmaMesh = new THREE.Mesh(plasmaGeo, plasmaMat);
    this.group.add(this.plasmaMesh);

    // Layer 4: Outer Glow Sphere
    const glowGeo = new THREE.SphereGeometry(1.6, 32, 32);
    this.glowMat = new THREE.MeshBasicMaterial({
      color: 0x00E5FF,
      transparent: true,
      opacity: 0.35,
      side: THREE.BackSide
    });
    const glowMesh = new THREE.Mesh(glowGeo, this.glowMat);
    this.group.add(glowMesh);

    // Layer 5: Floating Energy Particle Dust
    const particleCount = 120;
    const pGeo = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount * 3; i += 3) {
      const r = 1.6 + Math.random() * 0.8;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      positions[i] = r * Math.sin(phi) * Math.cos(theta);
      positions[i + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i + 2] = r * Math.cos(phi);
    }
    pGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const pMat = new THREE.PointsMaterial({
      color: 0x80D8FF,
      size: 0.04,
      transparent: true,
      opacity: 0.7
    });
    this.particles = new THREE.Points(pGeo, pMat);
    this.group.add(this.particles);
  }

  animate(time, orbState, micLevel = 0, bloomPass, caPass) {
    if (!this.group || !this.innerCore) return;

    // Continuous smooth rotations
    this.outerShell.rotation.y += 0.002;
    this.outerShell.rotation.x += 0.001;
    this.plasmaMesh.rotation.y -= 0.003;
    this.particles.rotation.y += 0.0015;

    // Pulsating energy & smooth breathing animation
    const breath = Math.sin(time * 2.2) * 0.04;
    this.innerCore.scale.setScalar(1.0 + breath);
    this.plasmaMesh.scale.setScalar(1.0 - breath * 0.5);

    // State-driven visuals (60% bloom cap)
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
      this.innerCore.scale.setScalar(1);
      this.glowMat.opacity = 0.35;
    }
  }
}
