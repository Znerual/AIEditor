# src/app.py

from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
from config import Config
from socket_manager import SocketManager
from cli import CLI
import threading
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('websocket_app')
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.WARNING)
class FlaskApp:
    def __init__(self):
        self.app = Flask(__name__)
        self.app.config.from_object(Config)
        self.app.config['SECRET_KEY'] = 'your-secret-key'  # Add a secret key

         # Initialize CORS
        CORS(self.app, resources={
            r"/*": {
                "origins": Config.CORS_ORIGINS,
                "supports_credentials": True,
                "allow_headers": ["Content-Type", "Authorization"],
                "methods": ["GET", "POST", "OPTIONS"]
            }
        })

        self.socket_manager = SocketManager()
        socketio = SocketIO(
            app=self.app,
            cors_allowed_origins=["http://localhost:3000"],
            #async_mode='threading',
            logger=False,
            engineio_logger=False,
            ping_timeout=60000,
            ping_interval=25000,
            manage_session=True,
            always_connect=True,
            path='socket.io'
        )

        self.socket_manager.init_socket_manager(socketio)

        # # Allow CORS for Socket.IO
        # self.socketio.init_app(self.app, cors_allowed_origins=Config.CORS_ORIGINS)

        # setup routes
        self.setup_routes()

    def setup_routes(self):
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
        cli = CLI(self.socket_manager)
        cli.start_cli()

    def run(self):
        # Start CLI in a separate thread
        cli_thread = threading.Thread(target=self.run_cli)
        cli_thread.daemon = True
        cli_thread.start()

        # Run the Flask application
        self.socket_manager.socketio.run(
            self.app, 
            debug=Config.DEBUG,
            host='0.0.0.0',
            port=5000,
            allow_unsafe_werkzeug=True,
            log_output=False, # hide heartbeat messages
            use_reloader=False) 

if __name__ == '__main__':
    app = FlaskApp()
    app.run()