# src/backend/models.py
from pyexpat.errors import messages
from typing import List, Optional
from flask_sqlalchemy import SQLAlchemy
from pgvector.sqlalchemy import Vector
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image
import io
import base64
import json
from delta import Delta
from dialog_types import ActionPlan, Decision, DialogTurn, DialogMessage, FunctionCall
db = SQLAlchemy()


class DocumentReadAccess(db.Model):
    __tablename__ = 'document_read_access'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    document_id = db.Column(db.String(36), db.ForeignKey('documents.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    granted_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    # Relationships
    document = db.relationship('Document', back_populates='read_access_entries')
    user = db.relationship('User', back_populates='read_access_documents')

class DocumentEditAccess(db.Model):
    __tablename__ = 'document_edit_access'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    document_id = db.Column(db.String(36), db.ForeignKey('documents.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    granted_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    # Relationships
    document = db.relationship('Document', back_populates='edit_access_entries')
    user = db.relationship('User', back_populates='edit_access_documents')

class Document(db.Model):
    __tablename__ = 'documents'
    
    id = db.Column(db.String(36), primary_key=True, unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=True)
    title_manually_set = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.JSON, nullable=False, default={})
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    embedding_valid = db.Column(db.Boolean, default=False)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('documents', lazy=True))
    read_access_entries = db.relationship('DocumentReadAccess', back_populates='document', lazy='dynamic')
    edit_access_entries = db.relationship('DocumentEditAccess', back_populates='document', lazy='dynamic')
    file_embedding = db.relationship('FileEmbedding', backref=db.backref('document', lazy=True))
    thumbnail = db.relationship("Thumbnail", 
                              uselist=False,  # one-to-one
                              back_populates="document", 
                              cascade="all, delete-orphan")  # delete thumbn

    def apply_delta(self, delta):
        """Apply a Quill delta to the document content"""
        if not self.content:
            self.content = {'ops': []}  # Initialize as dictionary with ops array
       
        current_content = Delta(self.content['ops'] if isinstance(self.content, dict) else self.content)
        
        if isinstance(delta, str):
            delta = Delta(json.loads(delta))
        elif isinstance(delta, list):
            delta = Delta(delta)
        elif not isinstance(delta, Delta):
            raise ValueError(f"Unknown delta type {type(delta)}")
        
        composed_delta = Delta()  # Start with an empty Delta
        for op in current_content.ops:
            composed_delta = Delta([op]).compose(composed_delta)
          
        # Compose the deltas
        new_content = composed_delta.compose(delta)
        
        # Store the ops array in the content field
        self.content = {'ops': new_content.ops}
        self.embedding_valid = False
        
        self.updated_at = datetime.now(timezone.utc)
        return new_content.ops
    
    def get_current_delta(self):
        if not self.content:
            return Delta()
        
        return Delta(self.content['ops'] if isinstance(self.content, dict) else self.content)
    
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    last_login_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    is_admin = db.Column(db.Boolean, default=False)

    # Relationships
    read_access_documents = db.relationship('DocumentReadAccess', back_populates='user', lazy='dynamic')
    edit_access_documents = db.relationship('DocumentEditAccess', back_populates='user', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
class FileContent(db.Model):
    __tablename__ = 'file_contents'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filepath = db.Column(db.String, unique=True, index=True)
    text_content = db.Column(db.Text, nullable=True)
    text_content_hash = db.Column(db.String(256), unique=True)
    content = db.Column(db.LargeBinary, nullable=False)
    content_hash = db.Column(db.String(256), unique=True)
    size = db.Column(db.Integer, nullable=False)
    file_type = db.Column(db.String(256), nullable=True)
    last_modified = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=True)
    creation_date = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    # Relationships
    file_embeddings = db.relationship('FileEmbedding', back_populates='content', lazy='dynamic')
    
class FileEmbedding(db.Model):
    __tablename__ = "file_embeddings"

    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    document_id = db.Column(db.String(36), db.ForeignKey("documents.id"), nullable=True)  # Relation to Document
    content_id = db.Column(db.Integer, db.ForeignKey("file_contents.id"), nullable=True)
    creation_date = db.Column(db.DateTime, default=datetime.now(timezone.utc))


    # Relationship to SequenceEmbedding
    sequences = db.relationship("SequenceEmbedding", back_populates="file", cascade="all, delete-orphan")
    content = db.relationship("FileContent", back_populates="file_embeddings", lazy='joined')


class SequenceEmbedding(db.Model):
    __tablename__ = "sequence_embeddings"

    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    file_id = db.Column(db.Integer, db.ForeignKey("file_embeddings.id"))  # Relation to FileEmbedding
    sequence_hash = db.Column(db.String(256), unique=True)
    sequence_text = db.Column(db.Text)
    embedding = db.Column(Vector(768))  # Store individual embeddings

    # Relationship to FileEmbedding
    file = db.relationship("FileEmbedding", back_populates="sequences")

class Thumbnail(db.Model):
    __tablename__ = 'thumbnails'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    document_id = db.Column(db.String(36), db.ForeignKey('documents.id'), nullable=False) 
    image_data = db.Column(db.LargeBinary, nullable=False)  # Store the image data
    creation_date = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    # Relationship (one-to-one)
    document = db.relationship("Document", back_populates="thumbnail")

    def __init__(self, image_data, document):
        if not document:
            raise ValueError("Thumbnail must be associated with a document")
        self.document = document
        
        if isinstance(image_data, str):
          image_data = base64.b64decode(image_data)

        try:
            img = Image.open(io.BytesIO(image_data))
        except Exception as e:
            raise ValueError(f"Invalid image data: {e}")

        img.thumbnail((128, 128))

        # Convert to RGB if necessary
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Save the resized image as WEBP
        with io.BytesIO() as output:
            img.save(output, format="WEBP")
            self.image_data = output.getvalue()

class DialogHistory(db.Model):
    __tablename__ = 'dialog_histories'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    document_id = db.Column(db.String(36), db.ForeignKey('documents.id'), nullable=True)
    turns = db.Column(db.JSON, nullable=False)

    def __init__(self, user_id: int, document_id: str, turns: Optional[List[DialogTurn]] = None):
        self.user_id = user_id
        self.document_id = document_id
        self.turns = [turn.to_dict() for turn in turns] if turns else []


    def get_turns(self) -> List[DialogTurn]:
        """Retrieves the dialog turns as a list of DialogTurn objects."""
        return [DialogTurn.from_dict(turn) for turn in (self.turns or [])]
    
    def get_messages(self) -> List[DialogMessage]:
        """Retrieves the dialog messages as a list of DialogMessage objects."""
        messages = []

        print(self.turns)

        for turn in self.turns:
            if "action_plan" in turn:
                if "find_actions" in turn["action_plan"] and "edit_actions" in turn["action_plan"] and "format_actions" in turn["action_plan"]:
                    action_plan = ActionPlan(find_actions=turn["action_plan"]["find_actions"], edit_actions=turn["action_plan"]["edit_actions"], format_actions=turn["action_plan"]["format_actions"])
                else:
                    action_plan = ActionPlan(find_actions=[], edit_actions=[], format_actions=[])

            function_calls = "-\n".join([str(FunctionCall.from_dict(call)) for call in (turn["function_calls"] or [])])
            messages.append(DialogMessage(sender="user", text=turn["user_message"]))
            messages.append(DialogMessage(sender="system", text=str(action_plan)))
            messages.append(DialogMessage(sender="system", text=function_calls))
            messages.append(DialogMessage(sender="system", text=turn["decision"] if "decision" in turn else ""))

        return messages
    
    def get_unresolved_edits(self) -> List[FunctionCall]:
        """Retrieves the unresolved edits for the current document."""
        edits = []
        for turn in self.turns:
            dialog_turn = DialogTurn.from_dict(turn)
            if dialog_turn.decision == Decision.REJECT:
                continue

            for function_call in dialog_turn.function_calls:
                if function_call.status == "rejected" or function_call.status == "accepted":
                    continue
                
                edits.append(function_call)
            
        return edits