/**
 * Chat Stream & UI Message Manager for FALSO Premium UI.
 */

const API_BASE = window.location.origin + '/api/v1';

export class ChatManager {
  constructor(voiceManager, settingsManager) {
    this.voiceManager = voiceManager;
    this.settingsManager = settingsManager;
    this.msgCount = 1;
    this.activeRequestId = null;
    this.activeAbortController = null;
  }

  appendMessage(role, text) {
    const chatContainer = document.getElementById('chatlog') || document.getElementById('chat-area');
    if (!chatContainer) return;

    const msgDiv = document.createElement('div');
    const roleClass = role === 'assistant' ? 'ai' : (role === 'system' ? 'sys' : role);
    msgDiv.className = `msg ${roleClass}`;
    
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    msgDiv.innerHTML = text.replace(/\n/g, '<br>') + `<span class="meta">FALSO · ${timeStr}</span>`;

    chatContainer.appendChild(msgDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    this.msgCount++;
    const msgCountEl = document.getElementById('msgCount');
    if (msgCountEl) msgCountEl.textContent = `${this.msgCount} MSGS`;
  }

  async sendToFalso(text) {
    const lowerText = text.toLowerCase().trim();

    // Voice Mode Switch Commands
    if (lowerText.includes("voice mode") || lowerText.includes("enable voice only") || lowerText.includes("go to voice mode") || lowerText.includes("hide the display") || lowerText.includes("dont show it") || lowerText.includes("don't show it") || lowerText.includes("hide transcript") || lowerText.includes("hide the transcript")) {
      this.settingsManager.updateInteractionMode('voice_only');
      return;
    }
    if (lowerText.includes("display mode") || lowerText.includes("enter display mode") || lowerText.includes("show the conversation") || lowerText.includes("show transcript") || lowerText.includes("show response") || lowerText.includes("show the answer") || lowerText.includes("display the response") || lowerText.includes("show it")) {
      this.settingsManager.updateInteractionMode('display_mode');
      return;
    }
    if (lowerText.includes("automatic mode") || lowerText.includes("enable automatic mode") || lowerText.includes("auto mode")) {
      this.settingsManager.updateInteractionMode('automatic_mode');
      return;
    }

    // Cancel any previous active streaming request & voice output
    if (this.activeAbortController) {
      console.log(`[CHAT][${this.activeRequestId}] CANCELLING_PREVIOUS_REQUEST`);
      try { this.activeAbortController.abort(); } catch(e) {}
    }
    this.voiceManager.triggerVoiceInterruption();

    const requestId = 'FALSO-' + Date.now() + '-' + Math.floor(Math.random() * 10000);
    this.activeRequestId = requestId;
    this.activeAbortController = new AbortController();
    const signal = this.activeAbortController.signal;

    this.voiceManager.setActiveRequestId(requestId);

    // Automatic Mode adaptive UI check
    const isCodeOrArtifactQuery = /code|script|create|python|html|javascript|function|explain|error|summary|pdf|image|generate|table/i.test(lowerText);
    if (this.settingsManager.currentInteractionMode === 'automatic_mode') {
      this.settingsManager.applyInteractionModeUI(isCodeOrArtifactQuery);
    }

    this.appendMessage('user', text);
    this.voiceManager.changeState('thinking');

    const t0 = performance.now();
    console.log(`[CHAT][${requestId}] REQUEST_START`);

    const chatContainer = document.getElementById('chatlog') || document.getElementById('chat-area');
    const msgDiv = document.createElement('div');
    msgDiv.className = 'msg ai';
    msgDiv.dataset.requestId = requestId;
    if (chatContainer) {
      chatContainer.appendChild(msgDiv);
    }

    let fullResponse = "";
    let firstTokenRendered = false;
    try {
      const res = await fetch(API_BASE + '/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: text, message: text, request_id: requestId }),
        signal: signal
      });

      console.log(`[CHAT][${requestId}] BACKEND_HEADERS_RECEIVED +${Math.round(performance.now() - t0)}ms`);

      if (!res.ok) {
        msgDiv.textContent = "[Error contacting FALSO Core]";
        this.voiceManager.changeState('listening');
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      let lineBuffer = "";
      while (true) {
        if (signal.aborted || this.activeRequestId !== requestId) {
          console.log(`[CHAT][${requestId}] ABORTED_OR_SUPERSEDED`);
          return;
        }
        const { done, value } = await reader.read();
        if (done) break;
        lineBuffer += decoder.decode(value, { stream: true });
        
        const lines = lineBuffer.split('\n');
        lineBuffer = lines.pop(); // Keep incomplete trailing fragment in buffer

        for (const line of lines) {
          if (signal.aborted || this.activeRequestId !== requestId) break;
          const trimmed = line.trim();
          if (!trimmed) continue;
          
          let textSnippet = "";
          let parsedEvent = null;
          try {
            const jsonStr = trimmed.startsWith("data: ") ? trimmed.slice(6) : trimmed;
            parsedEvent = JSON.parse(jsonStr);
            textSnippet = parsedEvent.response || parsedEvent.chunk || parsedEvent.text || "";
          } catch(e) {
            textSnippet = trimmed;
          }

          // Handle warming status event (NVIDIA cold start)
          if (parsedEvent && parsedEvent.type === 'status' && parsedEvent.status === 'warming') {
            const warmMs = Math.round(performance.now() - t0);
            console.log(`[CHAT][${requestId}] NVIDIA_WARMING +${warmMs}ms`);
            this.voiceManager.changeState('warming');
            // Update diagnostics state pill
            const stateVal = document.getElementById('stateVal');
            if (stateVal) {
              stateVal.className = 'state-pill state-thinking';
              stateVal.textContent = 'WARMING';
            }
            msgDiv.innerHTML = '<span class="meta">NVIDIA warming...</span>';
            if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
            continue;
          }

          if (textSnippet) {
            const chunkMs = Math.round(performance.now() - t0);
            console.log(`[STREAM][${requestId}] CHUNK_RECEIVED +${chunkMs}ms`);
            if (!firstTokenRendered) {
              firstTokenRendered = true;
              this.voiceManager.changeState('streaming');
              console.log(`[CHAT][${requestId}] FRONTEND_FIRST_TOKEN +${chunkMs}ms`);
            }
            fullResponse += textSnippet;
            msgDiv.innerHTML = fullResponse.replace(/\n/g, '<br>') + `<span class="meta">FALSO · Streaming...</span>`;
            if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
            const renderMs = Math.round(performance.now() - t0);
            console.log(`[STREAM][${requestId}] TOKEN_RENDERED +${renderMs}ms`);
            this.voiceManager.processIncomingTokenStream(textSnippet, requestId);
          }
        }
      }

      if (lineBuffer.trim() && !signal.aborted && this.activeRequestId === requestId) {
        try {
          const jsonStr = lineBuffer.trim().startsWith("data: ") ? lineBuffer.trim().slice(6) : lineBuffer.trim();
          const parsed = JSON.parse(jsonStr);
          const textSnippet = parsed.response || parsed.chunk || parsed.text || "";
          if (textSnippet) {
            if (!firstTokenRendered) {
              firstTokenRendered = true;
              console.log(`[CHAT][${requestId}] FRONTEND_FIRST_TOKEN +${Math.round(performance.now() - t0)}ms`);
            }
            fullResponse += textSnippet;
            this.voiceManager.processIncomingTokenStream(textSnippet, requestId);
          }
        } catch(e) {}
      }

      if (this.activeRequestId === requestId) {
        console.log(`[CHAT][${requestId}] RESPONSE_COMPLETE +${Math.round(performance.now() - t0)}ms`);
        const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        msgDiv.innerHTML = fullResponse.replace(/\n/g, '<br>') + `<span class="meta">FALSO · ${timeStr}</span>`;
        this.voiceManager.finalizeIncomingTokenStream(requestId);
      }
    } catch(err) {
      if (err.name === 'AbortError') {
        console.log(`[CHAT][${requestId}] STREAM_ABORTED`);
        msgDiv.innerHTML = fullResponse.replace(/\n/g, '<br>') + `<span class="meta">FALSO · Interrupted</span>`;
      } else {
        console.error("[Chat Stream Error]", err);
        msgDiv.textContent = "[Network Error]";
        this.voiceManager.changeState('listening');
      }
    }
  }
}
