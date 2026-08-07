/**
 * Settings & Interaction Mode Management Module for FALSO Spatial OS.
 */

export class SettingsManager {
  constructor() {
    this.currentInteractionMode = localStorage.getItem('falso_interaction_mode') || 'voice_only';
  }

  init() {
    this.applyInteractionModeUI();
  }

  updateInteractionMode(mode, saveToBackend = true) {
    this.currentInteractionMode = mode;
    localStorage.setItem('falso_interaction_mode', mode);
    this.applyInteractionModeUI();

    if (saveToBackend) {
      fetch('/api/v1/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ interaction_mode: mode })
      }).catch(e => console.warn('[Profile Sync Error]', e));
    }
  }

  applyInteractionModeUI(hasCodeOrArtifact = false) {
    const chatArea = document.getElementById('chat-area');
    const setSelect = document.getElementById('set-interaction-mode');
    if (setSelect) setSelect.value = this.currentInteractionMode;

    if (!chatArea) return;

    if (this.currentInteractionMode === 'voice_only') {
      chatArea.style.display = 'none';
    } else if (this.currentInteractionMode === 'display_mode') {
      chatArea.style.display = 'flex';
      chatArea.style.opacity = '1.0';
    } else if (this.currentInteractionMode === 'automatic_mode') {
      if (hasCodeOrArtifact) {
        chatArea.style.display = 'flex';
        chatArea.style.opacity = '0.95';
      } else {
        chatArea.style.display = 'none';
      }
    }
  }

  toggleTranscript() {
    const chatArea = document.getElementById('chat-area');
    if (!chatArea) return;
    if (chatArea.style.display === 'none' || chatArea.style.display === '') {
      chatArea.style.display = 'flex';
      chatArea.style.opacity = '0.95';
    } else {
      if (this.currentInteractionMode === 'voice_only') {
        chatArea.style.display = 'none';
      }
    }
  }
}

export const settingsManager = new SettingsManager();
