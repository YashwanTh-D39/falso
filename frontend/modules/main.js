console.log('[TRACE] 1. main.js executing...');

import { bootManager } from './boot.js';

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    console.log('[TRACE] 2. DOMContentLoaded -> calling bootManager.initializeApp()');
    bootManager.initializeApp();
  });
} else {
  console.log('[TRACE] 2. DOM ready -> calling bootManager.initializeApp()');
  bootManager.initializeApp();
}
