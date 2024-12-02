// src/services/socket.service.js
import { io } from 'socket.io-client';

class SocketService {
    constructor() {
        this.socket = null;
        this.debugMode = process.env.REACT_APP_DEBUG === 'true';
    }

    connect() {
        this.socket = io('http://localhost:5000', {
            transports: ['websocket'],
            debug: this.debugMode
        });

        this.setupDebugListeners();
        return this.socket;
    }

    setupDebugListeners() {
        if (!this.debugMode) return;

        this.socket.onAny((event, ...args) => {
            console.log(`[WebSocket] Event: ${event}`, args);
        });

        this.socket.on('connect', () => {
            console.log(`[WebSocket] Connected with ID: ${this.socket.id}`);
        });

        this.socket.on('connect_error', (error) => {
            console.error('[WebSocket] Connection error:', error);
        });
    }

    emit(event, data) {
        if (this.debugMode) {
            console.log(`[WebSocket] Emitting: ${event}`, data);
        }
        this.socket.emit(event, data);
    }

    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
            if (this.debugMode) {
                console.log('[WebSocket] Disconnected');
            }
        }
    }
}

export const socketService = new SocketService();