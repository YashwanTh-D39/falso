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

const API_WARM_URL = window.location.origin + '/api/v1/chat/warmup';

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

    console.log('[BOOT]');
    try {
      // 1. Settings
      settingsManager.init();

      // 2. Three.js Import & Scene/Camera/Renderer Initialization
      if (!rendererManager.THREE) {
        diagnosticsManager.setStage('threeImport', 'FAILED', 'Three.js library missing');
        console.error('[BOOT] FAILED STEP: Three.js Import\nReason: Three.js module failed to load');
        throw new Error('Three.js library missing');
      }
      console.log('[BOOT] ✓ Three.js loaded');

      rendererManager.init();

      if (!rendererManager.scene) {
        diagnosticsManager.setStage('sceneCreated', 'FAILED', 'Three.Scene creation failed');
        console.error('[BOOT] FAILED STEP: Scene Creation\nReason: THREE.Scene failed to instantiate');
        throw new Error('Scene creation failed');
      }
      console.log('[BOOT] ✓ Scene created');

      if (!rendererManager.camera) {
        diagnosticsManager.setStage('cameraCreated', 'FAILED', 'PerspectiveCamera creation failed');
        console.error('[BOOT] FAILED STEP: Camera Creation\nReason: THREE.PerspectiveCamera failed to instantiate');
        throw new Error('Camera creation failed');
      }
      console.log('[BOOT] ✓ Camera created');

      if (!rendererManager.renderer || !rendererManager.renderer.domElement) {
        diagnosticsManager.setStage('rendererCreated', 'FAILED', 'WebGLRenderer canvas missing');
        diagnosticsManager.setStage('domAttached', 'FAILED', 'Canvas #webgl-canvas missing from DOM');
        console.error('[BOOT] FAILED STEP: Canvas Attachment\nReason: Canvas #webgl-canvas is missing or not attached to DOM');
        throw new Error('WebGLRenderer canvas missing from DOM');
      }
      diagnosticsManager.setStage('rendererCreated', 'OK');
      diagnosticsManager.setStage('domAttached', 'OK');
      console.log('[BOOT] ✓ Renderer loaded');
      console.log('[BOOT] ✓ Canvas attached');

      // 3. OrbManager & Living Orb Mesh
      diagnosticsManager.setStage('orbManagerInstantiated', 'OK');
      console.log('[TRACE] 4. OrbManager instantiated');

      orbManager.init();
      orbManager.addOrb();
      console.log('[TRACE] 8. OrbManager.addOrb() executed');

      if (!orbManager.orbGroup || !orbManager.innerCore) {
        diagnosticsManager.setStage('livingOrbMeshCreated', 'FAILED', 'Orb mesh creation failed');
        console.error('[BOOT] FAILED STEP: Living Orb Creation\nReason: Orb mesh/geometry failed to attach to scene');
        throw new Error('Orb mesh creation failed');
      }
      diagnosticsManager.setStage('livingOrbMeshCreated', 'OK');
      diagnosticsManager.setStage('lightingCreated', 'OK');
      diagnosticsManager.setStage('orbAddedToScene', 'OK');
      console.log('[BOOT] ✓ Living Orb created');

      // 4. Spatial 3D Objects Manager & Fallback Entities
      this.spatialObjectManager = new SpatialObjectManager(rendererManager.scene, rendererManager.THREE);
      window.spatialObjectManager = this.spatialObjectManager;
      this.spatialObjectManager.ensureFallbackEntities();
      diagnosticsManager.setStage('nodesCreated', 'OK');

      // 5. Start Animation Loop AFTER OrbManager is completely initialized
      this.startAnimationLoop();
      diagnosticsManager.setStage('animLoopStarted', 'OK');
      console.log('[BOOT] ✓ Animation loop started');
      console.log('[BOOT] ✓ SpatialObjects initialized');

      // 6. WebSocket Connection & Packet Listener
      console.log('[BOOT] ✓ WebSocket connecting...');
      let packetLogged = false;
      this.spatialWSClient = new SpatialWSClient((payload) => {
        diagnosticsManager.setStage('webSocket', 'OK');
        diagnosticsManager.setStage('spatialService', 'OK');
        diagnosticsManager.setStage('entityBroadcaster', 'OK');
        diagnosticsManager.setStage('entityPackets', 'OK');
        if (!packetLogged) {
          console.log('[BOOT] ✓ WebSocket connected');
          console.log('[BOOT] ✓ Entity packet received');
          packetLogged = true;
        }

        if (this.spatialObjectManager) {
          this.spatialObjectManager.syncWithState(payload);
        }
      });
      window.spatialWSClient = this.spatialWSClient;
      this.spatialWSClient.connect();

      // 7. Voice & Chat Managers (Non-blocking)
      this.voiceManager = new VoiceManager(orbManager, settingsManager);
      this.chatManager = new ChatManager(this.voiceManager, settingsManager);

      window.voiceManager = this.voiceManager;
      window.chatManager = this.chatManager;
      window.settingsManager = settingsManager;

      // 8. UI Listeners & Voice-First Hands-Free Startup
      this.setupEventListeners();
      try {
        this.voiceManager.initSpeechRecognition((cleanText) => {
          this.chatManager.sendToFalso(cleanText);
        });
      } catch (sttErr) {
        console.warn('[BOOT] Speech recognition initialization warning:', sttErr);
      }

      // Voice-First Default Mode Startup: Request mic permission, verify STT, speak "Yes, Boss.", and enter LISTENING
      this.voiceManager.startVoiceFirstMode().catch((voiceErr) => {
        console.warn('[BOOT] Voice-first mode startup warning:', voiceErr);
      });

      console.log('[BOOT] ✓ All startup steps complete -> Living Orb rendering!');

      // Non-blocking warm: pins the local LLM so the first chat streams
      // immediately instead of paying the model-load cost.
      fetch(API_WARM_URL, { method: 'POST' }).catch(() => {});
    } catch (bootErr) {
      console.error('[BOOT] FAILED STEP:', bootErr.name || 'StartupError');
      console.error('Reason:', bootErr.message);
      console.error('Stack trace:', bootErr.stack);
      diagnosticsManager.setStage(diagnosticsManager.failedStage || 'rendererCreated', 'FAILED', bootErr.message);
      diagnosticsManager.renderHUD('error', false, false, false);
    }
  }

  setupEventListeners() {
    const sendBtn = document.getElementById('sendBtn') || document.getElementById('btn-send');
    const cmdInput = document.getElementById('cmdInput') || document.getElementById('cmd-input');
    const modeToggle = document.getElementById('modeToggle');

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

    if (modeToggle) {
      modeToggle.addEventListener('click', () => {
        if (this.voiceManager.sysState === 'sleeping' || !this.voiceManager.isHandsFreeEnabled) {
          this.voiceManager.enableHandsFreeMode();
        } else {
          this.voiceManager.disableHandsFreeMode();
        }
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
    let orbErrorLogged = false;
    let spatialErrorLogged = false;
    let renderErrLogged = false;

    const animate = () => {
      requestAnimationFrame(animate);

      const delta = clock ? clock.getDelta() : 0.016;
      const elapsed = clock ? clock.getElapsedTime() : performance.now() / 1000;

      // 1. Render Three.js Scene
      if (!renderErrLogged) {
        try {
          rendererManager.render(elapsed);
        } catch (err) {
          renderErrLogged = true;
          console.error('[RenderGuard] Scene render error:', err);
        }
      }

      // 2. Animate Living Orb
      if (!orbErrorLogged) {
        try {
          orbManager.animate(window.micLevel || 0);
        } catch (err) {
          orbErrorLogged = true;
          console.error('[RenderGuard] Orb animation error caught:', err);
        }
      }

      // 3. Update 3D Orbiting Objects
      if (this.spatialObjectManager && !spatialErrorLogged) {
        try {
          this.spatialObjectManager.update(delta, elapsed);
        } catch (err) {
          spatialErrorLogged = true;
          console.error('[RenderGuard] Spatial objects update error caught:', err);
        }
      }

      // 4. Throttled Diagnostics HUD (1 FPS)
      try {
        if (diagnosticsManager.tickFPS()) {
          const wsConn = this.spatialWSClient && this.spatialWSClient.ws && this.spatialWSClient.ws.readyState === 1;
          diagnosticsManager.renderHUD(
            this.voiceManager ? this.voiceManager.sysState : 'idle',
            this.voiceManager ? this.voiceManager.isSpeakingSpeech : false,
            this.voiceManager ? this.voiceManager.micActive : false,
            wsConn
          );
        }
      } catch (err) {
        // Silently swallow HUD rendering exceptions
      }
    };

    animate();
  }
}

export const bootManager = new BootManager();
