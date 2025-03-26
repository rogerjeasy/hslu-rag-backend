import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from google.cloud.firestore import Client as FirestoreClient

from app.schemas.statistics import (
    PlatformStatistics,
    CourseStatistics,
    UserStatistics,
    TimeSeriesStatistic,
    TimeSeriesDataPoint,
    PublicStatistics
)
from app.core.exceptions import FirebaseException, NotFoundException

logger = logging.getLogger(__name__)

class StatisticsService:
    """Service for managing platform statistics"""
    
    def __init__(self, firestore_client: FirestoreClient):
        """Initialize with Firestore client"""
        self.db = firestore_client
        
    async def get_platform_statistics(self) -> PlatformStatistics:
        """
        Get platform-wide statistics
        
        Returns:
            PlatformStatistics object
        """
        try:
            stats_ref = self.db.collection("statistics").document("platform")
            stats_doc = stats_ref.get()
            
            if not stats_doc.exists:
                # Create default stats document if it doesn't exist
                default_stats = PlatformStatistics().dict()
                stats_ref.set(default_stats)
                return PlatformStatistics()
            
            stats_data = stats_doc.to_dict()
            
            # Convert timestamp fields back to datetime
            if "last_updated" in stats_data and stats_data["last_updated"]:
                stats_data["last_updated"] = stats_data["last_updated"].replace(tzinfo=None)
                
            return PlatformStatistics(**stats_data)
            
        except Exception as e:
            logger.error(f"Error getting platform statistics: {str(e)}")
            raise FirebaseException(f"Failed to get platform statistics: {str(e)}")
    
    async def get_public_statistics(self) -> PublicStatistics:
        """
        Get public statistics that don't require authentication
        
        Returns:
            PublicStatistics object
        """
        try:
            # Get the platform statistics first
            platform_stats = await self.get_platform_statistics()
            
            # Get the most active courses (top 5)
            active_courses = []
            courses_query = self.db.collection("statistics").document("courses").collection("data")
            courses_query = courses_query.order_by("enrolled_students", direction="DESCENDING").limit(5)
            
            for course_doc in courses_query.stream():
                course_data = course_doc.to_dict()
                active_courses.append({
                    "id": course_data.get("course_id"),
                    "name": course_data.get("course_name"),
                    "enrolledStudents": course_data.get("enrolled_students", 0)
                })
                
            # Construct the public statistics response
            public_stats = PublicStatistics(
                total_users=platform_stats.total_users,
                total_courses=platform_stats.total_courses,
                total_conversations=platform_stats.total_conversations,
                total_study_guides=platform_stats.total_study_guides,
                total_practice_questions=platform_stats.total_practice_questions,
                active_courses=active_courses,
                last_updated=platform_stats.last_updated
            )
            
            return public_stats
            
        except Exception as e:
            logger.error(f"Error getting public statistics: {str(e)}")
            raise FirebaseException(f"Failed to get public statistics: {str(e)}")
    
    async def get_course_statistics(self, course_id: str) -> CourseStatistics:
        """
        Get statistics for a specific course
        
        Args:
            course_id: The ID of the course
            
        Returns:
            CourseStatistics object
        """
        try:
            stats_ref = self.db.collection("statistics").document("courses").collection("data").document(course_id)
            stats_doc = stats_ref.get()
            
            if not stats_doc.exists:
                raise NotFoundException(f"Statistics for course {course_id} not found")
            
            stats_data = stats_doc.to_dict()
            
            # Convert timestamp fields back to datetime
            if "last_updated" in stats_data and stats_data["last_updated"]:
                stats_data["last_updated"] = stats_data["last_updated"].replace(tzinfo=None)
                
            return CourseStatistics(**stats_data)
            
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error getting course statistics: {str(e)}")
            raise FirebaseException(f"Failed to get course statistics: {str(e)}")
    
    async def get_user_statistics(self, user_id: str) -> UserStatistics:
        """
        Get statistics for a specific user
        
        Args:
            user_id: The ID of the user
            
        Returns:
            UserStatistics object
        """
        try:
            stats_ref = self.db.collection("statistics").document("users").collection("data").document(user_id)
            stats_doc = stats_ref.get()
            
            if not stats_doc.exists:
                # Create default user statistics if it doesn't exist
                default_stats = UserStatistics(user_id=user_id).dict()
                stats_ref.set(default_stats)
                return UserStatistics(user_id=user_id)
            
            stats_data = stats_doc.to_dict()
            
            # Convert timestamp fields back to datetime
            if "last_updated" in stats_data and stats_data["last_updated"]:
                stats_data["last_updated"] = stats_data["last_updated"].replace(tzinfo=None)
            if "last_active" in stats_data and stats_data["last_active"]:
                stats_data["last_active"] = stats_data["last_active"].replace(tzinfo=None)
                
            return UserStatistics(**stats_data)
            
        except Exception as e:
            logger.error(f"Error getting user statistics: {str(e)}")
            raise FirebaseException(f"Failed to get user statistics: {str(e)}")
    
    async def get_time_series_statistics(self, metric_name: str) -> TimeSeriesStatistic:
        """
        Get time series statistics for a specific metric
        
        Args:
            metric_name: The name of the metric
            
        Returns:
            TimeSeriesStatistic object
        """
        try:
            stats_ref = self.db.collection("statistics").document("time_series").collection("metrics").document(metric_name)
            stats_doc = stats_ref.get()
            
            if not stats_doc.exists:
                raise NotFoundException(f"Time series statistics for metric {metric_name} not found")
            
            stats_data = stats_doc.to_dict()
            
            # Convert timestamp fields back to datetime
            if "last_updated" in stats_data and stats_data["last_updated"]:
                stats_data["last_updated"] = stats_data["last_updated"].replace(tzinfo=None)
                
            # Convert data points timestamps
            if "data_points" in stats_data:
                for dp in stats_data["data_points"]:
                    if "timestamp" in dp and dp["timestamp"]:
                        dp["timestamp"] = dp["timestamp"].replace(tzinfo=None)
                
            return TimeSeriesStatistic(**stats_data)
            
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error getting time series statistics: {str(e)}")
            raise FirebaseException(f"Failed to get time series statistics: {str(e)}")
    
    async def update_platform_statistics(self, stats_update: Dict[str, Any]) -> PlatformStatistics:
        """
        Update platform-wide statistics
        
        Args:
            stats_update: Dictionary of statistics to update
            
        Returns:
            Updated PlatformStatistics object
        """
        try:
            stats_ref = self.db.collection("statistics").document("platform")
            stats_doc = stats_ref.get()
            
            if not stats_doc.exists:
                # Create default stats document if it doesn't exist
                default_stats = PlatformStatistics().dict()
                stats_ref.set(default_stats)
                current_stats = PlatformStatistics()
            else:
                current_stats_data = stats_doc.to_dict()
                # Convert timestamp fields back to datetime
                if "last_updated" in current_stats_data and current_stats_data["last_updated"]:
                    current_stats_data["last_updated"] = current_stats_data["last_updated"].replace(tzinfo=None)
                current_stats = PlatformStatistics(**current_stats_data)
            
            # Update the statistics
            stats_update["last_updated"] = datetime.utcnow()
            stats_ref.update(stats_update)
            
            # Merge the updates with current stats
            updated_stats_dict = current_stats.dict()
            updated_stats_dict.update(stats_update)
            
            return PlatformStatistics(**updated_stats_dict)
            
        except Exception as e:
            logger.error(f"Error updating platform statistics: {str(e)}")
            raise FirebaseException(f"Failed to update platform statistics: {str(e)}")
    
    async def update_course_statistics(self, course_id: str, stats_update: Dict[str, Any]) -> CourseStatistics:
        """
        Update statistics for a specific course
        
        Args:
            course_id: The ID of the course
            stats_update: Dictionary of statistics to update
            
        Returns:
            Updated CourseStatistics object
        """
        try:
            stats_ref = self.db.collection("statistics").document("courses").collection("data").document(course_id)
            stats_doc = stats_ref.get()
            
            # Get course details to include in statistics
            course_ref = self.db.collection("courses").document(course_id)
            course_doc = course_ref.get()
            
            if not course_doc.exists:
                raise NotFoundException(f"Course {course_id} not found")
                
            course_data = course_doc.to_dict()
            course_name = course_data.get("title", "Unknown Course")
            
            if not stats_doc.exists:
                # Create default course statistics if it doesn't exist
                default_stats = CourseStatistics(
                    course_id=course_id,
                    course_name=course_name
                ).dict()
                stats_ref.set(default_stats)
                current_stats = CourseStatistics(
                    course_id=course_id,
                    course_name=course_name
                )
            else:
                current_stats_data = stats_doc.to_dict()
                # Convert timestamp fields back to datetime
                if "last_updated" in current_stats_data and current_stats_data["last_updated"]:
                    current_stats_data["last_updated"] = current_stats_data["last_updated"].replace(tzinfo=None)
                current_stats = CourseStatistics(**current_stats_data)
            
            # Update the statistics
            stats_update["last_updated"] = datetime.utcnow()
            # Ensure course name is always up to date
            stats_update["course_name"] = course_name
            stats_ref.update(stats_update)
            
            # Merge the updates with current stats
            updated_stats_dict = current_stats.dict()
            updated_stats_dict.update(stats_update)
            
            return CourseStatistics(**updated_stats_dict)
            
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error updating course statistics: {str(e)}")
            raise FirebaseException(f"Failed to update course statistics: {str(e)}")
    
    async def update_user_statistics(self, user_id: str, stats_update: Dict[str, Any]) -> UserStatistics:
        """
        Update statistics for a specific user
        
        Args:
            user_id: The ID of the user
            stats_update: Dictionary of statistics to update
            
        Returns:
            Updated UserStatistics object
        """
        try:
            stats_ref = self.db.collection("statistics").document("users").collection("data").document(user_id)
            stats_doc = stats_ref.get()
            
            if not stats_doc.exists:
                # Create default user statistics if it doesn't exist
                default_stats = UserStatistics(user_id=user_id).dict()
                stats_ref.set(default_stats)
                current_stats = UserStatistics(user_id=user_id)
            else:
                current_stats_data = stats_doc.to_dict()
                # Convert timestamp fields back to datetime
                if "last_updated" in current_stats_data and current_stats_data["last_updated"]:
                    current_stats_data["last_updated"] = current_stats_data["last_updated"].replace(tzinfo=None)
                if "last_active" in current_stats_data and current_stats_data["last_active"]:
                    current_stats_data["last_active"] = current_stats_data["last_active"].replace(tzinfo=None)
                current_stats = UserStatistics(**current_stats_data)
            
            # Update the statistics
            stats_update["last_updated"] = datetime.utcnow()
            stats_ref.update(stats_update)
            
            # Merge the updates with current stats
            updated_stats_dict = current_stats.dict()
            updated_stats_dict.update(stats_update)
            
            return UserStatistics(**updated_stats_dict)
            
        except Exception as e:
            logger.error(f"Error updating user statistics: {str(e)}")
            raise FirebaseException(f"Failed to update user statistics: {str(e)}")
    
    async def add_time_series_data_point(self, metric_name: str, metric_type: str, value: float) -> TimeSeriesStatistic:
        """
        Add a data point to a time series metric
        
        Args:
            metric_name: The name of the metric
            metric_type: The type of the metric (count, percentage, etc.)
            value: The value of the data point
            
        Returns:
            Updated TimeSeriesStatistic object
        """
        try:
            stats_ref = self.db.collection("statistics").document("time_series").collection("metrics").document(metric_name)
            stats_doc = stats_ref.get()
            
            now = datetime.utcnow()
            new_data_point = TimeSeriesDataPoint(timestamp=now, value=value).dict()
            
            if not stats_doc.exists:
                # Create new time series metric if it doesn't exist
                new_metric = TimeSeriesStatistic(
                    metric_name=metric_name,
                    metric_type=metric_type,
                    data_points=[new_data_point],
                    last_updated=now
                ).dict()
                stats_ref.set(new_metric)
                return TimeSeriesStatistic(**new_metric)
            
            # Get existing data and add new data point
            stats_data = stats_doc.to_dict()
            
            # Convert timestamp fields back to datetime
            if "last_updated" in stats_data and stats_data["last_updated"]:
                stats_data["last_updated"] = stats_data["last_updated"].replace(tzinfo=None)
                
            # Convert data points timestamps
            data_points = stats_data.get("data_points", [])
            for dp in data_points:
                if "timestamp" in dp and dp["timestamp"]:
                    dp["timestamp"] = dp["timestamp"].replace(tzinfo=None)
            
            # Add new data point
            data_points.append(new_data_point)
            
            # Limit to last 30 data points to prevent excessive growth
            if len(data_points) > 30:
                data_points = sorted(data_points, key=lambda dp: dp["timestamp"], reverse=True)[:30]
            
            # Update in Firestore
            stats_ref.update({
                "data_points": data_points,
                "last_updated": now
            })
            
            # Update the stats_data and return
            stats_data["data_points"] = data_points
            stats_data["last_updated"] = now
            
            return TimeSeriesStatistic(**stats_data)
            
        except Exception as e:
            logger.error(f"Error adding time series data point: {str(e)}")
            raise FirebaseException(f"Failed to add time series data point: {str(e)}")
    
    async def calculate_and_update_statistics(self) -> None:
        """
        Calculate and update all platform statistics based on current database state.
        This method should be called periodically to refresh statistics.
        """
        try:
            # Start with a transaction to ensure consistent reads
            transaction = self.db.transaction()
            
            # Calculate platform-wide statistics
            total_users = 0
            for _ in self.db.collection("users").stream():
                total_users += 1
                
            total_courses = 0
            for _ in self.db.collection("courses").stream():
                total_courses += 1
                
            total_conversations = 0
            for _ in self.db.collection("conversations").stream():
                total_conversations += 1
                
            total_study_guides = 0
            for _ in self.db.collection("study_guides").stream():
                total_study_guides += 1
                
            total_practice_questions = 0
            for _ in self.db.collection("practice_questions").stream():
                total_practice_questions += 1
                
            total_knowledge_gaps = 0
            for _ in self.db.collection("knowledge_gaps").stream():
                total_knowledge_gaps += 1
                
            # Calculate active users
            now = datetime.utcnow()
            one_day_ago = now - timedelta(days=1)
            one_week_ago = now - timedelta(days=7)
            one_month_ago = now - timedelta(days=30)
            
            active_users_last_day = 0
            active_users_last_week = 0
            active_users_last_month = 0
            
            for user_doc in self.db.collection("users").stream():
                user_data = user_doc.to_dict()
                last_login = user_data.get("last_login_at")
                
                if isinstance(last_login, int):
                    last_login = datetime.fromtimestamp(last_login)
                
                if last_login:
                    if last_login >= one_day_ago:
                        active_users_last_day += 1
                    if last_login >= one_week_ago:
                        active_users_last_week += 1
                    if last_login >= one_month_ago:
                        active_users_last_month += 1
            
            # Update platform statistics
            platform_stats_update = {
                "total_users": total_users,
                "total_courses": total_courses,
                "total_conversations": total_conversations,
                "total_study_guides": total_study_guides,
                "total_practice_questions": total_practice_questions,
                "total_knowledge_gaps": total_knowledge_gaps,
                "active_users_last_day": active_users_last_day,
                "active_users_last_week": active_users_last_week,
                "active_users_last_month": active_users_last_month,
                "last_updated": now
            }
            
            await self.update_platform_statistics(platform_stats_update)
            
            # Calculate and update course statistics
            for course_doc in self.db.collection("courses").stream():
                course_id = course_doc.id
                course_data = course_doc.to_dict()
                course_name = course_data.get("title", "Unknown Course")
                
                # Count enrolled students
                enrolled_students = 0
                active_students_last_week = 0
                active_students_last_month = 0
                
                for user_doc in self.db.collection("users").stream():
                    user_data = user_doc.to_dict()
                    user_courses = user_data.get("courses", [])
                    
                    is_enrolled = False
                    for user_course in user_courses:
                        if isinstance(user_course, dict) and user_course.get("course_id") == course_id:
                            is_enrolled = True
                            break
                        elif isinstance(user_course, str) and user_course == course_id:
                            is_enrolled = True
                            break
                    
                    if is_enrolled:
                        enrolled_students += 1
                        
                        # Check if active recently
                        last_login = user_data.get("last_login_at")
                        if isinstance(last_login, int):
                            last_login = datetime.fromtimestamp(last_login)
                            
                        if last_login:
                            if last_login >= one_week_ago:
                                active_students_last_week += 1
                            if last_login >= one_month_ago:
                                active_students_last_month += 1
                
                # Count course-specific activities
                course_conversations = 0
                for conv_doc in self.db.collection("conversations").stream():
                    conv_data = conv_doc.to_dict()
                    if conv_data.get("course_id") == course_id:
                        course_conversations += 1
                
                course_study_guides = 0
                for guide_doc in self.db.collection("study_guides").stream():
                    guide_data = guide_doc.to_dict()
                    if guide_data.get("course_id") == course_id:
                        course_study_guides += 1
                
                course_practice_questions = 0
                for questions_doc in self.db.collection("practice_questions").stream():
                    questions_data = questions_doc.to_dict()
                    if questions_data.get("course_id") == course_id:
                        course_practice_questions += 1
                
                course_knowledge_gaps = 0
                for gap_doc in self.db.collection("knowledge_gaps").stream():
                    gap_data = gap_doc.to_dict()
                    if gap_data.get("course_id") == course_id:
                        course_knowledge_gaps += 1
                
                # Analyze most discussed topics and difficult topics
                # This would require more complex analysis of conversations and knowledge gaps
                # For now, we'll use placeholder data
                most_discussed_topics = []
                most_difficult_topics = []
                
                # Update course statistics
                course_stats_update = {
                    "course_id": course_id,
                    "course_name": course_name,
                    "enrolled_students": enrolled_students,
                    "total_conversations": course_conversations,
                    "total_study_guides": course_study_guides,
                    "total_practice_questions": course_practice_questions,
                    "total_knowledge_gaps": course_knowledge_gaps,
                    "active_students_last_week": active_students_last_week,
                    "active_students_last_month": active_students_last_month,
                    "most_discussed_topics": most_discussed_topics,
                    "most_difficult_topics": most_difficult_topics,
                    "last_updated": now
                }
                
                await self.update_course_statistics(course_id, course_stats_update)
            
            # Add time series data points for tracking trends
            await self.add_time_series_data_point("total_users", "count", total_users)
            await self.add_time_series_data_point("active_users_weekly", "count", active_users_last_week)
            await self.add_time_series_data_point("total_conversations", "count", total_conversations)
            
            logger.info("Successfully calculated and updated all statistics")
            
        except Exception as e:
            logger.error(f"Error calculating statistics: {str(e)}")
            raise FirebaseException(f"Failed to calculate statistics: {str(e)}")