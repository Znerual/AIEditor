# src/document_manager.py
from models import db, Document, User
from typing import Optional, Union
from utils import delta_to_html, delta_to_string

class DocumentManager:
    @staticmethod
    def create_document(user_id: str, document_id: str) -> Document:
        
        document = Document.query.filter_by(id=document_id).first()
        if document:
            raise ValueError(f"Document with ID {document_id} already exists")
        
            
        user = User.query.filter_by(id=user_id).first()
                
        document = Document(id=document_id, user=user, content={"ops": [{"insert": "\n"}]})
        db.session.add(document)
        db.session.commit()
        return document
    
    @staticmethod
    def apply_delta(document_id: str, delta: dict) -> dict:
        document = Document.query.get(document_id)
        if not document:
            raise ValueError("Document not found")
            
        updated_content = document.apply_delta(delta)
        db.session.commit()
        return updated_content
    
    @staticmethod
    def get_document_content(document: Union[str, Document], as_string=False) -> dict:
        if isinstance(document, str):
            document_id = document
            document: Document = Document.query.get(document_id)
        
        if not document:
            raise ValueError("Document not found")
        
        return document.get_current_delta()

    @staticmethod
    def get_document_text(document: Union[str, Document]) -> str:
        content = DocumentManager.get_document_content(document)
        return delta_to_string(content)
        
    @staticmethod
    def get_document_html(document: Union[str, Document]) -> str:
        content = DocumentManager.get_document_content(document)
        return delta_to_html(content)
    
    
