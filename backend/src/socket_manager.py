# src/socket_manager.py
from flask import session
from flask_socketio import SocketIO, join_room, leave_room
from typing import Optional
from events import WebSocketEvent
from document_manager import DocumentManager
from autocomplete_manager import AutocompleteManager
from dialog_manager import DialogManager
from auth import Auth
from functools import partial
from concurrent.futures import ThreadPoolExecutor
from models import Document, db

from delta import Delta
import uuid
from utils import delta_to_string
import threading
from config import Config

class SocketManager:
    _instance: Optional['SocketManager'] = None
    _socketio: Optional[SocketIO] = None
    _autocomplete_manager: Optional[AutocompleteManager] = None
    _executor: Optional[ThreadPoolExecutor] = None
    current_content_selection = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def init_socket_manager(self, socketio, gemini_api_key, debug=False):
        self._socketio = socketio
        self._autocomplete_manager = AutocompleteManager(api_key=gemini_api_key, debug=debug)
        self._dialog_manager = DialogManager(api_key=gemini_api_key, debug=debug)
        self._executor = ThreadPoolExecutor(max_workers=5)
        self._setup_handlers()


    def _setup_handlers(self):

        # client connects to server
        @self._socketio.on('connect')
        def handle_connect():
            self.emit_event(WebSocketEvent("server_connects", {}))
            print("Client connected, before authentification")

        # client disconnects from server
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


        @self._socketio.on('client_authenticates')
        @Auth.socket_auth_required(emit_event=self.emit_event)
        def handle_client_authenticates(user_id, data): 
            print("Client tries to authenticate")
            print(f'Client authenticated: user_id={user_id}')

           
        @self._socketio.on('client_get_document')
        @Auth.socket_auth_required(emit_event=self.emit_event)
        def handle_client_get_document(user_id, data):
            try:
                document_id = data.get('documentId')
                
                if not document_id:
                    print(data)
                    raise ValueError("Missing documentId field in handle_get_document")
                
                # Store the document ID in the session for this client
                session['document_id'] = document_id

                # Join the room specific to the document ID
                join_room(document_id)

                document = Document.query.filter_by(id=document_id, user_id=user_id).first()
                if not document:
                    self.emit_event(WebSocketEvent('server_error', {'message': f"Document not found: {document_id}"}))
                    return
                
                content = DocumentManager.get_document_content(document)
                self.emit_event(WebSocketEvent('server_sent_document_content', {
                    'documentId': document_id,
                    'title': document.title,
                    'content': content.ops
                }))
                
            except Exception as e:
                print(f"Error getting document: {str(e)}")
                self._socketio.emit('error', {'message': str(e)})
        
        @self._socketio.on('client_text_change')
        @Auth.socket_auth_required(emit_event=self.emit_event)
        def handle_client_text_change(user_id, data):
            try:
                delta = data.get('delta')
                document_id = data.get('documentId')
                if not all([document_id, delta]):
                    raise ValueError("Missing required fields documentId or delta in handle_text_change")
                

                # User ID comes from the token, not the request
                updated_content = DocumentManager.apply_delta(document_id, user_id, delta)
                
                # Broadcast the delta to all other clients in the same document room (except the sender)
                self.emit_event(WebSocketEvent('client_text_change', data), room=document_id, include_self=False)
                
            except Exception as e:
                print(f"Error handling text change: {str(e)}")
                self.emit_event(WebSocketEvent('error', {'message': str(e), 'type' : str(type(e))}))
        
        @self._socketio.on('client_request_suggestions')
        @Auth.socket_auth_required(emit_event=self.emit_event)
        def handle_client_request_suggestions(user_id, data):

            try:
                document_id = data.get('documentId')
                cursor_position = data.get('cursorPosition', 0)
                request_id = data.get('requestId')
                if not all([document_id, request_id]):
                    raise ValueError("Missing required fields documentId and requestId in handle_text_change")
                
                document = Document.query.get(document_id)
                if not document:
                    raise ValueError("Document not found")
                
                content_str = DocumentManager.get_document_content(document, user_id, as_string=True)

                 # Get and emit autocompletion suggestions
                suggestions = self._autocomplete_manager.get_suggestions(
                    user_id=user_id,
                    content=content_str,
                    cursor_position=cursor_position
                )

                
                if suggestions:
                    self.emit_event(WebSocketEvent('server_autocompletion_suggestions', {
                        'documentId': document_id,
                        'suggestions': suggestions,
                        'cursorPosition': cursor_position,
                        'requestId': request_id
                    }))

                print(f"Title Mnaually set: {document.title_manually_set}, len content string: {len(content_str)}")

                # Generate a title for the document
                if not document.title_manually_set and len(content_str) > Config.TITLE_DOCUMENT_LENGTH_THRESHOLD:
                    print("Generating title")
                    title = self._autocomplete_manager.generate_title(content_str)
                    if title:
                        document.title = title
                        db.session.commit()
                        self.emit_event(WebSocketEvent('server_document_title_generated', {
                            'documentId': document_id,
                            'title': title
                        }), room=document_id, include_self=True)

                
                
            except Exception as e:
                print(f"Error handling text change: {str(e)}")
                self.emit_event(WebSocketEvent('error', {'message': str(e), 'type' : str(type(e))}))
        
        
        @self._socketio.on('client_title_change')
        @Auth.socket_auth_required(emit_event=self.emit_event)
        def handle_client_title_change(user_id, data):
            try:
                document_id = data.get('documentId')
                title = data.get('title')
                if not all([document_id, title]):
                    raise ValueError("Missing required fields documentId and title in handle_title_change")
                
                document = Document.query.get(document_id)
                if not document:
                    raise ValueError("Document not found")
                
                document.title = title
                document.title_manually_set = True
                db.session.commit()
                self.emit_event(WebSocketEvent('client_title_change', {
                    'documentId': document_id,
                    'title': title
                }), room=document_id, include_self=False)
            except Exception as e:
                print(f"Error handling title change: {str(e)}")
                self.emit_event(WebSocketEvent('error', {'message': str(e), 'type' : str(type(e))}))
                return False
            
        @self._socketio.on('client_content_changes')
        @Auth.socket_auth_required(emit_event=self.emit_event)
        def handle_client_content_changes(user_id, data):
            print("Content uploaded or selection changed")
            print(data)
            self.current_content_selection = [item for item in data if 'file_id' in item and 'content_type' in item]  
            self._autocomplete_manager.on_user_content_change(user_id, self.current_content_selection)

        @self._socketio.on('client_chat')
        @Auth.socket_auth_required(emit_event=self.emit_event)
        def handle_chat_event(user_id, msg):
            document_id = session.get('document_id')  # Get document_id from session
            response_data = self._dialog_manager.get_response(user_id, msg['text'], document_id, self.current_content_selection)

            # Emit response and suggested edits
            self.emit_event(WebSocketEvent("server_chat_answer", {
                "response": response_data["response"],
                "suggested_edits": response_data["suggested_edits"]
            }))

        @self._socketio.on('client_apply_edit')
        @Auth.socket_auth_required(emit_event=self.emit_event)
        def handle_apply_edit(user_id, data):
            document_id = session.get('document_id')
            edit_id = data.get("edit_id")
            accepted = data.get("accepted")

            if document_id is None or edit_id is None or accepted is None:
                self.emit_event(WebSocketEvent("server_error", {"message": "Invalid edit request"}))
                return

            try:
                self._dialog_manager.apply_edit(user_id, document_id, edit_id, accepted)
                self.emit_event(WebSocketEvent("server_edit_applied", {"edit_id": edit_id, "status": "accepted" if accepted else "rejected"}))
            except Exception as e:
                self.emit_event(WebSocketEvent("server_error", {"message": str(e)}))
        
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