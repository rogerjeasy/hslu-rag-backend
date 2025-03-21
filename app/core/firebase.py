import json
import os
import time
from typing import Optional, Dict, Any, List, Union
import firebase_admin
from firebase_admin import credentials, auth, firestore
from google.cloud.firestore import Client as FirestoreClient
from google.oauth2 import service_account
from app.core.config import settings
from app.core.exceptions import AuthenticationException, FirebaseException
from app.schemas.auth import UserResponse, CourseEnrollment
from app.dto.auth_dto import FrontendUserResponseDTO

class FirebaseManager:
    _instance = None
   
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirebaseManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
   
    def _initialize(self):
        """Initialize Firebase Admin SDK"""
        try:
            # If running in a testing environment, use the emulator
            if os.environ.get("ENV") == "test":
                self.app = None
                self.db = firestore.Client(project="test")
                return
           
            # Load service account key
            if settings.FIREBASE_CREDENTIALS:
                if os.path.isfile(settings.FIREBASE_CREDENTIALS):
                    # Load from file
                    cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS)
                else:
                    try:
                        # Load from environment variable (JSON string)
                        service_account_info = json.loads(settings.FIREBASE_CREDENTIALS)
                        cred = credentials.Certificate(service_account_info)
                    except json.JSONDecodeError as e:
                        print(f"Error parsing Firebase credentials JSON: {str(e)}")
                        print(f"Credentials string: {settings.FIREBASE_CREDENTIALS[:30]}...")
                        raise FirebaseException(f"Invalid Firebase credentials JSON: {str(e)}")
               
                # Initialize Firebase Admin
                self.app = firebase_admin.initialize_app(cred)
               
                # Initialize Firestore
                self.db = firestore.client()
            else:
                # For development with empty credentials
                print("WARNING: Firebase credentials not provided.")
                print("Please set FIREBASE_CREDENTIALS in your .env file or environment variables.")
                raise FirebaseException("Firebase credentials not provided")
               
        except Exception as e:
            # Re-raise the exception to handle it at the application level
            print(f"Firebase initialization error: {str(e)}")
            raise FirebaseException(f"Firebase initialization error: {str(e)}")
   
    def get_auth(self):
        """Get Firebase Auth instance"""
        return auth
   
    def get_firestore(self) -> FirestoreClient:
        """Get Firestore database instance"""
        return self.db
   
    def verify_id_token(self, id_token: str) -> dict:
        """Verify Firebase ID token and return user data"""
        try:
            return auth.verify_id_token(id_token)
        except Exception as e:
            raise AuthenticationException(f"Invalid authentication token: {str(e)}")
   
    def get_user(self, uid: str) -> dict:
        """Get user data from Firebase Auth"""
        try:
            return auth.get_user(uid)
        except auth.UserNotFoundError:
            raise AuthenticationException(f"User not found: {uid}")
        except Exception as e:
            raise FirebaseException(f"Error retrieving user: {str(e)}")
    
    # New methods to support DTO integration
    
    def get_user_profile(self, uid: str) -> UserResponse:
        """
        Get user profile from Firestore and convert to UserResponse schema
        
        Args:
            uid: User ID
            
        Returns:
            UserResponse object with user profile data
            
        Raises:
            AuthenticationException: If user not found
            FirebaseException: For other Firebase errors
        """
        try:
            # Get user document from Firestore
            user_ref = self.db.collection("users").document(uid)
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                # Get user from Firebase Auth and create document in Firestore
                try:
                    auth_user = auth.get_user(uid)
                    
                    # Create default user data with role as a list
                    user_data = {
                        "email": auth_user.email,
                        "display_name": auth_user.display_name or "",
                        "photo_url": auth_user.photo_url or "",
                        "first_name": None,
                        "last_name": None,
                        "created_at": int(time.time()),
                        "last_login_at": int(time.time()),
                        "role": ["student"],  # Default role as a list
                        "student_id": None,
                        "program": None,
                        "semester": None,
                        "preferences": {},
                        "courses": []
                    }
                    
                    # Save to Firestore
                    user_ref.set(user_data)
                    
                    # Return as UserResponse
                    return UserResponse(id=uid, **user_data)
                    
                except Exception as e:
                    raise AuthenticationException(f"User not found: {uid}")
            
            # Return user data from Firestore
            user_data = user_doc.to_dict()
            
            # Convert role to list if it's still a string (for backward compatibility)
            if "role" in user_data and isinstance(user_data["role"], str):
                user_data["role"] = [user_data["role"]]
            elif "role" not in user_data:
                user_data["role"] = ["student"]
                
            return UserResponse(id=uid, **user_data)
            
        except AuthenticationException:
            raise
        except Exception as e:
            raise FirebaseException(f"Error retrieving user profile: {str(e)}")
    
    def get_frontend_user_profile(self, uid: str) -> FrontendUserResponseDTO:
        """
        Get user profile from Firestore and convert to frontend DTO
        
        Args:
            uid: User ID
            
        Returns:
            FrontendUserResponseDTO object with user profile data
            
        Raises:
            AuthenticationException: If user not found
            FirebaseException: For other Firebase errors
        """
        # Get backend user response
        backend_user = self.get_user_profile(uid)
        
        # Convert to frontend DTO
        return FrontendUserResponseDTO.from_backend(backend_user)
    
    def update_user_profile(self, uid: str, update_data: Dict[str, Any]) -> UserResponse:
        """
        Update user profile in Firestore and Firebase Auth
        
        Args:
            uid: User ID
            update_data: Dictionary of data to update
            
        Returns:
            Updated UserResponse object
            
        Raises:
            AuthenticationException: If user not found
            FirebaseException: For other Firebase errors
        """
        try:
            # Get user reference
            user_ref = self.db.collection("users").document(uid)
            
            # Check if user exists
            if not user_ref.get().exists:
                raise AuthenticationException(f"User not found: {uid}")
            
            # If display_name is being updated, also update in Firebase Auth
            if "display_name" in update_data:
                try:
                    auth.update_user(
                        uid,
                        display_name=update_data["display_name"]
                    )
                except Exception as e:
                    raise FirebaseException(f"Error updating user display name: {str(e)}")
            
            # Update in Firestore
            user_ref.update(update_data)
            
            # Get updated user data
            updated_doc = user_ref.get()
            user_data = updated_doc.to_dict()
            
            # Return as UserResponse
            return UserResponse(id=uid, **user_data)
            
        except AuthenticationException:
            raise
        except Exception as e:
            raise FirebaseException(f"Error updating user profile: {str(e)}")
    
    def create_user(self, email: str, password: str, display_name: Optional[str] = None, 
               user_data: Optional[Dict[str, Any]] = None) -> UserResponse:
        """
        Create a new user in Firebase Auth and Firestore
        
        Args:
            email: User email
            password: User password
            display_name: User display name
            user_data: Additional user data for Firestore
            
        Returns:
            UserResponse object for the new user
            
        Raises:
            FirebaseException: If user creation fails
        """
        try:
            # Create user in Firebase Auth
            user_record = auth.create_user(
                email=email,
                password=password,
                display_name=display_name
            )
            
            # Prepare user data for Firestore with role as a list
            firestore_data = {
                "email": email,
                "display_name": display_name or "",
                "photo_url": "",
                "first_name": None,
                "last_name": None,
                "created_at": int(time.time()),
                "last_login_at": int(time.time()),
                "role": ["student"],  # Default role as a list
                "student_id": None,
                "program": None,
                "semester": None,
                "preferences": {},
                "courses": []
            }
            
            # Merge with additional user data if provided
            if user_data:
                firestore_data.update(user_data)
            
            # Save to Firestore
            user_ref = self.db.collection("users").document(user_record.uid)
            user_ref.set(firestore_data)
            
            # Return as UserResponse
            return UserResponse(id=user_record.uid, **firestore_data)
            
        except Exception as e:
            raise FirebaseException(f"Error creating user: {str(e)}")
    
    def get_all_users(self) -> List[UserResponse]:
        """
        Get all users from Firestore
        
        Returns:
            List of UserResponse objects
            
        Raises:
            FirebaseException: If retrieving users fails
        """
        try:
            users = []
            for user_doc in self.db.collection("users").stream():
                user_data = user_doc.to_dict()
                user = UserResponse(id=user_doc.id, **user_data)
                users.append(user)
            
            return users
            
        except Exception as e:
            raise FirebaseException(f"Error retrieving users: {str(e)}")
    
    def revoke_refresh_tokens(self, uid: str) -> None:
        """
        Revoke all refresh tokens for a user
        
        Args:
            uid: User ID
            
        Raises:
            AuthenticationException: If user not found
            FirebaseException: For other Firebase errors
        """
        try:
            auth.revoke_refresh_tokens(uid)
        except auth.UserNotFoundError:
            raise AuthenticationException(f"User not found: {uid}")
        except Exception as e:
            raise FirebaseException(f"Error revoking refresh tokens: {str(e)}")
    
    def check_user_role(self, uid: str, role: str) -> bool:
        """
        Check if a user has a specific role
        
        Args:
            uid: User ID
            role: Role to check
            
        Returns:
            True if user has the role, False otherwise
            
        Raises:
            FirebaseException: If checking role fails
        """
        try:
            user_ref = self.db.collection("users").document(uid)
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                return False
            
            user_data = user_doc.to_dict()
            user_role = user_data.get("role")
            
            # Handle the case where role is still stored as a string
            if isinstance(user_role, str):
                return user_role == role
            
            # For a list of roles, check if the specified role is in the list
            return user_role and role in user_role
            
        except Exception as e:
            raise FirebaseException(f"Error checking user role: {str(e)}")

# Create a singleton instance
try:
    firebase = FirebaseManager()
except FirebaseException as e:
    # This allows the application to load but Firebase functionality won't work
    # The application code should handle FirebaseException appropriately
    print(f"Firebase initialization failed: {str(e)}")
    print("Application will continue, but Firebase functionality will be unavailable.")
    
    # Create a placeholder that will raise exceptions when used
    class FirebaseUnavailable:
        def __getattr__(self, name):
            raise FirebaseException("Firebase is unavailable. Please check your credentials.")
    
    firebase = FirebaseUnavailable()