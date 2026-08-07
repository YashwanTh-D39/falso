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
    try {
      // 1. Settings
      console.log('[FALSO Boot Step 1/8] Initializing Settings...');
      settingsManager.init();

      // 2. Three.js Scene, Camera, & Renderer
      console.log('[FALSO Boot Step 2/8] Initializing Renderer, Scene & Camera...');
      rendererManager.init();
      if (!rendererManager.scene || !rendererManager.camera || !rendererManager.renderer) {
        throw new Error('Three.js scene/camera/renderer initialization failed');
      }

      // 3. OrbManager Instantiation & Attachment
      console.log('[FALSO Boot Step 3/8] Initializing Living Orb Manager...');
      orbManager.init();
      if (!orbManager.orbGroup) {
        throw new Error('OrbManager orbGroup failed to attach to scene');
      }

      // 4. Spatial 3D Objects Manager & Fallback Entities
      console.log('[FALSO Boot Step 4/8] Initializing Spatial Object Manager...');
      this.spatialObjectManager = new SpatialObjectManager(rendererManager.scene, rendererManager.THREE);
      window.spatialObjectManager = this.spatialObjectManager;
      this.spatialObjectManager.ensureFallbackEntities();

      // 5. WebSocket Connection & Packet Listener
      console.log('[FALSO Boot Step 5/8] Connecting Spatial Telemetry WebSocket...');
      this.spatialWSClient = new SpatialWSClient((payload) => {
        console.log('[SPATIAL WS] Entity packet received:', payload ? Object.keys(payload) : null);
        if (this.spatialObjectManager) {
          this.spatialObjectManager.syncWithState(payload);
        }
      });
      window.spatialWSClient = this.spatialWSClient;

      // 6. Voice & Chat Managers
      console.log('[FALSO Boot Step 6/8] Initializing Voice & Chat Managers...');
      this.voiceManager = new VoiceManager(orbManager, settingsManager);
      this.chatManager = new ChatManager(this.voiceManager, settingsManager);

      window.voiceManager = this.voiceManager;
      window.chatManager = this.chatManager;
      window.settingsManager = settingsManager;

      // 7. UI Listeners & Speech Recognition
      console.log('[FALSO Boot Step 7/8] Setting up UI & Speech Listeners...');
      this.setupEventListeners();
      this.voiceManager.initSpeechRecognition((cleanText) => {
        this.chatManager.sendToFalso(cleanText);
      });
      this.voiceManager.requestMicPermission();

      // 8. Animation Loop
      console.log('[FALSO Boot Step 8/8] Starting Unified Animation Loop...');
      this.startAnimationLoop();

      this.voiceManager.changeState('idle');
      console.log('[FALSO Boot Sequence] All 8 boot steps completed successfully!');
    } catch (bootErr) {
      console.error('[FALSO Boot Failure]', bootErr);
      const diag = document.getElementById('diag-content');
      if (diag) {
        diag.innerHTML = `<span style="color:#FF5252"><strong>BOOT ERROR:</strong> ${bootErr.message}</span>`;
      }
    }
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
