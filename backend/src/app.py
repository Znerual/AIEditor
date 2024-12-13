# src/app.py
from datetime import datetime
import hashlib
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO
from config import Config
from socket_manager import SocketManager
from cli import CLI
import requests
import threading
import logging
import textract
import queue
import config
import os
import tempfile
from models import db, User, Document, DocumentReadAccess, FileContent
from sqlalchemy import text
from auth import Auth
from werkzeug.utils import secure_filename

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('websocket_app')
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.WARNING)
class FlaskApp:
    def __init__(self):
        self.app = Flask(__name__)
        self.app.config.from_object(Config)

        # Initialize database
        db.init_app(self.app)
        
        # Create database tables
        with self.app.app_context():
            db.create_all()

         # Initialize CORS
        CORS(self.app, resources={
            r"/*": {
                "origins": Config.CORS_ORIGINS,
                "supports_credentials": True,
                "allow_headers": ["Content-Type", "Authorization"],
                "methods": ["GET", "POST", "OPTIONS"]
            }
        })

        # Init the temporary directory
        if not os.path.exists(Config.TMP_PATH):
            os.makedirs(Config.TMP_PATH)

        self.message_queue = queue.Queue() # Create the message queue
        self.socket_manager = SocketManager()
        socketio = SocketIO(
            app=self.app,
            cors_allowed_origins=Config.CORS_ORIGINS,
            async_mode='threading',
            logger=False,
            engineio_logger=False,
            ping_timeout=60000,
            ping_interval=25000,
            manage_session=True,
            always_connect=True,
            #path='socket.io'
        )

        gemini_api_key = "1234" # read from environment variables

        self.socket_manager.init_socket_manager(socketio, gemini_api_key, debug=Config.DEBUG)

        # setup routes
        self.setup_routes()

    def setup_routes(self):
        @self.app.route('/api/login', methods=['POST'])
        def login():
            data = request.get_json()
            email = data.get('email')
            password = data.get('password')
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                print("User logged in: ", user.email, " isAdmin: ", user.is_admin)
                token = Auth.generate_token(str(user.id), user.is_admin)
                return jsonify({
                    'token': token,
                    'user': {'id': user.id, 'email': user.email, 'isAdmin': user.is_admin}
                })
            
            return jsonify({'error': 'Invalid credentials'}), 401

        @self.app.route('/api/register', methods=['POST'])
        def register():
            data = request.get_json()
            email = data.get('email')
            password = data.get('password')
            is_admin = data.get('isAdmin', False)

            print(f"Using trying to register with {data}")

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
                return jsonify({'message': 'User registered successfully'}), 201
            except Exception as e:
                db.session.rollback()  # Rollback in case of error
                print(f"Error during registration: {e}") # Log the error for debugging
                return jsonify({'message': 'Registration failed'}), 500
            
        
        @self.app.route('/api/authenticate_token', methods=['GET'])
        @Auth.rest_auth_required
        def authenticate_token(user_id):
            existing_user = User.query.filter_by(id=user_id).first()
            if not existing_user:
                return jsonify({'message': 'User not found'}), 404
            
            return jsonify({    
                'user': {'id': existing_user.id, 'email': existing_user.email, 'isAdmin': existing_user.is_admin}
            })
        
        @self.app.route('/api/user/read_documents', methods=['GET'])
        @Auth.rest_auth_required
        def get_user_documents(user_id):
            if not user_id:
                return jsonify({'message': 'User not found'}), 404
            
            documents = Document.query.filter_by(user_id=user_id).all()

            # find all documents to which the user has read access
            read_access_entries = DocumentReadAccess.query.filter_by(user_id=user_id).all()
            
            all_readable_documents = [*documents]
            for read_access_entry in read_access_entries:
                all_readable_documents.append(read_access_entry.document)
            
            return jsonify([{'id': document.id, 'title': document.title, 'user_id': document.user_id, 'created_at': document.created_at, 'content': document.content} for document in all_readable_documents])

        @self.app.route('/api/fetch-website', methods=['GET'])
        def fetch_website():
            url = request.args.get('url')
            if not url:
                return jsonify({'error': 'Missing URL parameter'}), 400

            print("Fetching website", url)
            try:
                response = requests.get(url)
                response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

                # You might want to adjust the headers depending on what you're sending back
                return response.content, response.status_code, {'Content-Type': response.headers['Content-Type']}

            except requests.exceptions.RequestException as e:
                print(f"Error fetching website: {e}")
                return jsonify({'error': 'Failed to fetch website', 'message': str(e)}), 500

        @self.app.route('/api/extract_text', methods=['POST'])
        @Auth.rest_auth_required
        def extract_text_route(user_id):
            if not user_id:
                return jsonify({'message': 'User not found'}), 404

            if 'files' not in request.files:
                return jsonify({'message': 'No files provided'}), 400

            files = request.files.getlist('files')
            if not files:
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
                                print(f"Could not parse last_modified for {filename}")

                        content = file.read()
                        filename = secure_filename(file.filename)
                        
                        # Generate content hash
                        content_hash = hashlib.sha256(content).hexdigest()
                        
                        # Check if file already exists
                        existing_file = FileContent.query.filter_by(content_hash=content_hash).first()
                        if existing_file:
                            results.append({
                                'filename': filename,
                                'file_id': existing_file.id,
                                'success': True,
                                'text_extracted': existing_file.text_content,
                                'message': 'File already exists',
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
                            temp_file_path = os.path.join(Config.TMP_PATH, filename)
                            with open(temp_file_path, 'wb') as temp_file:
                                temp_file.write(content)
                            
                            # Process the file with textact (implement your processing logic here)
                            extracted_text = textract.process(temp_file_path).decode()
                            os.remove(temp_file_path)
                            text_content_hash = hashlib.sha256(extracted_text.encode()).hexdigest()
                            
                            file_content.text_content = extracted_text
                            file_content.text_content_hash = text_content_hash
                        except Exception as text_error:
                            # If text extraction fails, continue without text content
                            print(f"Text extraction failed: {str(text_error)}")
                        
                        db.session.add(file_content)
                        db.session.commit()
                        
                        results.append({
                            'filename': filename,
                            'file_id': file_content.id,
                            'success': True,
                            'text_extracted': file_content.text_content if file_content.text_content else False,
                            'message': 'File processed',
                        })
                        
                    except Exception as e:
                        results.append({
                            'filename': file.filename,
                            'error': str(e),
                            'success': False
                        })
                else:
                    results.append({
                        'filename': 'unknown',
                        'error': 'Invalid file',
                        'success': False
                    })
            
            return jsonify({
                'success': True,
                'results': results
            })

        @self.app.route('/api/user/content', methods=['GET'])
        @Auth.rest_auth_required
        def get_user_content(user_id):
            if not user_id:
                return jsonify({'message': 'User not found'}), 404

            # Query the database for all FileContent entries associated with the user
            content_items = FileContent.query.filter_by(user_id=user_id).all()

            # Serialize the data to JSON
            content_data = [{
                'id': item.id,
                'filepath': item.filepath,
                'creation_date': item.creation_date.isoformat(),
                'last_modified_date': item.last_modified
            } for item in content_items]

            return jsonify(content_data)

        @self.app.route('/api/content/<int:content_id>', methods=['GET'])
        @Auth.rest_auth_required
        def get_content_file(user_id, content_id):
            # Fetch the FileContent entry by ID and ensure it belongs to the current user
            content_entry = FileContent.query.filter_by(id=content_id, user_id=user_id).first()
            
            if not content_entry:
                return jsonify({'message': 'Content not found or access denied'}), 404
            
            content_data = {
                'id': content_entry.id,
                'filepath': content_entry.filepath,
                'creation_date': content_entry.creation_date.isoformat(),
                'text_content': content_entry.text_content,
                'size' : content_entry.size,
                'type' : content_entry.file_type,
                'lastModified' : content_entry.last_modified
            }

            # Serve the file from the temporary directory
            return jsonify(content_data)

        # def setup_embeddings_routes(app):
        # @self.app.route('/api/embeddings', methods=['POST'])
        # def create_embedding_route():
        #     data = request.get_json()
        #     request_data = FileEmbeddingRequest(filepath=data['filepath'], content=data['content'])
        #     store_file_embedding(request_data.filepath, request_data.content)
        #     return jsonify({'message': 'Embedding stored successfully'}), 201

        # Admin routes
        @self.app.route('/api/admin', methods=['GET'])
        @Auth.rest_admin_auth_required
        def admin():
            return jsonify({'message': 'Admin access granted'})

        @self.app.route('/api/admin/users', methods=['GET'])
        @Auth.rest_admin_auth_required
        def get_users():
            # Implementation to get users
            users = User.query.all()
            return jsonify([{'id': user.id, 'email': user.email, 'is_admin': user.is_admin, 'last_login_at': user.last_login_at} for user in users])

        @self.app.route('/api/admin/documents', methods=['GET'])
        @Auth.rest_admin_auth_required
        def get_documents():
            documents = Document.query.all()
            document_list = []
            for doc in documents:
                edit_access_users = [{'id': entry.id, 'user_id': entry.user_id, 'granted_at': entry.granted_at, 'user': {'id': entry.user.id, 'email': entry.user.email}} for entry in doc.edit_access_entries]
                read_access_users = [{'id': entry.id, 'user_id': entry.user_id, 'granted_at': entry.granted_at, 'user': {'id': entry.user.id, 'email': entry.user.email}} for entry in doc.read_access_entries]

                # Calculate size using pg_column_size
                size_query = text("SELECT pg_column_size(content) FROM documents WHERE id = :doc_id")
                size_result = db.session.execute(size_query, {'doc_id': doc.id}).fetchone()
                size_in_bytes = size_result[0] if size_result else 0
                size_in_kb = round(size_in_bytes / 1024.0, 2)

                document_list.append({
                    'id': doc.id,
                    'title': doc.title,
                    'user_id': doc.user_id,
                    'created_at': doc.created_at,
                    'size_kb': size_in_kb,
                    'edit_access_entries': edit_access_users,
                    'read_access_entries': read_access_users
                })

            return jsonify(document_list)
           
        # DELETE a user
        @self.app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
        @Auth.rest_admin_auth_required
        def delete_user(user_id):
            user = User.query.get_or_404(user_id)
            documents_from_user = Document.query.filter_by(user_id=user_id).all()
            for document in documents_from_user:
                db.session.delete(document)
            db.session.delete(user)
            db.session.commit()
            return jsonify({'message': 'User deleted'}), 200

        # Make a user an admin
        @self.app.route('/api/admin/users/<int:user_id>/make-admin', methods=['PATCH'])
        @Auth.rest_admin_auth_required
        def make_user_admin(user_id):
            user = User.query.get_or_404(user_id)
            user.is_admin = True
            db.session.commit()
            return jsonify({'message': 'User is now an admin'}), 200
        
        # Remove admin rights
        @self.app.route('/api/admin/users/<int:user_id>/remove-admin', methods=['PATCH'])
        @Auth.rest_admin_auth_required
        def remove_user_admin(user_id):
            user = User.query.get_or_404(user_id)
            user.is_admin = False
            db.session.commit()
            return jsonify({'message': 'User is no longer an admin'}), 200

        # DELETE a document
        @self.app.route('/api/admin/documents/<string:document_id>', methods=['DELETE'])
        @Auth.rest_admin_auth_required
        def delete_document(document_id):
            document = Document.query.get_or_404(document_id)
            db.session.delete(document)
            db.session.commit()
            return jsonify({'message': 'Document deleted'}), 200
        
        # GET a document
        @self.app.route('/api/admin/documents/<string:document_id>', methods=['GET'])
        @Auth.rest_admin_auth_required
        def get_document(document_id):
            document = Document.query.get_or_404(document_id)
            return jsonify({'id': document.id, 'title': document.title, 'user_id': document.user_id, 'created_at': document.created_at, 'content': document.content})

        @self.app.route('/health')
        def health_check():
            return jsonify({"status": "healthy"})
            
        @self.app.route('/api/test')
        def test_endpoint():
            return jsonify({"message": "API is working"})
        
        @self.app.after_request
        def after_request(response):
            response.headers.add('Access-Control-Allow-Credentials', 'true')
            response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
            response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
            return response

    def run_cli(self):
        cli = CLI(self.message_queue)
        cli.start_cli()

    def process_queue(self):
        while True:
            try:
                self.socket_manager.socketio.sleep(1)  
                message = self.message_queue.get()  # Non-blocking with timeout
                print("Processing message from queue:", message)
                # Simulate some work that might take time, but don't block
                self.socket_manager.socketio.emit(
                    message['event'], 
                    message['data'], 
                    namespace=message.get('namespace')
                )
                self.message_queue.task_done()
            
            except Exception as e:
                print(f"Error processing message: {e}")

    def run(self):
        # Start CLI in a separate thread
        cli_thread = threading.Thread(target=self.run_cli)
        cli_thread.daemon = True
        cli_thread.start()

        message_queue_thread = self.socket_manager.socketio.start_background_task(self.process_queue)

        # Run the Flask application
        self.socket_manager.socketio.run(
            self.app, 
            debug=Config.DEBUG,
            host='0.0.0.0',
            port=5000,
            allow_unsafe_werkzeug=True,
            log_output=False, # hide heartbeat messages
            use_reloader=False,
            ) 

if __name__ == '__main__':
    app = FlaskApp()
    app.run()