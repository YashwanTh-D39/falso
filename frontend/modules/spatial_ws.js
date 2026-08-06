/**
 * WebSocket Client for FALSO 3D Spatial OS real-time telemetry streaming.
 */

export class SpatialWSClient {
  constructor(onStateUpdate) {
    this.onStateUpdate = onStateUpdate;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectDelay = 5000;
    this.isConnecting = false;
  }

  connect() {
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) return;
    this.isConnecting = true;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/spatial`;

    try {
      this.ws = new WebSocket(wsUrl);
      this.ws.binaryType = 'arraybuffer';

      this.ws.onopen = () => {
        console.log('[SpatialWS] Connected to real-time spatial telemetry stream.');
        this.reconnectAttempts = 0;
        this.isConnecting = false;
      };

      this.ws.onmessage = (event) => {
        try {
          let parsed;
          if (typeof event.data === 'string') {
            parsed = JSON.parse(event.data);
          } else if (event.data instanceof ArrayBuffer) {
            const text = new TextDecoder().decode(event.data);
            parsed = JSON.parse(text);
          }

          if (parsed) {
            if (parsed.type === 'SPATIAL_STATE_UPDATE') {
              if (typeof this.onStateUpdate === 'function') {
                this.onStateUpdate(parsed);
              }
            } else if (parsed.type === 'proactive_notification') {
              if (typeof window.showProactiveToast === 'function') {
                window.showProactiveToast(parsed.data);
              }
            }
          }
        } catch (e) {
          console.warn('[SpatialWS] Error parsing websocket frame:', e);
        }
      };

      this.ws.onclose = () => {
        this.isConnecting = false;
        this.scheduleReconnect();
      };

      this.ws.onerror = (err) => {
        console.warn('[SpatialWS] WebSocket error:', err);
        this.isConnecting = false;
        this.ws?.close();
      };
    } catch (e) {
      console.warn('[SpatialWS] Failed to establish WebSocket connection:', e);
      this.isConnecting = false;
      this.scheduleReconnect();
    }
  }

  scheduleReconnect() {
    this.reconnectAttempts++;
    const delay = Math.min(200 * Math.pow(1.5, this.reconnectAttempts) + Math.random() * 200, this.maxReconnectDelay);
    setTimeout(() => this.connect(), delay);
  }
}
