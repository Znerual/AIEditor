# src/document_manager.py
from models import db, Document, User
from typing import Optional, Union
from delta import Delta
import json
from utils import delta_to_string, string_to_delta

class DocumentManager:
    @staticmethod
    def create_document(user_id: str, document_id: Optional[int] = None) -> Document:
        if document_id:
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
    def get_document_content(document: Union[str, Document], as_string=False) -> Union[dict, str]:
        if isinstance(document, str):
            document_id = document
            document = Document.query.get(document_id)
        
        if not document:
            raise ValueError("Document not found")
        
        if as_string:
            # Convert Delta to string
            return delta_to_string(document.get_current_delta()) # type: ignore
        else:
            return document.get_current_delta() # type: ignore
