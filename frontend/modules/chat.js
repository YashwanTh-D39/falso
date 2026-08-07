/**
 * Chat Stream & UI Message Manager for FALSO.
 */

const API_BASE = window.location.origin + '/api/v1';

export class ChatManager {
  constructor(voiceManager, settingsManager) {
    this.voiceManager = voiceManager;
    this.settingsManager = settingsManager;
  }

  appendMessage(role, text) {
    const chatArea = document.getElementById('chat-area');
    if (!chatArea) return;
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;
    msgDiv.innerHTML = text.replace(/\n/g, '<br>');
    chatArea.appendChild(msgDiv);
    chatArea.scrollTop = chatArea.scrollHeight;
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

    const chatArea = document.getElementById('chat-area');
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message system';
    if (chatArea) {
      chatArea.appendChild(msgDiv);
    }

    let fullResponse = "";
    try {
      const res = await fetch(API_BASE + '/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
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
        msgDiv.innerHTML = fullResponse.replace(/\n/g, '<br>');
        if (chatArea) chatArea.scrollTop = chatArea.scrollHeight;
        this.voiceManager.processIncomingTokenStream(chunk);
      }

      this.voiceManager.finalizeIncomingTokenStream();
    } catch(err) {
      console.error("[Chat Stream Error]", err);
      msgDiv.textContent = "[Network Error]";
      this.voiceManager.changeState('listening');
    }
  }
}
