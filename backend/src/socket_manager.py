# src/socket_manager.py
from flask import session
from flask_socketio import SocketIO, join_room, leave_room
from typing import Optional
from events import WebSocketEvent
from document_manager import DocumentManager
from auth import Auth
from autocomplete_manager import AutocompleteManager
import asyncio
from functools import partial
from concurrent.futures import ThreadPoolExecutor
import uuid

class SocketManager:
    _instance: Optional['SocketManager'] = None
    _socketio: Optional[SocketIO] = None
    _autocomplete_manager: Optional[AutocompleteManager] = None
    _executor: Optional[ThreadPoolExecutor] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def init_socket_manager(self, socketio, gemini_api_key):
        self._socketio = socketio
        self._autocomplete_manager = AutocompleteManager(api_key=gemini_api_key)
        self._executor = ThreadPoolExecutor(max_workers=5)
        self._setup_handlers()

    async def _get_autocompletion_suggestions(self, content: str, cursor_position: int):
        """
        Wrapper method to run autocompletion in thread pool
        """
        try:
            loop = asyncio.get_event_loop()
            suggestions = await loop.run_in_executor(
                self._executor,
                partial(self._autocomplete_manager.get_suggestions, content, cursor_position)
            )
            return suggestions
        except Exception as e:
            print(f"Error getting autocompletion suggestions: {str(e)}")
            return []


    def _setup_handlers(self):

        @self._socketio.on('connect')
        def handle_connect():
            print("Client connected, before authentification")

        @self._socketio.on('authentication')
        @Auth.socket_auth_required
        def handle_authentication(user_id, data): 
            print("Client tries to authenticate")
            try:
                # Generate a unique document ID
                document_id = str(uuid.uuid4())

                # Store the document ID in the session for this client
                session['document_id'] = document_id

                # Join the room specific to the document ID
                join_room(document_id)

                print(f'Client authenticated: user_id={user_id}, document_id={document_id}')

                # Send the document ID to the newly connected client
                self.emit_event(WebSocketEvent('document_created', {'document_id': document_id}))

                return True # Return True to acknowledge successful authentication

            except Exception as e:
                print(f"Authentication or room joining error: {e}")
                self.emit_event(WebSocketEvent('authentication_failed', {'message': str(e)}))  # Emit an error event
                return False # Return False to indicate authentication failure
           
        
        @self._socketio.on('disconnect')
        def handle_disconnect():
            try:
                # Client is disconnecting, leave the document room
                document_id = session.get('document_id')
                if document_id:
                    leave_room(document_id)
                    print(f"Client left room {document_id}")  # Log leaving room for debug
                print('Client disconnected') # Log disconnect for debug
            except KeyError as e:
                print(f"Error during disconnect: {e}")
        
        @self._socketio.on('text_change')
        @Auth.socket_auth_required
        async def handle_text_change(user_id, data):
            try:
                document_id = data.get('document_id')
                delta = data.get('delta')
                cursor_position = data.get('cursor_position', 0)
                
                if not all([document_id, delta]):
                    raise ValueError("Missing required fields document_id or delta in handle_text_change")
                
                # User ID comes from the token, not the request
                updated_content = DocumentManager.apply_delta(document_id, user_id, delta)
                
                # Broadcast the delta to all other clients in the same document room (except the sender)
                self.emit_event('text_change', data, room=document_id, include_self=False)

                 # Get and emit autocompletion suggestions
                suggestions = await self._get_autocompletion_suggestions(
                    updated_content,
                    cursor_position
                )
                
                if suggestions:
                    self._socketio.emit('autocompletion_suggestions', {
                        'document_id': document_id,
                        'suggestions': suggestions,
                        'cursor_position': cursor_position
                    })
                
            except Exception as e:
                print(f"Error handling text change: {str(e)}")
                self.emit_event('error', {'message': str(e)})
        
        @self._socketio.on('get_document')
        @Auth.socket_auth_required
        def handle_get_document(user_id, data):
            try:
                document_id = data.get('documentId')
                
                if not document_id:
                    print(data)
                    raise ValueError("Missing documentId field in handle_get_document")
                
                content = DocumentManager.get_document_content(document_id, user_id) + "Test Run"
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
    
    def emit_event(self, event: WebSocketEvent, **kwargs):
        if self._socketio is None:
            raise RuntimeError("SocketIO not initialized")
        
        try:
            print(f"🚀 Emitting event '{event.name}' with data: {event.data} and kwargs {kwargs}")
            self._socketio.emit(event.name, event.data, **kwargs)
            print(f"✅ Successfully emitted event '{event.name}'")
            return True
        except Exception as e:
            print(f"❌ Error emitting event: {str(e)}")
            return False
    
    @property
    def socketio(self):
        return self._socketio
    
    def __del__(self):
        if self._executor:
            self._executor.shutdown(wait=False)