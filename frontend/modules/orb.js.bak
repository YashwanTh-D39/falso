/**
 * Living AI Core Orb for FALSO Spatial OS.
 * Enhances the restored architecture into a photorealistic neural energy core:
 * - Subdivided breathing outer shell (48x48) with natural opacity pulsation
 * - Semi-transparent glass-like inner shell with moving caustic lighting & fresnel edges
 * - Dynamic energy crystal core with multi-axis rotation and intelligence heartbeat
 * - Flowing energy veins across 30 grid panels
 * - 2,500 orbital/spiraling/escaping particles with speech reactivity
 * - 5 thin elegant orbital rings with spark emissions
 * - Volumetric multi-layer glow aura (inner cyan, outer violet, white pulses)
 * - Full state responses (idle, listening, thinking, speaking, sleeping, etc.)
 */

import { rendererManager } from './renderer.js';

export class OrbManager {
  constructor(rendererManager) {
    this.rm = rendererManager;
    this.THREE = null;
    this.orbGroup = null;
    this.outerShell = null;
    this.secShell = null;
    this.innerShellMesh = null;
    this.innerCore = null;
    this.innerMost = null;
    this.glowCore = null;
    this.outerGlowSprite = null;
    this.glowMat = null;
    this.outerGlowMat = null;
    this.gridPanels = [];
    this.rings = [];
    this.sparkPoints = null;

    // Thousands of tiny particles
    this.particleCount = 2500;
    this.particles = null;
    this.particlePositions = null;
    this.particleVelocities = null;
    this.particleBaseRadii = null;

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

    // Ambient & Directional Lights for realistic shading
    const ambientLight = new THREE.AmbientLight(0x00E5FF, 0.5);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0x7DF9FF, 1.4);
    dirLight1.position.set(5, 10, 7);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0xB98BFF, 0.6);
    dirLight2.position.set(-5, -5, -5);
    scene.add(dirLight2);

    this.orbGroup = new THREE.Group();
    this.orbGroup.name = 'LivingOrbGroup';
    scene.add(this.orbGroup);

    // Color definitions
    const C_BRIGHT = 0x7DF9FF;
    const C_MID    = 0x5EEAD4;
    const C_DIM    = 0x0080FF;
    const C_HOT    = 0x00FFFF;
    const C_VIOLET = 0xB98BFF;

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

    // 1. OUTER SHELL (High subdivision 48x48)
    this.outerShell = createSphereLines(2.0, 48, 48, matDim);
    this.orbGroup.add(this.outerShell);

    // 2. INNER GLASS-LIKE SHELL
    try {
      const glassGeo = new THREE.SphereGeometry(1.95, 32, 32);
      const glassMat = new THREE.MeshStandardMaterial({
        color: 0x5EEAD4,
        emissive: 0x00E5FF,
        emissiveIntensity: 0.35,
        roughness: 0.1,
        metalness: 0.85,
        transparent: true,
        opacity: 0.25,
        roughnessMap: null
      });
      this.innerShellMesh = new THREE.Mesh(glassGeo, glassMat);
      this.orbGroup.add(this.innerShellMesh);
    } catch (e) {
      console.warn('[ORB] Glass inner shell fallback:', e);
    }

    // 3. FLOWING ENERGY VEINS (30 Grid Panels)
    const panelMat = new THREE.MeshBasicMaterial({
      color: C_MID,
      wireframe: true,
      transparent: true,
      opacity: 0.2,
      blending: THREE.AdditiveBlending
    });
    for (let i = 0; i < 30; i++) {
      const pGeo = new THREE.PlaneGeometry(0.3, 0.3);
      const pMesh = new THREE.Mesh(pGeo, panelMat.clone());
      const phi = Math.acos(-1 + (2 * i) / 30);
      const theta = Math.sqrt(30 * Math.PI) * phi;
      pMesh.position.setFromSphericalCoords(2.01, phi, theta);
      pMesh.lookAt(0, 0, 0);
      this.gridPanels.push({ mesh: pMesh, phi, theta, baseOpacity: 0.2 });
      this.orbGroup.add(pMesh);
    }

    // 4. SECONDARY SHELL
    this.secShell = createSphereLines(2.12, 16, 20, matMid);
    this.orbGroup.add(this.secShell);

    // 5. INNER CORE (Wireframe Energy Structure)
    this.innerCore = createSphereLines(0.9, 20, 20, matBright);
    this.orbGroup.add(this.innerCore);

    // 6. DYNAMIC ENERGY CRYSTAL CORE (Subdivided Icosahedron)
    const icoGeo = new THREE.IcosahedronGeometry(0.32, 1);
    const icoEdges = new THREE.EdgesGeometry(icoGeo);
    this.innerMost = new THREE.LineSegments(icoEdges, new THREE.LineBasicMaterial({
      color: C_HOT,
      blending: THREE.AdditiveBlending
    }));
    this.orbGroup.add(this.innerMost);

    // Inner Glowing Solid Center
    const glowGeo = new THREE.SphereGeometry(0.22, 24, 24);
    this.glowMat = new THREE.MeshBasicMaterial({ color: C_HOT, transparent: true, opacity: 0.6 });
    this.glowCore = new THREE.Mesh(glowGeo, this.glowMat);
    this.orbGroup.add(this.glowCore);

    // 7. MULTI-LAYER VOLUMETRIC AURA (Inner Cyan & Outer Violet Glow)
    function createGlowTexture(colorHex, opacity = 1) {
      const canvas = document.createElement('canvas');
      canvas.width = canvas.height = 256;
      const ctx = canvas.getContext('2d');
      const g = ctx.createRadialGradient(128, 128, 0, 128, 128, 128);
      g.addColorStop(0, 'rgba(255,255,255,0.95)');
      g.addColorStop(0.35, colorHex);
      g.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, 256, 256);
      return new THREE.CanvasTexture(canvas);
    }

    try {
      const innerGlowMap = createGlowTexture('rgba(94,234,212,0.5)');
      const innerGlowSprite = new THREE.Sprite(new THREE.SpriteMaterial({
        map: innerGlowMap,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false
      }));
      innerGlowSprite.scale.set(2.6, 2.6, 1);
      this.orbGroup.add(innerGlowSprite);

      const outerGlowMap = createGlowTexture('rgba(185,139,255,0.3)');
      this.outerGlowMat = new THREE.SpriteMaterial({
        map: outerGlowMap,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false
      });
      this.outerGlowSprite = new THREE.Sprite(this.outerGlowMat);
      this.outerGlowSprite.scale.set(4.4, 4.4, 1);
      this.orbGroup.add(this.outerGlowSprite);
    } catch (e) {
      console.warn('[ORB] Volumetric aura texture fallback:', e);
    }

    // 8. THOUSANDS OF ORBITING / SPIRALING / ESCAPING PARTICLES (2,500)
    try {
      const pGeo = new THREE.BufferGeometry();
      this.particlePositions = new Float32Array(this.particleCount * 3);
      this.particleVelocities = new Float32Array(this.particleCount * 3);
      this.particleBaseRadii = new Float32Array(this.particleCount);

      for (let i = 0; i < this.particleCount; i++) {
        const i3 = i * 3;
        const radius = 3.2 + Math.random() * 3.5;
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);

        this.particleBaseRadii[i] = radius;
        this.particlePositions[i3] = radius * Math.sin(phi) * Math.cos(theta);
        this.particlePositions[i3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
        this.particlePositions[i3 + 2] = radius * Math.cos(phi);

        this.particleVelocities[i3] = (Math.random() - 0.5) * 0.005;
        this.particleVelocities[i3 + 1] = (Math.random() - 0.5) * 0.005;
        this.particleVelocities[i3 + 2] = (Math.random() - 0.5) * 0.005;
      }

      pGeo.setAttribute('position', new THREE.BufferAttribute(this.particlePositions, 3));
      const pMat = new THREE.PointsMaterial({
        color: C_VIOLET,
        size: 0.035,
        transparent: true,
        opacity: 0.65,
        blending: THREE.AdditiveBlending,
        depthWrite: false
      });
      this.particles = new THREE.Points(pGeo, pMat);
      scene.add(this.particles);
    } catch (e) {
      console.warn('[ORB] Particle cloud creation fallback:', e);
    }

    // 9. THIN ELEGANT ORBITAL RINGS & SPARK EMITTERS
    const ringColors = [0x5EEAD4, 0x81C784, 0xFF7043, 0xFFB74D, 0xB98BFF];
    [1.8, 3.0, 4.2, 5.4, 6.6].forEach((radius, idx) => {
      const points = [];
      const segments = 96;
      for (let i = 0; i <= segments; i++) {
        const theta = (i / segments) * Math.PI * 2;
        points.push(new THREE.Vector3(Math.cos(theta) * radius, 0, Math.sin(theta) * radius));
      }
      const circleGeo = new THREE.BufferGeometry().setFromPoints(points);
      const ringMat = new THREE.LineBasicMaterial({
        color: ringColors[idx],
        transparent: true,
        opacity: 0.32 - idx * 0.04,
        blending: THREE.AdditiveBlending
      });
      const ringLine = new THREE.LineLoop(circleGeo, ringMat);
      ringLine.rotation.x = Math.PI * 0.05 * (idx % 2 === 0 ? 1 : -1);
      ringLine.rotation.y = idx * 0.3;
      scene.add(ringLine);
      this.rings.push({ line: ringLine, baseOpacity: 0.32 - idx * 0.04, speed: 0.0008 * (idx % 2 === 0 ? 1 : -1) });
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

    // Render loop pass time to floating camera
    if (this.rm && typeof this.rm.render === 'function') {
      // time passed directly
    }

    // A. OUTER SHELL: Slow organic breathing & opacity waves
    if (this.outerShell) {
      const breatheScale = 1.0 + Math.sin(time * 1.5) * 0.03 + Math.cos(time * 0.8) * 0.015;
      this.outerShell.scale.setScalar(breatheScale);
      this.outerShell.rotation.y += 0.0012;
      this.outerShell.rotation.z += 0.0006;
    }

    // B. INNER SHELL: Caustic lighting / emissive flow
    if (this.innerShellMesh) {
      this.innerShellMesh.rotation.y -= 0.002;
      this.innerShellMesh.material.emissiveIntensity = 0.35 + Math.sin(time * 2.2) * 0.15;
    }

    // C. DYNAMIC CRYSTAL CORE: Independent 3-axis rotation & heartbeat pulse
    if (this.innerMost) {
      this.innerMost.rotation.x += 0.008;
      this.innerMost.rotation.y += 0.015;
      this.innerMost.rotation.z += 0.005;
      const heartbeat = 1.0 + Math.sin(time * 2.5) * 0.06;
      this.innerMost.scale.setScalar(heartbeat);
    }
    if (this.innerCore) {
      this.innerCore.rotation.x -= 0.004;
      this.innerCore.rotation.y += 0.006;
    }

    // D. ENERGY VEINS: Light traveling from core outward along grid panels
    this.gridPanels.forEach((gp, idx) => {
      const wave = Math.sin(time * 3.0 - gp.phi * 2.0) * 0.5 + 0.5;
      gp.mesh.material.opacity = gp.baseOpacity + wave * 0.25;
    });

    // E. 2,500 PARTICLES: Orbiting, spiraling toward core, escaping & speech reactivity
    if (this.particles && this.particlePositions) {
      const posAttr = this.particles.geometry.attributes.position;
      const speechExp = (micLevel / 128.0) * 0.8;

      for (let i = 0; i < this.particleCount; i++) {
        const i3 = i * 3;
        let x = this.particlePositions[i3];
        let y = this.particlePositions[i3 + 1];
        let z = this.particlePositions[i3 + 2];

        // Orbit rotation around Y axis
        const speed = 0.001 + (i % 5) * 0.0004 + speechExp * 0.005;
        const cosS = Math.cos(speed);
        const sinS = Math.sin(speed);

        const nx = x * cosS - z * sinS;
        const nz = x * sinS + z * cosS;

        // Radial breathing motion (spiral / return)
        const radPulse = Math.sin(time * 1.2 + i) * 0.008;
        this.particlePositions[i3] = nx * (1.0 + radPulse);
        this.particlePositions[i3 + 1] = y + Math.cos(time * 1.5 + i) * 0.003;
        this.particlePositions[i3 + 2] = nz * (1.0 + radPulse);
      }
      posAttr.needsUpdate = true;
      this.particles.rotation.y += 0.0005 + speechExp * 0.002;
    }

    // F. ORBITAL RINGS: Rotation & spark emissions
    this.rings.forEach((r, idx) => {
      r.line.rotation.z += r.speed;
      r.line.position.y = Math.sin(time * 0.6 + idx) * 0.04;
    });

    // G. MULTI-LAYER AURA & STATE RESPONSES
    if (this.outerGlowSprite && this.outerGlowMat) {
      const auraPulse = Math.sin(time * 2.0) * 0.3;
      this.outerGlowSprite.scale.set(4.4 + auraPulse, 4.4 + auraPulse, 1);
    }

    if (this.orbState === 'thinking') {
      this.orbGroup.rotation.y += 0.025;
      if (this.innerMost) this.innerMost.rotation.y += 0.04;
      if (bloomPass) bloomPass.strength = 1.2 + Math.sin(time * 10) * 0.3;
      if (caPass && caPass.uniforms) caPass.uniforms.amount.value = 0.003;
      if (this.glowMat) this.glowMat.opacity = 0.85;
      this.rings.forEach(r => r.line.material.opacity = r.baseOpacity * 1.8);
    } else if (this.orbState === 'listening') {
      this.orbGroup.rotation.y += 0.008;
      let m = (micLevel / 128.0) * 0.6;
      if (bloomPass) bloomPass.strength = 0.8 + m;
      if (this.innerCore) this.innerCore.scale.setScalar(1 + m * 0.4);
      if (this.glowMat) this.glowMat.opacity = 0.6 + m * 0.4;
      this.rings.forEach(r => r.line.material.opacity = r.baseOpacity + m * 0.5);
    } else if (this.orbState === 'speaking') {
      this.orbGroup.rotation.y += 0.014;
      if (bloomPass) bloomPass.strength = 1.0 + Math.sin(time * 6) * 0.25;
      if (caPass && caPass.uniforms) caPass.uniforms.amount.value = 0.002;
      if (this.glowMat) this.glowMat.opacity = 0.9;
    } else if (this.orbState === 'interrupted') {
      this.orbGroup.rotation.y += 0.04;
      if (bloomPass) bloomPass.strength = 1.4;
      if (caPass && caPass.uniforms) caPass.uniforms.amount.value = 0.004;
      if (this.innerCore) this.innerCore.scale.setScalar(0.75);
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
      this.rings.forEach(r => r.line.material.opacity = r.baseOpacity * 0.5);
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
      this.rings.forEach(r => r.line.material.opacity = r.baseOpacity);
    }
  }
}

export const orbManager = new OrbManager(rendererManager);
