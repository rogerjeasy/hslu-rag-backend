import json
import os
from typing import Optional
import firebase_admin
from firebase_admin import credentials, auth, firestore
from google.cloud.firestore import Client as FirestoreClient
from google.oauth2 import service_account
from app.core.config import settings
from app.core.exceptions import AuthenticationException, FirebaseException

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