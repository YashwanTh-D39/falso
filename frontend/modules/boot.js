/**
 * Single Initialization Orchestrator for FALSO.
 * Enforces a single boot sequence without duplicate listeners or initializers.
 */

import { rendererManager } from './renderer.js';
import { orbManager } from './orb.js';
import { SpatialObjectManager } from './spatial_objects.js';
import { SpatialWSClient } from './spatial_ws.js';
import { diagnosticsManager } from './diagnostics.js';
import { settingsManager } from './settings.js';
import { VoiceManager } from './voice.js';
import { ChatManager } from './chat.js';

class BootManager {
  constructor() {
    this.initialized = false;
    this.voiceManager = null;
    this.chatManager = null;
    this.spatialObjectManager = null;
    this.spatialWSClient = null;
  }

  async initializeApp() {
    if (this.initialized) return;
    this.initialized = true;

    console.log('[FALSO Boot Sequence] Initializing single modular boot pipeline...');

    // 1. Settings
    settingsManager.init();

    // 2. Renderer & Orb
    rendererManager.init();
    orbManager.init();

    // 3. Spatial 3D Objects & WebSocket
    this.spatialObjectManager = new SpatialObjectManager(rendererManager.scene, rendererManager.THREE);
    window.spatialObjectManager = this.spatialObjectManager;

    this.spatialWSClient = new SpatialWSClient((payload) => {
      this.spatialObjectManager.syncWithState(payload);
    });
    window.spatialWSClient = this.spatialWSClient;

    // 4. Voice & Chat Managers
    this.voiceManager = new VoiceManager(orbManager, settingsManager);
    this.chatManager = new ChatManager(this.voiceManager, settingsManager);

    // Make available globally for click/HUD events
    window.voiceManager = this.voiceManager;
    window.chatManager = this.chatManager;
    window.settingsManager = settingsManager;

    // 5. UI Event Listeners
    this.setupEventListeners();

    // 6. Voice Recognition
    this.voiceManager.initSpeechRecognition((cleanText) => {
      this.chatManager.sendToFalso(cleanText);
    });

    // 7. Request Mic Access
    this.voiceManager.requestMicPermission();

    // 8. Start Unified Animation Loop
    this.startAnimationLoop();

    this.voiceManager.changeState('idle');
    console.log('[FALSO Boot Sequence] Single boot complete -> Systems online!');
  }

  setupEventListeners() {
    const sendBtn = document.getElementById('btn-send');
    const cmdInput = document.getElementById('cmd-input');

    const handleSend = () => {
      const val = cmdInput.value.trim();
      if (val) {
        cmdInput.value = '';
        this.chatManager.sendToFalso(val);
      }
    };

    if (sendBtn) sendBtn.addEventListener('click', handleSend);
    if (cmdInput) {
      cmdInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') handleSend();
      });
    }

    // Keyboard Shortcuts
    window.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'd') {
        e.preventDefault();
        const modes = ['voice_only', 'display_mode', 'automatic_mode'];
        const nextIdx = (modes.indexOf(settingsManager.currentInteractionMode) + 1) % modes.length;
        settingsManager.updateInteractionMode(modes[nextIdx]);
      }
    });
  }

  startAnimationLoop() {
    const clock = rendererManager.THREE ? new rendererManager.THREE.Clock() : null;

    const animate = () => {
      requestAnimationFrame(animate);

      const delta = clock ? clock.getDelta() : 0.016;
      const elapsed = clock ? clock.getElapsedTime() : performance.now() / 1000;

      // 1. Render Three.js Scene
      rendererManager.render();

      // 2. Animate Living Orb
      orbManager.animate(window.micLevel || 0);

      // 3. Update 3D Orbiting Objects
      if (this.spatialObjectManager) {
        this.spatialObjectManager.update(delta, elapsed);
      }

      // 4. Throttled Diagnostics HUD (1 FPS)
      if (diagnosticsManager.tickFPS()) {
        const wsConn = this.spatialWSClient && this.spatialWSClient.ws && this.spatialWSClient.ws.readyState === 1;
        diagnosticsManager.renderHUD(
          this.voiceManager ? this.voiceManager.sysState : 'idle',
          this.voiceManager ? this.voiceManager.isSpeakingSpeech : false,
          this.voiceManager ? this.voiceManager.micActive : false,
          wsConn
        );
      }
    };

    animate();
  }
}

export const bootManager = new BootManager();
