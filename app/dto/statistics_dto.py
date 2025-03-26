from typing import List, Dict, Any, Optional
from datetime import datetime
from app.schemas.statistics import (
    PlatformStatistics,
    CourseStatistics,
    UserStatistics,
    TimeSeriesStatistic,
    PublicStatistics
)


class FrontendStatisticsBaseDTO:
    """Base DTO for all statistics responses"""
    @staticmethod
    def format_datetime(dt: datetime) -> str:
        """Format datetime to ISO format string"""
        if dt:
            return dt.isoformat()
        return None


class FrontendPlatformStatisticsDTO(FrontendStatisticsBaseDTO):
    """DTO for platform-wide statistics"""
    @classmethod
    def from_backend(cls, stats: PlatformStatistics) -> Dict[str, Any]:
        """Convert backend PlatformStatistics to frontend format"""
        return {
            "totalUsers": stats.total_users,
            "totalCourses": stats.total_courses,
            "totalConversations": stats.total_conversations,
            "totalMessages": stats.total_messages,
            "totalStudyGuides": stats.total_study_guides,
            "totalPracticeQuestions": stats.total_practice_questions,
            "totalKnowledgeGaps": stats.total_knowledge_gaps,
            "activeUsersLastDay": stats.active_users_last_day,
            "activeUsersLastWeek": stats.active_users_last_week,
            "activeUsersLastMonth": stats.active_users_last_month,
            "lastUpdated": cls.format_datetime(stats.last_updated)
        }


class FrontendCourseStatisticsDTO(FrontendStatisticsBaseDTO):
    """DTO for course-specific statistics"""
    @classmethod
    def from_backend(cls, stats: CourseStatistics) -> Dict[str, Any]:
        """Convert backend CourseStatistics to frontend format"""
        return {
            "courseId": stats.course_id,
            "courseName": stats.course_name,
            "enrolledStudents": stats.enrolled_students,
            "totalConversations": stats.total_conversations,
            "totalMessages": stats.total_messages,
            "totalStudyGuides": stats.total_study_guides,
            "totalPracticeQuestions": stats.total_practice_questions,
            "totalKnowledgeGaps": stats.total_knowledge_gaps,
            "activeStudentsLastWeek": stats.active_students_last_week,
            "activeStudentsLastMonth": stats.active_students_last_month,
            "mostDiscussedTopics": stats.most_discussed_topics,
            "mostDifficultTopics": stats.most_difficult_topics,
            "lastUpdated": cls.format_datetime(stats.last_updated)
        }


class FrontendUserStatisticsDTO(FrontendStatisticsBaseDTO):
    """DTO for user-specific statistics"""
    @classmethod
    def from_backend(cls, stats: UserStatistics) -> Dict[str, Any]:
        """Convert backend UserStatistics to frontend format"""
        return {
            "userId": stats.user_id,
            "coursesEnrolled": stats.courses_enrolled,
            "totalConversations": stats.total_conversations,
            "totalMessages": stats.total_messages,
            "totalStudyGuides": stats.total_study_guides,
            "totalPracticeQuestions": stats.total_practice_questions,
            "totalKnowledgeGaps": stats.total_knowledge_gaps,
            "lastActive": cls.format_datetime(stats.last_active) if stats.last_active else None,
            "averageSessionDuration": stats.average_session_duration,
            "totalStudyTime": stats.total_study_time,
            "strongestTopics": stats.strongest_topics,
            "weakestTopics": stats.weakest_topics,
            "lastUpdated": cls.format_datetime(stats.last_updated)
        }


class FrontendTimeSeriesStatisticDTO(FrontendStatisticsBaseDTO):
    """DTO for time series statistics"""
    @classmethod
    def from_backend(cls, stats: TimeSeriesStatistic) -> Dict[str, Any]:
        """Convert backend TimeSeriesStatistic to frontend format"""
        return {
            "metricName": stats.metric_name,
            "metricType": stats.metric_type,
            "dataPoints": [
                {
                    "timestamp": cls.format_datetime(dp.timestamp),
                    "value": dp.value
                } 
                for dp in stats.data_points
            ],
            "lastUpdated": cls.format_datetime(stats.last_updated)
        }


class FrontendPublicStatisticsDTO(FrontendStatisticsBaseDTO):
    """DTO for public statistics"""
    @classmethod
    def from_backend(cls, stats: PublicStatistics) -> Dict[str, Any]:
        """Convert backend PublicStatistics to frontend format"""
        return {
            "totalUsers": stats.total_users,
            "totalCourses": stats.total_courses,
            "totalConversations": stats.total_conversations,
            "totalStudyGuides": stats.total_study_guides,
            "totalPracticeQuestions": stats.total_practice_questions,
            "activeCourses": stats.active_courses,
            "lastUpdated": cls.format_datetime(stats.last_updated)
        }