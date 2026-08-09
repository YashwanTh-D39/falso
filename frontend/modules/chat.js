/**
 * Chat Stream & UI Message Manager for FALSO Premium UI.
 */

const API_BASE = window.location.origin + '/api/v1';

export class ChatManager {
  constructor(voiceManager, settingsManager) {
    this.voiceManager = voiceManager;
    this.settingsManager = settingsManager;
    this.msgCount = 1;
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

    // Automatic Mode adaptive UI check
    const isCodeOrArtifactQuery = /code|script|create|python|html|javascript|function|explain|error|summary|pdf|image|generate|table/i.test(lowerText);
    if (this.settingsManager.currentInteractionMode === 'automatic_mode') {
      this.settingsManager.applyInteractionModeUI(isCodeOrArtifactQuery);
    }

    this.appendMessage('user', text);
    this.voiceManager.changeState('thinking');
    this.voiceManager.clearAudioStreamingQueue();
    this.voiceManager.stopActiveAudioPlayback();

    const chatContainer = document.getElementById('chatlog') || document.getElementById('chat-area');
    const msgDiv = document.createElement('div');
    msgDiv.className = 'msg ai';
    if (chatContainer) {
      chatContainer.appendChild(msgDiv);
    }

    let fullResponse = "";
    try {
      const res = await fetch(API_BASE + '/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: text, message: text })
      });

      if (!res.ok) {
        msgDiv.textContent = "[Error contacting FALSO Core]";
        this.voiceManager.changeState('listening');
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      let lineBuffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        lineBuffer += decoder.decode(value, { stream: true });
        
        const lines = lineBuffer.split('\n');
        lineBuffer = lines.pop(); // Keep incomplete trailing fragment in buffer

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          
          let textSnippet = "";
          try {
            const jsonStr = trimmed.startsWith("data: ") ? trimmed.slice(6) : trimmed;
            const parsed = JSON.parse(jsonStr);
            textSnippet = parsed.response || parsed.chunk || parsed.text || "";
          } catch(e) {
            textSnippet = trimmed;
          }

          if (textSnippet) {
            fullResponse += textSnippet;
            msgDiv.innerHTML = fullResponse.replace(/\n/g, '<br>') + `<span class="meta">FALSO · Streaming...</span>`;
            if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
            this.voiceManager.processIncomingTokenStream(textSnippet);
          }
        }
      }

      if (lineBuffer.trim()) {
        try {
          const jsonStr = lineBuffer.trim().startsWith("data: ") ? lineBuffer.trim().slice(6) : lineBuffer.trim();
          const parsed = JSON.parse(jsonStr);
          const textSnippet = parsed.response || parsed.chunk || parsed.text || "";
          if (textSnippet) {
            fullResponse += textSnippet;
            this.voiceManager.processIncomingTokenStream(textSnippet);
          }
        } catch(e) {}
      }

      const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      msgDiv.innerHTML = fullResponse.replace(/\n/g, '<br>') + `<span class="meta">FALSO · ${timeStr}</span>`;
      this.voiceManager.finalizeIncomingTokenStream();
    } catch(err) {
      console.error("[Chat Stream Error]", err);
      msgDiv.textContent = "[Network Error]";
      this.voiceManager.changeState('listening');
    }
  }
}
