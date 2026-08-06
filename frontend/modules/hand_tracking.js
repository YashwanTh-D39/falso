/**
 * MediaPipe Hands tracking module for FALSO 3D Spatial OS.
 * Initializes camera feed and loads MediaPipe tasks-vision HandLandmarker.
 */

import { FilesetResolver, HandLandmarker } from 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm/vision_bundle.mjs';

export class HandTracker {
  constructor() {
    this.handLandmarker = null;
    this.video = null;
    this.isReady = false;
    this.lastVideoTime = -1;
  }

  async initialize() {
    try {
      // 1. Create hidden video element
      this.video = document.createElement('video');
      this.video.style.display = 'none';
      this.video.setAttribute('playsinline', '');
      this.video.setAttribute('autoplay', '');
      document.body.appendChild(this.video);

      // 2. Request webcam
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, frameRate: { ideal: 30 } }
      });
      this.video.srcObject = stream;
      await this.video.play();

      // 3. Load MediaPipe WASM and HandLandmarker
      const vision = await FilesetResolver.forVisionTasks(
        'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm'
      );

      this.handLandmarker = await HandLandmarker.createFromOptions(vision, {
        baseOptions: {
          modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',
          delegate: 'GPU'
        },
        runningMode: 'VIDEO',
        numHands: 2
      });

      this.isReady = true;
      console.log('[HandTracker] MediaPipe Hands initialized successfully.');
    } catch (e) {
      console.warn('[HandTracker] Webcam or MediaPipe initialization error:', e);
    }
  }

  detectForVideo() {
    if (!this.isReady || !this.handLandmarker || !this.video || this.video.currentTime === this.lastVideoTime) {
      return null;
    }
    this.lastVideoTime = this.video.currentTime;
    try {
      return this.handLandmarker.detectForVideo(this.video, performance.now());
    } catch (e) {
      return null;
    }
  }
}
