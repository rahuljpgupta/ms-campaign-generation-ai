/**
 * WebSocket service for real-time communication with backend
 */

export class WebSocketService {
  constructor(clientId) {
    this.ws = null;
    this.clientId = clientId;
    this.messageCallbacks = [];
    this.connectionCallbacks = [];
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000;
  }

  connect() {
    const wsUrl = `ws://localhost:8000/ws/${this.clientId}`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
      this.notifyConnectionChange(true);
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.notifyMessageReceived(data);
      } catch (error) {
        console.error('Failed to parse message:', error);
      }
    };

    this.ws.onclose = () => {
      console.log('WebSocket closed');
      this.notifyConnectionChange(false);
      this.attemptReconnect();
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(`Reconnecting... Attempt ${this.reconnectAttempts}`);
      setTimeout(() => {
        this.connect();
      }, this.reconnectDelay * this.reconnectAttempts);
    } else {
      console.error('Max reconnection attempts reached');
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  sendMessage(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'user_message',
        message,
      }));
    } else {
      console.error('WebSocket is not connected');
    }
  }

  sendResponse(questionId, response) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'user_response',
        question_id: questionId,
        response,
      }));
    } else {
      console.error('WebSocket is not connected');
    }
  }

  onMessage(callback) {
    this.messageCallbacks.push(callback);
  }

  onConnectionChange(callback) {
    this.connectionCallbacks.push(callback);
  }

  notifyMessageReceived(data) {
    this.messageCallbacks.forEach(callback => callback(data));
  }

  notifyConnectionChange(connected) {
    this.connectionCallbacks.forEach(callback => callback(connected));
  }

  isConnected() {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }
}

