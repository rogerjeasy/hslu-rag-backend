# app/dto/auth_dto.py
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, EmailStr, Field
from app.schemas.auth import UserCreate, UserProfileUpdate, UserResponse, CourseEnrollment, Token

class FrontendUserRegisterDTO(BaseModel):
    """DTO for mapping frontend registration data to backend UserCreate schema"""
    name: str
    email: EmailStr
    password: str
    confirmPassword: str
    studentId: Optional[str] = None
    program: Optional[str] = None
    semester: Optional[int] = None
    terms: bool

    def to_user_create(self) -> UserCreate:
        """Convert frontend DTO to backend UserCreate schema"""
        # Extract first and last name from the full name if possible
        name_parts = self.name.split(" ", 1)
        first_name = name_parts[0] if len(name_parts) > 0 else None
        last_name = name_parts[1] if len(name_parts) > 1 else None
        
        return UserCreate(
            email=self.email,
            password=self.password,
            display_name=self.name,
            first_name=first_name,
            last_name=last_name,
            student_id=self.studentId,
            program=self.program,
            semester=self.semester
        )

class FrontendUserProfileUpdateDTO(BaseModel):
    """DTO for mapping frontend profile update data to backend UserProfileUpdate schema"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    studentId: Optional[str] = None
    program: Optional[str] = None
    semester: Optional[int] = None
    photoUrl: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None

    def to_user_profile_update(self) -> UserProfileUpdate:
        """Convert frontend DTO to backend UserProfileUpdate schema"""
        # Extract first and last name from the full name if possible
        first_name = None
        last_name = None
        if self.name:
            name_parts = self.name.split(" ", 1)
            first_name = name_parts[0] if len(name_parts) > 0 else None
            last_name = name_parts[1] if len(name_parts) > 1 else None
        
        return UserProfileUpdate(
            display_name=self.name,
            photo_url=self.photoUrl,
            student_id=self.studentId,
            program=self.program,
            semester=self.semester,
            preferences=self.preferences
        )

class FrontendLoginDTO(BaseModel):
    """DTO for mapping frontend login data"""
    email: EmailStr
    password: str

class FrontendCourseEnrollmentDTO(BaseModel):
    """DTO for mapping course enrollment to frontend format"""
    courseId: str
    enrolledAt: str
    
    @classmethod
    def from_backend(cls, enrollment: CourseEnrollment) -> 'FrontendCourseEnrollmentDTO':
        """Convert backend enrollment to frontend format"""
        return cls(
            courseId=enrollment.course_id,
            enrolledAt=enrollment.enrolled_at
        )

class FrontendUserResponseDTO(BaseModel):
    """DTO for mapping backend user response to frontend format"""
    id: str
    email: EmailStr
    name: str
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    photoUrl: Optional[str] = None
    role: List[str] = ["student"]  # Changed from string to list of strings
    createdAt: Optional[int] = None
    lastLoginAt: Optional[int] = None
    studentId: Optional[str] = None
    program: Optional[str] = None
    semester: Optional[int] = None
    courses: List[FrontendCourseEnrollmentDTO] = []
    preferences: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_backend(cls, user: UserResponse) -> 'FrontendUserResponseDTO':
        """Convert backend UserResponse to frontend format"""
        # If display_name is not available, construct from first and last name
        display_name = user.display_name
        if not display_name and (user.first_name or user.last_name):
            display_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        
        # Ensure role is a list for backward compatibility
        user_roles = user.role if user.role else ["student"]
        if isinstance(user_roles, str):
            user_roles = [user_roles]
        
        return cls(
            id=user.id,
            email=user.email,
            name=display_name or "",
            firstName=user.first_name,
            lastName=user.last_name,
            photoUrl=user.photo_url,
            role=user_roles,  # Now using the list of roles
            createdAt=user.created_at,
            lastLoginAt=user.last_login_at,
            studentId=user.student_id,
            program=user.program,
            semester=user.semester,
            courses=[FrontendCourseEnrollmentDTO.from_backend(course) for course in (user.courses or [])],
            preferences=user.preferences
        )

class FrontendTokenDTO(BaseModel):
    """DTO for mapping backend token data to frontend format"""
    accessToken: str
    tokenType: str = "bearer"
    expiresIn: int
    refreshToken: Optional[str] = None
    user: FrontendUserResponseDTO
    
    @classmethod
    def from_backend(cls, token: Token) -> 'FrontendTokenDTO':
        """Convert backend Token to frontend format"""
        return cls(
            accessToken=token.access_token,
            tokenType=token.token_type,
            expiresIn=token.expires_in,
            refreshToken=token.refresh_token,
            user=FrontendUserResponseDTO.from_backend(token.user)
        )