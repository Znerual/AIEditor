// src/hooks/useWebSocket.js
import { useEffect, useCallback, useState } from 'react';
import { socketService } from '../services/socket.service';

export const useWebSocket = (events) => {
    const [status, setStatus] = useState(socketService.getStatus());
    const [debugEvents, setDebugEvents] = useState([]);

    useEffect(() => {
        const socket = socketService.connect();
        
        // Setup status listener
        const handleStatus = (newStatus) => {
            setStatus(newStatus);
        };
        socketService.addStatusListener(handleStatus);

        // Wrap each event handler to track debug events
        const wrappedHandlers = Object.entries(events).reduce((acc, [event, handler]) => {
            acc[event] = (...args) => {
                // Add to debug events
                setDebugEvents(prev => [...prev, {
                    event,
                    data: args,
                    timestamp: new Date().toISOString()
                }]);
                
                // Call original handler
                handler(...args);
            };
            return acc;
        }, {});

        // Setup event listeners
        Object.entries(events).forEach(([event, handler]) => {
            socket.on(event, handler);
        });

        // Add a catch-all listener for debugging
        socket.onAny((eventName, ...args) => {
            console.log(`[WebSocket] Received event: ${eventName}`, args);
        });

         return () => {
            // Cleanup event listeners
            Object.keys(events).forEach((event) => {
                socket.off(event);
            });
            socketService.removeStatusListener(handleStatus);
            socket.disconnect();
        };
    }, [events]);

    const emit = useCallback((event, data) => {
        socketService.emit(event, data);

        // Track emitted events in debug panel
        setDebugEvents(prev => [...prev, {
            event,
            data,
            type: 'sent',
            timestamp: new Date().toISOString()
        }]);
    }, []);

    return { emit, status, debugEvents };
};