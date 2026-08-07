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

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        fullResponse += chunk;
        msgDiv.innerHTML = fullResponse.replace(/\n/g, '<br>') + `<span class="meta">FALSO · Streaming...</span>`;
        if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
        this.voiceManager.processIncomingTokenStream(chunk);
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
