# src/auth.py
from functools import wraps
from typing import Union, Tuple, Optional, Callable
from backend.src.events import WebSocketEvent
from flask import request, jsonify
from flask_socketio import disconnect
import jwt
from datetime import datetime, timedelta, timezone

class Auth:
    SECRET_KEY = 'your-secret-key'  # Move to environment variables in production
    
    @staticmethod
    def generate_token(user_id: str) -> str:
        payload = {
            'user_id': user_id,
            'exp': datetime.now(timezone.utc) + timedelta(days=1)
        }
        return jwt.encode(payload, Auth.SECRET_KEY, algorithm='HS256')
    
    @staticmethod
    def decode_token(token: str) -> Union[Tuple[dict, None], Tuple[None, str]]:
        try:
            payload = jwt.decode(token, Auth.SECRET_KEY, algorithms=['HS256'])
            return payload, None
        except jwt.ExpiredSignatureError:
            return None, 'Token has expired'
        except jwt.InvalidTokenError:
            return None, 'Invalid token'
    
    @staticmethod
    def socket_auth_required(emit_event: Callable):
        def decorator(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                
                
                auth_header = request.args.get('token')

                if not auth_header:
                    print("Authentication failed: Token missing")
                    emit_event(WebSocketEvent('server_authentication_failed', {
                        'message': 'Authentication token is missing'
                    }))
                    return False
                
                payload, error = Auth.decode_token(auth_header)

                if error:
                    print(f"Authentication failed: {error}")
                    emit_event(WebSocketEvent('server_authentication_failed', {
                        'message': error
                    }))
                    return False
                
                try:
                    return f(payload['user_id'], *args, **kwargs)
                except Exception as e:
                    print(f"Error in authenticated handler: {str(e)}")
                    emit_event(WebSocketEvent('server_authentication_failed', {
                        'message': f'Authentication error: {str(e)}'
                    }))
                    return False
                
            return decorated
        return decorator