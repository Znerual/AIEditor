# src/document_manager.py
from models import db, Document
from typing import Optional
import json

class DocumentManager:
    @staticmethod
    def get_or_create_document(user_id: str, document_id: Optional[int] = None) -> Document:
        if document_id:
            document = Document.query.filter_by(id=document_id, user_id=user_id).first()
            if document:
                return document
                
        document = Document(user_id=user_id, content={"ops": []})
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
    def get_document_content(document_id: int, user_id: str) -> dict:
        document = Document.query.filter_by(id=document_id, user_id=user_id).first()
        if not document:
            raise ValueError("Document not found")
        return document.content
