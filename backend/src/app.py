from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from socket_manager import SocketManager
from cli import CLI
import threading

class FlaskApp:
    def __init__(self):
        self.app = Flask(__name__)
        self.app.config.from_object(Config)

         # Initialize CORS
        CORS(self.app, resources={
            r"/*": {
                "origins": Config.CORS_ORIGINS,
                "supports_credentials": True
            }
        })

        self.socket_manager = SocketManager()
        self.socketio = self.socket_manager.init_socketio(self.app)

        # Allow CORS for Socket.IO
        self.socketio.init_app(self.app, cors_allowed_origins=Config.CORS_ORIGINS)

        # setup routes
        self.setup_routes()

    def setup_routes(self):
        @self.app.route('/health')
        def health_check():
            return jsonify({"status": "healthy"})
            
        @self.app.route('/api/test')
        def test_endpoint():
            return jsonify({"message": "API is working"})

    def run_cli(self):
        cli = CLI(self.socket_manager)
        cli.start_cli()

    def run(self):
        # Start CLI in a separate thread
        cli_thread = threading.Thread(target=self.run_cli)
        cli_thread.daemon = True
        cli_thread.start()

        # Run the Flask application
        self.socketio.run(self.app, debug=Config.DEBUG)

if __name__ == '__main__':
    app = FlaskApp()
    app.run()