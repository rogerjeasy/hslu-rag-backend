"""
Migration script to convert user roles from strings to lists.

This script should be run once after updating the backend code to support
role lists instead of role strings.
"""
import firebase_admin
from firebase_admin import credentials, firestore
import time
import os
import json
from typing import Dict, Any, List

# Initialize Firebase
def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    # Load service account key from environment variable or file
    firebase_credentials = os.environ.get("FIREBASE_CREDENTIALS")
    
    if not firebase_credentials:
        print("ERROR: FIREBASE_CREDENTIALS environment variable not set")
        exit(1)
    
    try:
        if os.path.isfile(firebase_credentials):
            # Load from file
            cred = credentials.Certificate(firebase_credentials)
        else:
            # Load from environment variable (JSON string)
            service_account_info = json.loads(firebase_credentials)
            cred = credentials.Certificate(service_account_info)
            
        # Initialize Firebase Admin
        firebase_admin.initialize_app(cred)
        
        # Initialize and return Firestore client
        return firestore.client()
    except Exception as e:
        print(f"ERROR: Failed to initialize Firebase: {str(e)}")
        exit(1)

def migrate_user_roles(db):
    """
    Migrate user roles from strings to lists in Firestore
    
    Args:
        db: Firestore database client
    """
    users_ref = db.collection("users")
    batch = db.batch()
    batch_count = 0
    total_users = 0
    updated_users = 0
    
    print("Starting user role migration...")
    
    try:
        # Get all users
        users = users_ref.stream()
        
        for user_doc in users:
            total_users += 1
            user_data = user_doc.to_dict()
            
            # Check if role is a string
            if "role" in user_data and isinstance(user_data["role"], str):
                # Convert to list
                user_ref = users_ref.document(user_doc.id)
                batch.update(user_ref, {"role": [user_data["role"]]})
                updated_users += 1
                batch_count += 1
                
                # Commit batch every 500 updates to avoid hitting limits
                if batch_count >= 500:
                    batch.commit()
                    print(f"Processed batch of {batch_count} users")
                    batch = db.batch()
                    batch_count = 0
                    
                    # Sleep a bit to avoid rate limiting
                    time.sleep(1)
            
            # If user has no role, add default role
            elif "role" not in user_data:
                user_ref = users_ref.document(user_doc.id)
                batch.update(user_ref, {"role": ["student"]})
                updated_users += 1
                batch_count += 1
                
                # Commit batch every 500 updates to avoid hitting limits
                if batch_count >= 500:
                    batch.commit()
                    print(f"Processed batch of {batch_count} users")
                    batch = db.batch()
                    batch_count = 0
                    
                    # Sleep a bit to avoid rate limiting
                    time.sleep(1)
        
        # Commit any remaining updates
        if batch_count > 0:
            batch.commit()
            print(f"Processed final batch of {batch_count} users")
        
        print(f"Migration complete! Updated {updated_users} of {total_users} users.")
        
    except Exception as e:
        print(f"ERROR: Migration failed: {str(e)}")
        exit(1)

if __name__ == "__main__":
    db = initialize_firebase()
    migrate_user_roles(db)