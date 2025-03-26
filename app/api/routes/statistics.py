from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from app.schemas.statistics import (
    StatisticsResponse, 
    PlatformStatistics, 
    CourseStatistics, 
    UserStatistics,
    TimeSeriesStatistic,
    PublicStatistics
)
from app.dto.statistics_dto import (
    FrontendPlatformStatisticsDTO,
    FrontendCourseStatisticsDTO,
    FrontendUserStatisticsDTO,
    FrontendTimeSeriesStatisticDTO,
    FrontendPublicStatisticsDTO
)
from app.services.statistics_service import StatisticsService
from app.core.security import (
    get_current_user_id, 
    check_admin_role,
    check_admin_or_instructor_role
)
from app.core.firebase import firebase
from app.core.exceptions import BaseAPIException

router = APIRouter(prefix="/statistics", tags=["statistics"])

# Initialize service
statistics_service = StatisticsService(firebase.get_firestore())

@router.get("/public", response_model=Dict[str, Any])
async def get_public_statistics():
    """
    Get public statistics about the platform that don't require authentication.
    
    Returns platform-wide statistics like total users, courses, and activity levels.
    """
    try:
        stats = await statistics_service.get_public_statistics()
        return {
            "success": True,
            "data": FrontendPublicStatisticsDTO.from_backend(stats)
        }
    except BaseAPIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve public statistics: {str(e)}"
        )

@router.get("/platform", response_model=Dict[str, Any])
async def get_platform_statistics(
    admin_id: str = Depends(check_admin_role)
):
    """
    Get comprehensive platform-wide statistics.
    
    Admin access only. Returns detailed statistics about platform usage.
    """
    try:
        stats = await statistics_service.get_platform_statistics()
        return {
            "success": True,
            "data": FrontendPlatformStatisticsDTO.from_backend(stats)
        }
    except BaseAPIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve platform statistics: {str(e)}"
        )

@router.get("/course/{course_id}", response_model=Dict[str, Any])
async def get_course_statistics(
    course_id: str,
    current_user_or_admin: str = Depends(check_admin_or_instructor_role)
):
    """
    Get statistics for a specific course.
    
    Admin or instructor access only. Returns detailed statistics about a course.
    """
    try:
        stats = await statistics_service.get_course_statistics(course_id)
        return {
            "success": True,
            "data": FrontendCourseStatisticsDTO.from_backend(stats)
        }
    except BaseAPIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve course statistics: {str(e)}"
        )

@router.get("/courses", response_model=Dict[str, Any])
async def get_all_courses_statistics(
    limit: int = Query(10, ge=1, le=100),
    skip: int = Query(0, ge=0),
    admin_id: str = Depends(check_admin_role)
):
    """
    Get statistics for all courses.
    
    Admin access only. Returns statistics summary for multiple courses.
    """
    try:
        # Get statistics for all courses from Firestore
        courses_ref = firebase.get_firestore().collection("statistics").document("courses").collection("data")
        query = courses_ref.limit(limit).offset(skip)
        
        courses_stats = []
        for doc in query.stream():
            course_stats_data = doc.to_dict()
            
            # Convert timestamp fields back to datetime
            if "last_updated" in course_stats_data and course_stats_data["last_updated"]:
                course_stats_data["last_updated"] = course_stats_data["last_updated"].replace(tzinfo=None)
                
            course_stats = CourseStatistics(**course_stats_data)
            courses_stats.append(FrontendCourseStatisticsDTO.from_backend(course_stats))
        
        return {
            "success": True,
            "data": courses_stats,
            "pagination": {
                "limit": limit,
                "skip": skip,
                "total": len(courses_stats)  # This is not the total count, just the returned count
            }
        }
    except BaseAPIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve courses statistics: {str(e)}"
        )

@router.get("/user", response_model=Dict[str, Any])
async def get_my_statistics(
    current_user_id: str = Depends(get_current_user_id)
):
    """
    Get statistics for the currently authenticated user.
    
    Returns personal usage statistics for the current user.
    """
    try:
        stats = await statistics_service.get_user_statistics(current_user_id)
        return {
            "success": True,
            "data": FrontendUserStatisticsDTO.from_backend(stats)
        }
    except BaseAPIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user statistics: {str(e)}"
        )

@router.get("/user/{user_id}", response_model=Dict[str, Any])
async def get_user_statistics(
    user_id: str,
    admin_id: str = Depends(check_admin_role)
):
    """
    Get statistics for a specific user.
    
    Admin access only. Returns usage statistics for the specified user.
    """
    try:
        stats = await statistics_service.get_user_statistics(user_id)
        return {
            "success": True,
            "data": FrontendUserStatisticsDTO.from_backend(stats)
        }
    except BaseAPIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user statistics: {str(e)}"
        )

@router.get("/timeseries/{metric_name}", response_model=Dict[str, Any])
async def get_timeseries_statistics(
    metric_name: str,
    admin_id: str = Depends(check_admin_role)
):
    """
    Get time series statistics for a specific metric.
    
    Admin access only. Returns historical data points for trend analysis.
    """
    try:
        stats = await statistics_service.get_time_series_statistics(metric_name)
        return {
            "success": True,
            "data": FrontendTimeSeriesStatisticDTO.from_backend(stats)
        }
    except BaseAPIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve time series statistics: {str(e)}"
        )

@router.post("/calculate", status_code=status.HTTP_200_OK)
async def calculate_statistics(
    admin_id: str = Depends(check_admin_role)
):
    """
    Manually trigger calculation and update of all platform statistics.
    
    Admin access only. This can be a resource-intensive operation.
    """
    try:
        await statistics_service.calculate_and_update_statistics()
        return {
            "success": True,
            "message": "Statistics have been calculated and updated successfully"
        }
    except BaseAPIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate statistics: {str(e)}"
        )