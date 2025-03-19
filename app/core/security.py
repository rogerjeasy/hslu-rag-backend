from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.firebase import firebase
from app.core.exceptions import AuthenticationException

# Security scheme for Bearer authentication
security = HTTPBearer()

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    Validate the access token and return the user ID.
    """
    try:
        # Verify the Firebase ID token
        token = credentials.credentials
        decoded_token = firebase.verify_id_token(token)
        
        # Return the user ID from the decoded token
        return decoded_token.get("uid")
        
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

async def get_current_user(user_id: str = Depends(get_current_user_id)):
    """
    Get the current user from the database based on the user ID.
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
                "created_at": auth_user.user_metadata.creation_timestamp,
                "last_login_at": auth_user.user_metadata.last_sign_in_timestamp,
                "courses": [],
            }
            user_ref.set(user_data)
            return {"id": user_id, **user_data}
            
        return {"id": user_id, **user_doc.to_dict()}
        
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

async def check_admin_role(user_id: str = Depends(get_current_user_id)):
    """
    Check if the current user has admin role.
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