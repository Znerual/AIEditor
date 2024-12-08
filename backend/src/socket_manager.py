# src/socket_manager.py
from flask_socketio import SocketIO
from typing import Optional
from events import WebSocketEvent
from document_manager import DocumentManager
from auth import Auth
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
        @Auth.socket_auth_required
        def handle_connect(user_id): 
            self._socketio.emit("connected")
            print(f'Client connected: user_id={user_id}')
            return True
           
        
        @self._socketio.on('disconnect')
        def handle_disconnect():
            print('Client disconnected')
        
        @self._socketio.on('text_change')
        @Auth.socket_auth_required
        def handle_text_change(user_id, data):
            try:
                document_id = data.get('document_id')
                delta = data.get('delta')
                
                if not all([document_id, delta]):
                    raise ValueError("Missing required fields document_id or delta in handle_text_change")
                
                # User ID comes from the token, not the request
                updated_content = DocumentManager.apply_delta(document_id, user_id, delta)
                
                self._socketio.emit('document_updated', {
                    'document_id': document_id,
                    #'content': updated_content
                })
                
            except Exception as e:
                print(f"Error handling text change: {str(e)}")
                self._socketio.emit('error', {'message': str(e)})
        
        @self._socketio.on('get_document')
        @Auth.socket_auth_required
        def handle_get_document(user_id, data):
            try:
                document_id = data.get('document_id')
                
                if not document_id:
                    raise ValueError("Missing document_id field in handle_get_document")
                
                content = DocumentManager.get_document_content(document_id, user_id)
                self._socketio.emit('document_content', {
                    'document_id': document_id,
                    'content': content
                })
                
            except Exception as e:
                print(f"Error getting document: {str(e)}")
                self._socketio.emit('error', {'message': str(e)})
        
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