/**
 * Voice, Speech Recognition, VAD, Streaming Audio Queue, and Barge-In Controller for FALSO.
 */

const API_BASE = window.location.origin + '/api/v1';

export class VoiceManager {
  constructor(orbManager, settingsManager) {
    this.orbManager = orbManager;
    this.settingsManager = settingsManager;

    this.speechRec = null;
    this.micActive = false;
    this.isRecStarting = false;

    this.isSpeakingSpeech = false;
    this.lastSpeechTime = Date.now();

    this.sentenceBuffer = "";
    this.audioSentenceQueue = [];
    this.isProcessingAudioQueue = false;
    this.currentAudioSource = null;
    this.activeTTSFetchController = null;
    this.sysState = 'booting';
    this.activeRequestId = null;
  }

  setActiveRequestId(requestId) {
    this.activeRequestId = requestId;
    this.sentenceBuffer = "";
    this.clearAudioStreamingQueue();
    this.stopActiveAudioPlayback();
  }

  changeState(newState) {
    this.sysState = newState;
    if (this.orbManager) {
      this.orbManager.updateState(newState);
    }
    const statusPill = document.getElementById('mic-status-pill');
    if (statusPill) {
      if (newState === 'listening') {
        statusPill.innerHTML = '<span class="pulse-dot">●</span> AUTO MIC ACTIVE';
        statusPill.style.borderColor = '#00E5FF';
        statusPill.style.color = '#00E5FF';
      } else if (newState === 'thinking') {
        statusPill.innerHTML = '<span class="pulse-dot">🧠</span> THINKING...';
        statusPill.style.borderColor = '#7DF9FF';
        statusPill.style.color = '#7DF9FF';
      } else if (newState === 'streaming') {
        statusPill.innerHTML = '<span class="pulse-dot">⚡</span> STREAMING...';
        statusPill.style.borderColor = '#00FF9D';
        statusPill.style.color = '#00FF9D';
      } else if (newState === 'speaking') {
        statusPill.innerHTML = '<span class="pulse-dot">🗣️</span> SPEAKING...';
        statusPill.style.borderColor = '#4DA6FF';
        statusPill.style.color = '#4DA6FF';
      } else if (newState === 'searching') {
        statusPill.innerHTML = '<span class="pulse-dot">&#127760;</span> SEARCHING WEB...';
        statusPill.style.borderColor = '#7DF9FF';
        statusPill.style.color = '#7DF9FF';
      } else if (newState === 'warming') {
        statusPill.innerHTML = '<span class="pulse-dot">&#9889;</span> NVIDIA WARMING...';
        statusPill.style.borderColor = '#FFA726';
        statusPill.style.color = '#FFA726';
      } else if (newState === 'interrupted') {
        statusPill.innerHTML = '<span>⚡</span> INTERRUPTED!';
        statusPill.style.borderColor = '#7DF9FF';
        statusPill.style.color = '#FFFFFF';
      } else if (newState === 'sleeping') {
        statusPill.innerHTML = '<span style="opacity:0.5">💤</span> SLEEPING';
        statusPill.style.borderColor = 'rgba(120,220,255,0.2)';
        statusPill.style.color = '#B6D7F5';
      } else if (newState === 'booting') {
        statusPill.innerHTML = '<span class="pulse-dot">⚡</span> BOOTING...';
        statusPill.style.borderColor = '#00BFFF';
        statusPill.style.color = '#00BFFF';
      } else if (newState === 'error') {
        statusPill.innerHTML = '<span>⚠️</span> ERROR';
        statusPill.style.borderColor = '#FF6B6B';
        statusPill.style.color = '#FF6B6B';
      } else {
        statusPill.innerHTML = '<span>●</span> IDLE';
        statusPill.style.borderColor = 'rgba(120,220,255,0.3)';
        statusPill.style.color = '#B6D7F5';
      }
    }
  }

  ensureSpeechRecognitionActive() {
    if (!this.micActive || !this.speechRec || this.isRecStarting) return;
    try {
      this.isRecStarting = true;
      this.speechRec.start();
    } catch (e) {
      this.isRecStarting = false;
    }
  }

  initSpeechRecognition(sendToFalsoCb) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn('[Recognition Error] Web Speech API not supported in this browser');
      return;
    }

    if (this.speechRec) return;

    this.speechRec = new SpeechRecognition();
    this.speechRec.continuous = true;
    this.speechRec.interimResults = true;
    this.speechRec.lang = 'en-US';

    this.speechRec.onstart = () => {
      this.isRecStarting = false;
      console.log('[STT] Listening');
    };

    this.speechRec.onspeechstart = () => {
      console.log('[VAD] Human voice detected');
      if (this.sysState === 'speaking' || this.isSpeakingSpeech || this.audioSentenceQueue.length > 0) {
        console.log('[TTS] Interrupted');
        this.triggerVoiceInterruption();
      } else if (this.sysState === 'idle' || this.sysState === 'sleeping') {
        this.changeState('listening');
      }
    };

    this.speechRec.onspeechend = () => {
      console.log('[Speech Ended]');
    };

    this.speechRec.onresult = (event) => {
      let finalTranscript = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        }
      }

      const clean = finalTranscript.trim();
      if (clean) {
        console.log('[STT] Recognizing:', clean);
        this.lastSpeechTime = Date.now();
        if (this.sysState === 'speaking' || this.isSpeakingSpeech || this.audioSentenceQueue.length > 0) {
          console.log('[FULL-DUPLEX] Mid-speech interruption detected -> Triggering instant barge-in');
          this.triggerVoiceInterruption();
        }
        sendToFalsoCb(clean);
      }
    };

    this.speechRec.onerror = (event) => {
      this.isRecStarting = false;
      if (event.error !== 'no-speech') {
        console.warn('[Recognition Error]', event.error);
      }
    };

    this.speechRec.onend = () => {
      this.isRecStarting = false;
      if (this.micActive) {
        setTimeout(() => {
          this.ensureSpeechRecognitionActive();
        }, 100);
      }
    };

    this.ensureSpeechRecognitionActive();
  }

  async requestMicPermission() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(t => t.stop());
      const overlay = document.getElementById('mic-permission-overlay');
      if (overlay) overlay.style.display = 'none';
      this.micActive = true;
      this.ensureSpeechRecognitionActive();
    } catch (e) {
      console.warn('[Mic Permission Denied]', e);
      const overlay = document.getElementById('mic-permission-overlay');
      if (overlay) overlay.style.display = 'flex';
    }
  }

  triggerVoiceInterruption(requestId) {
    if (this.sysState === 'speaking' || this.isSpeakingSpeech || this.audioSentenceQueue.length > 0) {
      console.log(`[TTS][${requestId || this.activeRequestId || 'GLOBAL'}] INTERRUPTED`);
      this.stopActiveAudioPlayback();
      this.clearAudioStreamingQueue();
      this.isSpeakingSpeech = false;
      this.isProcessingAudioQueue = false;
      this.changeState('interrupted');
      setTimeout(() => {
        this.changeState('listening');
        this.ensureSpeechRecognitionActive();
      }, 50);
    }
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
    // Sentence deduplication check against tail of queue
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
    console.log(`[TTS][${reqId}] RESPONSE_RECEIVED`, ttsText);
    console.log(`[TTS][${reqId}] REQUEST_START`, ttsText);
    try {
      const res = await fetch(API_BASE + '/voice/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: ttsText, request_id: reqId }),
        signal: signal
      });

      if (signal.aborted || (this.activeRequestId && reqId !== this.activeRequestId)) {
        console.log(`[TTS][${reqId}] ABORTED_IN_FLIGHT`);
        return false;
      }

      if (res.ok) {
        const audioBlob = await res.blob();
        console.log(`[TTS][${reqId}] AUDIO_RECEIVED`, audioBlob.size, "bytes");
        if (signal.aborted || audioBlob.size < 100 || (this.activeRequestId && reqId !== this.activeRequestId)) {
          this.isSpeakingSpeech = false;
          return false;
        }
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        this.currentAudioSource = audio;
        this.changeState('speaking');
        audio.onended = () => {
          console.log(`[TTS][${reqId}] PLAYBACK_END`);
          URL.revokeObjectURL(audioUrl);
          this.currentAudioSource = null;
          this.isSpeakingSpeech = false;
          this.lastSpeechTime = Date.now();
          this.playNextSentenceInQueue();
        };
        audio.onerror = (err) => {
          console.warn(`[TTS][${reqId}] PLAYBACK_ERROR`, err);
          URL.revokeObjectURL(audioUrl);
          this.currentAudioSource = null;
          this.isSpeakingSpeech = false;
          this.playNextSentenceInQueue();
        };
        try {
          if (!signal.aborted && (!this.activeRequestId || reqId === this.activeRequestId)) {
            console.log(`[TTS][${reqId}] PLAYBACK_START`);
            await audio.play();
            console.log(`[TTS][${reqId}] PLAYBACK_STARTED_SUCCESSFULLY`);
            return true;
          }
        } catch (playErr) {
          console.warn(`[TTS][${reqId}] PLAYBACK_ERROR`, playErr);
          this.currentAudioSource = null;
          this.isSpeakingSpeech = false;
          return false;
        }
      }
    } catch(e) {
      if (e.name === 'AbortError') {
        console.log(`[TTS][${reqId}] ABORTED`);
        return false;
      }
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
