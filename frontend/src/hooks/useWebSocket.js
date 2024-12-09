// src/hooks/useWebSocket.js
import { useEffect, useCallback, useState, useRef } from 'react';
import { socketService } from '../services/socket.service';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

export const useWebSocket = (events) => {
    const { token } = useAuth(); // Get token from auth context
    const [status, setStatus] = useState(socketService.getStatus());
    const [debugEvents, setDebugEvents] = useState([]);
    const eventsRef = useRef(events);
    const navigate = useNavigate();

    // Update events ref when events change
    useEffect(() => {
        eventsRef.current = events;
    }, [events]);

    useEffect(() => {
        if (!token) {
            socketService.disconnect();
            setStatus('unauthorized');
            console.log('Disconnect because there is no access token, login first')
            navigate('/'); // send user to login form
            return;
        }

        const socket = socketService.connect();
        if (!socket) return;

        // Start the authentication handshake with the jwt
        socket.on('server_connects', () => {
            socket.emit('client_authenticates', { token }); // Emit authentication event with token
        });

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
                    type: 'received',
                    timestamp: new Date().toISOString()
                }]);
                
                // Call original handler
                handler(...args);

                if (typeof handler === 'function') {  // Check if handler is a function
                    console.log(`Attached listener for event: ${event}`);
                } else {
                    console.error(`Handler for event '${event}' is not a function:`, handler);
                }
            };
            return acc;
        }, {});

        // Setup event listeners
        Object.entries(wrappedHandlers).forEach(([event, handler]) => {
            socket.on(event, handler);
            console.log(`[WebSocket] Registered listener for: ${event}`);
        });

        // Add a catch-all listener for debugging
        socket.onAny((eventName, ...args) => {
            console.log(`[WebSocket] Received event: ${eventName}`, args);
        });

        return () => {
            // Cleanup event listeners
            if (socket) {
                Object.keys(eventsRef.current).forEach((event) => {
                    socket.off(event);
                });
            }
            socketService.removeStatusListener(handleStatus);
            socketService.disconnect();
            console.log("[WebSocket] Cleanup complete");
        };
    }, [token, events]);

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