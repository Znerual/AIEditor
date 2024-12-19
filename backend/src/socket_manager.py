# src/socket_manager.py
from os import access
from flask import session
from flask_socketio import SocketIO, join_room, leave_room
from typing import Optional
from events import WebSocketEvent
from document_manager import DocumentManager
from autocomplete_manager import AutocompleteManager
from dialog_manager import DialogManager
from structure_manager import StructureManager
from auth import Auth
from functools import partial
from models import User, Document, DocumentEditAccess,DocumentReadAccess
from concurrent.futures import ThreadPoolExecutor
from models import Document, db

from delta import Delta
import uuid
from utils import string_to_delta
import threading
from config import Config

class SocketManager:
    _instance: Optional['SocketManager'] = None
    _socketio: Optional[SocketIO] = None
    _autocomplete_manager: Optional[AutocompleteManager] = None
    _structure_manager: Optional[StructureManager] = None
    _executor: Optional[ThreadPoolExecutor] = None
    current_content_selection = []

    def __new__(cls, socketio, gemini_api_key, debug=False):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, socketio, gemini_api_key, debug=False):
        self._init_socket_manager(socketio, gemini_api_key, debug)
        
    
    def _init_socket_manager(self, socketio, gemini_api_key, debug=False):
        self._socketio = socketio
        self._autocomplete_manager = AutocompleteManager(api_key=gemini_api_key, debug=debug)
        self._dialog_manager = DialogManager(api_key=gemini_api_key, debug=debug)
        self._structure_manager = StructureManager(api_key=gemini_api_key, debug=debug)
        self._executor = ThreadPoolExecutor(max_workers=5)
        self.active_users = {}
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

        @self._socketio.on('client_leave_document')
        @Auth.socket_auth_required(emit_event=self.emit_event)
        def handle_client_leave_document(user_id, data):
            try:
                document_id = data.get('documentId')

                # Remove user from active users list
                if document_id in self.active_users:
                    self.active_users[document_id].discard(user_id)

                    # If no users are left in the document, remove the document from the list
                    if not self.active_users[document_id]:
                        del self.active_users[document_id]

                # Leave the room
                leave_room(document_id)

                # Broadcast user left event
                self.emit_event(
                    WebSocketEvent('server_user_left', {
                        'userId': user_id,
                        'documentId': document_id
                    }),
                    room=document_id
                )

            except Exception as e:
                print(f"Error handling client_leave_document: {e}")
                self.emit_event(WebSocketEvent('server_error', {'message': str(e)}))

           
        @self._socketio.on('client_get_document')
        @Auth.socket_auth_required(emit_event=self.emit_event)
        def handle_client_get_document(user_id, data):
            try:
                document_id = data.get('documentId')
                
                if not document_id:
                    print(data)
                    raise ValueError("Missing documentId field in handle_get_document")
                
                document = Document.query.get_or_404(document_id)
                
                access_rights = None
                # get the access rights for the file
                if int(user_id) == int(document.user_id):
                    access_rights = 'owner'
                else:
                    edit_access_users = User.query.join(DocumentEditAccess, DocumentEditAccess.user_id == User.id).filter(DocumentEditAccess.document_id == document.id, DocumentEditAccess.user_id == user_id).first()
                    if edit_access_users:
                        access_rights ='edit'
                    else:
                        read_access_users = User.query.join(DocumentReadAccess, DocumentReadAccess.user_id == User.id).filter(DocumentReadAccess.document_id == document.id, DocumentReadAccess.user_id == user_id).first()
                        if read_access_users:
                            access_rights = 'read'
                        
                
                if not access_rights:
                    print(f"WARNING! Client {user_id} tries to get unauthorized access to document {document_id}.")
                    return
                
                # Store the document ID in the session for this client
                session['document_id'] = document_id
                session['access_rights'] = access_rights


                # Join the room specific to the document ID
                join_room(document_id)
                # Add user to active users list
                if document_id not in self.active_users:
                    self.active_users[document_id] = set()
                self.active_users[document_id].add(user_id)

                # Broadcast user joined event
                self.emit_event(
                    WebSocketEvent('server_user_joined', {
                        'userId': user_id,
                        'documentId': document_id,
                        'username': User.query.get(user_id).email  # Get user's email or other identifying info
                    }),
                    room=document_id
                )

                content = DocumentManager.get_document_content(document)
                self.emit_event(WebSocketEvent('server_sent_document_content', {
                    'documentId': document_id,
                    'title': document.title,
                    'content': content.ops,
                    'access_rights': access_rights,
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
                
                if not session['access_rights'] in ["owner", "edit"]:
                    self.emit_event(WebSocketEvent('error', {'message' : 'No rights to edit document'}))
                    return
                
                print("Text change data: " ,data)
                # User ID comes from the token, not the request
                updated_content = DocumentManager.apply_delta(document_id, user_id, delta)
                print("Updated content: ", updated_content)
                # Broadcast the delta to all other clients in the same document room (except the sender)
                self.emit_event(WebSocketEvent('server_text_change', {
                                    'delta' : delta,
                                    'documentId': document_id,
                                    'userId' : user_id,
                                }), 
                                room=document_id, include_self=False)
                
            except Exception as e:
                print(f"Error handling text change server: {str(e)}")
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
                
                if not session['access_rights'] in ["owner", "edit"]:
                    self.emit_event(WebSocketEvent('error', {'message' : 'No rights to edit document'}))
                    return
                
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
                if (not document.title or (document.title and not len(document.title) > 3)) and not document.title_manually_set and len(content_str) > Config.TITLE_DOCUMENT_LENGTH_THRESHOLD:
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
                print(f"Error handling generating suggestions: {str(e)}")
                self.emit_event(WebSocketEvent('error', {'message': str(e), 'type' : str(type(e))}))
        
        
        @self._socketio.on('client_title_change')
        @Auth.socket_auth_required(emit_event=self.emit_event)
        def handle_client_title_change(user_id, data):
            try:
                document_id = data.get('documentId')
                title = data.get('title')
                if not all([document_id, title]):
                    raise ValueError("Missing required fields documentId and title in handle_title_change")
                
                if not session['access_rights'] in ["owner", "edit"]:
                    self.emit_event(WebSocketEvent('error', {'message' : 'No rights to edit document'}))
                    return
                
                document = Document.query.get(document_id)
                if not document:
                    raise ValueError("Document not found")
                
                document.title = title
                document.title_manually_set = True
                db.session.commit()
                self.emit_event(WebSocketEvent('server_title_change', {
                    'documentId': document_id,
                    'title': title,
                    'userId' : user_id,
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
            if not session['access_rights'] in ["owner", "edit"]:
                self.emit_event(WebSocketEvent('error', {'message' : 'No rights to upload content'}))
                return
            self.current_content_selection = [item for item in data if 'file_id' in item and 'content_type' in item]  
            self._autocomplete_manager.on_user_content_change(user_id, self.current_content_selection)

            self.emit_event(WebSocketEvent('server_content_changes', data), room=session['document_id'], include_self=False)

        @self._socketio.on('client_structure_uploaded')
        @Auth.socket_auth_required(emit_event=self.emit_event)
        def handle_client_structure_uploaded(user_id, data):
            if not session['access_rights'] in ["owner", "edit"]:
                self.emit_event(WebSocketEvent('error', {'message' : 'No rights to change structure'}))
                return
            print("Structure uploaded")
            if not data:
                self.emit_event(WebSocketEvent('server_error', {'message': 'Missing data'}))
                return
            
           
            
            structure_text = ""
            if data["content_type"] == 'file_content': 
                structure_text = data["text_extracted"]
            elif data["content_type"] == 'document':
                document_id = data["file_id"]
                document = Document.query.get(document_id)
                if not document:
                    self.emit_event(WebSocketEvent('server_error', {'message': 'Document not found'}))
                    return

                structure_text = DocumentManager.get_document_content(document, as_string=True)
            
            if not structure_text or structure_text == "":
                self.emit_event(WebSocketEvent('server_error', {'message': 'Missing text_extracted'}))
                return


            # Extract structure from the uploaded text
            extracted_structure = self._structure_manager.extract_structure(structure_text)
            print("Extracted structure:", extracted_structure)

            # get the current document
            document_id = session.get('document_id')
            document = Document.query.get(document_id)
            if not document:
                self.emit_event(WebSocketEvent('server_error', {'message': 'Document not found'}))
                return
            
            # Apply the extracted structure to the document
            new_document_content = self._structure_manager.apply_structure(document, extracted_structure)

            # Convert the new content (string) to a Delta object
            new_document_content_delta = string_to_delta(new_document_content)

            # # Update the document content in the database
            # document.content = new_document_content_delta.ops
            # db.session.commit()


            self.emit_event(WebSocketEvent('server_sent_new_structure', {
                'documentId': document_id,
                'title': document.title,
                'content': new_document_content_delta.ops
            }))

        @self._socketio.on('client_structure_accepted')
        @Auth.socket_auth_required(emit_event=self.emit_event)
        def handle_client_structure_accepted(user_id, data):

            if not session['access_rights'] in ["owner", "edit"]:
                self.emit_event(WebSocketEvent('error', {'message' : 'No rights to edit document'}))
                return
            
            print("Structure removed")
            if not data or not 'content' in data:
                self.emit_event(WebSocketEvent('server_error', {'message': 'Missing data'}))
                return
            
            document_id = session.get('document_id')
            if not data["documentId"] or document_id != data["documentId"]:
                self.emit_event(WebSocketEvent('server_error', {'message': 'Invalid documentId'}))
                return
            
            # get the current document
            document = Document.query.get(document_id)
            if not document:
                self.emit_event(WebSocketEvent('server_error', {'message': 'Document not found'}))
                return
            
            document.content = data["content"]
            db.session.commit()

            self.emit_event(WebSocketEvent('server_sent_accepted_new_structure', {
                'documentId': document_id,
                'title': document.title,
                'content': data["content"]
            }), room=document_id, include_self=False)
            print("Document content updated")
            

        @self._socketio.on('client_structure_rejected')
        @Auth.socket_auth_required(emit_event=self.emit_event)
        def handle_client_structure_rejected(user_id, data):
            print("Structure rejected")

        @self._socketio.on('client_chat')
        @Auth.socket_auth_required(emit_event=self.emit_event)
        def handle_chat_event(user_id, msg):
            document_id = session.get('document_id')  # Get document_id from session
            response_data = self._dialog_manager.get_response(user_id, msg['text'], document_id, self.current_content_selection)

            # TODO, how to deal with chat if only read access is given?
            # Maybe allow chat, but no edits
            # Emit response and suggested edits
            if session['access_rights'] in ["owner", "edit"]:
                suggested_edits =  response_data["suggested_edits"]
            else:
                suggested_edits = []
            
            self.emit_event(WebSocketEvent("server_chat_answer", {
                "response": response_data["response"],
                "suggested_edits": suggested_edits,
            }))

        @self._socketio.on('client_apply_edit')
        @Auth.socket_auth_required(emit_event=self.emit_event)
        def handle_apply_edit(user_id, data):
            document_id = session.get('document_id')
            edit_id = data.get("edit_id")
            accepted = data.get("accepted")

            if not accepted:
                return
            
            if not session['access_rights'] in ["owner", "edit"]:
                self.emit_event(WebSocketEvent('error', {'message' : 'No rights to edit document'}))
                return

            if document_id is None or edit_id is None or accepted is None:
                self.emit_event(WebSocketEvent("server_error", {"message": "Invalid edit request"}))
                return

            try:
                response, deltas = self._dialog_manager.apply_edit(user_id, document_id, edit_id, accepted)
                self.emit_event(WebSocketEvent("server_edit_applied", {
                    "edit_id": edit_id, 
                    "response": response,
                    "deltas_ops": deltas,
                }))
            except Exception as e:
                self.emit_event(WebSocketEvent("server_error", {"message": str(e)}))
        
    def emit_event(self, event: WebSocketEvent, **kwargs):
        if self._socketio is None:
            raise RuntimeError("SocketIO not initialized")
        
        try:
            self._socketio.emit(event.name, event.data, **kwargs)
            if Config.SHOW_EMIT_SUCCESS:
                print(f"🚀 Emitting event '{event.name}' with data: {event.data} and kwargs {kwargs}")
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