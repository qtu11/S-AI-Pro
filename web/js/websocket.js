/**
 * WebSocket Client v5.0 — Enhanced connection with auto-reconnect.
 * Copyright © 2025-2026 Qtus Dev (Anh Tú)
 */

class WSClient {
  constructor() {
    this.ws = null;
    this.url = `ws://${location.host}/ws`;
    this.connected = false;
    this.reconnectDelay = 1000;
    this.maxReconnectDelay = 15000;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 50;
    this.handlers = {};
    this.messageQueue = [];
    this._heartbeatTimer = null;
    this._reconnectTimer = null;
  }

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) {
      return;
    }

    try {
      this.ws = new WebSocket(this.url);
    } catch (e) {
      console.error('[WS] Connection error:', e);
      this._scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.connected = true;
      this.reconnectAttempts = 0;
      this.reconnectDelay = 1000;
      console.log('[WS] Connected');
      this._emit('connected');
      this._startHeartbeat();

      // Flush queued messages
      while (this.messageQueue.length > 0) {
        const msg = this.messageQueue.shift();
        this.send(msg);
      }
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this._handleMessage(data);
      } catch (e) {
        console.warn('[WS] Parse error:', e);
      }
    };

    this.ws.onclose = (event) => {
      this.connected = false;
      this._stopHeartbeat();
      console.log('[WS] Disconnected', event.code);
      this._emit('disconnected');
      this._scheduleReconnect();
    };

    this.ws.onerror = (error) => {
      console.error('[WS] Error:', error);
    };
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      this.messageQueue.push(data);
    }
  }

  on(event, handler) {
    if (!this.handlers[event]) this.handlers[event] = [];
    this.handlers[event].push(handler);
  }

  off(event, handler) {
    if (this.handlers[event]) {
      this.handlers[event] = this.handlers[event].filter(h => h !== handler);
    }
  }

  _emit(event, data) {
    const handlers = this.handlers[event] || [];
    handlers.forEach(h => {
      try { h(data); } catch (e) { console.error(`[WS] Handler error (${event}):`, e); }
    });
  }

  _handleMessage(data) {
    const type = data.type;
    if (type === 'pong') return; // Heartbeat response

    // Emit specific event
    this._emit(type, data);
    // Also emit 'message' for catch-all
    this._emit('message', data);
  }

  _startHeartbeat() {
    this._stopHeartbeat();
    this._heartbeatTimer = setInterval(() => {
      this.send({ type: 'ping' });
    }, 25000);
  }

  _stopHeartbeat() {
    if (this._heartbeatTimer) {
      clearInterval(this._heartbeatTimer);
      this._heartbeatTimer = null;
    }
  }

  _scheduleReconnect() {
    if (this._reconnectTimer) return;
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('[WS] Max reconnect attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(this.reconnectDelay * Math.pow(1.3, this.reconnectAttempts - 1), this.maxReconnectDelay);

    console.log(`[WS] Reconnecting in ${Math.round(delay)}ms (attempt ${this.reconnectAttempts})`);
    this._reconnectTimer = setTimeout(() => {
      this._reconnectTimer = null;
      this.connect();
    }, delay);
  }

  disconnect() {
    this._stopHeartbeat();
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
    this.maxReconnectAttempts = 0; // Prevent reconnect
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

// Singleton
const wsClient = new WSClient();
