# src/models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import json

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(datetime.timezone.utc))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Document(db.Model):
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.JSON, nullable=False, default={})
    created_at = db.Column(db.DateTime, default=datetime.now(datetime.timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(datetime.timezone.utc), onupdate=datetime.now(datetime.timezone.utc))
    
    user = db.relationship('User', backref=db.backref('documents', lazy=True))

    def apply_delta(self, delta):
        """Apply a Quill delta to the document content"""
        if not self.content:
            self.content = {"ops": []}
        
        if isinstance(delta, str):
            delta = json.loads(delta)
            
        # If content is empty, just set it to the delta
        if not self.content["ops"]:
            self.content["ops"] = delta["ops"]
        else:
            # Merge the delta with existing content
            # This is a simplified version - you might want to use a proper delta composition library
            self.content["ops"].extend(delta["ops"])
        
        self.updated_at = datetime.now(datetime.timezone.utc)
        return self.content