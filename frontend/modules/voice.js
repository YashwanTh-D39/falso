/**
 * Voice, Speech Recognition, VAD, Streaming Audio Queue, and Barge-In Controller for FALSO 4.2.
 * Voice-First, Full-Duplex, Noise-Resistant Hands-Free Assistant.
 */

const API_BASE = window.location.origin + '/api/v1';

export class VoiceManager {
  constructor(orbManager, settingsManager) {
    this.orbManager = orbManager;
    this.settingsManager = settingsManager;

    this.speechRec = null;
    this.micActive = false;
    this.sttActive = false;
    this.isListeningActive = false;
    this.isRecStarting = false;
    this.mediaStream = null;
    this.restartTimer = null;

    this.isSpeakingSpeech = false;
    this.lastSpeechTime = Date.now();
    this.currentSpokenSentence = "";

    this.sentenceBuffer = "";
    this.audioSentenceQueue = [];
    this.isProcessingAudioQueue = false;
    this.currentAudioSource = null;
    this.activeTTSFetchController = null;
    this.sysState = 'booting';
    this.activeRequestId = null;
    this.greetingSpoken = false;
    this.isHandsFreeEnabled = true;
  }

  setActiveRequestId(requestId) {
    this.activeRequestId = requestId;
    this.sentenceBuffer = "";
    this.clearAudioStreamingQueue();
    this.stopActiveAudioPlayback();
  }

  changeState(newState) {
    if (!newState) return;
    const normState = newState.toLowerCase().trim();
    const upperState = newState.toUpperCase().trim();
    const oldState = (this.sysState || 'sleeping').toUpperCase().trim();

    if (oldState === upperState) return;

    this.sysState = normState;
    console.log(`[VOICE][STATE] old=${oldState} new=${upperState}`);

    if (this.orbManager) {
      this.orbManager.updateState(normState);
    }

    const stateVal = document.getElementById('stateVal');
    if (stateVal) {
      stateVal.className = `state-pill state-${normState}`;
      stateVal.textContent = upperState;
    }

    const modeLabel = document.getElementById('modeLabel');
    if (modeLabel) {
      modeLabel.textContent = upperState;
    }

    const modeToggle = document.getElementById('modeToggle');
    if (modeToggle) {
      modeToggle.className = `mode-toggle ${normState}`;
    }

    const statusPill = document.getElementById('mic-status-pill');
    if (statusPill) {
      statusPill.innerHTML = `<span>●</span> ${upperState}`;
    }
  }

  async requestMicPermission() {
    console.log('[VOICE][INIT]');
    console.log('[VOICE][MIC_CHECK] Requesting audio media stream for mic permission verification');
    try {
      const constraints = {
        audio: {
          echoCancellation: { ideal: true },
          noiseSuppression: { ideal: true },
          autoGainControl: { ideal: true }
        }
      };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      console.log('[VOICE][MIC_CHECK] Microphone access GRANTED with echo cancellation & noise suppression');
      // Stop tracks so the mic device is released cleanly for Web Speech API
      stream.getTracks().forEach(t => t.stop());

      const overlay = document.getElementById('mic-permission-overlay');
      if (overlay) overlay.style.display = 'none';
      this.micActive = true;
      return true;
    } catch (e) {
      console.warn('[VOICE][EVENT] ERROR mic-permission-denied:', e.name || e.message || e);
      console.warn('[VOICE][ERROR] mic-permission-denied:', e.name || e.message || e);
      const overlay = document.getElementById('mic-permission-overlay');
      if (overlay) overlay.style.display = 'flex';
      this.micActive = false;
      this.sttActive = false;
      this.changeState('error');
      setTimeout(() => {
        if (this.sysState === 'error') this.changeState('idle');
      }, 2000);
      return false;
    }
  }

  ensureSpeechRecognitionActive() {
    if (!this.micActive || !this.speechRec || this.isRecStarting || this.isListeningActive || this.sysState === 'sleeping') return;
    try {
      this.isRecStarting = true;
      console.log('[VOICE][START_REQUEST] Starting SpeechRecognition engine');
      this.speechRec.start();
    } catch (e) {
      this.isRecStarting = false;
      if (e.name === 'InvalidStateError') {
        this.isListeningActive = true;
      }
    }
  }

  initSpeechRecognition(sendToFalsoCb) {
    console.log('[VOICE][INIT] Initializing Web Speech API');
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const implName = window.SpeechRecognition ? 'window.SpeechRecognition' : (window.webkitSpeechRecognition ? 'window.webkitSpeechRecognition' : 'none');
    console.log(`[VOICE][INIT] Selected STT Implementation: ${implName}`);

    if (!SpeechRecognition) {
      console.warn('[VOICE][EVENT] ERROR service-not-supported: Web Speech API not supported in this browser');
      console.warn('[VOICE][ERROR] service-not-supported: Web Speech API not supported in this browser');
      this.changeState('error');
      return;
    }

    if (this.speechRec) return;

    this.speechRec = new SpeechRecognition();
    this.speechRec.continuous = true;
    this.speechRec.interimResults = true;
    this.speechRec.lang = navigator.language || 'en-US';

    console.log(`[VOICE][CONFIG] language=${this.speechRec.lang} continuous=${this.speechRec.continuous} interimResults=${this.speechRec.interimResults}`);

    this.speechRec.onstart = () => {
      this.isRecStarting = false;
      this.sttActive = true;
      this.isListeningActive = true;
      console.log('[VOICE][EVENT] START');
      console.log('[VOICE][STARTED] SpeechRecognition active');
      if (this.isHandsFreeEnabled && this.sysState !== 'speaking' && this.sysState !== 'thinking' && this.sysState !== 'streaming' && this.sysState !== 'executing') {
        this.changeState('listening');
        console.log('[VOICE][LISTENING] System ready for hands-free voice input');
      }
    };

    this.speechRec.onaudiostart = () => {
      console.log('[VOICE][EVENT] AUDIO_START');
      console.log('[VOICE][AUDIO_START] Audio stream captured by STT');
    };

    this.speechRec.onsoundstart = () => {
      console.log('[VOICE][EVENT] SOUND_START');
    };

    this.speechRec.onspeechstart = () => {
      console.log('[VOICE][EVENT] SPEECH_START');
      console.log('[VOICE][SPEECH_START] Speech sound detected');
      if (this.sysState === 'speaking' || this.isSpeakingSpeech || this.audioSentenceQueue.length > 0) {
        // Will check in onresult if it's self-voice or user barge-in
      } else if (this.sysState === 'listening' || this.sysState === 'idle') {
        this.changeState('hearing');
      }
    };

    this.speechRec.onspeechend = () => {
      console.log('[VOICE][EVENT] SPEECH_END');
      console.log('[VOICE][END] Speech sound ended');
    };

    this.speechRec.onsoundend = () => {
      console.log('[VOICE][EVENT] SOUND_END');
    };

    this.speechRec.onaudioend = () => {
      console.log('[VOICE][EVENT] AUDIO_END');
      console.log('[VOICE][AUDIO_END] Audio stream ended');
    };

    this.speechRec.onresult = (event) => {
      console.log('[VOICE][EVENT] RESULT');
      let finalTranscript = '';
      let interimTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const res = event.results[i];
        const text = res[0] ? res[0].transcript : '';
        const isFinal = res.isFinal;
        console.log(`[VOICE][EVENT] RESULT index=${i} isFinal=${isFinal} length=${text.length}`);
        if (isFinal) {
          finalTranscript += text;
        } else {
          interimTranscript += text;
        }
      }

      const cleanFinal = finalTranscript.trim();
      const cleanInterim = interimTranscript.trim();
      const currentText = cleanFinal || cleanInterim;

      if (currentText) {
        console.log('[VOICE][RESULT] STT result:', currentText);

        if (this.isSleeping || this.sysState === 'sleeping') {
          const lowerText = currentText.toLowerCase().trim();
          const isWake = /hello\s*falso|falso\s*wake|wake\s*up\s*falso|wake\s*up|falso/i.test(lowerText);
          if (isWake) {
            console.log('[SLEEP][WAKE_DETECTED] source=voice phrase=' + currentText);
            this.wakeUp();
          } else {
            console.log('[SLEEP] Suppressed audio while sleeping:', currentText);
          }
          return;
        }

        if (this.sysState === 'listening') {
          this.changeState('hearing');
        }

        // Self-Voice Protection: ignore if transcript matches FALSO's currently spoken output
        if (this.isSelfVoiceEcho(currentText)) {
          console.log('[VOICE][SELF_VOICE_PROTECTION] Ignored self-voice echo:', currentText);
          return;
        }

        // Voice Interruption / Barge-In Check while FALSO is speaking
        if (this.sysState === 'speaking' || this.isSpeakingSpeech || this.audioSentenceQueue.length > 0) {
          console.log('[VOICE][INTERRUPT] User barge-in detected during TTS playback:', currentText);
          this.triggerVoiceInterruption();
        }

        if (cleanFinal) {
          console.log('[VOICE][TRANSCRIPT] Final transcript:', cleanFinal);
          this.changeState('thinking');
          this.lastSpeechTime = Date.now();

          // Handle Voice System Commands
          const lower = cleanFinal.toLowerCase();

          // Mode Switches
          if (lower.includes("display mode")) {
            this.settingsManager.updateInteractionMode('display_mode');
            this.changeState('listening');
            return;
          }
          if (lower.includes("voice mode")) {
            this.settingsManager.updateInteractionMode('voice_only');
            this.changeState('listening');
            return;
          }
          if (lower.includes("go to sleep") || lower.includes("sleep falso") || lower === "falso sleep") {
            this.goToSleep();
            return;
          }
          if (lower.includes("wake up") || lower.includes("wake up falso") || lower === "falso wake") {
            this.wakeUp();
            return;
          }
          if (lower === "falso stop" || lower === "stop" || lower === "cancel") {
            console.log('[VOICE][INTERRUPT] "FALSO stop" command executed');
            this.stopActiveAudioPlayback();
            if (window.chatManager && window.chatManager.activeAbortController) {
              window.chatManager.activeAbortController.abort();
            }
            fetch(API_BASE + '/chat/stream', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ prompt: 'falso stop', message: 'falso stop' })
            }).catch(() => {});
            this.changeState('interrupted');
            setTimeout(() => {
              if (this.isHandsFreeEnabled) {
                this.changeState('listening');
                this.ensureSpeechRecognitionActive();
              }
            }, 600);
            return;
          }

          // Send Normal Command to Brain Service
          console.log('[VOICE][THINKING] Routing transcript to BrainService');
          this.changeState('thinking');
          sendToFalsoCb(cleanFinal);
        }
      }
    };

    this.speechRec.onerror = (event) => {
      this.isRecStarting = false;
      const errCode = event.error || 'unknown';
      console.log('[VOICE][EVENT] ERROR', errCode);
      if (errCode === 'no-speech' || errCode === 'aborted') {
        console.log(`[VOICE][ERROR] ${errCode} (benign background silence/reset)`);
        if (this.isHandsFreeEnabled && this.sysState !== 'speaking' && this.sysState !== 'thinking' && this.sysState !== 'streaming' && this.sysState !== 'executing') {
          this.changeState('listening');
        }
      } else {
        console.warn('[VOICE][ERROR]', errCode);
        if (errCode === 'not-allowed' || errCode === 'service-not-allowed' || errCode === 'audio-capture') {
          this.sttActive = false;
          this.micActive = false;
          this.changeState('error');
        }
      }
    };

    this.speechRec.onend = () => {
      this.isRecStarting = false;
      this.isListeningActive = false;
      console.log('[VOICE][EVENT] END');
      console.log('[VOICE][END] SpeechRecognition onend fired');
      if (this.isHandsFreeEnabled && this.sysState !== 'error') {
        if (!this.isSleeping && this.sysState !== 'sleeping' && this.sysState !== 'speaking' && this.sysState !== 'thinking' && this.sysState !== 'streaming' && this.sysState !== 'executing') {
          this.changeState('listening');
        }
        clearTimeout(this.restartTimer);
        this.restartTimer = setTimeout(() => {
          this.ensureSpeechRecognitionActive();
        }, 300);
      }
    };

    this.ensureSpeechRecognitionActive();
  }

  async startVoiceFirstMode() {
    this.isHandsFreeEnabled = true;
    const hasMic = await this.requestMicPermission();
    if (!hasMic) {
      console.warn('[VOICE][ERROR] Could not start voice-first mode — mic access failed.');
      this.changeState('sleeping');
      return;
    }

    this.changeState('listening');
    this.ensureSpeechRecognitionActive();

    // Startup greeting: "Yes, Boss."
    if (!this.greetingSpoken) {
      this.greetingSpoken = true;
      console.log('[VOICE][TTS_START] Playing voice-first startup greeting: "Yes, Boss."');
      await this.playServerTTS("Yes, Boss.", "STARTUP_GREETING");
    }
  }

  isSelfVoiceEcho(transcript) {
    if (!this.isSpeakingSpeech || !this.currentSpokenSentence) return false;
    const cleanT = transcript.toLowerCase().trim();
    const cleanS = this.currentSpokenSentence.toLowerCase().trim();
    if (!cleanT || !cleanS) return false;

    // Check direct equality or high substring match
    if (cleanS.includes(cleanT) || cleanT.includes(cleanS)) return true;

    // Check token overlap
    const wordsT = cleanT.split(/\s+/);
    const wordsS = new Set(cleanS.split(/\s+/));
    let matchCount = 0;
    for (const w of wordsT) {
      if (wordsS.has(w)) matchCount++;
    }
    const ratio = matchCount / Math.max(wordsT.length, 1);
    return ratio >= 0.7;
  }

  goToSleep() {
    console.log('[SLEEP][REQUEST] Entering Sleep Mode');
    console.log('[SLEEP][ENTER] Deep Sleep Active (wake listener remains active)');
    this.isSleeping = true;
    this.isHandsFreeEnabled = true;
    this.stopActiveAudioPlayback();
    if (window.chatManager && window.chatManager.activeAbortController) {
      try { window.chatManager.activeAbortController.abort(); } catch(e) {}
    }
    fetch(API_BASE + '/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: 'falso stop', message: 'falso stop' })
    }).catch(() => {});

    this.changeState('sleeping');
    this.playServerTTS("Going to sleep.", "SLEEP_CONFIRMATION");
    setTimeout(() => {
      this.ensureSpeechRecognitionActive();
    }, 500);
  }

  wakeUp() {
    console.log('[SLEEP][WAKE_DETECTED] Waking up from Sleep Mode');
    console.log('[SLEEP][WAKE] state=LISTENING');
    this.isSleeping = false;
    this.isHandsFreeEnabled = true;
    this.changeState('waking');
    setTimeout(() => {
      this.changeState('listening');
      this.ensureSpeechRecognitionActive();
      this.playServerTTS("Yes, Boss.", "WAKE_GREETING");
    }, 300);
  }

  enableHandsFreeMode() {
    this.wakeUp();
  }

  disableHandsFreeMode() {
    this.goToSleep();
  }

  triggerVoiceInterruption(requestId) {
    console.log(`[VOICE][INTERRUPT] Interrupting active request (req=${requestId || this.activeRequestId || 'ACTIVE'})`);
    this.stopActiveAudioPlayback();
    this.clearAudioStreamingQueue();
    this.isSpeakingSpeech = false;
    this.isProcessingAudioQueue = false;

    if (window.chatManager && window.chatManager.activeAbortController) {
      window.chatManager.activeAbortController.abort();
    }

    this.changeState('interrupted');
    console.log('[VOICE][INTERRUPT_COMPLETE] Active playback cancelled, ready for user barge-in');
    setTimeout(() => {
      if (this.isHandsFreeEnabled) {
        this.changeState('listening');
        this.ensureSpeechRecognitionActive();
      }
    }, 600);
  }

  clearAudioStreamingQueue() {
    this.sentenceBuffer = "";
    this.audioSentenceQueue = [];
    this.isProcessingAudioQueue = false;
  }

  stopActiveAudioPlayback() {
    if (this.activeTTSFetchController) {
      try { this.activeTTSFetchController.abort(); } catch(e) {}
      this.activeTTSFetchController = null;
    }
    this.clearAudioStreamingQueue();
    if (this.currentAudioSource) {
      try {
        this.currentAudioSource.pause();
        this.currentAudioSource.currentTime = 0;
        this.currentAudioSource.src = "";
      } catch(e) {}
      this.currentAudioSource = null;
    }
    if ('speechSynthesis' in window) {
      try { speechSynthesis.cancel(); } catch(e) {}
    }
    this.isSpeakingSpeech = false;
    this.currentSpokenSentence = "";
    this.isProcessingAudioQueue = false;
  }

  processIncomingTokenStream(tokenText, requestId) {
    if (requestId && this.activeRequestId && requestId !== this.activeRequestId) {
      return;
    }
    this.sentenceBuffer += tokenText;
    const match = this.sentenceBuffer.match(/([^.!?\n]+[.!?\n]+)/);
    if (match) {
      const completeSentence = match[0];
      this.sentenceBuffer = this.sentenceBuffer.substring(completeSentence.length);
      this.enqueueSentenceForTTS(completeSentence, requestId);
    }
  }

  finalizeIncomingTokenStream(requestId) {
    if (requestId && this.activeRequestId && requestId !== this.activeRequestId) {
      return;
    }
    if (this.sentenceBuffer.trim().length > 0) {
      this.enqueueSentenceForTTS(this.sentenceBuffer, requestId);
      this.sentenceBuffer = "";
    }
  }

  enqueueSentenceForTTS(sentenceText, requestId) {
    const clean = this.cleanTextForSpeech(sentenceText);
    if (!clean || clean.trim().length === 0) return;
    const reqId = requestId || this.activeRequestId;
    if (this.audioSentenceQueue.length > 0) {
      const lastItem = this.audioSentenceQueue[this.audioSentenceQueue.length - 1];
      if (lastItem.text === clean && lastItem.requestId === reqId) return;
    }
    this.audioSentenceQueue.push({ text: clean, requestId: reqId });
    if (!this.isProcessingAudioQueue) {
      this.playNextSentenceInQueue();
    }
  }

  async playNextSentenceInQueue() {
    if (this.audioSentenceQueue.length === 0) {
      this.isProcessingAudioQueue = false;
      if (this.sysState === 'speaking' || this.sysState === 'streaming') {
        console.log('[VOICE][TTS_END] Queue empty, returning to LISTENING');
        setTimeout(() => {
          if (!this.isProcessingAudioQueue && this.audioSentenceQueue.length === 0) {
            this.changeState('listening');
            this.ensureSpeechRecognitionActive();
          }
        }, 300);
      }
      return;
    }

    const nextItem = this.audioSentenceQueue.shift();
    if (!nextItem || (nextItem.requestId && this.activeRequestId && nextItem.requestId !== this.activeRequestId)) {
      this.playNextSentenceInQueue();
      return;
    }

    this.isProcessingAudioQueue = true;
    this.changeState('speaking');
    const played = await this.playServerTTS(nextItem.text, nextItem.requestId);
    if (!played) {
      this.playNextSentenceInQueue();
    }
  }

  async playServerTTS(text, requestId) {
    const reqId = requestId || this.activeRequestId || 'GLOBAL';
    if (this.activeTTSFetchController) {
      try { this.activeTTSFetchController.abort(); } catch(e) {}
    }
    this.activeTTSFetchController = new AbortController();
    const signal = this.activeTTSFetchController.signal;

    const ttsText = text.length > 2000 ? text.substring(0, 2000) + '...' : text;
    this.isSpeakingSpeech = true;
    this.currentSpokenSentence = ttsText;
    console.log(`[VOICE][TTS_START] [req=${reqId}] Speaking:`, ttsText);

    try {
      const res = await fetch(API_BASE + '/voice/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: ttsText, request_id: reqId }),
        signal: signal
      });

      if (signal.aborted || (this.activeRequestId && reqId !== this.activeRequestId && reqId !== 'STARTUP_GREETING' && reqId !== 'WAKE_GREETING')) {
        console.log(`[VOICE][TTS_END] [req=${reqId}] Aborted in flight`);
        this.isSpeakingSpeech = false;
        this.currentSpokenSentence = "";
        return false;
      }

      if (res.ok) {
        const audioBlob = await res.blob();
        if (signal.aborted || audioBlob.size < 100 || (this.activeRequestId && reqId !== this.activeRequestId && reqId !== 'STARTUP_GREETING' && reqId !== 'WAKE_GREETING')) {
          this.isSpeakingSpeech = false;
          this.currentSpokenSentence = "";
          return false;
        }
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        this.currentAudioSource = audio;
        this.changeState('speaking');

        return new Promise((resolve) => {
          audio.onended = () => {
            console.log(`[VOICE][TTS_END] [req=${reqId}] Playback completed`);
            URL.revokeObjectURL(audioUrl);
            this.currentAudioSource = null;
            this.isSpeakingSpeech = false;
            this.currentSpokenSentence = "";
            this.lastSpeechTime = Date.now();
            this.playNextSentenceInQueue();
            resolve(true);
          };
          audio.onerror = (err) => {
            console.warn(`[VOICE][ERROR] [req=${reqId}] Audio playback error`, err);
            URL.revokeObjectURL(audioUrl);
            this.currentAudioSource = null;
            this.isSpeakingSpeech = false;
            this.currentSpokenSentence = "";
            this.playNextSentenceInQueue();
            resolve(false);
          };
          audio.play().catch((playErr) => {
            console.warn(`[VOICE][ERROR] [req=${reqId}] Audio play rejected`, playErr);
            this.currentAudioSource = null;
            this.isSpeakingSpeech = false;
            this.currentSpokenSentence = "";
            resolve(false);
          });
        });
      }
    } catch(e) {
      if (e.name === 'AbortError') {
        console.log(`[VOICE][TTS_END] [req=${reqId}] TTS fetch aborted`);
      } else {
        console.warn(`[VOICE][ERROR] [req=${reqId}] TTS request failed`, e);
      }
      this.isSpeakingSpeech = false;
      this.currentSpokenSentence = "";
    }
    return false;
  }

  cleanTextForSpeech(raw) {
    if (!raw) return "";
    return raw
      .replace(/<details>[\s\S]*?<\/details>/gi, "")
      .replace(/https?:\/\/[^\s]+/g, "")
      .replace(/www\.[^\s]+/g, "")
      .replace(/<[^>]*>/g, "")
      .replace(/```[\s\S]*?```/g, " [code block] ")
      .replace(/`/g, "")
      .replace(/#+/g, "")
      .replace(/[*_~>]/g, "")
      .replace(/[/\\|]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }
}
