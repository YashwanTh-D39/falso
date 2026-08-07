import { rendererManager } from './renderer.js';

export class OrbManager {
  constructor(rendererManager) {
    this.rm = rendererManager;
    this.THREE = rendererManager.THREE;
    this.orbGroup = null;
    this.innerCore = null;
    this.outerShell = null;
    this.glowMat = null;
    this.clock = new this.THREE.Clock();
    this.orbState = 'idle';
  }

  init() {
    const THREE = this.THREE;
    const scene = this.rm.scene;

    // Ambient & Directional Lighting
    const ambientLight = new THREE.AmbientLight(0x00E5FF, 0.6);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0x7DF9FF, 1.2);
    dirLight1.position.set(5, 10, 7);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0xFFB74D, 0.4);
    dirLight2.position.set(-5, -5, -5);
    scene.add(dirLight2);

    this.orbGroup = new THREE.Group();
    scene.add(this.orbGroup);

    // Layer 1: Core - Bright white-blue energy
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
    this.orbGroup.add(this.innerCore);

    // Layer 2: Inner shell - Electric cyan
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
    this.orbGroup.add(this.outerShell);

    // Layer 3: Outer Shell Glow
    const glowGeo = new THREE.SphereGeometry(1.4, 32, 32);
    this.glowMat = new THREE.MeshBasicMaterial({
      color: 0x00E5FF,
      transparent: true,
      opacity: 0.35,
      side: THREE.BackSide
    });
    const glowMesh = new THREE.Mesh(glowGeo, this.glowMat);
    this.orbGroup.add(glowMesh);
  }

  updateState(newState) {
    this.orbState = newState;
    window.orbState = newState;
  }

  animate(micLevel = 0) {
    const dt = this.clock.getDelta();
    const time = this.clock.getElapsedTime();

    if (!this.orbGroup) return;

    this.outerShell.rotation.y += 0.001;
    this.outerShell.rotation.x += 0.0005;

    const bloomPass = this.rm.bloomPass;
    const caPass = this.rm.caPass;

    // 60% bloom reduction state visual adjustments
    if (this.orbState === 'thinking') {
      this.orbGroup.rotation.y += 0.025;
      bloomPass.strength = 1.1 + Math.sin(time * 10) * 0.2;
      caPass.uniforms.amount.value = 0.003;
      this.glowMat.opacity = 0.65;
    } else if (this.orbState === 'listening') {
      this.orbGroup.rotation.y += 0.006;
      let m = (micLevel / 128.0) * 0.4;
      bloomPass.strength = 0.8 + m;
      this.innerCore.scale.setScalar(1 + m * 0.5);
      this.glowMat.opacity = 0.5 + m * 0.3;
    } else if (this.orbState === 'speaking') {
      this.orbGroup.rotation.y += 0.012;
      bloomPass.strength = 0.9 + Math.sin(time * 6) * 0.2;
      caPass.uniforms.amount.value = 0.002;
      this.glowMat.opacity = 0.7;
    } else if (this.orbState === 'interrupted') {
      this.orbGroup.rotation.y += 0.04;
      bloomPass.strength = 1.2;
      caPass.uniforms.amount.value = 0.004;
      this.innerCore.scale.setScalar(0.85);
      this.glowMat.opacity = 0.8;
    } else if (this.orbState === 'searching') {
      this.orbGroup.rotation.y += 0.035;
      this.outerShell.rotation.z += 0.015;
      bloomPass.strength = 1.1;
      caPass.uniforms.amount.value = 0.003;
      this.glowMat.opacity = 0.75;
    } else if (this.orbState === 'sleeping') {
      this.orbGroup.rotation.y += 0.0008;
      bloomPass.strength = 0.4;
      caPass.uniforms.amount.value = 0.001;
      this.innerCore.scale.setScalar(0.95);
      this.glowMat.opacity = 0.2;
    } else if (this.orbState === 'booting') {
      this.orbGroup.rotation.y += 0.015;
      bloomPass.strength = 0.6;
      caPass.uniforms.amount.value = 0.001;
      this.glowMat.opacity = 0.4;
    } else if (this.orbState === 'error') {
      this.orbGroup.rotation.y += 0.03;
      bloomPass.strength = 1.0 + Math.sin(time * 15) * 0.3;
      caPass.uniforms.amount.value = 0.005;
      this.glowMat.opacity = 0.8;
    } else { // idle
      this.orbGroup.rotation.y += 0.003;
      bloomPass.strength = 0.7;
      caPass.uniforms.amount.value = 0.001;
      this.innerCore.scale.setScalar(1);
      this.glowMat.opacity = 0.35;
    }
  }
}

export const orbManager = new OrbManager(rendererManager);
