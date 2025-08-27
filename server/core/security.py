from fastapi import Header, HTTPException, Depends
from typing import Optional, Dict
import jwt
import os
import secrets
from .config import load_settings

_settings = load_settings()

# API Key for internal authentication (hidden from public)
# This should be stored in environment variables in production
INTERNAL_API_KEY = os.getenv("ONMEMOS_INTERNAL_API_KEY", "onmemos-internal-key-2024-secure")

def get_auth_token(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    return authorization.split(" ", 1)[1]

def get_claims(token: str = Depends(get_auth_token)) -> Dict:
    try:
        return jwt.decode(token, _settings.server.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid token")

def require_namespace(claims: Dict = Depends(get_claims)) -> Dict:
    # Minimal RBAC: allow any namespace; extend to claims['namespaces'] if needed.
    return claims

def verify_api_key(x_api_key: Optional[str] = Header(None)) -> bool:
    """Verify the internal API key for protected endpoints"""
    if not x_api_key:
        raise HTTPException(
            status_code=401, 
            detail={
                "error": "Authentication required",
                "message": "API key is required for this endpoint",
                "suggestion": "Include X-API-Key header with valid API key"
            }
        )
    
    if x_api_key != INTERNAL_API_KEY:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Invalid API key",
                "message": "The provided API key is invalid",
                "suggestion": "Check your API key and try again"
            }
        )
    
    return True

def require_api_key(_: bool = Depends(verify_api_key)) -> bool:
    """Dependency for endpoints that require API key authentication"""
    return True
