from models import db, User, Document, DocumentReadAccess, DocumentEditAccess, Thumbnail, FileContent, FileEmbedding, SequenceEmbedding
from sqlalchemy import text
from auth import Auth
from werkzeug.utils import secure_filename
from bs4 import BeautifulSoup
from sqlalchemy.exc import IntegrityError
from embedding_manager import EmbeddingManager
from document_manager import DocumentManager
from flask import jsonify, request, send_file
from datetime import datetime
from delta import Delta
from config import Config

import logging
import hashlib
import subprocess
import uuid
import requests
import io
import os
logger = logging.getLogger('eddy_logger')

def setup_routes(app, file_processor):
    @app.route('/api/login', methods=['POST'])
    def login():
        logger.info("Login attempt started.")
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            logger.info(f"User logged in: {user.email}, isAdmin: {user.is_admin}")
            token = Auth.generate_token(str(user.id), user.is_admin)
            logger.info("Login attempt successful.")
            return jsonify({
                'token': token,
                'user': {'id': user.id, 'email': user.email, 'isAdmin': user.is_admin}
            })
        
        logger.warning(f"Failed login attempt for email: {email}")
        return jsonify({'error': 'Invalid credentials'}), 401

    @app.route('/api/register', methods=['POST'])
    def register():
        logger.info("User registration started.")
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        is_admin = data.get('isAdmin', False)


        if not email or not password:
            return jsonify({'message': 'Email and password are required'}), 400
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({'message': 'Email address already exists'}), 409  # 409 Conflict
        
        try:
            new_user = User(email=email, is_admin=is_admin)
            new_user.set_password(password)  # Hash the password
            db.session.add(new_user)
            db.session.commit()

            token = Auth.generate_token(str(new_user.id), new_user.is_admin)
            logger.info(f"User registered successfully: {email}")
            return jsonify({
                'message': 'User registered successfully',
                'token': token,
                'user': {'id': new_user.id, 'email': new_user.email, 'isAdmin': new_user.is_admin}
            }), 201
        except Exception as e:
            db.session.rollback()  # Rollback in case of error
            logger.error(f"Error during registration: {e}") # Log the error for debugging
            return jsonify({'message': 'Registration failed'}), 500
        

    @app.route('/api/authenticate_token', methods=['GET'])
    @Auth.rest_auth_required
    def authenticate_token(user_id):
        logger.info(f"Token authentication requested for user ID: {user_id}")
        existing_user = User.query.filter_by(id=user_id).first()
        if not existing_user:
            logger.warning(f"Token authentication failed: User not found for ID: {user_id}")
            return jsonify({'message': 'User not found'}), 404
        
        logger.info(f"Token authentication successful for user: {existing_user.email}")
        return jsonify({    
            'user': {'id': existing_user.id, 'email': existing_user.email, 'isAdmin': existing_user.is_admin}
        })

    @app.route('/api/documents/<string:document_id>/collaborators', methods=['POST'])
    @Auth.rest_auth_required
    def add_collaborator(user_id, document_id):
        """
        Adds a collaborator to a document with specified access rights.
        """
        logger.info(f"Adding collaborator to document: {document_id} by user: {user_id}")

        data = request.get_json()
        collaborator_email = data.get('email')
        rights = data.get('rights', 'read')  # Default to 'read' if not specified

        # Validate input
        if not collaborator_email:
            logger.warning("Failed to add collaborator: Collaborator email is required.")
            return jsonify({'message': 'Collaborator email is required'}), 400

        # Check if the document exists and if the current user is the owner
        document = Document.query.filter_by(id=document_id).first()
        if not document:
            logger.warning(f"Document not found for ID: {document_id}")
            return jsonify({'message': 'Document not found'}), 404
        
        if int(document.user_id) != int(user_id):
            logger.warning(f"Unauthorized attempt to add collaborator by user: {user_id} for document: {document_id}")
            return jsonify({'message': 'Only the document owner can add collaborators'}), 403

        # Check if the collaborator exists
        collaborator = User.query.filter_by(email=collaborator_email).first()
        if not collaborator:
            logger.warning(f"Collaborator not found for email: {collaborator_email}")
            return jsonify({'message': 'Collaborator not found'}), 404

        # Add collaborator with specified rights
        try:
            if rights == 'edit':
                # Check for existing edit access
                edit_access = DocumentEditAccess.query.filter_by(document_id=document_id, user_id=collaborator.id).first()
                if edit_access:
                    logger.warning(f"Collaborator {collaborator_email} already has edit access to document {document_id}")
                    return jsonify({'message': 'Collaborator already has edit access to this document'}), 409

                # Remove existing read access if it exists
                read_access = DocumentReadAccess.query.filter_by(document_id=document_id, user_id=collaborator.id).first()
                if read_access:
                    db.session.delete(read_access)

                # Add edit access
                db.session.add(DocumentEditAccess(document=document, user=collaborator))
            else:
                # Check for existing read access
                read_access = DocumentReadAccess.query.filter_by(document_id=document_id, user_id=collaborator.id).first()
                if read_access:
                    logger.warning(f"Collaborator {collaborator_email} already has read access to document {document_id}")
                    return jsonify({'message': 'Collaborator already has read access to this document'}), 409

                # Remove existing edit access if it exists
                edit_access = DocumentEditAccess.query.filter_by(document_id=document_id, user_id=collaborator.id).first()
                if edit_access:
                    db.session.delete(edit_access)

                # Add read access
                db.session.add(DocumentReadAccess(document=document, user=collaborator))
            
            db.session.commit()
            logger.info(f"Collaborator {collaborator_email} added with {rights} access to document {document_id}")
            return jsonify({'message': f'Collaborator {collaborator_email} added with {rights} access to document {document_id}'}), 200
        except Exception as e:
            db.session.rollback()
            print(f"Error adding collaborator: {e}")
            return jsonify({'message': 'Failed to add collaborator'}), 500

    @app.route('/api/thumbnails', methods=['POST'])
    @Auth.rest_auth_required
    def create_thumbnail(user_id):
        logger.info(f"Creating thumbnail for user: {user_id}")
        data = request.get_json()
        document_id = data.get('document_id')
        image_data = data.get('image_data')  # Assuming base64 encoded image
        #file_format = data.get('file_format', 'PNG')  # Default to PNG

        if not image_data:
            logger.warning("Thumbnail creation failed: Missing image data.")
            return jsonify({'message': 'Missing image data'}), 400
        
        document = Document.query.get_or_404(document_id)

        try:

            # Create a new thumbnail
            new_thumbnail = Thumbnail(
                image_data=image_data,
                document=document
            )

            db.session.add(new_thumbnail)
            db.session.commit()

            logger.info(f"Thumbnail created successfully for document: {document_id}")
            return jsonify({
                'message': 'Thumbnail created successfully',
                'thumbnail_id': new_thumbnail.id
            }), 201

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error during thumbnail creation: {e}")
            return jsonify({'message': 'Thumbnail creation failed'}), 500

    @app.route('/api/thumbnails/<int:thumbnail_id>', methods=['GET'])
    @Auth.rest_auth_required
    def get_thumbnail(user_id, thumbnail_id):
        logger.info(f"Retrieving thumbnail: {thumbnail_id} for user: {user_id}")
        thumbnail = Thumbnail.query.get_or_404(thumbnail_id)

        # Check if the user has access to the document associated with the thumbnail
        if thumbnail.document:
            if int(thumbnail.document.user_id) != int(user_id):
                # Check if the user has read access to the document
                read_access = DocumentReadAccess.query.filter_by(document_id=thumbnail.document.id, user_id=user_id).first()
                if not read_access:
                    edit_access = DocumentEditAccess.query.filter_by(document_id=thumbnail.document.id, user_id=user_id).first()
                    if not edit_access:
                        logger.warning(f"Access denied for user: {user_id} to thumbnail: {thumbnail_id}")
                        return jsonify({'message': 'Access denied'}), 403
                    

        # Return the thumbnail data
        logger.info(f"Thumbnail retrieved successfully: {thumbnail_id}")
        return send_file(
            io.BytesIO(thumbnail.image_data),
            mimetype=f'image/webp',
            as_attachment=False
        )

    @app.route('/api/thumbnails/<int:thumbnail_id>', methods=['DELETE'])
    @Auth.rest_auth_required
    def delete_thumbnail(user_id, thumbnail_id):
        logger.info(f"Deleting thumbnail: {thumbnail_id} for user: {user_id}")
        thumbnail = Thumbnail.query.get_or_404(thumbnail_id)

        # Check if the user has access to the associated document or is an admin
        if thumbnail.document:
            if thumbnail.document.user_id != user_id:
                auth_header = request.headers.get('Authorization')
                token = auth_header.split(" ")[1]
                payload, error = Auth.decode_token(token)
                if error or not payload.get('is_admin', False): # type: ignore
                    logger.warning(f"Access denied for user: {user_id} to delete thumbnail: {thumbnail_id}")
                    return jsonify({'message': 'Access denied'}), 403

        db.session.delete(thumbnail)
        db.session.commit()
        logger.info(f"Thumbnail deleted successfully: {thumbnail_id}")
        return jsonify({'message': 'Thumbnail deleted successfully'}), 200

    @app.route('/api/user/create_new_document', methods=['POST'])
    @Auth.rest_auth_required
    def handle_client_create_new_document(user_id):
        logger.info(f"Creating new document for user: {user_id}")
        try:
            # Generate a unique document ID and ensure it doesn't already exist
            while True:
                document_id = str(uuid.uuid4())
                if not Document.query.filter_by(id=document_id).first():
                    break

            # Create a new document for the user
            new_document = DocumentManager.create_document(user_id, document_id)

            logger.info(f"New document created with ID: {document_id} for user: {user_id}")
            return jsonify({
                'documentId': new_document.id
            })
        
        except IntegrityError as e:
            db.session.rollback()
            logger.error(f"Database integrity error while creating document: {e}")
            return jsonify({'message': 'Database integrity error'}), 500

        except Exception as e:
            logger.error(f"Authentication or room joining error: {e}")
            return jsonify({'message': str(e)}), 500


    @app.route('/api/user/search_documents', methods=['GET'])
    @Auth.rest_auth_required
    def search_documents(user_id):
        search_term = request.args.get('search_term')
        logger.info(f"Searching documents for user: {user_id} with term: '{search_term}'")
        if not search_term:
            logger.warning("Document search failed: Missing search term.")
            return jsonify({'message': 'Missing search term'}), 400
        
        if not user_id:
            logger.warning("Document search failed: User not found.")
            return jsonify({'message': 'User not found'}), 404

        user = User.query.get_or_404(user_id)
        

        try:
            print("Searching for documents with term", search_term)
            # Fetch documents owned by the user
            owned_documents = Document.query.filter_by(user_id=user_id).all()

            # Fetch documents shared with the user for read access
            read_access_documents = [entry.document for entry in user.read_access_documents]

            # Fetch documents shared with the user for edit access
            edit_access_documents = [entry.document for entry in user.edit_access_documents]

            # Combine all documents
            all_accessible_documents = owned_documents + read_access_documents + edit_access_documents

            # Remove duplicates (if a document is shared with both read and edit access)
            unique_documents = list({doc.id: doc for doc in all_accessible_documents}.values())

            logger.debug(f"Getting embeddings for user: {user_id}")
            user_embeddings = [EmbeddingManager.get_embeddings(doc) for doc in unique_documents]
            logger.debug(f"Found {len(user_embeddings)} embeddings for user")

            # Use the embedding manager to find similar documents
            similar_file_embeddings = EmbeddingManager.find_similar_files(
                search_term,
                embedding_ids=user_embeddings,
                limit=10
            )
            logger.debug(f"Found {len(similar_file_embeddings)} similar documents")
            # Extract the document IDs from the similar file embeddings
            similar_document_ids = {embedding.document_id for embedding in similar_file_embeddings if embedding.document_id}

            # Fetch the actual documents using the IDs
            similar_documents = Document.query.filter(Document.id.in_(similar_document_ids)).all()

            documents_data = []
            for document in similar_documents:
                if document.thumbnail:
                    documents_data.append({
                        'id': document.id, 
                        'thumbnail_id': document.thumbnail.id,
                        'title': document.title, 
                        'title_manually_set': document.title_manually_set, 
                        'user_id': document.user_id, 
                        'created_at': document.created_at, 
                        'updated_at': document.updated_at, 
                        'content': document.content}
                        )
                else:
                    documents_data.append({
                        'id': document.id, 
                        'title': document.title, 
                        'title_manually_set': document.title_manually_set, 
                        'user_id': document.user_id, 
                        'created_at': document.created_at, 
                        'updated_at': document.updated_at, 
                        'content': document.content}
                        )
                    
            logger.info(f"Document search successful for user: {user_id}")
            return jsonify(documents_data)

        except Exception as e:
            logger.error(f"Error during document search: {e}")
            return jsonify({'message': 'Error during document search', 'error': str(e)}), 500

    @app.route('/api/user/documents', methods=['GET'])
    @Auth.rest_auth_required
    def get_user_documents(user_id):
        logger.info(f"Retrieving documents for user: {user_id}")
        if not user_id:
            logger.warning("Document retrieval failed: User not found.")
            return jsonify({'message': 'User not found'}), 404

        user = User.query.get_or_404(user_id)
        

        # Fetch documents owned by the user
        owned_documents = Document.query.filter_by(user_id=user_id).all()

        # Fetch documents shared with the user for read access
        read_access_documents = [entry.document for entry in user.read_access_documents]

        # Fetch documents shared with the user for edit access
        edit_access_documents = [entry.document for entry in user.edit_access_documents]

        # Combine all documents
        all_accessible_documents = owned_documents + read_access_documents + edit_access_documents

        # Remove duplicates (if a document is shared with both read and edit access)
        unique_documents = list({doc.id: doc for doc in all_accessible_documents}.values())

        documents_data = []
        for document in unique_documents:
            # Determine the access level for this user
            access_level = 'owner'
            if int(document.user_id) != int(user_id):
                if any(int(entry.user_id) == int(user_id) for entry in document.edit_access_entries):
                    access_level = 'edit'
                elif any(int(entry.user_id) == int(user_id) for entry in document.read_access_entries):
                    access_level = 'read'
            
            
            document_info = {
                'id': document.id,
                'title': document.title,
                'title_manually_set': document.title_manually_set,
                'user_id': document.user_id,
                'created_at': document.created_at,
                'updated_at': document.updated_at,
                'content': document.content,
                'access_level': access_level,  # Include the access level
            }

            # Include thumbnail_id only if it exists
            if document.thumbnail:
                document_info['thumbnail_id'] = document.thumbnail.id

            documents_data.append(document_info)

        logger.info(f"Documents retrieved successfully for user: {user_id}")
        return jsonify(documents_data)
                
    @app.route('/api/documents/<string:document_id>/collaborators', methods=['GET'])
    @Auth.rest_auth_required
    def get_collaborators(user_id, document_id):
        logger.info(f"Get collaborators for document: {document_id} for user: {user_id}")
        if not user_id:
            logger.warning("Collaborator retrieval failed: User not found.")
            return jsonify({'message': 'User not found'}), 404

        # owner sees all other collaborators, others with rights only owner
        user = User.query.get_or_404(user_id)
                    
        owns_document = Document.query.filter_by(id=document_id, user_id=user_id).first()
        if owns_document:
            read_access_entries = DocumentReadAccess.query.filter_by(document_id=document_id).all()
            edit_access_entries = DocumentEditAccess.query.filter_by(document_id=document_id).all()
            
            logger.info(f"Collaborators retrieved successfully for document: {document_id} for user: {user_id}")
            return jsonify({
                'documentId': document_id,
                'status' : 'owner',
                'read_access_entries': [{ 'user' : { 'id' : entry.user.id, 'email' : entry.user.email } } for entry in read_access_entries],
                'edit_access_entries': [{ 'user' : { 'id' : entry.user.id, 'email' : entry.user.email } } for entry in edit_access_entries],
            })
        
        document = Document.query.filter_by(id=document_id).first()
        if not document:
            logger.warning("Collaborator retrieval failed: Document not found.")
            return jsonify({'message': 'Document not found'}), 404
        
        logger.info(f"Owner retrieved successfully for document: {document_id} for user: {user_id}")
        return jsonify({
            'documentId': document_id,
            'status' : 'viewer',
            'owner' : { 'id' : document.user.id, 'email' : document.user.email },
        })


    @app.route('/api/user/document/<document_id>', methods=['DELETE'])
    @Auth.rest_auth_required
    def delete_document_user(user_id, document_id):
        logger.info(f"Deleting document: {document_id} for user: {user_id}")
        if not user_id:
            logger.warning("Document deletion failed: User not found.")
            return jsonify({'message': 'User not found'}), 404
        
        document = Document.query.filter_by(user_id=user_id, id=document_id).first()
        if not document:
            logger.warning(f"Document deletion failed: Document not found for ID: {document_id}")
            return jsonify({'message': 'Document not found'}), 404
        
        db.session.delete(document)
        db.session.commit()
        logger.info(f"Document deleted successfully: {document_id}")
        return jsonify({'message': 'Document deleted'}), 200
        

    @app.route('/api/fetch-website', methods=['GET'])
    @Auth.rest_auth_required
    def fetch_website():
        url = request.args.get('url')
        logger.info(f"Fetching website: {url}")

        if not url:
            logger.warning("Website fetch failed: Missing URL parameter.")
            return jsonify({'error': 'Missing URL parameter'}), 400

        
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

            # You might want to adjust the headers depending on what you're sending back
            logger.info(f"Website fetched successfully: {url}")
            return response.content, response.status_code, {'Content-Type': response.headers['Content-Type']}

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching website: {e}")
            return jsonify({'error': 'Failed to fetch website', 'message': str(e)}), 500
        
    @app.route('/api/extract_text_website', methods=['POST'])
    @Auth.rest_auth_required
    def extract_text_website(user_id):
        data = request.get_json()
        url = data.get('url')
        logger.info(f"Extracting text from website: {url} for user: {user_id}")

        if not url:
            logger.warning("Text extraction failed: Missing URL parameter.")
            return jsonify({'error': 'Missing URL parameter'}), 400

        try:
            response = requests.get(url)
            response.raise_for_status()
            
            content = response.content
            content_hash = hashlib.sha256(content).hexdigest()
            
            # Check if the website already exists in the database
            existing_website = FileContent.query.filter_by(content_hash=content_hash).first()
            if existing_website:
                logger.info(f"Website already exists: {url}")
                return jsonify({
                    'filename': url,
                    'file_id': existing_website.id,
                    'raw': { 
                        'File' : content.decode(),
                        'type' : existing_website.file_type,
                        'size' : existing_website.size, 
                        'lastModified' : existing_website.last_modified
                        },
                    'success': True,
                    'text_extracted': existing_website.text_content,
                    'message': 'Website already exists',
                    'content_type': 'file_content',
                })

            # Parse the website content
            soup = BeautifulSoup(response.content, 'html.parser')
            for script in soup(['script', 'style']):
                script.decompose()
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)

            text_content_hash = hashlib.sha256(text.encode()).hexdigest()

            last_modified = datetime.now()
            # Create a new FileContent object for the website
            file_content = FileContent(
                user_id=user_id,
                filepath=url,
                content=content,
                content_hash=content_hash,
                size=len(content),
                file_type=response.headers.get('Content-Type', '').split(';')[0],
                text_content=text,
                text_content_hash=text_content_hash,
                last_modified=last_modified
            )

            db.session.add(file_content)
            db.session.commit()
            logger.info(f"Website text extracted and saved successfully: {url}")
            return jsonify({
                'filename': url,
                'file_id': file_content.id,
                'raw': {
                    'File' : response.content.decode(),
                    'type' : response.headers.get('Content-Type', '').split(';')[0],
                    'size' : len(content),
                    'lastModified' : last_modified
                },
                'success': True,
                'text_extracted': text,
                'message': 'Website fetched and parsed successfully',
                'content_type': 'file_content',
            })

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch website: {e}")
            return jsonify({'error': 'Failed to fetch website', 'message': str(e)}), 500
        except Exception as e:
            logger.error(f"An error occurred during website text extraction: {e}")
            return jsonify({'error': 'An error occurred', 'message': str(e)}), 500

    @app.route('/api/extract_text', methods=['POST'])
    @Auth.rest_auth_required
    def extract_text_route(user_id):
        logger.info(f"Text extraction initiated for user: {user_id}")

        if not user_id:
            logger.warning("Text extraction failed: User not found.")
            return jsonify({'message': 'User not found'}), 404

        if 'files' not in request.files:
            logger.warning("Text extraction failed: No files provided.")
            return jsonify({'message': 'No files provided'}), 400

        files = request.files.getlist('files')
        if not files:
            logger.warning("Text extraction failed: No files selected.")
            return jsonify({'message': 'No files selected'}), 400

        results = []
        for file in files:
            if file:
                try:
                    # Read file content
                    file_size = file.content_length
                    file_type = file.content_type
                    last_modified_field_name = f"{file.filename}.lastModified"
                    file_last_modified_str = request.form.get(last_modified_field_name)
                    file_last_modified = None
                    if file_last_modified_str:
                        try:
                            file_last_modified = datetime.fromtimestamp(int(file_last_modified_str) / 1000)
                        except (ValueError, TypeError):
                            logger.warning(f"Could not parse last_modified for {filename}")

                    content = file.read()
                    filename = secure_filename(file.filename)
                    
                    # Generate content hash
                    content_hash = hashlib.sha256(content).hexdigest()
                    
                    # Check if file already exists
                    existing_file = FileContent.query.filter_by(content_hash=content_hash).first()
                    if existing_file:
                        logger.debug(f"File already exists: {filename}")
                        results.append({
                            'filename': filename,
                            'file_id': existing_file.id,
                            'success': True,
                            'text_extracted': existing_file.text_content,
                            'message': 'File already exists',
                            'content_type': 'file_content',
                        })
                        continue
                    
                    # Create new file content entry
                    file_content = FileContent(
                        user_id=user_id,
                        filepath=filename,
                        content=content,
                        content_hash=content_hash,
                        size=file_size,
                        file_type=file_type,
                        last_modified=file_last_modified
                    )
                    
                    # Try to extract text content if possible
                    try:
                        file_content_data = file_processor.process_file_content(filename, content)
                        
                        file_content.text_content = file_content_data['text_content']
                        file_content.text_content_hash = file_content_data['text_content_hash']
                    except Exception as text_error:
                        # If text extraction fails, continue without text content
                        logger.error(f"Text extraction failed: {str(text_error)}")
                    
                    db.session.add(file_content)
                    db.session.commit()
                    
                    logger.info(f"File processed: {filename}")
                    results.append({
                        'filename': filename,
                        'file_id': file_content.id,
                        'success': True,
                        'text_extracted': file_content.text_content if file_content.text_content else False,
                        'message': 'File processed',
                        'content_type': 'file_content',
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing file {file.filename}: {e}")
                    results.append({
                        'filename': file.filename,
                        'error': str(e),
                        'success': False
                    })
            else:
                logger.warning("Invalid file encountered.")
                results.append({
                    'filename': 'unknown',
                    'error': 'Invalid file',
                    'success': False
                })
        
        logger.info("Text extraction completed.")
        return jsonify({
            'success': True,
            'results': results
        })

    @app.route('/api/user/content', methods=['GET'])
    @Auth.rest_auth_required
    def get_user_content(user_id):
        logger.info(f"Retrieving user content for user: {user_id}")

        if not user_id:
            logger.warning("User content retrieval failed: User not found.")
            return jsonify({'message': 'User not found'}), 404

        # Query the database for all FileContent entries associated with the user
        content_items = FileContent.query.filter_by(user_id=user_id).all()

        # Serialize the data to JSON
        content_data = [{
            'file_id': item.id,
            'filename': item.filepath,
            'filepath': item.filepath,
            'creation_date': item.creation_date.isoformat(),
            'last_modified_date': item.last_modified,
        } for item in content_items]

        logger.info(f"User content retrieved successfully for user: {user_id}")
        return jsonify(content_data)

    @app.route('/api/content/<int:content_id>', methods=['GET'])
    @Auth.rest_auth_required
    def get_content_file(user_id, content_id):
        logger.info(f"Retrieving content file: {content_id} for user: {user_id}")

        # Fetch the FileContent entry by ID and ensure it belongs to the current user
        content_entry = FileContent.query.filter_by(id=content_id, user_id=user_id).first()
        
        if not content_entry:
            logger.warning(f"Content file not found or access denied for ID: {content_id}, user: {user_id}")
            return jsonify({'message': 'Content not found or access denied'}), 404
        
        content_data = {
            'file_id': content_entry.id,
            'filepath': content_entry.filepath,
            'filename': content_entry.filepath,
            'creation_date': content_entry.creation_date.isoformat(),
            'text_content': content_entry.text_content,
            'size' : content_entry.size,
            'type' : content_entry.file_type,
            'lastModified' : content_entry.last_modified
        }

        # Serve the file from the temporary directory
        logger.info(f"Content file retrieved successfully: {content_id}")
        return jsonify(content_data)

    @app.route('/api/upload_structure', methods=['POST'])
    @Auth.rest_auth_required
    def handle_structure_upload(user_id):
        logger.info(f"Structure upload initiated by user: {user_id}")
        
        if 'file' not in request.files:
            logger.warning("Structure upload failed: No file part.")
            return jsonify({'message': 'No file part'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            logger.warning("Structure upload failed: No selected file.")
            return jsonify({'message': 'No selected file'}), 400
        
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(Config.TMP_PATH, filename)
            file.save(filepath)
            
            try:
                # Convert the document to Markdown using Pandoc
                result = subprocess.run(
                    ['pandoc', filepath, '-t', 'markdown', '--toc', '--normalize'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                markdown_content = result.stdout
                
                # Optionally, remove the temporary file
                os.remove(filepath)
                
                logger.info(f"Document structure converted successfully for user: {user_id}")
                return jsonify({
                    'message': 'Document converted successfully',
                    'markdown': markdown_content
                }), 200
            except subprocess.CalledProcessError as e:
                logger.error(f"Error during document conversion: {e}")
                return jsonify({'message': 'Failed to convert document', 'error': str(e)}), 500
        
        logger.warning("Structure upload failed: File upload failed.")
        return jsonify({'message': 'Failed to upload file'}), 500
        
    # Admin routes
    @app.route('/api/admin', methods=['GET'])
    @Auth.rest_admin_auth_required
    def admin():
        logger.info("Admin access granted.")
        return jsonify({'message': 'Admin access granted'})

    @app.route('/api/admin/users', methods=['GET'])
    @Auth.rest_admin_auth_required
    def get_users():
        logger.info("Retrieving all users for admin.")
        users = User.query.all()
        logger.info(f"Retrieved {len(users)} users.")
        return jsonify([{'id': user.id, 'email': user.email, 'is_admin': user.is_admin, 'last_login_at': user.last_login_at} for user in users])

    @app.route('/api/admin/documents', methods=['GET'])
    @Auth.rest_admin_auth_required
    def get_documents():
        logger.info("Retrieving all documents for admin.")
        documents = Document.query.all()
        document_list = []
        for doc in documents:
            # Fetch collaborators (users with read or edit access)
            collaborators = []
            read_access_users = User.query.join(DocumentReadAccess, DocumentReadAccess.user_id == User.id).filter(DocumentReadAccess.document_id == doc.id).all()
            edit_access_users = User.query.join(DocumentEditAccess, DocumentEditAccess.user_id == User.id).filter(DocumentEditAccess.document_id == doc.id).all()
            for user in read_access_users:
                collaborators.append({'id': user.id, 'email': user.email, 'access': 'read'})
            for user in edit_access_users:
                collaborators.append({'id': user.id, 'email': user.email, 'access': 'edit'})

            # Calculate size using pg_column_size
            size_query = text("SELECT pg_column_size(content) FROM documents WHERE id = :doc_id")
            size_result = db.session.execute(size_query, {'doc_id': doc.id}).fetchone()
            size_in_bytes = size_result[0] if size_result else 0
            size_in_kb = round(size_in_bytes / 1024.0, 2)

            doc_info = {
                'id': doc.id,
                'title': doc.title,
                'title_manually_set': doc.title_manually_set,
                'user_id': doc.user_id,
                'created_at': doc.created_at,
                'last_modified': doc.updated_at,
                'size_kb': size_in_kb,
                'collaborators': collaborators  # Add collaborators to the document info
            }

            # Include thumbnail_id only if it exists
            if doc.thumbnail:
                doc_info['thumbnail_id'] = doc.thumbnail.id

            document_list.append(doc_info)

        logger.info(f"Retrieved {len(document_list)} documents.")
        return jsonify(document_list)

    @app.route('/api/admin/file_contents', methods=['GET'])
    @Auth.rest_admin_auth_required
    def get_file_contents_list():
        logger.info("Retrieving all file contents for admin.")
        file_contents = FileContent.query.all()
        file_content_list = []
        for file_content in file_contents:
            file_content_list.append({
                'id': file_content.id,
                'filepath': file_content.filepath,
                'size': file_content.size,
                'file_type': file_content.file_type,
                'last_modified': file_content.last_modified,
                'creation_date': file_content.creation_date,
                'text_content_hash': file_content.text_content_hash,
                'content_hash': file_content.content_hash,
                'user_id': file_content.user_id,
            })

        logger.info(f"Retrieved {len(file_content_list)} file contents.")
        return jsonify(file_content_list)

    @app.route('/api/admin/file_embeddings', methods=['GET'])
    @Auth.rest_admin_auth_required
    def get_file_embeddings():
        logger.info("Retrieving all file embeddings for admin.")
        file_embeddings = FileEmbedding.query.all()
        file_embedding_list = []
        for file_embedding in file_embeddings:
            file_embedding_list.append({
                'id': file_embedding.id,
                'document_id': file_embedding.document_id,
                'content_id': file_embedding.content_id,
                'creation_date': file_embedding.creation_date,
            })
        logger.info(f"Retrieved {len(file_embedding_list)} file embeddings.")
        return jsonify(file_embedding_list)
        
    # DELETE a user
    @app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
    @Auth.rest_admin_auth_required
    def delete_user(user_id):
        logger.info(f"Deleting user: {user_id}")
        user = User.query.get_or_404(user_id)
        documents_from_user = Document.query.filter_by(user_id=user_id).all()
        for document in documents_from_user:
            logger.info(f"Deleting document: {document.id} owned by user: {user_id}")
            db.session.delete(document)
        db.session.delete(user)
        db.session.commit()
        logger.info(f"User deleted successfully: {user_id}")
        return jsonify({'message': 'User deleted'}), 200

    # Make a user an admin
    @app.route('/api/admin/users/<int:user_id>/make-admin', methods=['PATCH'])
    @Auth.rest_admin_auth_required
    def make_user_admin(user_id):
        logger.info(f"Making user admin: {user_id}")
        user = User.query.get_or_404(user_id)
        user.is_admin = True
        db.session.commit()
        logger.info(f"User is now an admin: {user_id}")
        return jsonify({'message': 'User is now an admin'}), 200

    # Remove admin rights
    @app.route('/api/admin/users/<int:user_id>/remove-admin', methods=['PATCH'])
    @Auth.rest_admin_auth_required
    def remove_user_admin(user_id):
        logger.info(f"Removing admin rights from user: {user_id}")
        user = User.query.get_or_404(user_id)
        user.is_admin = False
        db.session.commit()
        logger.info(f"Admin rights removed from user: {user_id}")
        return jsonify({'message': 'User is no longer an admin'}), 200

    # DELETE a document
    @app.route('/api/admin/documents/<string:document_id>', methods=['DELETE'])
    @Auth.rest_admin_auth_required
    def delete_document(document_id):
        logger.info(f"Deleting document: {document_id}")
        document = Document.query.get_or_404(document_id)
        db.session.delete(document)
        db.session.commit()
        logger.info(f"Document deleted successfully: {document_id}")
        return jsonify({'message': 'Document deleted'}), 200

    # GET a document
    @app.route('/api/admin/documents/<string:document_id>', methods=['GET'])
    @Auth.rest_admin_auth_required
    def get_document(document_id):
        logger.info(f"Retrieving document: {document_id}")
        document = Document.query.get_or_404(document_id)
        if document.thumbnail:
            logger.info(f"Document retrieved: {document_id} with thumbnail")
            return jsonify({
                'id': document.id, 
                'thumbnail_id': document.thumbnail.id,
                'title': document.title, 
                'title_manually_set': document.title_manually_set,
                'user_id': document.user_id, 
                'created_at': document.created_at, 
                'updated_at': document.updated_at,
                'content': document.content})
        
        logger.info(f"Document retrieved: {document_id} without thumbnail")
        return jsonify({
            'id': document.id, 
            'title': document.title, 
            'title_manually_set': document.title_manually_set,
            'user_id': document.user_id, 
            'created_at': document.created_at, 
            'updated_at': document.updated_at,
            'content': document.content})

    # Get a file content entry
    @app.route('/api/admin/file_contents/<int:file_content_id>', methods=['GET'])
    @Auth.rest_admin_auth_required
    def get_file_content(file_content_id):
        logger.info(f"Retrieving file content: {file_content_id}")
        file_content = FileContent.query.get_or_404(file_content_id)
        
        logger.info(f"File content retrieved: {file_content_id}")
        return jsonify(
            {
            'id': file_content.id,
            'filepath': file_content.filepath,
            'size': file_content.size,
            'file_type': file_content.file_type,
            'last_modified': file_content.last_modified,
            'creation_date': file_content.creation_date,
            'text_content_hash': file_content.text_content_hash,
            'content_hash': file_content.content_hash,
            'text_content': file_content.text_content,
            #'content': base64.b64decode(file_content.content),
            'user_id': file_content.user_id,
            })

    # delete a file content entry
    @app.route('/api/admin/file_contents/<int:file_content_id>', methods=['DELETE'])
    @Auth.rest_admin_auth_required
    def delete_file_content(file_content_id):
        logger.info(f"Deleting file content: {file_content_id}")
        file_content = FileContent.query.get_or_404(file_content_id)
        db.session.delete(file_content)
        db.session.commit()
        logger.info(f"File content deleted successfully: {file_content_id}")
        return jsonify({'message': 'FileContent deleted'}), 200

    @app.route('/api/admin/file_embeddings/<int:file_embedding_id>', methods=['GET'])
    @Auth.rest_admin_auth_required
    def get_file_embedding(file_embedding_id):
        logger.info(f"Retrieving file embedding: {file_embedding_id}")
        file_embedding = FileEmbedding.query.get_or_404(file_embedding_id)
        sequence_embeddings = []
        for sequence_embedding in file_embedding.sequences:
            sequence_embeddings.append({
                'id': sequence_embedding.id,
                'sequence_hash': sequence_embedding.sequence_hash,
                'sequence_text': sequence_embedding.sequence_text,
                'embedding': sequence_embedding.embedding.tolist(),
            })
        
        logger.info(f"File embedding retrieved: {file_embedding_id}")
        return jsonify({
            'id': file_embedding.id,
            'document_id': file_embedding.document_id,
            'content_id': file_embedding.content_id,
            'creation_date': file_embedding.creation_date,
            'sequences': sequence_embeddings,
        })

    @app.route('/api/admin/file_embeddings/<int:file_embedding_id>', methods=['DELETE'])
    @Auth.rest_admin_auth_required
    def delete_file_embedding(file_embedding_id):
        logger.info(f"Deleting file embedding: {file_embedding_id}")
        file_embedding = FileEmbedding.query.get_or_404(file_embedding_id)
        db.session.delete(file_embedding)
        db.session.commit()
        logger.info(f"File embedding deleted successfully: {file_embedding_id}")
        return jsonify({'message': 'File embedding deleted'}), 200

    @app.route('/api/admin/file_embeddings/<int:file_embedding_id>/sequences', methods=['GET'])
    @Auth.rest_admin_auth_required
    def get_file_embedding_sequences(file_embedding_id):
        logger.info(f"Retrieving sequences for file embedding: {file_embedding_id}")
        file_embedding = FileEmbedding.query.get_or_404(file_embedding_id)
        sequence_embeddings = []
        for sequence_embedding in file_embedding.sequences:
            sequence_embeddings.append({
                'id': sequence_embedding.id,
                'sequence_hash': sequence_embedding.sequence_hash,
                'sequence_text': sequence_embedding.sequence_text,
            })

        logger.info(f"Sequences retrieved for file embedding: {file_embedding_id}")
        return jsonify(sequence_embeddings)

    @app.route('/api/admin/file_embeddings/<int:file_embedding_id>/sequences/<int:sequence_embedding_id>', methods=['GET'])
    @Auth.rest_admin_auth_required
    def get_sequence_embedding(file_embedding_id, sequence_embedding_id):
        logger.info(f"Retrieving sequence embedding: {sequence_embedding_id} for file embedding: {file_embedding_id}")
        sequence_embedding = SequenceEmbedding.query.get_or_404(sequence_embedding_id)

        # Check if the sequence embedding belongs to the specified file embedding
        if sequence_embedding.file_id != file_embedding_id:
            logger.warning(f"Sequence embedding {sequence_embedding_id} does not belong to file embedding {file_embedding_id}")
            return jsonify({'message': 'Sequence embedding not found for the specified file embedding'}), 404
        
        logger.info(f"Sequence embedding retrieved: {sequence_embedding_id}")
        return jsonify({
            'id': sequence_embedding.id,
            'sequence_hash': sequence_embedding.sequence_hash,
            'sequence_text': sequence_embedding.sequence_text,
            'embedding': sequence_embedding.embedding
        })

    @app.route('/health')
    def health_check():
        logger.debug("Health check requested.")
        return jsonify({"status": "healthy"})
        
    @app.route('/api/test')
    def test_endpoint():
        logger.debug("Test endpoint requested.")
        return jsonify({"message": "API is working"})

    app.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response