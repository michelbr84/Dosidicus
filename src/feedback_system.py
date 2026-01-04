# src/feedback_system.py
"""
User Feedback Integration System - Collects and manages user feedback.
"""

import os
import json
import time
import logging
import hashlib
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """Types of feedback."""
    BUG_REPORT = "bug_report"
    FEATURE_REQUEST = "feature_request"
    GENERAL = "general"
    RATING = "rating"
    SUGGESTION = "suggestion"
    CRASH_REPORT = "crash_report"


class FeedbackPriority(Enum):
    """Priority levels for feedback."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class UserFeedback:
    """A single feedback entry."""
    id: str
    type: FeedbackType
    title: str
    description: str
    priority: FeedbackPriority
    created_at: float
    user_id: Optional[str] = None
    email: Optional[str] = None
    attachments: List[str] = None
    metadata: Dict[str, Any] = None
    status: str = "new"
    
    def __post_init__(self):
        if self.attachments is None:
            self.attachments = []
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['type'] = self.type.value
        data['priority'] = self.priority.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserFeedback':
        data['type'] = FeedbackType(data['type'])
        data['priority'] = FeedbackPriority(data['priority'])
        return cls(**data)


@dataclass
class FeedbackAnalytics:
    """Analytics summary of feedback."""
    total_count: int
    by_type: Dict[str, int]
    by_priority: Dict[str, int]
    by_status: Dict[str, int]
    average_rating: float
    recent_trend: str  # "improving", "declining", "stable"
    top_requested_features: List[str]
    common_issues: List[str]


class FeedbackStorage:
    """Stores and retrieves feedback data."""
    
    def __init__(self, storage_dir: Path = None):
        """
        Initialize feedback storage.
        
        Args:
            storage_dir: Directory for storing feedback files
        """
        if storage_dir is None:
            storage_dir = Path.home() / '.dosidicus' / 'feedback'
        
        self.storage_dir = storage_dir
        self.feedback_file = storage_dir / 'feedback.json'
        self.analytics_file = storage_dir / 'analytics.json'
        
        # Ensure directory exists
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache
        self._feedback_cache: Dict[str, UserFeedback] = {}
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Load feedback from file into cache."""
        if self.feedback_file.exists():
            try:
                with open(self.feedback_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data:
                        feedback = UserFeedback.from_dict(item)
                        self._feedback_cache[feedback.id] = feedback
            except Exception as e:
                logger.error(f"Failed to load feedback cache: {e}")
    
    def _save_cache(self) -> None:
        """Save cache to file."""
        try:
            data = [fb.to_dict() for fb in self._feedback_cache.values()]
            with open(self.feedback_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save feedback cache: {e}")
    
    def add(self, feedback: UserFeedback) -> bool:
        """Add new feedback."""
        self._feedback_cache[feedback.id] = feedback
        self._save_cache()
        return True
    
    def get(self, feedback_id: str) -> Optional[UserFeedback]:
        """Get feedback by ID."""
        return self._feedback_cache.get(feedback_id)
    
    def update(self, feedback: UserFeedback) -> bool:
        """Update existing feedback."""
        if feedback.id not in self._feedback_cache:
            return False
        self._feedback_cache[feedback.id] = feedback
        self._save_cache()
        return True
    
    def delete(self, feedback_id: str) -> bool:
        """Delete feedback by ID."""
        if feedback_id not in self._feedback_cache:
            return False
        del self._feedback_cache[feedback_id]
        self._save_cache()
        return True
    
    def get_all(self) -> List[UserFeedback]:
        """Get all feedback."""
        return list(self._feedback_cache.values())
    
    def get_by_type(self, feedback_type: FeedbackType) -> List[UserFeedback]:
        """Get feedback by type."""
        return [fb for fb in self._feedback_cache.values() 
                if fb.type == feedback_type]
    
    def get_by_status(self, status: str) -> List[UserFeedback]:
        """Get feedback by status."""
        return [fb for fb in self._feedback_cache.values() 
                if fb.status == status]


class FeedbackAnalyzer:
    """Analyzes feedback for insights."""
    
    def __init__(self, storage: FeedbackStorage):
        self.storage = storage
    
    def generate_analytics(self) -> FeedbackAnalytics:
        """Generate analytics summary."""
        all_feedback = self.storage.get_all()
        
        if not all_feedback:
            return FeedbackAnalytics(
                total_count=0,
                by_type={},
                by_priority={},
                by_status={},
                average_rating=0.0,
                recent_trend="stable",
                top_requested_features=[],
                common_issues=[]
            )
        
        # Count by type
        by_type = {}
        for fb in all_feedback:
            type_name = fb.type.value
            by_type[type_name] = by_type.get(type_name, 0) + 1
        
        # Count by priority
        by_priority = {}
        for fb in all_feedback:
            priority_name = fb.priority.value
            by_priority[priority_name] = by_priority.get(priority_name, 0) + 1
        
        # Count by status
        by_status = {}
        for fb in all_feedback:
            by_status[fb.status] = by_status.get(fb.status, 0) + 1
        
        # Calculate average rating
        ratings = [fb.metadata.get('rating', 0) for fb in all_feedback 
                   if fb.type == FeedbackType.RATING]
        average_rating = sum(ratings) / len(ratings) if ratings else 0.0
        
        # Determine trend
        recent_trend = self._calculate_trend(all_feedback)
        
        # Extract top features and issues
        top_features = self._extract_top_items(
            [fb for fb in all_feedback if fb.type == FeedbackType.FEATURE_REQUEST]
        )
        common_issues = self._extract_top_items(
            [fb for fb in all_feedback if fb.type == FeedbackType.BUG_REPORT]
        )
        
        return FeedbackAnalytics(
            total_count=len(all_feedback),
            by_type=by_type,
            by_priority=by_priority,
            by_status=by_status,
            average_rating=average_rating,
            recent_trend=recent_trend,
            top_requested_features=top_features[:5],
            common_issues=common_issues[:5]
        )
    
    def _calculate_trend(self, feedback_list: List[UserFeedback]) -> str:
        """Calculate feedback trend based on ratings."""
        # Get feedback from last 30 days
        thirty_days_ago = time.time() - (30 * 24 * 60 * 60)
        recent = [fb for fb in feedback_list if fb.created_at > thirty_days_ago]
        
        if len(recent) < 5:
            return "stable"
        
        # Calculate sentiment from ratings
        ratings = [fb.metadata.get('rating', 3) for fb in recent 
                   if fb.type == FeedbackType.RATING]
        
        if not ratings:
            return "stable"
        
        avg = sum(ratings) / len(ratings)
        if avg > 4:
            return "improving"
        elif avg < 2.5:
            return "declining"
        return "stable"
    
    def _extract_top_items(self, feedback_list: List[UserFeedback]) -> List[str]:
        """Extract most common keywords from feedback."""
        # Simple keyword extraction
        word_counts = {}
        stop_words = {'the', 'a', 'an', 'is', 'it', 'to', 'for', 'and', 'or', 
                     'but', 'in', 'on', 'at', 'be', 'this', 'that', 'with'}
        
        for fb in feedback_list:
            words = fb.title.lower().split()
            for word in words:
                word = word.strip('.,!?;:')
                if word and word not in stop_words and len(word) > 2:
                    word_counts[word] = word_counts.get(word, 0) + 1
        
        # Sort by count
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return [word for word, count in sorted_words[:10]]


class FeedbackManager:
    """
    Main feedback management system.
    
    Provides methods for:
    - Collecting user feedback
    - Managing feedback lifecycle
    - Analyzing feedback trends
    - Exporting feedback data
    """
    
    def __init__(self, storage_dir: Path = None):
        """
        Initialize feedback manager.
        
        Args:
            storage_dir: Directory for feedback storage
        """
        self.storage = FeedbackStorage(storage_dir)
        self.analyzer = FeedbackAnalyzer(self.storage)
        self._callbacks: Dict[str, List[Callable]] = {}
        
        logger.info("FeedbackManager initialized")
    
    def submit_feedback(self,
                       feedback_type: FeedbackType,
                       title: str,
                       description: str,
                       priority: FeedbackPriority = FeedbackPriority.MEDIUM,
                       user_id: Optional[str] = None,
                       email: Optional[str] = None,
                       metadata: Optional[Dict] = None) -> UserFeedback:
        """
        Submit new user feedback.
        
        Args:
            feedback_type: Type of feedback
            title: Short title/summary
            description: Detailed description
            priority: Priority level
            user_id: Optional user identifier
            email: Optional contact email
            metadata: Additional metadata
            
        Returns:
            Created feedback object
        """
        # Generate unique ID
        feedback_id = self._generate_id(title, description)
        
        feedback = UserFeedback(
            id=feedback_id,
            type=feedback_type,
            title=title,
            description=description,
            priority=priority,
            created_at=time.time(),
            user_id=user_id,
            email=email,
            metadata=metadata or {}
        )
        
        self.storage.add(feedback)
        self._trigger_callback('feedback_submitted', feedback)
        
        logger.info(f"Feedback submitted: {feedback_id} ({feedback_type.value})")
        return feedback
    
    def submit_bug_report(self,
                         title: str,
                         description: str,
                         steps_to_reproduce: Optional[str] = None,
                         expected_behavior: Optional[str] = None,
                         actual_behavior: Optional[str] = None,
                         system_info: Optional[Dict] = None) -> UserFeedback:
        """
        Submit a bug report with structured information.
        
        Args:
            title: Bug title
            description: Bug description
            steps_to_reproduce: Steps to reproduce the bug
            expected_behavior: What should happen
            actual_behavior: What actually happens
            system_info: System information
            
        Returns:
            Created feedback object
        """
        metadata = {
            'steps_to_reproduce': steps_to_reproduce,
            'expected_behavior': expected_behavior,
            'actual_behavior': actual_behavior,
            'system_info': system_info or self._get_system_info()
        }
        
        return self.submit_feedback(
            feedback_type=FeedbackType.BUG_REPORT,
            title=title,
            description=description,
            priority=FeedbackPriority.HIGH,
            metadata=metadata
        )
    
    def submit_feature_request(self,
                              title: str,
                              description: str,
                              use_case: Optional[str] = None,
                              priority: FeedbackPriority = FeedbackPriority.MEDIUM) -> UserFeedback:
        """
        Submit a feature request.
        
        Args:
            title: Feature title
            description: Feature description
            use_case: Use case / why this is needed
            priority: Priority level
            
        Returns:
            Created feedback object
        """
        metadata = {
            'use_case': use_case
        }
        
        return self.submit_feedback(
            feedback_type=FeedbackType.FEATURE_REQUEST,
            title=title,
            description=description,
            priority=priority,
            metadata=metadata
        )
    
    def submit_rating(self,
                     rating: int,
                     comment: Optional[str] = None) -> UserFeedback:
        """
        Submit a rating.
        
        Args:
            rating: Rating value (1-5)
            comment: Optional comment
            
        Returns:
            Created feedback object
        """
        rating = max(1, min(5, rating))
        
        return self.submit_feedback(
            feedback_type=FeedbackType.RATING,
            title=f"Rating: {rating}/5",
            description=comment or "",
            priority=FeedbackPriority.LOW,
            metadata={'rating': rating}
        )
    
    def update_status(self, feedback_id: str, new_status: str) -> bool:
        """
        Update feedback status.
        
        Args:
            feedback_id: ID of feedback to update
            new_status: New status (new, in_progress, resolved, closed, wontfix)
            
        Returns:
            True if updated successfully
        """
        feedback = self.storage.get(feedback_id)
        if not feedback:
            return False
        
        old_status = feedback.status
        feedback.status = new_status
        
        if self.storage.update(feedback):
            self._trigger_callback('status_changed', {
                'feedback': feedback,
                'old_status': old_status,
                'new_status': new_status
            })
            return True
        
        return False
    
    def get_analytics(self) -> FeedbackAnalytics:
        """Get feedback analytics summary."""
        return self.analyzer.generate_analytics()
    
    def export_feedback(self, filepath: str, format: str = 'json') -> bool:
        """
        Export all feedback to file.
        
        Args:
            filepath: Output file path
            format: Export format ('json', 'csv')
            
        Returns:
            True if exported successfully
        """
        all_feedback = self.storage.get_all()
        
        try:
            if format == 'json':
                data = [fb.to_dict() for fb in all_feedback]
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
            
            elif format == 'csv':
                import csv
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['ID', 'Type', 'Title', 'Description', 
                                   'Priority', 'Status', 'Created'])
                    for fb in all_feedback:
                        writer.writerow([
                            fb.id, fb.type.value, fb.title, fb.description,
                            fb.priority.value, fb.status,
                            datetime.fromtimestamp(fb.created_at).isoformat()
                        ])
            
            logger.info(f"Exported {len(all_feedback)} feedback items to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export feedback: {e}")
            return False
    
    def on_event(self, event: str, callback: Callable) -> None:
        """Register event callback."""
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)
    
    def _trigger_callback(self, event: str, data: Any) -> None:
        """Trigger callbacks for an event."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def _generate_id(self, title: str, description: str) -> str:
        """Generate unique feedback ID."""
        content = f"{title}{description}{time.time()}"
        hash_obj = hashlib.sha256(content.encode())
        return f"fb_{hash_obj.hexdigest()[:12]}"
    
    def _get_system_info(self) -> Dict[str, str]:
        """Get system information for bug reports."""
        import platform
        
        return {
            'os': platform.system(),
            'os_version': platform.version(),
            'python_version': platform.python_version(),
            'machine': platform.machine()
        }


# Convenience functions
_feedback_manager = None

def get_feedback_manager() -> FeedbackManager:
    """Get global feedback manager instance."""
    global _feedback_manager
    if _feedback_manager is None:
        _feedback_manager = FeedbackManager()
    return _feedback_manager

def submit_feedback(feedback_type: FeedbackType, title: str, 
                   description: str, **kwargs) -> UserFeedback:
    """Convenience function to submit feedback."""
    return get_feedback_manager().submit_feedback(
        feedback_type, title, description, **kwargs
    )

def submit_bug_report(title: str, description: str, **kwargs) -> UserFeedback:
    """Convenience function to submit bug report."""
    return get_feedback_manager().submit_bug_report(title, description, **kwargs)

def submit_feature_request(title: str, description: str, **kwargs) -> UserFeedback:
    """Convenience function to submit feature request."""
    return get_feedback_manager().submit_feature_request(title, description, **kwargs)
