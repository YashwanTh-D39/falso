/**
 * OrbCore V2 module for FALSO Living Orb.
 * Implements 10-layer visual specifications:
 * 1. Faint containment sphere
 * 2. Latitude/Longitude holographic shell (20% opacity)
 * 4. Animated breathing plasma core
 * 5. Bright inner icosahedron crystal
 * 7. Radial center-outward fading energy particles
 * 9. State colors (idle: cyan, listening: blue pulse, thinking: purple, speaking: white/cyan, sleeping: dim blue)
 */

export class OrbCore {
  constructor(THREE) {
    this.THREE = THREE;
    this.group = new THREE.Group();

    this.containmentSphere = null;
    this.holographicShell = null;
    this.plasmaCore = null;
    this.innerCrystal = null;
    this.particlePoints = null;
    this.particlePositions = null;
    this.particleVelocities = null;
    this.particleCount = 150;

    this.coreMat = null;
    this.crystalMat = null;
    this.shellMat = null;

    this.init();
  }

  init() {
    const THREE = this.THREE;

    // Layer 1: Faint Large Containment Sphere
    try {
      const cGeo = new THREE.SphereGeometry(3.6, 32, 32);
      const cMat = new THREE.MeshBasicMaterial({
        color: 0x00E5FF,
        transparent: true,
        opacity: 0.05,
        side: THREE.BackSide
      });
      this.containmentSphere = new THREE.Mesh(cGeo, cMat);
      this.group.add(this.containmentSphere);
    } catch (e) {
      console.error('[ORB_CORE] Containment sphere error:', e);
    }

    // Layer 2: Latitude / Longitude Holographic Shell (20% Opacity)
    try {
      const sGeo = new THREE.SphereGeometry(2.4, 24, 18);
      this.shellMat = new THREE.MeshBasicMaterial({
        color: 0x00E5FF,
        wireframe: true,
        transparent: true,
        opacity: 0.20
      });
      this.holographicShell = new THREE.Mesh(sGeo, this.shellMat);
      this.group.add(this.holographicShell);
    } catch (e) {
      console.error('[ORB_CORE] Holographic shell error:', e);
    }

    // Layer 4: Central Plasma Core (Breathing Animated Sphere)
    try {
      const pGeo = new THREE.IcosahedronGeometry(0.85, 3);
      this.coreMat = new THREE.MeshStandardMaterial({
        color: 0x00E5FF,
        emissive: 0x00E5FF,
        emissiveIntensity: 0.8,
        roughness: 0.15,
        metalness: 0.85
      });
      this.plasmaCore = new THREE.Mesh(pGeo, this.coreMat);
      this.group.add(this.plasmaCore);
    } catch (e) {
      console.error('[ORB_CORE] Plasma core error:', e);
    }

    // Layer 5: Bright Inner Crystal (Icosahedron)
    try {
      const crystalGeo = new THREE.IcosahedronGeometry(0.4, 0);
      this.crystalMat = new THREE.MeshStandardMaterial({
        color: 0xF0F8FF,
        emissive: 0x80D8FF,
        emissiveIntensity: 1.2,
        roughness: 0.1,
        metalness: 0.9,
        wireframe: true
      });
      this.innerCrystal = new THREE.Mesh(crystalGeo, this.crystalMat);
      this.group.add(this.innerCrystal);
    } catch (e) {
      console.error('[ORB_CORE] Inner crystal error:', e);
    }

    // Layer 7: Center-Outward Moving Energy Particles
    try {
      const pGeo = new THREE.BufferGeometry();
      this.particlePositions = new Float32Array(this.particleCount * 3);
      this.particleVelocities = new Float32Array(this.particleCount * 3);

      for (let i = 0; i < this.particleCount; i++) {
        const i3 = i * 3;
        this.particlePositions[i3] = 0;
        this.particlePositions[i3 + 1] = 0;
        this.particlePositions[i3 + 2] = 0;

        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);
        const speed = 0.015 + Math.random() * 0.02;

        this.particleVelocities[i3] = Math.sin(phi) * Math.cos(theta) * speed;
        this.particleVelocities[i3 + 1] = Math.sin(phi) * Math.sin(theta) * speed;
        this.particleVelocities[i3 + 2] = Math.cos(phi) * speed;
      }

      pGeo.setAttribute('position', new THREE.BufferAttribute(this.particlePositions, 3));
      const pMat = new THREE.PointsMaterial({
        color: 0x80D8FF,
        size: 0.04,
        transparent: true,
        opacity: 0.6
      });
      this.particlePoints = new THREE.Points(pGeo, pMat);
      this.group.add(this.particlePoints);
    } catch (e) {
      console.error('[ORB_CORE] Energy particles error:', e);
    }
  }

  animate(time, orbState, micLevel = 0) {
    if (!this.group) return;

    // Smooth rotations
    if (this.holographicShell) {
      this.holographicShell.rotation.y += 0.0015;
      this.holographicShell.rotation.x += 0.0005;
    }

    if (this.innerCrystal) {
      this.innerCrystal.rotation.x += 0.005;
      this.innerCrystal.rotation.y += 0.01;
    }

    // Breathing plasma core animation
    const breath = Math.sin(time * 2.5) * 0.05;
    if (this.plasmaCore) this.plasmaCore.scale.setScalar(1.0 + breath);

    // Layer 7: Update Radial Energy Particles
    if (this.particlePositions && this.particlePoints) {
      const posAttr = this.particlePoints.geometry.attributes.position;
      for (let i = 0; i < this.particleCount; i++) {
        const i3 = i * 3;
        this.particlePositions[i3] += this.particleVelocities[i3];
        this.particlePositions[i3 + 1] += this.particleVelocities[i3 + 1];
        this.particlePositions[i3 + 2] += this.particleVelocities[i3 + 2];

        const dist = Math.sqrt(
          this.particlePositions[i3] ** 2 +
          this.particlePositions[i3 + 1] ** 2 +
          this.particlePositions[i3 + 2] ** 2
        );

        // Reset particle to center when it travels past 3.5 units
        if (dist > 3.5) {
          this.particlePositions[i3] = 0;
          this.particlePositions[i3 + 1] = 0;
          this.particlePositions[i3 + 2] = 0;
        }
      }
      posAttr.needsUpdate = true;
    }

    // Layer 9: State Colors (idle: cyan, listening: blue pulse, thinking: purple, speaking: white/cyan, sleeping: dim blue)
    if (this.coreMat) {
      if (orbState === 'thinking') {
        this.coreMat.color.setHex(0xAB47BC); // Purple energy
        this.coreMat.emissive.setHex(0x9C27B0);
        this.coreMat.emissiveIntensity = 1.0 + Math.sin(time * 10) * 0.3;
      } else if (orbState === 'listening') {
        let m = (micLevel / 128.0) * 0.5;
        this.coreMat.color.setHex(0x29B6F6); // Blue pulse
        this.coreMat.emissive.setHex(0x0288D1);
        this.coreMat.emissiveIntensity = 0.8 + m;
        if (this.plasmaCore) this.plasmaCore.scale.setScalar(1.0 + m * 0.6);
      } else if (orbState === 'speaking') {
        this.coreMat.color.setHex(0xE0F7FA); // White/cyan emission
        this.coreMat.emissive.setHex(0x00E5FF);
        this.coreMat.emissiveIntensity = 1.1 + Math.sin(time * 6) * 0.2;
      } else if (orbState === 'sleeping') {
        this.coreMat.color.setHex(0x0288D1); // Dim blue
        this.coreMat.emissive.setHex(0x01579B);
        this.coreMat.emissiveIntensity = 0.2;
      } else { // idle
        this.coreMat.color.setHex(0x00E5FF); // Cyan
        this.coreMat.emissive.setHex(0x00E5FF);
        this.coreMat.emissiveIntensity = 0.8;
      }
    }
  }
}
