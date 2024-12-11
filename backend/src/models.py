# src/models.py
from flask_sqlalchemy import SQLAlchemy
from pgvector.sqlalchemy import Vector
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
import json
from delta import Delta
db = SQLAlchemy()
    
def add_read_access(document_id, user_id):
    """Add read access for a user to a document"""

    # Check if the user already has read access
    access_entry = DocumentReadAccess.query.filter_by(document_id=document_id, user_id=user_id).first()
    if access_entry:
        return access_entry
    
    access = DocumentReadAccess(document_id=document_id, user_id=user_id)
    db.session.add(access)
    db.session.commit()
    return access
    
def add_edit_access(document_id, user_id):
    """Add edit access for a user to a document"""

    # Check if the user already has edit access
    access_entry = DocumentEditAccess.query.filter_by(document_id=document_id, user_id=user_id).first()
    if access_entry:
        return access_entry
    
    access = DocumentEditAccess(document_id=document_id, user_id=user_id)
    db.session.add(access)
    db.session.commit()
    return access

def remove_read_access(document_id, user_id):
    """Remove read access for a user from a document"""
    access_entry = DocumentReadAccess.query.filter_by(document_id=document_id, user_id=user_id).first()
    if not access_entry:
        raise ValueError(f"No read access entry found for user {user_id} on document {document_id}")

    db.session.delete(access_entry)
    db.session.commit()

def remove_edit_access(document_id, user_id):
    """Remove edit access for a user from a document"""
    access_entry = DocumentEditAccess.query.filter_by(document_id=document_id, user_id=user_id).first()
    if not access_entry:
        raise ValueError(f"No edit access entry found for user {user_id} on document {document_id}")

    db.session.delete(access_entry)
    db.session.commit()

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
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.JSON, nullable=False, default={})
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    user = db.relationship('User', backref=db.backref('documents', lazy=True))
    read_access_entries = db.relationship('DocumentReadAccess', back_populates='document', lazy='dynamic')
    edit_access_entries = db.relationship('DocumentEditAccess', back_populates='document', lazy='dynamic')

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
        
        # Compose the deltas
        new_content = current_content.compose(delta)
        
        # Store the ops array in the content field
        self.content = {'ops': new_content.ops}
        
        self.updated_at = datetime.now(timezone.utc)
        return self.content['ops']
    
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
    
class FileEmbedding(db.Model):
    __tablename__ = "file_embeddings"

    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=True)  # Relation to Document
    filepath = db.Column(db.String, unique=True, index=True)
    content_hash = db.Column(db.String(256), unique=True)
    sequence_ids = db.Column(db.ARRAY(db.Integer))

    # Relationship to SequenceEmbedding
    sequences = db.relationship("SequenceEmbedding", back_populates="file", cascade="all, delete-orphan")


class SequenceEmbedding(db.Model):
    __tablename__ = "sequence_embeddings"

    id = db.Column(db.Integer, primary_key=True, index=True, unique=True)
    file_id = db.Column(db.Integer, db.ForeignKey("file_embeddings.id"))  # Relation to FileEmbedding
    sequence_hash = db.Column(db.String(256), unique=True)
    sequence_text = db.Column(db.Text)
    embedding = db.Column(Vector(768))  # Store individual embeddings

    # Relationship to FileEmbedding
    file = db.relationship("FileEmbedding", back_populates="sequences")
