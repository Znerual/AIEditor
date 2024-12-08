# src/auth.py
from functools import wraps
from flask import request, jsonify
from flask_socketio import disconnect
import jwt
from datetime import datetime, timedelta
from models import User

class Auth:
    SECRET_KEY = 'your-secret-key'  # Move to environment variables in production
    
    @staticmethod
    def generate_token(user_id: str) -> str:
        payload = {
            'user_id': user_id,
            'exp': datetime.now(datetime.timezone.utc) + timedelta(days=1)
        }
        return jwt.encode(payload, Auth.SECRET_KEY, algorithm='HS256')
    
    @staticmethod
    def decode_token(token: str) -> dict:
        try:
            return jwt.decode(token, Auth.SECRET_KEY, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            raise ValueError('Token has expired')
        except jwt.InvalidTokenError:
            raise ValueError('Invalid token')
    
    @staticmethod
    def socket_auth_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            try:
                auth_header = request.args.get('token')
                if not auth_header:
                    disconnect()
                    return False
                
                payload = Auth.decode_token(auth_header)
                return f(payload['user_id'], *args, **kwargs)
            except Exception as e:
                disconnect()
                return False
        return decorated