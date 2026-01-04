# src/bug_tracker.py
"""
Bug Tracker - Error Tracking and Analysis Infrastructure

This module provides automatic error categorization, stack trace analysis,
and pattern detection to help identify and fix bugs in long-running simulations.
"""

import os
import sys
import time
import json
import logging
import traceback
import hashlib
from datetime import datetime
from pathlib import Path
from collections import deque, Counter
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class BugReport:
    """Represents a captured bug/error event."""
    timestamp: float
    error_type: str
    error_message: str
    stack_trace: str
    context: Dict[str, Any]
    fingerprint: str  # Hash for deduplication
    severity: str  # 'critical', 'error', 'warning', 'info'
    category: str  # 'simulation', 'ui', 'network', 'memory', 'other'
    count: int = 1  # Number of occurrences
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BugReport':
        return cls(**data)


class BugTracker:
    """
    Centralized bug tracking and analysis system.
    
    Features:
    - Automatic error categorization
    - Stack trace fingerprinting for deduplication
    - Pattern detection for recurring issues
    - Memory-efficient bounded storage
    - Crash report generation
    """
    
    # Error category keywords
    CATEGORY_KEYWORDS = {
        'simulation': ['brain', 'neuron', 'learning', 'neurogenesis', 'squid', 'decision'],
        'ui': ['qt', 'widget', 'window', 'gui', 'display', 'render', 'paint'],
        'network': ['socket', 'network', 'multiplayer', 'connect', 'send', 'receive'],
        'memory': ['memory', 'alloc', 'heap', 'stack', 'overflow', 'leak'],
        'io': ['file', 'save', 'load', 'read', 'write', 'open', 'close'],
    }
    
    def __init__(self, 
                 max_reports: int = 1000,
                 log_dir: Optional[str] = None,
                 auto_save: bool = True):
        """
        Initialize the bug tracker.
        
        Args:
            max_reports: Maximum number of unique reports to keep
            log_dir: Directory for crash reports (defaults to ./logs)
            auto_save: Whether to auto-save crash reports
        """
        self.max_reports = max_reports
        self.log_dir = Path(log_dir) if log_dir else Path('./logs')
        self.auto_save = auto_save
        
        # Bounded storage for reports
        self._reports: Dict[str, BugReport] = {}
        self._report_order: deque = deque(maxlen=max_reports)
        
        # Pattern tracking
        self._error_counts: Counter = Counter()
        self._category_counts: Counter = Counter()
        self._recent_errors: deque = deque(maxlen=100)
        
        # Statistics
        self._total_errors = 0
        self._session_start = time.time()
        
        # Callbacks
        self._error_callbacks: List[Callable[[BugReport], None]] = []
        
        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def capture_exception(self, 
                         exc_info: Optional[tuple] = None,
                         context: Optional[Dict[str, Any]] = None,
                         severity: str = 'error') -> Optional[BugReport]:
        """
        Capture an exception and create a bug report.
        
        Args:
            exc_info: Exception info tuple (type, value, traceback)
            context: Additional context information
            severity: Error severity level
            
        Returns:
            BugReport if captured, None if deduplicated
        """
        if exc_info is None:
            exc_info = sys.exc_info()
        
        if exc_info[0] is None:
            return None
        
        exc_type, exc_value, exc_tb = exc_info
        
        # Format the stack trace
        stack_trace = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
        
        # Create fingerprint for deduplication
        fingerprint = self._create_fingerprint(exc_type.__name__, str(exc_value), stack_trace)
        
        # Determine category
        category = self._categorize_error(stack_trace, str(exc_value))
        
        # Check for existing report
        if fingerprint in self._reports:
            self._reports[fingerprint].count += 1
            self._total_errors += 1
            return None
        
        # Create new report
        report = BugReport(
            timestamp=time.time(),
            error_type=exc_type.__name__,
            error_message=str(exc_value),
            stack_trace=stack_trace,
            context=context or {},
            fingerprint=fingerprint,
            severity=severity,
            category=category
        )
        
        # Store report
        self._add_report(report)
        
        # Update statistics
        self._total_errors += 1
        self._error_counts[exc_type.__name__] += 1
        self._category_counts[category] += 1
        self._recent_errors.append((time.time(), exc_type.__name__))
        
        # Trigger callbacks
        for callback in self._error_callbacks:
            try:
                callback(report)
            except Exception as cb_err:
                logger.warning(f"Error in bug tracker callback: {cb_err}")
        
        # Auto-save critical errors
        if self.auto_save and severity == 'critical':
            self.save_crash_report(report)
        
        return report
    
    def capture_error(self,
                     error_type: str,
                     error_message: str,
                     context: Optional[Dict[str, Any]] = None,
                     severity: str = 'warning') -> Optional[BugReport]:
        """
        Capture a non-exception error.
        
        Args:
            error_type: Type/name of the error
            error_message: Error description
            context: Additional context
            severity: Error severity
            
        Returns:
            BugReport if captured
        """
        # Get current stack trace
        stack_trace = ''.join(traceback.format_stack()[:-1])
        
        fingerprint = self._create_fingerprint(error_type, error_message, stack_trace)
        
        if fingerprint in self._reports:
            self._reports[fingerprint].count += 1
            return None
        
        category = self._categorize_error(stack_trace, error_message)
        
        report = BugReport(
            timestamp=time.time(),
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace,
            context=context or {},
            fingerprint=fingerprint,
            severity=severity,
            category=category
        )
        
        self._add_report(report)
        self._total_errors += 1
        self._error_counts[error_type] += 1
        self._category_counts[category] += 1
        
        return report
    
    def _add_report(self, report: BugReport) -> None:
        """Add report to storage, respecting size limits."""
        # Evict oldest if at capacity
        if len(self._reports) >= self.max_reports:
            if self._report_order:
                oldest_fp = self._report_order.popleft()
                if oldest_fp in self._reports:
                    del self._reports[oldest_fp]
        
        self._reports[report.fingerprint] = report
        self._report_order.append(report.fingerprint)
    
    def _create_fingerprint(self, error_type: str, error_message: str, stack_trace: str) -> str:
        """Create a unique fingerprint for deduplication."""
        # Extract key frames from stack trace (ignore line numbers for fuzzy matching)
        key_content = f"{error_type}:{error_message}:"
        
        for line in stack_trace.split('\n'):
            line = line.strip()
            if line.startswith('File '):
                # Extract file path and function name, ignore line numbers
                parts = line.split(',')
                if len(parts) >= 1:
                    key_content += parts[0] + ':'
                if len(parts) >= 3:
                    key_content += parts[2].strip() + ':'
        
        return hashlib.md5(key_content.encode()).hexdigest()[:16]
    
    def _categorize_error(self, stack_trace: str, error_message: str) -> str:
        """Automatically categorize an error based on content."""
        combined = (stack_trace + error_message).lower()
        
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in combined:
                    return category
        
        return 'other'
    
    def register_callback(self, callback: Callable[[BugReport], None]) -> None:
        """Register a callback to be called when errors are captured."""
        self._error_callbacks.append(callback)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get error statistics for the session."""
        session_duration = time.time() - self._session_start
        
        return {
            'session_duration_seconds': session_duration,
            'total_errors': self._total_errors,
            'unique_errors': len(self._reports),
            'errors_by_type': dict(self._error_counts.most_common(10)),
            'errors_by_category': dict(self._category_counts),
            'error_rate_per_minute': (self._total_errors / session_duration * 60) if session_duration > 0 else 0,
            'top_recurring_errors': [
                {'fingerprint': fp, 'count': self._reports[fp].count, 'type': self._reports[fp].error_type}
                for fp in sorted(self._reports.keys(), 
                               key=lambda x: self._reports[x].count, 
                               reverse=True)[:5]
            ]
        }
    
    def detect_patterns(self) -> List[Dict[str, Any]]:
        """Detect recurring error patterns."""
        patterns = []
        
        # Check for error bursts
        if len(self._recent_errors) >= 10:
            recent_five_min = [e for e in self._recent_errors if time.time() - e[0] < 300]
            if len(recent_five_min) >= 10:
                patterns.append({
                    'pattern': 'error_burst',
                    'description': f'{len(recent_five_min)} errors in the last 5 minutes',
                    'severity': 'warning'
                })
        
        # Check for repeating errors
        for report in self._reports.values():
            if report.count >= 10:
                patterns.append({
                    'pattern': 'recurring_error',
                    'description': f'{report.error_type} occurred {report.count} times',
                    'error_type': report.error_type,
                    'fingerprint': report.fingerprint,
                    'severity': 'warning' if report.count < 50 else 'error'
                })
        
        # Check for category concentration
        if self._category_counts:
            total = sum(self._category_counts.values())
            for category, count in self._category_counts.items():
                if total > 0 and count / total > 0.7:
                    patterns.append({
                        'pattern': 'category_concentration',
                        'description': f'{count}/{total} ({count/total*100:.0f}%) errors in {category}',
                        'category': category,
                        'severity': 'info'
                    })
        
        return patterns
    
    def save_crash_report(self, report: Optional[BugReport] = None) -> str:
        """
        Save a crash report to disk.
        
        Args:
            report: Specific report to save (or all if None)
            
        Returns:
            Path to saved report
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"crash_report_{timestamp}.json"
        filepath = self.log_dir / filename
        
        crash_data = {
            'generated_at': datetime.now().isoformat(),
            'session_duration': time.time() - self._session_start,
            'statistics': self.get_statistics(),
            'patterns': self.detect_patterns(),
            'reports': []
        }
        
        if report:
            crash_data['reports'] = [report.to_dict()]
        else:
            crash_data['reports'] = [r.to_dict() for r in self._reports.values()]
        
        with open(filepath, 'w') as f:
            json.dump(crash_data, f, indent=2)
        
        logger.info(f"Crash report saved to {filepath}")
        return str(filepath)
    
    def clear(self) -> None:
        """Clear all stored reports and statistics."""
        self._reports.clear()
        self._report_order.clear()
        self._error_counts.clear()
        self._category_counts.clear()
        self._recent_errors.clear()
        self._total_errors = 0
        self._session_start = time.time()

    @contextmanager
    def track_context(self, context_name: str, **context_data):
        """
        Context manager for tracking errors within a specific context.
        
        Usage:
            with bug_tracker.track_context('brain_update', neuron_count=100):
                # code that might fail
        """
        try:
            yield
        except Exception:
            self.capture_exception(
                context={'context_name': context_name, **context_data}
            )
            raise


# Global bug tracker instance
_bug_tracker: Optional[BugTracker] = None


def get_bug_tracker() -> BugTracker:
    """Get or create the global bug tracker instance."""
    global _bug_tracker
    if _bug_tracker is None:
        _bug_tracker = BugTracker()
    return _bug_tracker


def install_global_exception_hook() -> None:
    """Install a global exception hook to capture all unhandled exceptions."""
    original_hook = sys.excepthook
    
    def exception_hook(exc_type, exc_value, exc_tb):
        # Capture with bug tracker
        tracker = get_bug_tracker()
        tracker.capture_exception(
            exc_info=(exc_type, exc_value, exc_tb),
            severity='critical',
            context={'unhandled': True}
        )
        
        # Save crash report
        if tracker.auto_save:
            tracker.save_crash_report()
        
        # Call original hook
        original_hook(exc_type, exc_value, exc_tb)
    
    sys.excepthook = exception_hook
    logger.info("Global exception hook installed")
