from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordBearer
from typing import Dict, Any
from app.core.security import get_current_user
from app.schemas.auth import UserResponse, UserCreate, UserProfileUpdate, Token, LoginCredentials
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])
auth_service = AuthService()

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

@router.post("/register", response_model=UserResponse)
async def register_user(user_data: UserCreate):
    """
    Register a new user in the application.
   
    This endpoint creates a new user in Firebase Authentication and adds user profile
    information to Firestore. It returns the user's profile data along with an ID token.
    """
    try:
        user = await auth_service.create_user(user_data)
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {str(e)}",
        )

@router.post("/login", response_model=Token)
async def login(login_data: LoginCredentials):
    """
    Authenticate a user and return an access token.
   
    This endpoint authenticates a user with their email and password, and returns
    an access token for use in subsequent requests along with the user profile.
    """
    try:
        token = await auth_service.login_user(login_data.email, login_data.password)
        return token
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@router.post("/refresh", response_model=Token)
async def refresh_access_token(refresh_token: str):
    """
    Refresh an access token.
   
    This endpoint takes a refresh token and returns a new access token
    if the refresh token is valid.
    """
    try:
        new_token = await auth_service.refresh_token(refresh_token)
        return new_token
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Token refresh not implemented for this authentication method"
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user=Depends(get_current_user)):
    """
    Get the profile of the currently authenticated user.
    """
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_user_profile(
    profile_update: UserProfileUpdate,
    current_user=Depends(get_current_user)
):
    """
    Update the profile of the currently authenticated user.
    """
    try:
        updated_user = await auth_service.update_user_profile(
            current_user["id"],
            profile_update
        )
        return updated_user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Profile update failed: {str(e)}",
        )

@router.post("/token/verify")
async def verify_token(current_user=Depends(get_current_user)):
    """
    Verify the provided authentication token.
   
    This endpoint validates the Firebase ID token provided in the Authorization header.
    It returns a success message if the token is valid.
    """
    return {"detail": "Token is valid", "user_id": current_user["id"]}