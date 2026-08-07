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
    this.activeProvider = "Ollama";
    this.activeModel = "gemma3:4b";
  }

  tickFPS() {
    this.frameCount++;
    const now = performance.now();
    if (now - this.lastFpsCalcTime >= 1000) {
      this.currentFPS = this.frameCount;
      this.frameCount = 0;
      this.lastFpsCalcTime = now;
      return true;
    }
    return false;
  }

  renderHUD(sysState, isSpeakingSpeech, micActive, wsConnected) {
    const diag = document.getElementById('diag-content');
    if (!diag) return;

    const secondsAgo = Math.round((Date.now() - (this.lastWsUpdateTime || Date.now())) / 1000);
    const rCount = window.renderedEntitiesCount || this.renderedEntitiesCount || 0;
    const frameTimeMs = (1000 / Math.max(this.currentFPS, 1)).toFixed(1);

    const esc = (str) => String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

    diag.innerHTML = `
      Provider: ${esc(this.activeProvider)}<br>
      Model: ${esc(this.activeModel)}<br>
      FPS: ${this.currentFPS} / 60<br>
      Frame time: ${frameTimeMs} ms<br>
      WebSocket: ${wsConnected ? 'Connected' : 'Connecting'}<br>
      Backend entities: ${rCount}<br>
      Rendered entities: ${rCount > 0 ? rCount : '<span style="color:#FFA726">No live entities available.</span>'}<br>
      TTS state: ${isSpeakingSpeech ? 'SPEAKING' : 'IDLE'}<br>
      STT state: ${micActive ? 'LISTENING' : 'OFF'}<br>
      Last update: ${secondsAgo}s ago<br>
      STATE: ${(sysState || 'IDLE').toUpperCase()}
    `;
  }
}

export const diagnosticsManager = new DiagnosticsManager();
