/**
 * Diagnostics & Performance HUD Module for FALSO Spatial OS.
 */

export class DiagnosticsManager {
  constructor() {
    this.currentFPS = 60;
    this.frameCount = 0;
    this.lastFpsCalcTime = performance.now();
    this.lastWsUpdateTime = Date.now();
    this.renderedEntitiesCount = 0;
    this.activeProvider = "NVIDIA";
    this.activeModel = "nvidia/llama-3.3-nemotron-super-49b-v1";

    this.stages = {
      threeImport: 'PENDING',
      sceneCreated: 'PENDING',
      cameraCreated: 'PENDING',
      rendererCreated: 'PENDING',
      domAttached: 'PENDING',
      animLoopStarted: 'PENDING',
      orbManagerInstantiated: 'PENDING',
      livingOrbMeshCreated: 'PENDING',
      lightingCreated: 'PENDING',
      orbAddedToScene: 'PENDING',
      renderLoopFrames: 'PENDING',
      webSocket: 'PENDING',
      spatialService: 'PENDING',
      entityBroadcaster: 'PENDING',
      entityPackets: 'PENDING',
      nodesCreated: 'PENDING'
    };
    this.failedStage = null;
    this.failureReason = null;
  }

  setStage(stage, status, reason = null) {
    this.stages[stage] = status;
    if (status === 'FAILED') {
      this.failedStage = stage;
      this.failureReason = reason;
      console.error(`[DIAGNOSTICS STAGE FAILURE] ${stage}: ${reason}`);
    }
  }

  tickFPS() {
    this.frameCount++;
    const now = performance.now();
    if (now - this.lastFpsCalcTime >= 1000) {
      this.currentFPS = this.frameCount;
      this.frameCount = 0;
      this.lastFpsCalcTime = now;
      if (this.stages.renderLoopFrames !== 'OK') {
        this.setStage('renderLoopFrames', 'OK');
      }
      return true;
    }
    return false;
  }

  renderHUD(sysState, isSpeakingSpeech, micActive, wsConnected) {
    const rCount = window.renderedEntitiesCount || this.renderedEntitiesCount || 0;
    const secondsAgo = Math.round((Date.now() - (this.lastWsUpdateTime || Date.now())) / 1000);

    const fpsVal = document.getElementById('fpsVal');
    if (fpsVal) fpsVal.textContent = `${this.currentFPS} / 60`;

    const lastUpdate = document.getElementById('lastUpdate');
    if (lastUpdate) lastUpdate.textContent = `${secondsAgo}s ago`;

    const renderedVal = document.getElementById('renderedVal');
    if (renderedVal) renderedVal.textContent = `${rCount}`;

    const wsStatus = document.getElementById('wsStatus');
    if (wsStatus) {
      wsStatus.className = wsConnected ? 'ok' : '';
      wsStatus.textContent = wsConnected ? 'Connected' : 'Connecting...';
    }

    const stateVal = document.getElementById('stateVal');
    if (stateVal && sysState) {
      const stateLower = String(sysState).toLowerCase();
      stateVal.className = `state-pill state-${stateLower}`;
      stateVal.textContent = String(sysState).toUpperCase();
    }

    const diag = document.getElementById('diag-content');
    if (!diag) return;

    const frameTimeMs = (1000 / Math.max(this.currentFPS, 1)).toFixed(1);

    const esc = (str) => String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const colorStatus = (st) => {
      if (st === 'OK') return '<span style="color:#81C784;font-weight:bold;">OK</span>';
      if (st === 'FAILED') return '<span style="color:#FF5252;font-weight:bold;">FAILED</span>';
      return '<span style="color:#FFA726;">WAITING</span>';
    };

    let failureAlert = '';
    if (this.failedStage) {
      failureAlert = `<div style="background:rgba(255,82,82,0.2);border:1px solid #FF5252;padding:6px;margin-bottom:8px;color:#FF5252;font-size:11px;">
        <strong>STAGE FAILURE: ${esc(this.failedStage)}</strong><br>${esc(this.failureReason || 'Unknown error')}
      </div>`;
    }

    diag.innerHTML = `
      ${failureAlert}
      Renderer: ${colorStatus(this.stages.rendererCreated)}<br>
      Scene: ${colorStatus(this.stages.sceneCreated)}<br>
      Camera: ${colorStatus(this.stages.cameraCreated)}<br>
      Orb Mesh: ${colorStatus(this.stages.livingOrbMeshCreated)}<br>
      WebSocket: ${wsConnected ? colorStatus('OK') : colorStatus(this.stages.webSocket)}<br>
      Entity Feed: ${rCount > 0 ? colorStatus('OK') : '<span style="color:#FFA726">Waiting for live system entities...</span>'}<br>
      FPS: ${this.currentFPS} / 60 (${frameTimeMs} ms)<br>
      Rendered nodes: ${rCount}<br>
      STATE: ${(sysState || 'IDLE').toUpperCase()}
    `;
  }
}

export const diagnosticsManager = new DiagnosticsManager();
