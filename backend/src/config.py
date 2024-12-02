class Config:
    SECRET_KEY = 'secret!'
    DEBUG = True
    # Allow connections from React development server
    CORS_ORIGINS = ["http://localhost:3000"]