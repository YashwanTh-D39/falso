/**
 * Spatial 3D Object Manager for FALSO Spatial OS.
 * Transforms live backend OS resources (Apps, Folders, Files, Drives, Hardware) into interactive 3D orbiting entities.
 */

import * as THREE from 'three';
import { createTextSprite } from './utils.js';

export class SpatialObjectManager {
  constructor(scene, THREE) {
    this.scene = scene;
    this.THREE = THREE;
    
    // Group container for all orbiting entities
    this.containerGroup = new THREE.Group();
    this.containerGroup.name = 'SpatialOSObjects';
    this.scene.add(this.containerGroup);

    this.entities = new Map();
    this.materialCache = new Map();
    this.initSharedResources();
  }

  ensureFallbackEntities() {
    // No-op: Do not render fallback objects around the orb core
  }

  initSharedResources() {
    const THREE = this.THREE;
    this.materials = {
      app: new THREE.MeshStandardMaterial({ color: 0x81C784, roughness: 0.2, metalness: 0.9, transparent: true, opacity: 0.95 }),
      folder: new THREE.MeshStandardMaterial({ color: 0xFFB74D, roughness: 0.3, metalness: 0.8, transparent: true, opacity: 0.9 }),
      file: new THREE.MeshStandardMaterial({ color: 0x4FC3F7, roughness: 0.3, metalness: 0.8, transparent: true, opacity: 0.85 }),
      drive: new THREE.MeshStandardMaterial({ color: 0xB0BEC5, roughness: 0.2, metalness: 0.9, transparent: true, opacity: 0.9 }),
      system: new THREE.MeshStandardMaterial({ color: 0xFF7043, roughness: 0.2, metalness: 0.9, transparent: true, opacity: 0.9 })
    };

    this.geometries = {
      box: new THREE.BoxGeometry(0.22, 0.26, 0.06),
      sphere: new THREE.SphereGeometry(0.16, 16, 16),
      octahedron: new THREE.OctahedronGeometry(0.18, 0),
      cylinder: new THREE.CylinderGeometry(0.15, 0.15, 0.1, 16),
      ring: new THREE.TorusGeometry(0.18, 0.03, 16, 32)
    };
  }

  syncWithState(state) {
    const candidates = [];
    const MAX_VISIBLE_ENTITIES = 15;

    const ctx = state.context || {};

    // Deduplicate running processes into high-value application nodes
    if (state.processes) {
      const procMap = new Map();
      state.processes.forEach(proc => {
        const nameLower = proc.name.toLowerCase();
        let key = 'other';
        let label = proc.name;
        let priority = 30;
        let color = 0x29B6F6;

        if (nameLower.includes('ollama')) {
          key = 'ollama'; label = 'Ollama LLM'; priority = 82; color = 0x7DF9FF;
        } else if (nameLower.includes('code')) {
          key = 'vscode'; label = 'VS Code'; priority = 78; color = 0x29B6F6;
        } else if (nameLower.includes('chrome')) {
          key = 'chrome'; label = 'Chrome'; priority = 72; color = 0x42A5F5;
        } else if (nameLower.includes('edge')) {
          key = 'edge'; label = 'MS Edge'; priority = 70; color = 0x00B0FF;
        } else if (nameLower.includes('python')) {
          key = 'python'; label = 'Python Core'; priority = 75; color = 0xAB47BC;
        } else if (nameLower.includes('cmd') || nameLower.includes('powershell') || nameLower.includes('terminal')) {
          key = 'terminal'; label = 'Terminal'; priority = 68; color = 0xAB47BC;
        } else if (nameLower.includes('explorer')) {
          key = 'explorer'; label = 'File Explorer'; priority = 50; color = 0xFFA726;
        }

        if (key !== 'other') {
          if (!procMap.has(key) || proc.cpu_percent > procMap.get(key).proc.cpu_percent) {
            procMap.set(key, { key, label, priority, color, proc });
          }
        }
      });

      procMap.forEach(item => {
        candidates.push({
          id: `proc_app_${item.key}`,
          type: 'app',
          name: item.label,
          label: item.label,
          status: `App: ${item.label} (PID ${item.proc.pid} | CPU: ${item.proc.cpu_percent}%)`,
          ring: 2,
          color: item.color,
          priority: item.priority
        });
      });
    }

    // Hardware Telemetry Nodes (CPU, RAM, Network)
    if (state.system) {
      candidates.push({
        id: 'hw_cpu',
        type: 'system',
        name: 'CPU',
        label: `CPU: ${state.system.cpu.total_percent}%`,
        status: `${state.system.cpu.logical_cores} Cores | ${state.system.cpu.total_percent}% Load`,
        ring: 3,
        color: state.system.cpu.total_percent > 80 ? 0xEF5350 : 0x66BB6A,
        priority: 65
      });

      candidates.push({
        id: 'hw_ram',
        type: 'system',
        name: 'RAM',
        label: `RAM: ${state.system.ram.percent}%`,
        status: `${(state.system.ram.used / 1073741824).toFixed(1)} / ${(state.system.ram.total / 1073741824).toFixed(1)} GB`,
        ring: 3,
        color: state.system.ram.percent > 85 ? 0xEF5350 : 0x66BB6A,
        priority: 60
      });

      candidates.push({
        id: 'hw_net',
        type: 'system',
        name: 'Network',
        label: `Net: ${(state.system.network.download_bytes_sec / (1024*1024)).toFixed(1)} MB/s`,
        status: `Down: ${(state.system.network.download_bytes_sec / (1024*1024)).toFixed(1)} MB/s`,
        ring: 3,
        color: 0x26A69A,
        priority: 55
      });
    }

    // Sort by Priority Descending & Enforce Hard Budget MAX_VISIBLE_ENTITIES = 15
    candidates.sort((a, b) => b.priority - a.priority);
    const selected = candidates.slice(0, MAX_VISIBLE_ENTITIES);

    const activeIds = new Set();
    selected.forEach(item => {
      activeIds.add(item.id);
      this.upsertEntity(item.id, item);
    });

    // Remove stale/hidden entities
    for (const [id, entity] of this.entities.entries()) {
      if (!activeIds.has(id)) {
        if (entity.group && this.containerGroup) {
          this.containerGroup.remove(entity.group);
        }
        this.entities.delete(id);
      }
    }
    
    // Update global telemetry counters for Debug Panel
    if (typeof window !== 'undefined') {
      window.renderedEntitiesCount = this.entities.size;
      window.lastWsUpdateTime = Date.now();
      console.log(`[Frontend Received & Orb Rendered] ${this.entities.size} active 3D entities`);
    }
  }

  getMaterialForColor(hexColor) {
    if (!this.materialCache.has(hexColor)) {
      const mat = new this.THREE.MeshStandardMaterial({
        color: hexColor,
        roughness: 0.25,
        metalness: 0.85,
        transparent: true,
        opacity: 0.95
      });
      this.materialCache.set(hexColor, mat);
    }
    return this.materialCache.get(hexColor);
  }

  upsertEntity(id, data) {
    const THREE = this.THREE;
    let entity = this.entities.get(id);

    if (!entity) {
      const group = new THREE.Group();
      let geom = this.geometries.sphere;

      if (data.type === 'app') {
        geom = this.geometries.octahedron;
      } else if (data.type === 'file') {
        geom = this.geometries.box;
      } else if (data.type === 'folder') {
        geom = this.geometries.box;
      } else if (data.type === 'drive') {
        geom = this.geometries.cylinder;
      } else if (data.type === 'system') {
        geom = this.geometries.ring;
      }

      const mat = this.getMaterialForColor(data.color || 0x00E5FF);
      const mesh = new THREE.Mesh(geom, mat);
      group.add(mesh);

      // Add Canvas Sprite Label
      const label = createTextSprite(data.label || data.name, { fontsize: 22 });
      label.position.set(0, 0.28, 0);
      group.add(label);

      // Orbit parameters per ring
      const ringIndex = data.ring || 3;
      const baseRadius = 1.4 + ringIndex * 1.1;
      const angle = Math.random() * Math.PI * 2;
      const speed = (0.04 + Math.random() * 0.04) * (ringIndex % 2 === 0 ? 1 : -1);

      entity = {
        id,
        data,
        group,
        mesh,
        label,
        orbitRadius: baseRadius,
        orbitAngle: angle,
        orbitSpeed: speed
      };

      this.containerGroup.add(group);
      this.entities.set(id, entity);
      window.renderedEntitiesCount = this.entities.size;
    } else {
      entity.data = data;
    }
  }

  update(delta, elapsed) {
    for (const [id, entity] of this.entities.entries()) {
      entity.orbitAngle += entity.orbitSpeed * delta;
      const x = Math.cos(entity.orbitAngle) * entity.orbitRadius;
      const z = Math.sin(entity.orbitAngle) * entity.orbitRadius;
      const y = Math.sin(elapsed * 1.5 + entity.orbitAngle) * 0.15;

      entity.group.position.set(x, y, z);
      entity.mesh.rotation.y += delta * 0.5;

      // Distance culling for sprite labels (only show labels facing user)
      if (entity.label) {
        entity.label.visible = z > -entity.orbitRadius * 0.6;
      }
    }
  }
}
