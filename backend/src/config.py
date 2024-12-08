class Config:
    SECRET_KEY = 'secret!'
    DEBUG = True
    # Allow connections from React development server
    CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3000/", "*"] # http://localhost:3000
    SQLALCHEMY_DATABASE_URI = 'postgresql://username:password@localhost:5432/your_database'
    SQLALCHEMY_TRACK_MODIFICATIONS = False