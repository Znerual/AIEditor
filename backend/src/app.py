# src/app.py

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_migrate import Migrate
from models import db
from config import Config
from socket_manager import SocketManager
from fileProcessor import FileProcessor
from routes import setup_routes

import logging
import os

# Configure logging
# Create a logger
logger = logging.getLogger('eddy_logger')
logger.setLevel(logging.DEBUG)  # Set the minimum logging level

# Create a file handler to write logs to a file
log_file = os.path.join(os.path.dirname(__file__), 'eddy.log')
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)  # Set the minimum logging level for the file handler

# Create a console handler to output logs to the console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)  # Set the minimum logging level for the console handler

# Create a formatter and set it for both handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add both handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.WARNING)

def create_app():
  
    logger.info("Initializing FlaskApp...")
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize database
    db.init_app(app)

    # Initialize database migrations
    migrate = Migrate(app, db)
    
    

    # Initialize CORS
    CORS(app, resources={
        r"/*": {
            "origins": Config.CORS_ORIGINS,
            "supports_credentials": True,
            "allow_headers": ["Content-Type", "Authorization"],
            "methods": ["GET", "POST", "OPTIONS"]
        }
    })

    # Create database tables
    with app.app_context():
        db.create_all()

    # Init the temporary directory
    if not os.path.exists(Config.TMP_PATH):
        os.makedirs(Config.TMP_PATH)
    
    # Initialize the file processor
    file_processor = FileProcessor(Config.TMP_PATH)


    # setup routes
    setup_routes(app, file_processor)
    
    return app

app = create_app()
socketio = SocketIO(
    app=app,
    cors_allowed_origins=Config.CORS_ORIGINS,
    async_mode='threading',
    logger=False,
    engineio_logger=False,
    ping_timeout=60000,
    ping_interval=25000,
    manage_session=True,
    always_connect=True,
    
)

gemini_api_key = os.getenv("GEMINI_API_KEY") # read from environment variables
if not gemini_api_key:
    logger.error("GEMINI_API_KEY environment variable not set")
    # exit(1)

socket_manager = SocketManager(socketio, gemini_api_key=gemini_api_key, debug=Config.DEBUG)

if __name__ == '__main__':
    socket_manager.socketio.run(
        app, 
        debug=Config.DEBUG,
        host='0.0.0.0',
        port=5000,
        allow_unsafe_werkzeug=True,
        log_output=False, # hide heartbeat messages
        use_reloader=False,
        )
    #app.run()