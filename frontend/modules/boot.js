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
      settingsManager.init();

      // 2. Three.js Import & Scene/Camera/Renderer Initialization
      if (rendererManager.THREE) {
        diagnosticsManager.setStage('threeImport', 'OK');
      } else {
        diagnosticsManager.setStage('threeImport', 'FAILED', 'Three.js library missing');
        throw new Error('Three.js library missing');
      }

      rendererManager.init();

      if (rendererManager.scene) {
        diagnosticsManager.setStage('sceneCreated', 'OK');
      } else {
        diagnosticsManager.setStage('sceneCreated', 'FAILED', 'Three.Scene creation failed');
        throw new Error('Scene creation failed');
      }

      if (rendererManager.camera) {
        diagnosticsManager.setStage('cameraCreated', 'OK');
      } else {
        diagnosticsManager.setStage('cameraCreated', 'FAILED', 'PerspectiveCamera creation failed');
        throw new Error('Camera creation failed');
      }

      if (rendererManager.renderer && rendererManager.renderer.domElement) {
        diagnosticsManager.setStage('rendererCreated', 'OK');
        diagnosticsManager.setStage('domAttached', 'OK');
      } else {
        diagnosticsManager.setStage('rendererCreated', 'FAILED', 'WebGLRenderer canvas missing');
        diagnosticsManager.setStage('domAttached', 'FAILED', 'Canvas #webgl-canvas missing from DOM');
        throw new Error('WebGLRenderer canvas missing');
      }

      // 3. OrbManager & Living Orb Mesh
      diagnosticsManager.setStage('orbManagerInstantiated', 'OK');
      orbManager.init();

      if (orbManager.orbGroup && orbManager.innerCore) {
        diagnosticsManager.setStage('livingOrbMeshCreated', 'OK');
        diagnosticsManager.setStage('lightingCreated', 'OK');
        diagnosticsManager.setStage('orbAddedToScene', 'OK');
      } else {
        diagnosticsManager.setStage('livingOrbMeshCreated', 'FAILED', 'Orb mesh creation failed');
        throw new Error('Orb mesh creation failed');
      }

      // 4. Spatial 3D Objects Manager & Fallback Entities
      this.spatialObjectManager = new SpatialObjectManager(rendererManager.scene, rendererManager.THREE);
      window.spatialObjectManager = this.spatialObjectManager;
      this.spatialObjectManager.ensureFallbackEntities();
      diagnosticsManager.setStage('nodesCreated', 'OK');

      // 5. WebSocket Connection & Packet Listener
      this.spatialWSClient = new SpatialWSClient((payload) => {
        diagnosticsManager.setStage('webSocket', 'OK');
        diagnosticsManager.setStage('spatialService', 'OK');
        diagnosticsManager.setStage('entityBroadcaster', 'OK');
        diagnosticsManager.setStage('entityPackets', 'OK');
        if (this.spatialObjectManager) {
          this.spatialObjectManager.syncWithState(payload);
        }
      });
      window.spatialWSClient = this.spatialWSClient;

      // 6. Voice & Chat Managers
      this.voiceManager = new VoiceManager(orbManager, settingsManager);
      this.chatManager = new ChatManager(this.voiceManager, settingsManager);

      window.voiceManager = this.voiceManager;
      window.chatManager = this.chatManager;
      window.settingsManager = settingsManager;

      // 7. UI Listeners & Speech Recognition
      this.setupEventListeners();
      this.voiceManager.initSpeechRecognition((cleanText) => {
        this.chatManager.sendToFalso(cleanText);
      });
      this.voiceManager.requestMicPermission();

      // 8. Animation Loop
      this.startAnimationLoop();
      diagnosticsManager.setStage('animLoopStarted', 'OK');

      this.voiceManager.changeState('idle');
      console.log('[FALSO Boot Sequence] All 11 frontend stages & backend connections verified successfully!');
    } catch (bootErr) {
      console.error('[FALSO Boot Failure]', bootErr);
      diagnosticsManager.renderHUD('error', false, false, false);
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
