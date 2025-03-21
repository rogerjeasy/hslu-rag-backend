from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field

class UserBase(BaseModel):
    """Base model for user data"""
    email: EmailStr
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[List[str]] = ["student"]

class UserCreate(UserBase):
    """Schema for user registration"""
    password: str = Field(..., min_length=8)
    student_id: Optional[str] = None
    program: Optional[str] = None
    semester: Optional[int] = None

class LoginCredentials(BaseModel):
    """Schema for login credentials"""
    email: EmailStr
    password: str

class UserProfileUpdate(BaseModel):
    """Schema for user profile updates"""
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    student_id: Optional[str] = None
    program: Optional[str] = None
    semester: Optional[int] = None
    preferences: Optional[dict] = None

class CourseEnrollment(BaseModel):
    """Schema for course enrollment data"""
    course_id: str
    enrolled_at: str

class UserResponse(UserBase):
    """Schema for user data in responses"""
    id: str
    created_at: Optional[int] = None
    last_login_at: Optional[int] = None
    student_id: Optional[str] = None
    program: Optional[str] = None
    semester: Optional[int] = None
    courses: Optional[List[CourseEnrollment]] = []
    preferences: Optional[dict] = None
    role: Optional[List[str]] = ["student"]
    
    class Config:
        orm_mode = True

class Token(BaseModel):
    """Schema for authentication token"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    user: UserResponse

class TokenData(BaseModel):
    """Schema for token payload data"""
    uid: str
    email: Optional[str] = None
    role: Optional[List[str]] = None
    exp: Optional[int] = None