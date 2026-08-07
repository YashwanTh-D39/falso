/**
 * Spatial 3D Object Manager for FALSO Spatial OS.
 * Transforms live backend OS resources (Apps, Folders, Files, Drives, Hardware) into interactive 3D orbiting entities.
 */

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
    if (this.entities.size === 0) {
      console.log('[SpatialOS] Zero backend entities available -> Rendering fallback system entities');
      const fallbacks = [
        { id: 'fallback_core', type: 'system', name: 'FALSO Core', label: 'FALSO Core (Waiting...)', status: 'Waiting for live system entities...', ring: 1, color: 0x00E5FF },
        { id: 'fallback_sys', type: 'app', name: 'System Monitor', label: 'System Monitor', status: 'Connecting to Spatial WS...', ring: 2, color: 0x29B6F6 }
      ];
      fallbacks.forEach(item => this.upsertEntity(item.id, item));
    }
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
    const activeIds = new Set();

    // ── RING 1: Current Active Context (Radius 1.8) ──
    const ctx = state.context || {};
    const currentProj = ctx.project || 'Project-Falso';
    const activeWin = ctx.active_window || 'VS Code';
    const activeFile = ctx.active_file || 'index.html';

    const ring1Entities = [
      { id: 'ctx_proj', type: 'system', name: 'Project-Falso', label: `Proj: ${currentProj} (${ctx.git_branch || 'main'})`, status: `Git Branch: ${ctx.git_branch || 'main'} | ${ctx.git_uncommitted || 0} uncommitted changes`, ring: 1, color: 0x00E5FF },
      { id: 'ctx_win', type: 'app', name: 'Active Window', label: activeWin.length > 20 ? activeWin.substring(0, 17) + '...' : activeWin, status: `Window: ${activeWin} (${ctx.running_ide || 'IDE'})`, ring: 1, color: 0x7DF9FF },
      { id: 'ctx_file', type: 'file', name: 'Active File', label: `File: ${activeFile}`, status: `Editing File: ${activeFile}`, ring: 1, color: 0x4FC3F7 }
    ];

    ring1Entities.forEach(item => {
      activeIds.add(item.id);
      this.upsertEntity(item.id, item);
    });

    // ── RING 2: Running Applications (Radius 3.0) ──
    if (state.processes) {
      state.processes.forEach(proc => {
        const appId = `proc_${proc.pid}`;
        activeIds.add(appId);
        let color = 0x29B6F6; // Blue
        if (proc.name.includes('Chrome')) color = 0x42A5F5;
        else if (proc.name.includes('Edge')) color = 0x00B0FF;
        else if (proc.name.includes('Code')) color = 0x29B6F6;
        else if (proc.name.includes('Explorer')) color = 0xFFA726;
        else if (proc.name.includes('Terminal') || proc.name.includes('Python')) color = 0xAB47BC;

        this.upsertEntity(appId, {
          type: 'app',
          name: proc.name,
          label: proc.name,
          status: proc.status || `PID: ${proc.pid} | CPU: ${proc.cpu_percent}%`,
          pid: proc.pid,
          ring: 2,
          color: color
        });
      });
    }

    // ── RING 3: File System Folders & Recent Files (Radius 4.2) ──
    const systemFolders = [
      { id: 'dir_project_falso', name: 'Project-Falso', path: 'c:/Users/Admin/Project-Falso' },
      { id: 'dir_desktop', name: 'Desktop', path: 'c:/Users/Admin/Desktop' },
      { id: 'dir_downloads', name: 'Downloads', path: 'c:/Users/Admin/Downloads' },
      { id: 'dir_documents', name: 'Documents', path: 'c:/Users/Admin/Documents' },
      { id: 'dir_pictures', name: 'Pictures', path: 'c:/Users/Admin/Pictures' },
      { id: 'dir_videos', name: 'Videos', path: 'c:/Users/Admin/Videos' },
      { id: 'dir_music', name: 'Music', path: 'c:/Users/Admin/Music' }
    ];

    systemFolders.forEach(f => {
      activeIds.add(f.id);
      this.upsertEntity(f.id, {
        type: 'folder',
        name: f.name,
        label: f.name,
        path: f.path,
        status: `Directory: ${f.name}`,
        ring: 3,
        color: 0xFFB74D // Amber
      });
    });

    if (state.files) {
      state.files.slice(0, 10).forEach(file => {
        const fileId = `file_${file.path}`;
        activeIds.add(fileId);
        this.upsertEntity(fileId, {
          type: file.is_dir ? 'folder' : 'file',
          name: file.name,
          label: file.name.length > 18 ? file.name.substring(0, 15) + '...' : file.name,
          status: file.is_dir ? 'Folder' : `${(file.size_bytes / 1024).toFixed(1)} KB`,
          path: file.path,
          ring: 3,
          color: file.is_dir ? 0xFFB74D : 0x4FC3F7
        });
      });
    }

    // ── RING 4: System Hardware Telemetry (Radius 5.4) ──
    if (state.system) {
      const cpuId = 'hw_cpu';
      activeIds.add(cpuId);
      this.upsertEntity(cpuId, {
        type: 'system',
        name: 'CPU',
        label: `CPU: ${state.system.cpu.total_percent}%`,
        status: `${state.system.cpu.logical_cores} Cores | ${state.system.cpu.total_percent}% Load`,
        ring: 4,
        color: state.system.cpu.total_percent > 80 ? 0xEF5350 : 0x66BB6A // Emerald Green / Red
      });

      const ramId = 'hw_ram';
      activeIds.add(ramId);
      this.upsertEntity(ramId, {
        type: 'system',
        name: 'RAM',
        label: `RAM: ${state.system.ram.percent}%`,
        status: `${(state.system.ram.used / 1073741824).toFixed(1)} / ${(state.system.ram.total / 1073741824).toFixed(1)} GB`,
        ring: 4,
        color: state.system.ram.percent > 85 ? 0xEF5350 : 0x66BB6A
      });

      const netId = 'hw_net';
      activeIds.add(netId);
      this.upsertEntity(netId, {
        type: 'system',
        name: 'Network',
        label: `Net: ${(state.system.network.download_bytes_sec / (1024*1024)).toFixed(1)} MB/s`,
        status: `Down: ${(state.system.network.download_bytes_sec / (1024*1024)).toFixed(1)} MB/s | Up: ${(state.system.network.upload_bytes_sec / (1024*1024)).toFixed(1)} MB/s`,
        ring: 4,
        color: 0x26A69A
      });

      if (state.system.disks) {
        state.system.disks.forEach(disk => {
          const driveId = `drive_${disk.device.replace(/[^a-zA-Z0-9]/g, '')}`;
          activeIds.add(driveId);
          this.upsertEntity(driveId, {
            type: 'drive',
            name: `${disk.mountpoint} Drive`,
            label: `${disk.mountpoint} (${disk.percent}%)`,
            status: `${(disk.free_bytes / (1073741824)).toFixed(0)} GB Free of ${(disk.total_bytes / (1073741824)).toFixed(0)} GB`,
            ring: 4,
            color: 0xB0BEC5
          });
        });
      }

      if (state.system.battery) {
        const batId = 'hw_battery';
        activeIds.add(batId);
        this.upsertEntity(batId, {
          type: 'system',
          name: 'Battery',
          label: `Bat: ${state.system.battery.percent}%`,
          status: `${state.system.battery.percent}% | ${state.system.battery.power_plugged ? 'Plugged In' : 'Discharging'}`,
          ring: 4,
          color: 0xFFD54F
        });
      }
    }

    // ── RING 5: Browser Tabs (Radius 6.6) ──
    if (state.browser_tabs && state.browser_tabs.length > 0) {
      state.browser_tabs.forEach((tab, idx) => {
        const tabId = `tab_${idx}_${tab.title.replace(/[^a-zA-Z0-9]/g, '')}`;
        activeIds.add(tabId);
        const shortTitle = tab.title.length > 20 ? tab.title.substring(0, 17) + '...' : tab.title;
        this.upsertEntity(tabId, {
          type: 'app',
          name: tab.title,
          label: `[${tab.browser}] ${shortTitle}`,
          status: `Browser Tab: ${tab.title}`,
          ring: 5,
          color: tab.browser === 'Chrome' ? 0xFF7043 : 0x26C6DA
        });
      });
    }

    // Remove stale entities (Apps closed, files deleted, tabs closed)
    for (const [id, entity] of this.entities.entries()) {
      if (!activeIds.has(id)) {
        this.containerGroup.remove(entity.group);
        this.entities.delete(id);
      }
    }

    // Update global telemetry counters for Debug Panel & Empty State
    if (typeof window !== 'undefined') {
      window.renderedEntitiesCount = activeIds.size;
      window.lastWsUpdateTime = Date.now();
      console.log(`[Frontend Received & Orb Rendered] ${activeIds.size} real system entities`);
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
