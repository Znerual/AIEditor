// src/hooks/useWebSocket.js
import { useEffect, useCallback } from 'react';
import { socketService } from '../services/socket.service';

export const useWebSocket = (events) => {
    useEffect(() => {
        const socket = socketService.connect();
        
        // Setup event listeners
        Object.entries(events).forEach(([event, handler]) => {
            socket.on(event, handler);
        });

        return () => {
            socket.disconnect();
        };
    }, [events]);

    const emit = useCallback((event, data) => {
        socketService.emit(event, data);
    }, []);

    return { emit };
};