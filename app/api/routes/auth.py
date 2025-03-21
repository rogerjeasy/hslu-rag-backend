from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List

from app.core.firebase import firebase
from app.schemas.auth import UserProfileUpdate, UserResponse
from app.dto.auth_dto import (
    FrontendUserRegisterDTO, 
    FrontendUserProfileUpdateDTO, 
    FrontendLoginDTO,
    FrontendUserResponseDTO,
    FrontendTokenDTO
)
from app.services.auth_service import AuthService
from app.core.security import (
    get_current_user_id,
    get_current_user, 
    get_current_user_frontend, 
    check_admin_role,
    check_admin_or_instructor_role
)

router = APIRouter(prefix="/auth", tags=["authentication"])
auth_service = AuthService()

@router.post("/register", response_model=FrontendUserResponseDTO)
async def register_user(user_data: FrontendUserRegisterDTO):
    """
    Register a new user in the application.
   
    This endpoint creates a new user in Firebase Authentication and adds user profile
    information to Firestore. It returns the user's profile data.
    """
    try:
        # Convert frontend DTO to backend schema
        backend_user_data = user_data.to_user_create()
        
        # Create user using service
        user = await auth_service.create_user(backend_user_data)
        
        # Convert backend response to frontend DTO
        return FrontendUserResponseDTO.from_backend(user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {str(e)}",
        )

@router.post("/login", response_model=FrontendTokenDTO)
async def login(login_data: FrontendLoginDTO):
    """
    Authenticate a user and return an access token.
   
    This endpoint authenticates a user with their email and password, and returns
    an access token for use in subsequent requests along with the user profile.
    """
    try:
        token = await auth_service.login_user(login_data.email, login_data.password)
        
        # Convert backend token to frontend DTO
        return FrontendTokenDTO.from_backend(token)
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

@router.post("/refresh", response_model=FrontendTokenDTO)
async def refresh_access_token(refresh_token: str):
    """
    Refresh an access token.
   
    This endpoint takes a refresh token and returns a new access token
    if the refresh token is valid.
    """
    try:
        new_token = await auth_service.refresh_token(refresh_token)
        
        # Convert backend token to frontend DTO
        return FrontendTokenDTO.from_backend(new_token)
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

@router.get("/me", response_model=FrontendUserResponseDTO)
async def get_current_user_profile(
    # Use the get_current_user_frontend dependency for direct frontend format
    current_user: FrontendUserResponseDTO = Depends(get_current_user_frontend)
):
    """
    Get the profile of the currently authenticated user.
    """
    return current_user

@router.put("/me", response_model=FrontendUserResponseDTO)
async def update_user_profile(
    profile_update: FrontendUserProfileUpdateDTO,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Update the profile of the currently authenticated user.
    """
    try:
        # Convert frontend DTO to backend schema
        backend_profile_update = profile_update.to_user_profile_update()
        
        # Update user profile using service
        updated_user = await auth_service.update_user_profile(
            current_user.id,
            backend_profile_update
        )
        
        # Convert backend response to frontend DTO
        return FrontendUserResponseDTO.from_backend(updated_user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Profile update failed: {str(e)}",
        )

@router.post("/token/verify")
async def verify_token(user_id: str = Depends(get_current_user_id)):
    """
    Verify the provided authentication token.
   
    This endpoint validates the token provided in the Authorization header.
    It returns a success message if the token is valid.
    """
    return {"detail": "Token is valid", "user_id": user_id}

@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(user_id: str = Depends(get_current_user_id)):
    """
    Log out the currently authenticated user.
    
    This endpoint revokes all of the user's Firebase refresh tokens,
    effectively logging them out from all devices.
    """
    try:
        # Use the user_id directly instead of the full user object
        # This avoids token verification issues
        result = await auth_service.logout_user(user_id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {str(e)}"
        )

# Admin-only endpoint
@router.get("/admin/users", response_model=List[FrontendUserResponseDTO])
async def get_all_users(admin_id: str = Depends(check_admin_role)):
    """
    Get all users in the system. Admin access only.
    """
    try:
        # Use the service method instead of direct Firestore access
        users = await auth_service.get_all_frontend_users()
        return users
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving users: {str(e)}"
        )

@router.get("/users/{user_id}", response_model=FrontendUserResponseDTO)
async def get_user_by_id(
    user_id: str,
    # Only admins or instructors can access other user profiles
    current_user_id: str = Depends(check_admin_or_instructor_role)
):
    """
    Get a specific user by ID. Admin or instructor access only.
    """
    try:
        # Get user profile using service
        user = await auth_service.get_user_profile(user_id)
        
        # Convert to frontend format and return
        return FrontendUserResponseDTO.from_backend(user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user: {str(e)}"
        )

@router.put("/admin/users/{user_id}/role", status_code=status.HTTP_200_OK)
async def update_user_role(
    user_id: str,
    role: str,
    admin_id: str = Depends(check_admin_role)
):
    """
    Update a user's role. Admin access only.
    """
    try:
        # Validate role
        if role not in ["student", "instructor", "admin"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role. Must be one of: student, instructor, admin"
            )
        
        # Update user profile with new role
        await auth_service.update_user_profile(
            user_id,
            UserProfileUpdate(role=role)
        )
        
        return {"detail": f"User role updated to {role}", "user_id": user_id}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user role: {str(e)}"
        )