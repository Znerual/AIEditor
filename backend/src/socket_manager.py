# src/socket_manager.py
from multiprocessing import Value
from os import access
from flask import session
from flask_socketio import SocketIO, join_room, leave_room
from typing import Optional
from events import WebSocketEvent
from document_manager import DocumentManager
from autocomplete_manager import AutocompleteManager
from dialog_manager import DialogManager
from structure_manager import StructureManager
from llm_manager import LLMManager
from auth import Auth
from functools import partial
from models import User, Document, DocumentEditAccess,DocumentReadAccess, DialogHistory
from concurrent.futures import ThreadPoolExecutor
from models import Document, db
import logging
from delta import Delta
import uuid
from utils import string_to_delta
import threading
from config import Config
from dialog_types import IntermediaryResult, IntermediaryStatus, FinalResult

logger = logging.getLogger('eddy_logger')

class SocketManager:
    _instance: Optional['SocketManager'] = None
    _socketio: Optional[SocketIO] = None
    _llm_manager: Optional[LLMManager] = None
    _autocomplete_manager: Optional[AutocompleteManager] = None
    _structure_manager: Optional[StructureManager] = None
    _executor: Optional[ThreadPoolExecutor] = None
    current_content_selection = []

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, socketio, debug=False, gemini_api_key=None, anthropic_api_key=None, ollama_base_url=None):
        self._init_socket_manager(socketio, gemini_api_key, anthropic_api_key=anthropic_api_key, ollama_base_url=ollama_base_url, debug=debug)
        
    
    def _init_socket_manager(self, socketio, gemini_api_key=None, anthropic_api_key=None, ollama_base_url=None, debug=False):
        self._socketio = socketio
        self._llm_manager = LLMManager(debug=debug, provider="google", ollama_base_url=ollama_base_url, gemini_api_key=gemini_api_key, anthropic_api_key=anthropic_api_key)
        self._autocomplete_manager = AutocompleteManager(llm_manager=self._llm_manager, debug=debug)
        self._dialog_manager = DialogManager(llm_manager=self._llm_manager, debug=debug)
        self._structure_manager = StructureManager(llm_manager=self._llm_manager, debug=debug)
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
                
                # get the access rights for the file
                access_rights = None
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

                # send the document
                content = DocumentManager.get_document_content(document)
                self.emit_event(WebSocketEvent('server_sent_document_content', {
                    'documentId': document_id,
                    'title': document.title,
                    'content': content.ops,
                    'access_rights': access_rights,
                }))

                # load the chat history and send it to the client
                history = DialogHistory.query.filter_by(document_id=document_id, user_id=user_id).first()
                self.emit_event(WebSocketEvent('server_sent_chat_history', {
                    'documentId': document_id,
                    'messages': [message.to_dict() for message in history.get_messages()],
                    'unresolved_edits' : [edit.to_dict() for edit in history.get_unresolved_edits()]
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
                
                #print("Text change data: " ,data)
                # User ID comes from the token, not the request
                updated_content = DocumentManager.apply_delta(document_id, delta)
                #print("Updated content: ", updated_content)
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
                
                #print("Document", document)
                content_str: str = DocumentManager.get_document_text(document) # type: ignore
                #print("Content str", content_str)
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

                structure_text = DocumentManager.get_document_text(document)
            
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
            document_id = session.get('document_id')

            #def stream_response(user_id, msg, document_id, current_content_selection, emit_event):
            for response_data in self._dialog_manager.get_response_stream(user_id, msg['text'], document_id, self.current_content_selection):
                
                # convert to serializable format
                if isinstance(response_data, IntermediaryResult):
                    if isinstance(response_data.message, IntermediaryStatus):
                        response_dict = {
                            "status" : response_data.message.status,
                            "action_plan" : str(response_data.message.action_plan),
                            "problems" : response_data.message.problems,
                            "mistakes" : response_data.message.mistakes,
                            "timings" : response_data.message.timings,
                            "positions" : response_data.message.positions
                        }
                        # Emit intermediary responses
                        self.emit_event(WebSocketEvent(
                            "server_chat_answer_intermediary", 
                            response_dict))
                        
                    elif isinstance(response_data.message, dict):
                        self.emit_event(WebSocketEvent(
                            "server_chat_answer_intermediary", 
                            response_data.message))
                    else:
                        raise ValueError(f"Unknown intermediary result type: {type(response_data.message)}")
                
                elif isinstance(response_data, FinalResult):
                    # Emit final response with suggested edits
                    
                    response_dict = {
                        "status" : response_data.status,
                        "response" : response_data.response,
                        "suggested_edits" : [action.to_dict() for action in response_data.suggested_edits],
                        "timing_info" : response_data.timing_info
                    }

                    if not session['access_rights'] in ["owner", "edit"]:
                        response_dict["suggested_edits"] = []
                  
                    logger.info(f"Final Response data: {response_dict}")

                    self.emit_event(WebSocketEvent(
                        "server_chat_answer_final", 
                        response_dict
                    ))
                else:
                    raise ValueError(f"Unknown response data type: {type(response_data)}")
                

        @self._socketio.on('client_apply_edit')
        @Auth.socket_auth_required(emit_event=self.emit_event)
        def handle_apply_edit(user_id, data):
            document_id = session.get('document_id')
            edit_id = data.get("edit_id")
            accepted = data.get("accepted")
            action_type = data.get("action_type")
            text = data.get("text")
            start = data.get("start")
            end = data.get("end")

            if not accepted:
                logger.info(f"User {user_id} rejected edit with id {edit_id}")
                delta = self._dialog_manager.apply_edit(user_id, document_id, edit_id, start, end, accepted)
                return
            
            if not session['access_rights'] in ["owner", "edit"]:
                logger.warning(f"User {user_id} tried to apply edit without access rights")
                self.emit_event(WebSocketEvent('error', {'message' : 'No rights to edit document'}))
                return

            if document_id is None or edit_id is None or accepted is None:
                logger.warning(f"User {user_id} tried to apply edit with invalid data")
                self.emit_event(WebSocketEvent("server_error", {"message": "Invalid edit request"}))
                return

            try:
                delta = self._dialog_manager.apply_edit(user_id, document_id, edit_id, start, end, accepted)
                self.emit_event(WebSocketEvent("server_edit_applied", {
                    "edit_id": edit_id,
                    "text" : text,
                    "action_type" : action_type,
                    "start" : start,
                    "end" : end,
                    "delta_ops": delta.ops,
                }))
            except Exception as e:
                self.emit_event(WebSocketEvent("server_error", {"message": str(e)}))
        

        @self._socketio.on("client_delete_chat_history")
        @Auth.socket_auth_required(emit_event=self.emit_event)
        def handle_client_delete_chat_history(user_id, data):
            document_id = data.get('document_id')
            if not document_id:
                self.emit_event(WebSocketEvent("server_error", {"message": "Missing document_id in handle_client_delete_chat_history"}))
                return
            
            history_entry = DialogHistory.query.filter_by(document_id=document_id, user_id=user_id).first()
            if not history_entry:
                self.emit_event(WebSocketEvent("server_error", {"message": "No history found for user"}))
                return
            
            history_entry.turns = []
            db.session.commit()
            self.emit_event(WebSocketEvent("server_deleted_chat_history", {"document_id": document_id}))


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