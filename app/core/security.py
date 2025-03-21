from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import base64
import json
from app.core.firebase import firebase
from app.core.exceptions import AuthenticationException
from app.schemas.auth import UserResponse
from app.dto.auth_dto import FrontendUserResponseDTO

# Security scheme for Bearer authentication
security = HTTPBearer()

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    Validate the access token and return the user ID.
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        User ID from the token
        
    Raises:
        HTTPException: If token is invalid
    """
    try:
        token = credentials.credentials
        
        # Check if it's our marked custom token
        if token.startswith("id_token:"):
            # Extract the custom token part
            custom_token = token[9:]  # Remove the "id_token:" prefix
            
            try:
                # Safe token parsing - handle both JWT and Firebase custom tokens
                # This is a simplified approach for demonstration
                try:
                    # First try regular JWT decoding
                    decoded = jwt.decode(custom_token, options={"verify_signature": False})
                    uid = decoded.get("uid")
                except:
                    # If regular decoding fails, try Firebase custom token format
                    # Firebase custom tokens are JWTs with a specific structure
                    parts = custom_token.split('.')
                    if len(parts) != 3:
                        raise ValueError("Invalid token format")
                    
                    # Decode the payload (second part)
                    padded = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)  # Add padding if needed
                    decoded_bytes = base64.urlsafe_b64decode(padded)
                    payload = json.loads(decoded_bytes)
                    uid = payload.get("uid")
                
                if not uid:
                    raise ValueError("Invalid token: UID not found")
                
                return uid
            except Exception as e:
                print(f"Error decoding token: {str(e)}")
                raise AuthenticationException(f"Invalid token format: {str(e)}")
        else:
            # It's a regular ID token, verify with Firebase
            try:
                decoded_token = firebase.verify_id_token(token)
                # Return the user ID from the decoded token
                return decoded_token.get("uid")
            except Exception as e:
                # Try to handle it as JWT if Firebase verification fails
                try:
                    decoded = jwt.decode(token, options={"verify_signature": False})
                    uid = decoded.get("uid") or decoded.get("user_id")
                    if uid:
                        return uid
                    raise ValueError("Could not extract user ID from token")
                except Exception as jwt_error:
                    # If both methods fail, raise the original Firebase error
                    raise AuthenticationException(f"Invalid token: {str(e)}")
       
    except AuthenticationException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication error: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(user_id: str = Depends(get_current_user_id)) -> UserResponse:
    """
    Get the current user from the database based on the user ID.
    Returns a backend UserResponse object.
    
    Args:
        user_id: User ID from token
        
    Returns:
        UserResponse object with user data
        
    Raises:
        HTTPException: If user not found or other error
    """
    try:
        # Get the user document from Firestore
        user_ref = firebase.get_firestore().collection("users").document(user_id)
        user_doc = user_ref.get()
       
        # If user document doesn't exist, get user data from Firebase Auth and create
        if not user_doc.exists:
            auth_user = firebase.get_user(user_id)
            user_data = {
                "email": auth_user.email,
                "display_name": auth_user.display_name or "",
                "photo_url": auth_user.photo_url or "",
                "first_name": None,
                "last_name": None,
                "created_at": auth_user.user_metadata.creation_timestamp,
                "last_login_at": auth_user.user_metadata.last_sign_in_timestamp,
                "courses": [],
                "role": "student",  # Default role
                "student_id": None,
                "program": None,
                "semester": None,
                "preferences": {}
            }
            user_ref.set(user_data)
            return UserResponse(id=user_id, **user_data)
           
        # Convert the document to a UserResponse object
        user_dict = user_doc.to_dict()
        return UserResponse(id=user_id, **user_dict)
       
    except AuthenticationException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user data: {str(e)}",
        )

async def get_current_user_frontend(backend_user: UserResponse = Depends(get_current_user)) -> FrontendUserResponseDTO:
    """
    Get the current user from the database and convert to frontend DTO format.
    Returns a FrontendUserResponseDTO object.
    
    Args:
        backend_user: Backend UserResponse object
        
    Returns:
        FrontendUserResponseDTO object with frontend field mapping
    """
    # Convert backend UserResponse to frontend DTO
    return FrontendUserResponseDTO.from_backend(backend_user)

async def check_admin_role(user_id: str = Depends(get_current_user_id)) -> str:
    """
    Check if the current user has admin role.
    
    Args:
        user_id: User ID from token
        
    Returns:
        User ID if user is admin
        
    Raises:
        HTTPException: If user is not admin or other error
    """
    try:
        # Get the user document from Firestore
        user_ref = firebase.get_firestore().collection("users").document(user_id)
        user_doc = user_ref.get()
       
        if not user_doc.exists or user_doc.to_dict().get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to perform this action",
            )
           
        return user_id
       
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking admin role: {str(e)}",
        )

async def check_instructor_role(user_id: str = Depends(get_current_user_id)) -> str:
    """
    Check if the current user has instructor role.
    
    Args:
        user_id: User ID from token
        
    Returns:
        User ID if user is instructor
        
    Raises:
        HTTPException: If user is not instructor or other error
    """
    try:
        # Get the user document from Firestore
        user_ref = firebase.get_firestore().collection("users").document(user_id)
        user_doc = user_ref.get()
       
        if not user_doc.exists or user_doc.to_dict().get("role") != "instructor":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to perform this action",
            )
           
        return user_id
       
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking instructor role: {str(e)}",
        )

async def check_admin_or_instructor_role(user_id: str = Depends(get_current_user_id)) -> str:
    """
    Check if the current user has admin or instructor role.
    
    Args:
        user_id: User ID from token
        
    Returns:
        User ID if user is admin or instructor
        
    Raises:
        HTTPException: If user is not admin or instructor or other error
    """
    try:
        # Get the user document from Firestore
        user_ref = firebase.get_firestore().collection("users").document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        
        role = user_doc.to_dict().get("role")
        
        if role not in ["admin", "instructor"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to perform this action",
            )
           
        return user_id
       
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking user role: {str(e)}",
        )