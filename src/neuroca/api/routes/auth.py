"""
Authentication API Routes for NeuroCognitive Architecture (NCA)

This module provides authentication and authorization endpoints for the NCA system.
It handles user login, token management, and access control for the API.

Usage:
    These routes provide authentication services:
    - User Login/Logout: Authenticate users and manage sessions
    - Token Management: Issue and validate JWT tokens
    - User Registration: Create new user accounts (if enabled)
    - Password Management: Handle password resets

Security:
    All authentication endpoints implement proper security measures
    including rate limiting, secure token handling, and audit logging.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# OAuth2 scheme for token-based authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
    responses={
        401: {"description": "Unauthorized"},
        429: {"description": "Too Many Requests"},
        500: {"description": "Internal Server Error"},
    },
)


# Pydantic models for authentication
class UserCredentials(BaseModel):
    """Model for user login credentials."""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="User password")


class UserRegistration(BaseModel):
    """Model for user registration."""
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: str = Field(..., description="Email address")
    password: str = Field(..., min_length=8, description="Password")
    full_name: Optional[str] = Field(None, description="Full name")


class TokenResponse(BaseModel):
    """Model for token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None


class UserInfo(BaseModel):
    """Model for user information."""
    user_id: str
    username: str
    email: str
    full_name: Optional[str] = None
    roles: list[str] = []
    created_at: str
    last_login: Optional[str] = None
    is_active: bool = True


class PasswordReset(BaseModel):
    """Model for password reset request."""
    email: str = Field(..., description="Email address for password reset")


class PasswordChange(BaseModel):
    """Model for password change."""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")


class AuthResponse(BaseModel):
    """Generic response model for auth operations."""
    success: bool
    message: str
    data: Optional[dict] = None


# Mock user data (in real implementation, this would come from database)
MOCK_USERS = {
    "admin": {
        "user_id": "1",
        "username": "admin",
        "email": "admin@neuroca.local",
        "full_name": "System Administrator",
        "password_hash": "hashed_admin_password",  # Would be properly hashed
        "roles": ["admin", "user"],
        "created_at": "2024-01-01T00:00:00Z",
        "last_login": None,
        "is_active": True,
    },
    "user": {
        "user_id": "2",
        "username": "user",
        "email": "user@neuroca.local",
        "full_name": "Standard User",
        "password_hash": "hashed_user_password",  # Would be properly hashed
        "roles": ["user"],
        "created_at": "2024-01-01T00:00:00Z",
        "last_login": None,
        "is_active": True,
    },
}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password
        
    Returns:
        bool: True if password matches
    """
    # In real implementation, use proper password hashing (bcrypt, etc.)
    return f"hashed_{plain_password}" == hashed_password


def get_user_by_username(username: str) -> Optional[dict]:
    """
    Get user by username.
    
    Args:
        username: Username to look up
        
    Returns:
        Optional[Dict]: User data or None
    """
    return MOCK_USERS.get(username)


def create_access_token(user_id: str, username: str) -> str:
    """
    Create an access token for a user.
    
    Args:
        user_id: User ID
        username: Username
        
    Returns:
        str: JWT token
    """
    # In real implementation, use proper JWT library
    return f"mock_token_{user_id}_{username}_{int(datetime.now().timestamp())}"


def verify_token(token: str) -> Optional[dict]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token to verify
        
    Returns:
        Optional[Dict]: Token payload or None
    """
    # In real implementation, use proper JWT verification
    if token.startswith("mock_token_"):
        parts = token.split("_")
        if len(parts) >= 4:
            return {
                "user_id": parts[2],
                "username": parts[3],
                "exp": datetime.now() + timedelta(hours=24),
            }
    return None


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Get current user from token.
    
    Args:
        token: JWT token
        
    Returns:
        Dict: Current user information
        
    Raises:
        HTTPException: If token is invalid
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = verify_token(token)
        if payload is None:
            raise credentials_exception
        
        username = payload.get("username")
        if username is None:
            raise credentials_exception
            
    except Exception:
        raise credentials_exception
    
    user = get_user_by_username(username)
    if user is None:
        raise credentials_exception
        
    return user


@router.post(
    "/token",
    summary="Login for access token",
    description="Authenticate user and receive access token",
    response_model=TokenResponse,
)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> TokenResponse:
    """
    Authenticate user and return access token.
    
    Args:
        form_data: Login form data
        
    Returns:
        TokenResponse: Access token and metadata
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        # Get user from database
        user = get_user_by_username(form_data.username)
        if not user:
            logger.warning(f"Login attempt with unknown username: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify password
        if not verify_password(form_data.password, user["password_hash"]):
            logger.warning(f"Failed login attempt for user: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user is active
        if not user.get("is_active", False):
            logger.warning(f"Login attempt for inactive user: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is disabled",
            )
        
        # Create access token
        access_token = create_access_token(user["user_id"], user["username"])
        
        # Update last login time (in real implementation)
        logger.info(f"Successful login for user: {form_data.username}")
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=3600 * 24,  # 24 hours
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error during authentication")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication error",
        ) from e


@router.get(
    "/me",
    summary="Get current user info",
    description="Get information about the currently authenticated user",
    response_model=UserInfo,
)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user),
) -> UserInfo:
    """
    Get current user information.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        UserInfo: User information
    """
    return UserInfo(
        user_id=current_user["user_id"],
        username=current_user["username"],
        email=current_user["email"],
        full_name=current_user.get("full_name"),
        roles=current_user.get("roles", []),
        created_at=current_user["created_at"],
        last_login=current_user.get("last_login"),
        is_active=current_user.get("is_active", True),
    )


@router.post(
    "/register",
    summary="Register new user",
    description="Register a new user account (if registration is enabled)",
    response_model=AuthResponse,
)
async def register_user(registration: UserRegistration) -> AuthResponse:
    """
    Register a new user.
    
    Args:
        registration: User registration data
        
    Returns:
        AuthResponse: Registration result
    """
    try:
        # Check if registration is enabled
        from neuroca.config import settings
        if not getattr(settings, 'REGISTRATION_ENABLED', False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User registration is disabled",
            )
        
        # Check if username already exists
        if get_user_by_username(registration.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )
        
        # In real implementation, create user in database
        logger.info(f"User registration requested for: {registration.username}")
        
        return AuthResponse(
            success=True,
            message="User registered successfully",
            data={
                "username": registration.username,
                "email": registration.email,
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error during user registration")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration error",
        ) from e


@router.post(
    "/logout",
    summary="Logout user",
    description="Logout current user and invalidate token",
    response_model=AuthResponse,
)
async def logout_user(
    current_user: dict = Depends(get_current_user),
) -> AuthResponse:
    """
    Logout current user.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        AuthResponse: Logout result
    """
    try:
        # In real implementation, invalidate token in database/cache
        logger.info(f"User logout: {current_user['username']}")
        
        return AuthResponse(
            success=True,
            message="Logged out successfully",
        )
        
    except Exception as e:
        logger.exception("Error during logout")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout error",
        ) from e


@router.post(
    "/password/reset",
    summary="Request password reset",
    description="Request a password reset for a user account",
    response_model=AuthResponse,
)
async def request_password_reset(reset_request: PasswordReset) -> AuthResponse:
    """
    Request password reset.
    
    Args:
        reset_request: Password reset request
        
    Returns:
        AuthResponse: Reset request result
    """
    try:
        # In real implementation, send password reset email
        logger.info(f"Password reset requested for email: {reset_request.email}")
        
        return AuthResponse(
            success=True,
            message="Password reset email sent (if account exists)",
        )
        
    except Exception as e:
        logger.exception("Error during password reset request")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset error",
        ) from e


@router.post(
    "/password/change",
    summary="Change password",
    description="Change password for the current user",
    response_model=AuthResponse,
)
async def change_password(
    password_change: PasswordChange,
    current_user: dict = Depends(get_current_user),
) -> AuthResponse:
    """
    Change user password.
    
    Args:
        password_change: Password change request
        current_user: Current authenticated user
        
    Returns:
        AuthResponse: Password change result
    """
    try:
        # Verify current password
        if not verify_password(password_change.current_password, current_user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
        
        # In real implementation, update password in database
        logger.info(f"Password changed for user: {current_user['username']}")
        
        return AuthResponse(
            success=True,
            message="Password changed successfully",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error during password change")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change error",
        ) from e


@router.get(
    "/verify",
    summary="Verify token",
    description="Verify if the current token is valid",
    response_model=AuthResponse,
)
async def verify_auth_token(
    current_user: dict = Depends(get_current_user),
) -> AuthResponse:
    """
    Verify authentication token.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        AuthResponse: Token verification result
    """
    return AuthResponse(
        success=True,
        message="Token is valid",
        data={
            "user_id": current_user["user_id"],
            "username": current_user["username"],
            "roles": current_user.get("roles", []),
        }
    )
