from typing import Dict, Any, Optional, Tuple
import uuid
import time
from datetime import datetime, timedelta
from pydantic import EmailStr
from firebase_admin import auth as firebase_auth
from firebase_admin.exceptions import FirebaseError
from app.core.firebase import firebase
from app.schemas.auth import UserCreate, UserProfileUpdate, UserResponse, Token, TokenData
from app.core.config import settings

class AuthService:
    """Service for handling user authentication and profile management"""
    
    async def create_user(self, user_data: UserCreate) -> UserResponse:
        """
        Create a new user in Firebase Authentication and Firestore.
        
        Args:
            user_data: User registration data
            
        Returns:
            User data with authentication token
        """
        try:
            # If we're in mock mode, create a mock user
            if firebase.app is None:
                user_id = f"{uuid.uuid4()}"
                user_data_dict = {
                    "id": user_id,
                    "email": user_data.email,
                    "first_name": user_data.first_name,
                    "last_name": user_data.last_name,
                    "role": "student",
                    "created_at": int(time.time()),
                    "last_login_at": int(time.time()),
                    "student_id": user_data.student_id,
                    "program": user_data.program,
                    "semester": user_data.semester,
                    "courses": []
                }
                return UserResponse(**user_data_dict)
            
            # Create the user in Firebase Auth
            auth = firebase.get_auth()
            user = auth.create_user(
                email=user_data.email,
                password=user_data.password,
                display_name=user_data.display_name or f"{user_data.first_name or ''} {user_data.last_name or ''}".strip() or None
            )
            
            # Store additional user data in Firestore
            db = firebase.get_firestore()
            user_ref = db.collection("users").document(user.uid)
            
            user_data_dict = {
                "email": user_data.email,
                "display_name": user_data.display_name,
                "first_name": user_data.first_name,
                "last_name": user_data.last_name,
                "created_at": int(time.time()),
                "last_login_at": int(time.time()),
                "role": "student",
                "student_id": user_data.student_id,
                "program": user_data.program,
                "semester": user_data.semester,
                "preferences": {},
                "courses": []
            }
            
            user_ref.set(user_data_dict)
            
            # Return user data
            return UserResponse(
                id=user.uid,
                **user_data_dict
            )
        except Exception as e:
            # Log the error
            print(f"Error creating user: {str(e)}")
            raise
    
    async def login_user(self, email: str, password: str) -> Token:
        """
        Authenticate a user with email and password.
        
        Args:
            email: User's email address
            password: User's password
            
        Returns:
            Authentication token and user data
        """
        try:
            # If we're in mock mode, return mock data
            if firebase.app is None:
                user_id = f"{uuid.uuid4()}"
                mock_token = f"mock_token_{user_id}"
                
                user_data = UserResponse(
                    id=user_id,
                    email=email,
                    display_name="Mock User",
                    first_name="Mock",
                    last_name="User",
                    role="student",
                    created_at=int(time.time()) - 3600,
                    last_login_at=int(time.time()),
                    courses=[]
                )
                
                return Token(
                    access_token=mock_token,
                    token_type="bearer",
                    expires_in=3600,
                    refresh_token=f"mock_refresh_{user_id}",
                    user=user_data
                )
            
            # For Firebase authentication, we need to sign in with email and password
            # using the REST API since the Admin SDK doesn't provide this functionality
            try:
                # In a real implementation, you would call Firebase Auth REST API
                # For simplicity, we'll simulate the authentication process
                # Get user by email
                auth = firebase.get_auth()
                try:
                    user = auth.get_user_by_email(email)
                except firebase_auth.UserNotFoundError:
                    raise ValueError("Invalid email or password")
                
                # In a real implementation, you would verify the password here
                # For now, we'll assume the password is correct
                
                # Create custom token for the user
                custom_token = auth.create_custom_token(user.uid)
                token_str = custom_token.decode("utf-8") if isinstance(custom_token, bytes) else custom_token
                
                # Get user data from Firestore
                db = firebase.get_firestore()
                user_ref = db.collection("users").document(user.uid)
                user_doc = user_ref.get()
                
                if not user_doc.exists:
                    raise ValueError("User profile not found")
                    
                user_data = user_doc.to_dict()
                
                # Update last login timestamp
                current_time = int(time.time())
                user_ref.update({"last_login_at": current_time})
                user_data["last_login_at"] = current_time
                
                # Return token with user data
                user_response = UserResponse(
                    id=user.uid,
                    **user_data
                )
                
                return Token(
                    access_token=token_str,
                    token_type="bearer",
                    expires_in=3600,  # 1 hour expiration
                    refresh_token=None,  # Firebase custom tokens don't include refresh tokens
                    user=user_response
                )
            except firebase_auth.UserNotFoundError:
                raise ValueError("Invalid email or password")
            except Exception as e:
                print(f"Firebase auth error: {str(e)}")
                raise ValueError("Authentication failed")
                
        except ValueError:
            # Re-raise credential validation errors
            raise
        except Exception as e:
            print(f"Error during login: {str(e)}")
            raise ValueError("Authentication failed")
        
    async def get_user_profile(self, user_id: str) -> UserResponse:
        """
        Get user profile information from Firestore.
        
        Args:
            user_id: Firebase user ID
            
        Returns:
            Complete user profile
        """
        try:
            # If we're in mock mode, return mock data
            if firebase.app is None:
                return UserResponse(
                    id=user_id,
                    email=f"mock-{user_id}@example.com",
                    display_name="Mock User",
                    first_name="Mock",
                    last_name="User",
                    role="student",
                    created_at=int(time.time()) - 86400,
                    last_login_at=int(time.time()) - 3600,
                    courses=[]
                )
                
            # Get user data from Firestore
            db = firebase.get_firestore()
            user_ref = db.collection("users").document(user_id)
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                raise ValueError(f"User profile for {user_id} not found")
                
            user_data = user_doc.to_dict()
            
            # Return complete user profile
            return UserResponse(
                id=user_id,
                **user_data
            )
        except Exception as e:
            print(f"Error retrieving user profile: {str(e)}")
            raise
    
    async def update_user_profile(self, user_id: str, profile_data: UserProfileUpdate) -> UserResponse:
        """
        Update user profile information in Firestore.
        
        Args:
            user_id: Firebase user ID
            profile_data: New profile data
            
        Returns:
            Updated user profile
        """
        try:
            # If we're in mock mode, return mock data
            if firebase.app is None:
                profile_dict = profile_data.dict(exclude_unset=True)
                return UserResponse(
                    id=user_id,
                    email=f"mock-{user_id}@example.com",
                    display_name=profile_dict.get("display_name", "Mock User"),
                    first_name=profile_dict.get("first_name", "Mock"),
                    last_name=profile_dict.get("last_name", "User"),
                    role="student",
                    created_at=int(time.time()) - 86400,
                    last_login_at=int(time.time()) - 3600,
                    student_id=profile_dict.get("student_id"),
                    program=profile_dict.get("program"),
                    semester=profile_dict.get("semester"),
                    courses=[]
                )
                
            # Update user data in Firestore
            db = firebase.get_firestore()
            user_ref = db.collection("users").document(user_id)
            
            # Get only the fields that were provided (not None)
            update_data = profile_data.dict(exclude_unset=True)
            
            # Update display_name in Firebase Auth if provided
            if "display_name" in update_data:
                auth = firebase.get_auth()
                auth.update_user(
                    user_id,
                    display_name=update_data["display_name"]
                )
            
            if update_data:
                user_ref.update(update_data)
                
            # Retrieve the updated user profile
            return await self.get_user_profile(user_id)
        except Exception as e:
            print(f"Error updating user profile: {str(e)}")
            raise
    
    async def verify_token(self, token: str) -> TokenData:
        """
        Verify a Firebase token and return the user ID.
        
        Args:
            token: Firebase authentication token
            
        Returns:
            User ID and email from the token
        """
        try:
            # If we're in mock mode, verify the token format
            if firebase.app is None:
                if token.startswith("mock_token_"):
                    user_id = token.replace("mock_token_", "")
                    return TokenData(uid=user_id, email=f"mock-{user_id}@example.com")
                raise ValueError("Invalid token")
            
            # Verify the Firebase token
            auth = firebase.get_auth()
            decoded_token = auth.verify_id_token(token)
            
            # Return token data
            return TokenData(
                uid=decoded_token["uid"],
                email=decoded_token.get("email"),
                role=decoded_token.get("role", "student"),
                exp=decoded_token.get("exp")
            )
        except Exception as e:
            print(f"Error verifying token: {str(e)}")
            raise ValueError("Invalid token")
    
    async def refresh_token(self, refresh_token: str) -> Token:
        """
        Refresh an authentication token.
        
        Args:
            refresh_token: Refresh token
            
        Returns:
            New authentication token
        """
        try:
            # This would use Firebase's token refresh endpoint
            # For now, we'll just simulate this process
            
            # If we're in mock mode, verify the token format
            if firebase.app is None:
                if refresh_token.startswith("mock_refresh_"):
                    user_id = refresh_token.replace("mock_refresh_", "")
                    mock_token = f"mock_token_{user_id}"
                    
                    user_data = UserResponse(
                        id=user_id,
                        email=f"mock-{user_id}@example.com",
                        display_name="Mock User",
                        first_name="Mock",
                        last_name="User",
                        role="student",
                        created_at=int(time.time()) - 3600,
                        last_login_at=int(time.time()),
                        courses=[]
                    )
                    
                    return Token(
                        access_token=mock_token,
                        token_type="bearer",
                        expires_in=3600,
                        refresh_token=refresh_token,
                        user=user_data
                    )
                raise ValueError("Invalid refresh token")
            
            # In a real implementation, we would call Firebase's token refresh API
            # Since we're using custom tokens, we would need to implement this manually
            # or use Firebase Authentication REST API
            
            raise NotImplementedError("Token refresh not implemented for Firebase Auth")
        except Exception as e:
            print(f"Error refreshing token: {str(e)}")
            raise ValueError("Invalid refresh token")
        
    
    # Add this method to the AuthService class

async def logout_user(self, user_id: str) -> Dict[str, Any]:
    """
    Log out a user by revoking their Firebase tokens.
    
    Args:
        user_id: Firebase user ID
        
    Returns:
        Success message
    """
    try:
        # If we're in mock mode, return mock success
        if firebase.app is None:
            return {"detail": "User logged out successfully"}
            
        # Revoke all refresh tokens for the user
        auth = firebase.get_auth()
        auth.revoke_refresh_tokens(user_id)
        
        # Update the user's lastLogout timestamp in Firestore
        db = firebase.get_firestore()
        user_ref = db.collection("users").document(user_id)
        user_ref.update({"last_logout_at": int(time.time())})
        
        return {"detail": "User logged out successfully"}
    except Exception as e:
        print(f"Error during logout: {str(e)}")
        raise ValueError("Logout failed")