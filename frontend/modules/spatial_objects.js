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

    // Map: objectId -> SpatialEntity
    this.entities = new Map();

    this.initSharedResources();
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

    // 1. Core Hardware Metrics (Ring 1)
    if (state.system) {
      const cpuId = 'hw_cpu';
      activeIds.add(cpuId);
      this.upsertEntity(cpuId, {
        type: 'system',
        name: 'CPU',
        label: `CPU: ${state.system.cpu.total_percent}%`,
        status: `${state.system.cpu.logical_cores} Cores | ${state.system.cpu.total_percent}% Load`,
        ring: 1,
        color: state.system.cpu.total_percent > 80 ? 0xEF5350 : 0x42A5F5
      });

      const ramId = 'hw_ram';
      activeIds.add(ramId);
      this.upsertEntity(ramId, {
        type: 'system',
        name: 'RAM',
        label: `RAM: ${state.system.ram.percent}%`,
        status: `${(state.system.ram.used / 1073741824).toFixed(1)} / ${(state.system.ram.total / 1073741824).toFixed(1)} GB`,
        ring: 1,
        color: state.system.ram.percent > 85 ? 0xEF5350 : 0x66BB6A
      });

      const netId = 'hw_net';
      activeIds.add(netId);
      this.upsertEntity(netId, {
        type: 'system',
        name: 'Network',
        label: `Net: ${(state.system.network.download_bytes_sec / (1024*1024)).toFixed(1)} MB/s`,
        status: `Down: ${(state.system.network.download_bytes_sec / (1024*1024)).toFixed(1)} MB/s | Up: ${(state.system.network.upload_bytes_sec / (1024*1024)).toFixed(1)} MB/s`,
        ring: 1,
        color: 0x26A69A
      });

      // Disk Drives
      if (state.system.disks) {
        state.system.disks.forEach(disk => {
          const driveId = `drive_${disk.device.replace(/[^a-zA-Z0-9]/g, '')}`;
          activeIds.add(driveId);
          this.upsertEntity(driveId, {
            type: 'drive',
            name: `${disk.mountpoint} Drive`,
            label: `${disk.mountpoint} (${disk.percent}%)`,
            status: `${(disk.free_bytes / (1073741824)).toFixed(0)} GB Free of ${(disk.total_bytes / (1073741824)).toFixed(0)} GB`,
            ring: 1,
            color: 0xB0BEC5
          });
        });
      }
    }

    // 2. Core System Folders (Ring 2)
    const defaultFolders = [
      { id: 'dir_project_falso', name: 'Project-Falso', path: 'c:/Users/Admin/Project-Falso', status: 'Active Project Directory' },
      { id: 'dir_downloads', name: 'Downloads', path: 'c:/Users/Admin/Downloads', status: 'User Downloads Directory' },
      { id: 'dir_desktop', name: 'Desktop', path: 'c:/Users/Admin/Desktop', status: 'User Desktop Directory' },
      { id: 'dir_documents', name: 'Documents', path: 'c:/Users/Admin/Documents', status: 'User Documents Directory' }
    ];

    defaultFolders.forEach(f => {
      activeIds.add(f.id);
      this.upsertEntity(f.id, {
        type: 'folder',
        name: f.name,
        label: f.name,
        path: f.path,
        status: f.status,
        ring: 2,
        color: 0xFFB74D
      });
    });

    // 3. Live Running Applications (Ring 3)
    if (state.processes) {
      state.processes.forEach((proc) => {
        const appId = `proc_${proc.pid}`;
        activeIds.add(appId);
        this.upsertEntity(appId, {
          type: 'app',
          name: proc.name,
          label: proc.name,
          status: proc.status || `PID: ${proc.pid} | CPU: ${proc.cpu_percent}%`,
          pid: proc.pid,
          ring: 3,
          color: proc.name === 'Chrome' ? 0xFF5252 : proc.name === 'Explorer' ? 0xFFC107 : 0x81C784
        });
      });
    }

    // 4. Live Indexed Files (Ring 4)
    if (state.files) {
      state.files.forEach((file) => {
        const fileId = `file_${file.path}`;
        activeIds.add(fileId);
        this.upsertEntity(fileId, {
          type: file.is_dir ? 'folder' : 'file',
          name: file.name,
          label: file.name.length > 18 ? file.name.substring(0, 15) + '...' : file.name,
          status: file.is_dir ? 'Folder' : `${(file.size_bytes / 1024).toFixed(1)} KB`,
          path: file.path,
          ring: 4,
          color: file.is_dir ? 0xFFB74D : 0x4FC3F7
        });
      });
    }

    // Remove stale entities (Apps closed, files deleted)
    for (const [id, entity] of this.entities.entries()) {
      if (!activeIds.has(id)) {
        this.containerGroup.remove(entity.group);
        this.entities.delete(id);
      }
    }
  }

  upsertEntity(id, data) {
    let entity = this.entities.get(id);

    if (!entity) {
      const THREE = this.THREE;
      const group = new THREE.Group();

      let geom = this.geometries.box;
      let mat = this.materials.file;

      if (data.type === 'app') {
        geom = this.geometries.octahedron;
        mat = this.materials.app;
      } else if (data.type === 'system') {
        geom = this.geometries.ring;
        mat = this.materials.system;
      } else if (data.type === 'folder') {
        geom = this.geometries.box;
        mat = this.materials.folder;
      } else if (data.type === 'drive') {
        geom = this.geometries.cylinder;
        mat = this.materials.drive;
      }

      const mesh = new THREE.Mesh(geom, mat.clone());
      if (data.color) {
        mesh.material.color.setHex(data.color);
      }
      group.add(mesh);

      // Add Canvas Sprite Label
      const label = createTextSprite(data.label || data.name, { fontsize: 22 });
      label.position.set(0, 0.28, 0);
      group.add(label);

      // Orbit parameters per ring
      const ringIndex = data.ring || 3;
      const baseRadius = 2.4 + ringIndex * 1.0;
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
      entity.mesh.rotation.x += 0.5 * delta;
      entity.mesh.rotation.y += 0.8 * delta;
    }
  }
}
