# src/models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
import json
from delta import Delta
db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    last_login_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    

class Document(db.Model):
    __tablename__ = 'documents'
    
    id = db.Column(db.String(36), primary_key=True, unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.JSON, nullable=False, default={})
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    user = db.relationship('User', backref=db.backref('documents', lazy=True))

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
    