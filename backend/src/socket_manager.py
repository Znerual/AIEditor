# src/socket_manager.py
from flask_socketio import SocketIO
from typing import Optional
from events import WebSocketEvent
class SocketManager:
    _instance: Optional['SocketManager'] = None
    _socketio: Optional[SocketIO] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def init_socket_manager(self, socketio):
        self._socketio = socketio
    
        self._setup_handlers()

    def _setup_handlers(self):
        @self._socketio.on('connect')
        def handle_connect():
            print('Client connected')
        
        @self._socketio.on('disconnect')
        def handle_disconnect():
            print('Client disconnected')
        
        @self._socketio.on('text_change')
        def handle_text_change(msg):
            print('Message: ' + str(msg))
        
        @self._socketio.on('chat')
        def handle_chat_event(msg):
            self._socketio.emit("chat_answer", f"Answer: {msg}")
    
    def emit_event(self, event: WebSocketEvent):
        if self._socketio is None:
            raise RuntimeError("SocketIO not initialized")
        
        try:
            print(f"🚀 Emitting event '{event.name}' with data: {event.data}")
            self._socketio.emit(event.name, event.data)
            print(f"✅ Successfully emitted event '{event.name}'")
            return True
        except Exception as e:
            print(f"❌ Error emitting event: {str(e)}")
            return False
    
    @property
    def socketio(self):
        return self._socketio