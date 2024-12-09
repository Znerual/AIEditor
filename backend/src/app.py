# src/app.py
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO
from config import Config
from socket_manager import SocketManager
from cli import CLI
import threading
import logging
import queue
from models import db, User
from auth import Auth

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
                token = Auth.generate_token(str(user.id))
                return jsonify({
                    'token': token,
                    'user': {'id': user.id, 'email': user.email}
                })
            
            return jsonify({'error': 'Invalid credentials'}), 401

        @self.app.route('/api/register', methods=['POST'])
        def register():
            data = request.get_json()
            email = data.get('email')
            password = data.get('password')

            print(f"Using trying to register with {data}")

            if not email or not password:
                return jsonify({'message': 'Email and password are required'}), 400
            
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                return jsonify({'message': 'Email address already exists'}), 409  # 409 Conflict
            
            try:
                new_user = User(email=email)
                new_user.set_password(password)  # Hash the password
                db.session.add(new_user)
                db.session.commit()
                return jsonify({'message': 'User registered successfully'}), 201
            except Exception as e:
                db.session.rollback()  # Rollback in case of error
                print(f"Error during registration: {e}") # Log the error for debugging
                return jsonify({'message': 'Registration failed'}), 500

           

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