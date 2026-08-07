/**
 * Shared utility functions for FALSO 3D Spatial OS frontend modules.
 */

import * as THREE from 'three';

export function createTextSprite(text, options = {}) {
  const fontface = options.fontface || 'Arial';
  const fontsize = options.fontsize || 24;
  const borderThickness = options.borderThickness || 2;
  const borderColor = options.borderColor || { r: 0, g: 255, b: 255, a: 1.0 };
  const backgroundColor = options.backgroundColor || { r: 10, g: 20, b: 30, a: 0.8 };
  const textColor = options.textColor || '#ffffff';

  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 128;
  const context = canvas.getContext('2d');

  context.font = `Bold ${fontsize}px ${fontface}`;
  
  // Background box
  context.fillStyle = `rgba(${backgroundColor.r},${backgroundColor.g},${backgroundColor.b},${backgroundColor.a})`;
  context.strokeStyle = `rgba(${borderColor.r},${borderColor.g},${borderColor.b},${borderColor.a})`;
  context.lineWidth = borderThickness;

  const textWidth = context.measureText(text).width;
  const rectX = (canvas.width - textWidth) / 2 - 12;
  const rectY = (canvas.height - fontsize) / 2 - 8;
  const rectW = textWidth + 24;
  const rectH = fontsize + 16;

  // Rounded rectangle
  context.beginPath();
  context.roundRect(rectX, rectY, rectW, rectH, 8);
  context.fill();
  context.stroke();

  // Text
  context.fillStyle = textColor;
  context.textAlign = 'center';
  context.textBaseline = 'middle';
  context.fillText(text, canvas.width / 2, canvas.height / 2);

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;

  const spriteMaterial = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthTest: false
  });

  const sprite = new THREE.Sprite(spriteMaterial);
  sprite.scale.set(1.5, 0.375, 1.0);
  return sprite;
}

export function formatBytes(bytes, decimals = 1) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}
