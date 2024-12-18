class Config:
    SECRET_KEY = 'secret!'
    DEBUG = True
    SHOW_EMIT_SUCCESS = False
    # Allow connections from React development server
    CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3000/", "*"] # http://localhost:3000
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:1234@localhost:5432/eddy_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TMP_PATH = '/tmp'
    TITLE_DOCUMENT_LENGTH_THRESHOLD = 128