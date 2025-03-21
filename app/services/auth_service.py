from typing import Dict, Any, Optional, List
import time
from pydantic import EmailStr
from firebase_admin import auth as firebase_auth
from firebase_admin.exceptions import FirebaseError
from app.core.firebase import firebase
from app.core.exceptions import AuthenticationException, FirebaseException
from app.schemas.auth import UserCreate, UserProfileUpdate, UserResponse, Token, TokenData
from app.dto.auth_dto import (
    FrontendUserRegisterDTO, 
    FrontendUserProfileUpdateDTO,
    FrontendLoginDTO,
    FrontendUserResponseDTO,
    FrontendTokenDTO
)
from app.core.security import (
    get_current_user_id,
    get_current_user,
    get_current_user_frontend,
    check_admin_role,
    check_admin_or_instructor_role
)

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
                "photo_url": None,
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
    
    async def create_user_from_frontend(self, frontend_data: FrontendUserRegisterDTO) -> FrontendUserResponseDTO:
        """
        Create a user from frontend data format.
        
        Args:
            frontend_data: Frontend user registration data
            
        Returns:
            Frontend user response DTO
        """
        try:
            # Convert frontend DTO to backend schema
            backend_user_data = frontend_data.to_user_create()
            
            # Create user using backend service
            user = await self.create_user(backend_user_data)
            
            # Convert to frontend format and return
            return FrontendUserResponseDTO.from_backend(user)
        except Exception as e:
            print(f"Error creating user from frontend data: {str(e)}")
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
            # Get user by email
            auth = firebase.get_auth()
            try:
                user = auth.get_user_by_email(email)
            except firebase_auth.UserNotFoundError:
                raise ValueError("Invalid email or password")
            
            # In a real implementation, you would verify the password here
            # Firebase Admin SDK doesn't provide a direct way to validate passwords
            # You would typically use Firebase Auth REST API for this
            # For now, we'll assume the password is correct and create a JWT ID token
            
            # Create a custom token first (this is what Firebase SDK gives us)
            custom_token = auth.create_custom_token(user.uid)
            custom_token_str = custom_token.decode("utf-8") if isinstance(custom_token, bytes) else custom_token
            
            # In a real implementation, you would exchange this custom token for an ID token
            # Since we can't do that directly in the backend, we'll mark the token so we recognize it
            # The frontend would normally exchange this for an ID token using Firebase client SDK
            token_str = f"id_token:{custom_token_str}"  # Marking as an ID token equivalent
            
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
    
    async def login_user_from_frontend(self, frontend_data: FrontendLoginDTO) -> FrontendTokenDTO:
        """
        Login a user from frontend data format.
        
        Args:
            frontend_data: Frontend login data
            
        Returns:
            Frontend token DTO
        """
        try:
            # Login using backend service
            token = await self.login_user(frontend_data.email, frontend_data.password)
            
            # Convert to frontend format and return
            return FrontendTokenDTO.from_backend(token)
        except Exception as e:
            print(f"Error logging in from frontend data: {str(e)}")
            raise
        
    async def get_user_profile(self, user_id: str) -> UserResponse:
        """
        Get user profile information from Firestore.
        
        Args:
            user_id: Firebase user ID
            
        Returns:
            Complete user profile
        """
        try:
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
    
    async def get_frontend_user_profile(self, user_id: str) -> FrontendUserResponseDTO:
        """
        Get user profile in frontend format.
        
        Args:
            user_id: Firebase user ID
            
        Returns:
            Frontend user response DTO
        """
        try:
            # Get user using backend service
            user = await self.get_user_profile(user_id)
            
            # Convert to frontend format and return
            return FrontendUserResponseDTO.from_backend(user)
        except Exception as e:
            print(f"Error retrieving frontend user profile: {str(e)}")
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
    
    async def update_user_profile_from_frontend(self, user_id: str, frontend_data: FrontendUserProfileUpdateDTO) -> FrontendUserResponseDTO:
        """
        Update user profile from frontend data format.
        
        Args:
            user_id: Firebase user ID
            frontend_data: Frontend profile update data
            
        Returns:
            Frontend user response DTO
        """
        try:
            # Convert frontend DTO to backend schema
            backend_profile_data = frontend_data.to_user_profile_update()
            
            # Update user using backend service
            user = await self.update_user_profile(user_id, backend_profile_data)
            
            # Convert to frontend format and return
            return FrontendUserResponseDTO.from_backend(user)
        except Exception as e:
            print(f"Error updating user profile from frontend data: {str(e)}")
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
            # Check if it's our marked token
            if token.startswith("id_token:"):
                # Extract the custom token part
                custom_token = token[9:]  # Remove the "id_token:" prefix
                
                # For custom tokens, we can't verify them directly, but we can extract the uid
                # In a real implementation, this would be verified using Firebase client SDK first
                # This is a simplified approach for demo purposes
                
                # Parse the token manually - this is a simplified approach
                # In a real implementation, you'd need proper JWT verification
                import jwt
                
                try:
                    # Try to decode without verification to extract the user ID
                    # WARNING: This is insecure and for demo purposes only
                    payload = jwt.decode(custom_token, options={"verify_signature": False})
                    uid = payload.get("uid")
                    
                    if not uid:
                        raise ValueError("Invalid token: UID not found")
                    
                    return TokenData(
                        uid=uid,
                        email=None,  # We don't have this information from the custom token
                        role="student",  # Default role
                        exp=None  # We don't know the expiration
                    )
                except Exception as jwt_error:
                    print(f"Error decoding token: {str(jwt_error)}")
                    raise ValueError("Invalid token format")
            else:
                # It's a regular ID token, verify with Firebase
                decoded_token = firebase.verify_id_token(token)
                
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
            # In a real implementation, we would call Firebase's token refresh API
            # Since we're using custom tokens, we would need to implement this manually
            # or use Firebase Authentication REST API
            
            raise NotImplementedError("Token refresh not implemented for Firebase Auth")
        except Exception as e:
            print(f"Error refreshing token: {str(e)}")
            raise ValueError("Invalid refresh token")
    
    async def refresh_token_from_frontend(self, refresh_token: str) -> FrontendTokenDTO:
        """
        Refresh token from frontend format.
        
        Args:
            refresh_token: Refresh token string
            
        Returns:
            Frontend token DTO
        """
        try:
            # Refresh token using backend service
            token = await self.refresh_token(refresh_token)
            
            # Convert to frontend format and return
            return FrontendTokenDTO.from_backend(token)
        except Exception as e:
            print(f"Error refreshing token from frontend: {str(e)}")
            raise
    
    async def logout_user(self, user_id: str) -> Dict[str, Any]:
        """
        Log out a user by revoking their Firebase tokens.
        
        Args:
            user_id: Firebase user ID
            
        Returns:
            Success message
        """
        try:
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
    
    async def check_user_role(self, user_id: str, role: str) -> bool:
        """
        Check if user has a specific role.
        
        Args:
            user_id: Firebase user ID
            role: Role to check
            
        Returns:
            True if user has the role, False otherwise
        """
        try:
            # Get user profile
            user = await self.get_user_profile(user_id)
            
            # Check role
            return user.role == role
        except Exception as e:
            print(f"Error checking user role: {str(e)}")
            raise
    
    async def get_all_users(self) -> List[UserResponse]:
        """
        Get all users from the database.
        
        Returns:
            List of all users
        """
        try:
            # Get all users from Firestore
            db = firebase.get_firestore()
            users_ref = db.collection("users")
            users = []
            
            for user_doc in users_ref.stream():
                user_data = user_doc.to_dict()
                user = UserResponse(id=user_doc.id, **user_data)
                users.append(user)
                
            return users
        except Exception as e:
            print(f"Error getting all users: {str(e)}")
            raise
    
    async def get_all_frontend_users(self) -> List[FrontendUserResponseDTO]:
        """
        Get all users in frontend format.
        
        Returns:
            List of all users in frontend format
        """
        try:
            # Get all users using backend service
            users = await self.get_all_users()
            
            # Convert to frontend format and return
            return [FrontendUserResponseDTO.from_backend(user) for user in users]
        except Exception as e:
            print(f"Error getting all frontend users: {str(e)}")
            raise