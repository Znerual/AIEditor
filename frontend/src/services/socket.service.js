// src/services/socket.service.js
import { io } from 'socket.io-client';

class SocketService {
    constructor() {
        this.socket = null;
        this.debugMode = process.env.REACT_APP_DEBUG === 'true';
        this.statusListeners = new Set();
        this.activeConnections = 0;
    }

    addStatusListener(listener) {
        this.statusListeners.add(listener);
        // Immediately notify of current status
        if (this.socket) {
            listener(this.socket.connected ? 'connected' : 'disconnected');
        }
    }

    removeStatusListener(listener) {
        this.statusListeners.delete(listener);
    }

    notifyStatusListeners(status) {
        this.statusListeners.forEach(listener => listener(status));
    }


    connect() {
        if (this.socket?.connected) {
            return this.socket;
        }

        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }

        this.socket = io('http://localhost:5000', {
            transports: ['websocket', 'polling'],  // Allow fallback to polling
            debug: this.debugMode,
            reconnection: true,
            reconnectionAttempts: 5,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            timeout: 20000,
            autoConnect: true,
            withCredentials: true,
            // path: 'socket.io'
        });

        this.activeConnections += 1;
        this.setupDebugListeners();
        return this.socket;
    }

    disconnect() {
       this.activeConnections -= 1;
        if (this.activeConnections === 0 && this.socket) {
            this.socket.disconnect();
            this.socket = null;
        }
        this.notifyStatusListeners('disconnected');
        if (this.debugMode) {
            console.log('[WebSocket] Disconnected');
        }
    }

    setupDebugListeners() {
        if (!this.socket) return;

        this.socket.on('connect', () => {
            this.notifyStatusListeners('connected');
            if (this.debugMode) {
                console.log(`[WebSocket] Connected with ID: ${this.socket.id}`);
            }
        });

        this.socket.on('disconnect', (reason) => {
            this.notifyStatusListeners('disconnected');
            if (this.debugMode) {
                console.log('[WebSocket] Disconnected:', reason);
            }
        });

        this.socket.on('connect_error', (error) => {
            console.error('[WebSocket] Connection error:', error);
            // Try to reconnect using polling if websocket fails
            if (this.socket.io.opts.transports[0] === 'websocket') {
                console.log('[WebSocket] Falling back to polling');
                this.socket.io.opts.transports = ['polling', 'websocket'];
            }
        });

        if (this.debugMode) {
            this.socket.onAny((event, ...args) => {
                console.log(`[WebSocket] Event: ${event}`, args);
            });

            this.socket.io.on('ping', () => {
                console.log('[WebSocket] Ping sent');
            });

            this.socket.io.on('pong', (latency) => {
                console.log('[WebSocket] Pong received, latency:', latency, 'ms');
            });
        }
    }

    emit(event, data) {
        if (!this.socket?.connected) {
            console.error('[WebSocket] Cannot emit - socket not connected');
            return;
        }

        if (this.debugMode) {
            console.log(`[WebSocket] Emitting: ${event}`, data);
        }
        
        this.socket.emit(event, data);
    }


    getStatus() {
        return this.socket?.connected ? 'connected' : 'disconnected';
    }
}

export const socketService = new SocketService();