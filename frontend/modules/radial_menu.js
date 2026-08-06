/**
 * Holographic 3D Radial Action Menu for FALSO Spatial OS.
 * Appears when holding or selecting a 3D object to provide context actions.
 */

import { createTextSprite } from './utils.js';

export class RadialMenu {
  constructor(scene, THREE) {
    this.scene = scene;
    this.THREE = THREE;

    this.menuGroup = new THREE.Group();
    this.menuGroup.name = 'SpatialRadialMenu';
    this.menuGroup.visible = false;
    this.scene.add(this.menuGroup);

    this.activeEntity = null;
    this.actionButtons = [];
  }

  showForEntity(entity, position) {
    this.activeEntity = entity;
    this.menuGroup.clear();
    this.actionButtons = [];

    const THREE = this.THREE;
    this.menuGroup.position.copy(position);

    const actions = this.getActionsForType(entity.data.type);
    const radius = 0.5;
    const angleStep = (Math.PI * 2) / actions.length;

    actions.forEach((act, idx) => {
      const angle = idx * angleStep;
      const x = Math.cos(angle) * radius;
      const y = Math.sin(angle) * radius;

      const sprite = createTextSprite(act.label, {
        fontsize: 20,
        backgroundColor: { r: 15, g: 30, b: 50, a: 0.9 },
        borderColor: { r: 0, g: 229, b: 255, a: 1.0 }
      });
      sprite.position.set(x, y, 0);
      sprite.userData = { action: act.id, data: entity.data };

      this.menuGroup.add(sprite);
      this.actionButtons.push(sprite);
    });

    this.menuGroup.visible = true;
  }

  hide() {
    this.menuGroup.visible = false;
    this.activeEntity = null;
  }

  getActionsForType(type) {
    if (type === 'file' || type === 'folder') {
      return [
        { id: 'open', label: '📂 Open' },
        { id: 'summarize', label: '🧠 Summarize' },
        { id: 'delete', label: '🗑 Delete' }
      ];
    } else if (type === 'process') {
      return [
        { id: 'kill', label: '❌ Terminate' },
        { id: 'info', label: '📊 Status' }
      ];
    }
    return [
      { id: 'info', label: '📊 Status' }
    ];
  }

  async triggerAction(actionId, entityData) {
    console.log(`[RadialMenu] Executing action: ${actionId} on`, entityData);
    if (actionId === 'open' && entityData.path) {
      await fetch('/api/v1/spatial/files/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_path: entityData.path })
      });
    } else if (actionId === 'summarize') {
      // Send to speech/chat prompt
      if (window.sendToFalso) {
        window.sendToFalso(`Summarize the file at ${entityData.path}`);
      }
    } else if (actionId === 'delete' && entityData.path) {
      const res = await fetch('/api/v1/spatial/files/request-delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_path: entityData.path })
      });
      const data = await res.json();
      if (data.token) {
        if (confirm(`Confirm deletion of ${entityData.name}?`)) {
          await fetch('/api/v1/spatial/confirm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: data.token })
          });
        }
      }
    } else if (actionId === 'kill' && entityData.pid) {
      const res = await fetch('/api/v1/spatial/processes/request-kill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pid: entityData.pid })
      });
      const data = await res.json();
      if (data.token) {
        await fetch('/api/v1/spatial/confirm', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token: data.token })
        });
      }
    }
    this.hide();
  }
}
