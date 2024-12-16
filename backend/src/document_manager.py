# src/document_manager.py
from models import db, Document, User
from typing import Optional, Union
from delta import Delta
import json
from utils import delta_to_string, string_to_delta

class DocumentManager:
    @staticmethod
    def get_or_create_document(user_id: str, document_id: Optional[int] = None) -> Document:
        if document_id:
            document = Document.query.filter_by(id=document_id, user_id=user_id).first()
            if document:
                return document
            
        user = User.query.filter_by(user_id=user_id).first()
                
        document = Document(user=user, content={"ops": []})
        db.session.add(document)
        db.session.commit()
        return document
    
    @staticmethod
    def apply_delta(document_id: int, user_id: str, delta: dict) -> dict:
        document = Document.query.filter_by(id=document_id, user_id=user_id).first()
        if not document:
            raise ValueError("Document not found")
            
        updated_content = document.apply_delta(delta)
        db.session.commit()
        return updated_content
    
    @staticmethod
    def get_document_content(document: Union[str, Document], user_id: Optional[int] = None, as_string=False) -> dict:
        if isinstance(document, str):
            if not user_id:
                raise ValueError("user_id is required when passing a document_id as a string")
            document_id = document
            document = Document.query.filter_by(id=document_id, user_id=user_id).first()
        
        if not document:
            raise ValueError("Document not found")
        
        if as_string:
            # Convert Delta to string
            return delta_to_string(document.get_current_delta()) # You'll need to implement `to_plain_text()`
        else:
            return document.get_current_delta()
