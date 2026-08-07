/**
 * Main ES6 Entry Point for FALSO Spatial OS.
 * Automatically triggered when DOM is ready.
 */

import { bootManager } from './boot.js';

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => bootManager.initializeApp());
} else {
  bootManager.initializeApp();
}
