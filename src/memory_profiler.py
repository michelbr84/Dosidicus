# src/memory_profiler.py
"""
Memory Profiler - Memory Leak Detection and Monitoring

This module provides utilities for detecting memory leaks in long-running
simulations, tracking object references, and triggering cleanup.
"""

import gc
import sys
import time
import weakref
import logging
import tracemalloc
from collections import Counter, deque
from typing import Dict, Any, Optional, List, Set, Callable, TypeVar
from dataclasses import dataclass
from contextlib import contextmanager

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class MemorySnapshot:
    """Represents a point-in-time memory snapshot."""
    timestamp: float
    total_memory_mb: float
    object_counts: Dict[str, int]
    gc_stats: Dict[str, Any]
    top_allocations: List[Dict[str, Any]]


class ObjectTracker:
    """
    Track objects to detect potential memory leaks.
    
    Uses weak references to avoid preventing garbage collection.
    """
    
    def __init__(self, max_tracked: int = 1000):
        self.max_tracked = max_tracked
        self._tracked: Dict[int, weakref.ref] = {}
        self._creation_times: Dict[int, float] = {}
        self._type_counts: Counter = Counter()
    
    def track(self, obj: T, name: Optional[str] = None) -> T:
        """
        Track an object for leak detection.
        
        Args:
            obj: Object to track
            name: Optional name for identification
            
        Returns:
            The same object (for chaining)
        """
        if len(self._tracked) >= self.max_tracked:
            self._cleanup_dead_refs()
        
        obj_id = id(obj)
        try:
            self._tracked[obj_id] = weakref.ref(obj)
            self._creation_times[obj_id] = time.time()
            self._type_counts[type(obj).__name__] += 1
        except TypeError:
            # Some objects can't be weak-referenced
            pass
        
        return obj
    
    def _cleanup_dead_refs(self) -> int:
        """Remove dead weak references. Returns count of cleaned refs."""
        dead_ids = [oid for oid, ref in self._tracked.items() if ref() is None]
        for oid in dead_ids:
            del self._tracked[oid]
            if oid in self._creation_times:
                del self._creation_times[oid]
        return len(dead_ids)
    
    def get_live_objects(self) -> List[Dict[str, Any]]:
        """Get information about currently live tracked objects."""
        self._cleanup_dead_refs()
        live = []
        current_time = time.time()
        
        for obj_id, ref in list(self._tracked.items()):
            obj = ref()
            if obj is not None:
                age = current_time - self._creation_times.get(obj_id, current_time)
                live.append({
                    'id': obj_id,
                    'type': type(obj).__name__,
                    'age_seconds': age,
                    'size_bytes': sys.getsizeof(obj)
                })
        
        return live
    
    def get_long_lived_objects(self, min_age_seconds: float = 300) -> List[Dict[str, Any]]:
        """Get objects that have been alive longer than expected."""
        return [obj for obj in self.get_live_objects() 
                if obj['age_seconds'] > min_age_seconds]
    
    def get_type_summary(self) -> Dict[str, int]:
        """Get summary of tracked object types."""
        return dict(self._type_counts.most_common(20))


class MemoryProfiler:
    """
    Memory profiling and leak detection for long-running applications.
    
    Features:
    - Periodic memory snapshots
    - Growth rate detection
    - Object tracking
    - Tracemalloc integration
    - Cleanup trigger callbacks
    """
    
    def __init__(self,
                 snapshot_interval: float = 60.0,
                 max_snapshots: int = 100,
                 growth_threshold_mb: float = 50.0):
        """
        Initialize memory profiler.
        
        Args:
            snapshot_interval: Seconds between automatic snapshots
            max_snapshots: Maximum snapshots to keep
            growth_threshold_mb: MB growth to trigger warning
        """
        self.snapshot_interval = snapshot_interval
        self.max_snapshots = max_snapshots
        self.growth_threshold_mb = growth_threshold_mb
        
        self._snapshots: deque = deque(maxlen=max_snapshots)
        self._object_tracker = ObjectTracker()
        self._cleanup_callbacks: List[Callable[[], None]] = []
        self._warning_callbacks: List[Callable[[str, float], None]] = []
        
        self._tracemalloc_enabled = False
        self._start_time = time.time()
        self._last_snapshot_time = 0.0
        
        # Tracked collections that should be bounded
        self._bounded_collections: Dict[str, weakref.ref] = {}
    
    def start_tracemalloc(self, nframe: int = 25) -> None:
        """Start tracemalloc for detailed allocation tracking."""
        if not tracemalloc.is_tracing():
            tracemalloc.start(nframe)
            self._tracemalloc_enabled = True
            logger.info(f"Tracemalloc started with {nframe} frames")
    
    def stop_tracemalloc(self) -> None:
        """Stop tracemalloc."""
        if tracemalloc.is_tracing():
            tracemalloc.stop()
            self._tracemalloc_enabled = False
            logger.info("Tracemalloc stopped")
    
    def take_snapshot(self) -> MemorySnapshot:
        """Take a memory snapshot."""
        import resource
        
        # Get current memory usage
        try:
            # Try resource module (Unix)
            usage = resource.getrusage(resource.RUSAGE_SELF)
            total_memory_mb = usage.ru_maxrss / 1024  # Convert to MB
        except:
            # Fallback for Windows
            try:
                import psutil
                process = psutil.Process()
                total_memory_mb = process.memory_info().rss / (1024 * 1024)
            except ImportError:
                # No psutil, estimate from gc
                total_memory_mb = sum(sys.getsizeof(obj) for obj in gc.get_objects()) / (1024 * 1024)
        
        # Count objects by type
        object_counts: Counter = Counter()
        for obj in gc.get_objects():
            object_counts[type(obj).__name__] += 1
        
        # Get GC stats
        gc_stats = {
            'collections': gc.get_count(),
            'threshold': gc.get_threshold(),
            'objects': len(gc.get_objects())
        }
        
        # Get top allocations from tracemalloc if available
        top_allocations = []
        if self._tracemalloc_enabled:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')[:10]
            for stat in top_stats:
                top_allocations.append({
                    'file': str(stat.traceback),
                    'size_kb': stat.size / 1024,
                    'count': stat.count
                })
        
        snapshot = MemorySnapshot(
            timestamp=time.time(),
            total_memory_mb=total_memory_mb,
            object_counts=dict(object_counts.most_common(20)),
            gc_stats=gc_stats,
            top_allocations=top_allocations
        )
        
        self._snapshots.append(snapshot)
        self._last_snapshot_time = time.time()
        
        # Check for memory growth
        self._check_memory_growth()
        
        return snapshot
    
    def _check_memory_growth(self) -> None:
        """Check for concerning memory growth patterns."""
        if len(self._snapshots) < 2:
            return
        
        oldest = self._snapshots[0]
        newest = self._snapshots[-1]
        
        growth_mb = newest.total_memory_mb - oldest.total_memory_mb
        time_diff_hours = (newest.timestamp - oldest.timestamp) / 3600
        
        if time_diff_hours > 0:
            growth_rate_per_hour = growth_mb / time_diff_hours
            
            if growth_mb > self.growth_threshold_mb:
                warning_msg = (f"Memory growth detected: {growth_mb:.1f}MB over "
                             f"{time_diff_hours:.1f}h ({growth_rate_per_hour:.1f}MB/h)")
                logger.warning(warning_msg)
                
                for callback in self._warning_callbacks:
                    try:
                        callback(warning_msg, growth_mb)
                    except Exception as e:
                        logger.error(f"Error in memory warning callback: {e}")
    
    def track_object(self, obj: T, name: Optional[str] = None) -> T:
        """Track an object for leak detection."""
        return self._object_tracker.track(obj, name)
    
    def register_bounded_collection(self, name: str, collection: Any) -> None:
        """
        Register a collection that should be monitored for unbounded growth.
        
        Args:
            name: Identifier for the collection
            collection: The collection to monitor (list, dict, set, deque, etc.)
        """
        try:
            self._bounded_collections[name] = weakref.ref(collection)
        except TypeError:
            logger.warning(f"Cannot create weak ref to collection {name}")
    
    def check_bounded_collections(self, max_size: int = 10000) -> List[Dict[str, Any]]:
        """
        Check registered collections for potential unbounded growth.
        
        Returns list of collections exceeding max_size.
        """
        warnings = []
        
        for name, ref in list(self._bounded_collections.items()):
            collection = ref()
            if collection is None:
                del self._bounded_collections[name]
                continue
            
            try:
                size = len(collection)
                if size > max_size:
                    warnings.append({
                        'name': name,
                        'type': type(collection).__name__,
                        'size': size,
                        'max_size': max_size
                    })
            except TypeError:
                pass  # Object doesn't support len()
        
        return warnings
    
    def register_cleanup_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback to be called when cleanup is triggered."""
        self._cleanup_callbacks.append(callback)
    
    def register_warning_callback(self, callback: Callable[[str, float], None]) -> None:
        """Register a callback for memory warnings."""
        self._warning_callbacks.append(callback)
    
    def trigger_cleanup(self) -> Dict[str, Any]:
        """
        Trigger cleanup operations to free memory.
        
        Returns cleanup statistics.
        """
        logger.info("Triggering memory cleanup...")
        
        # Record state before cleanup
        gc.collect()
        before_objects = len(gc.get_objects())
        
        # Call registered cleanup callbacks
        callback_results = []
        for callback in self._cleanup_callbacks:
            try:
                callback()
                callback_results.append({'success': True})
            except Exception as e:
                callback_results.append({'success': False, 'error': str(e)})
                logger.error(f"Error in cleanup callback: {e}")
        
        # Force garbage collection
        gc.collect()
        gc.collect()  # Second pass for cyclic references
        
        after_objects = len(gc.get_objects())
        
        stats = {
            'objects_freed': before_objects - after_objects,
            'callbacks_run': len(callback_results),
            'callbacks_succeeded': sum(1 for r in callback_results if r['success']),
            'timestamp': time.time()
        }
        
        logger.info(f"Cleanup complete: freed {stats['objects_freed']} objects")
        return stats
    
    def get_leak_candidates(self) -> List[Dict[str, Any]]:
        """
        Identify potential memory leak candidates.
        
        Returns list of suspicious objects/patterns.
        """
        candidates = []
        
        # Check for long-lived tracked objects
        long_lived = self._object_tracker.get_long_lived_objects(min_age_seconds=600)
        if long_lived:
            candidates.append({
                'type': 'long_lived_objects',
                'count': len(long_lived),
                'objects': long_lived[:10],
                'severity': 'warning'
            })
        
        # Check bounded collections
        oversized = self.check_bounded_collections()
        if oversized:
            candidates.append({
                'type': 'unbounded_collections',
                'collections': oversized,
                'severity': 'warning'
            })
        
        # Check for memory growth trend
        if len(self._snapshots) >= 5:
            # Calculate linear regression of memory over time
            recent = list(self._snapshots)[-10:]
            if len(recent) >= 2:
                first_mem = recent[0].total_memory_mb
                last_mem = recent[-1].total_memory_mb
                time_span_hours = (recent[-1].timestamp - recent[0].timestamp) / 3600
                
                if time_span_hours > 0.1:  # At least 6 minutes of data
                    growth_rate = (last_mem - first_mem) / time_span_hours
                    if growth_rate > 10:  # More than 10MB/hour growth
                        candidates.append({
                            'type': 'memory_growth_trend',
                            'growth_rate_mb_per_hour': growth_rate,
                            'current_mb': last_mem,
                            'severity': 'error' if growth_rate > 50 else 'warning'
                        })
        
        return candidates
    
    def get_report(self) -> Dict[str, Any]:
        """Get comprehensive memory report."""
        latest_snapshot = self._snapshots[-1] if self._snapshots else None
        
        return {
            'uptime_seconds': time.time() - self._start_time,
            'snapshot_count': len(self._snapshots),
            'tracemalloc_enabled': self._tracemalloc_enabled,
            'current_memory_mb': latest_snapshot.total_memory_mb if latest_snapshot else None,
            'object_counts': latest_snapshot.object_counts if latest_snapshot else {},
            'tracked_objects': self._object_tracker.get_type_summary(),
            'leak_candidates': self.get_leak_candidates(),
            'bounded_collection_warnings': self.check_bounded_collections()
        }


# Global memory profiler instance
_memory_profiler: Optional[MemoryProfiler] = None


def get_memory_profiler() -> MemoryProfiler:
    """Get or create the global memory profiler instance."""
    global _memory_profiler
    if _memory_profiler is None:
        _memory_profiler = MemoryProfiler()
    return _memory_profiler


def run_leak_detection(duration_seconds: float = 60.0) -> Dict[str, Any]:
    """
    Run a leak detection session.
    
    Args:
        duration_seconds: How long to monitor for leaks
        
    Returns:
        Leak detection report
    """
    profiler = get_memory_profiler()
    profiler.start_tracemalloc()
    
    logger.info(f"Starting leak detection for {duration_seconds}s...")
    
    # Take initial snapshot
    profiler.take_snapshot()
    
    # Wait and take periodic snapshots
    interval = min(10.0, duration_seconds / 6)
    start_time = time.time()
    
    while time.time() - start_time < duration_seconds:
        time.sleep(interval)
        profiler.take_snapshot()
    
    # Generate report
    report = profiler.get_report()
    profiler.stop_tracemalloc()
    
    logger.info("Leak detection complete")
    return report


@contextmanager
def memory_tracking_context(name: str = "unnamed"):
    """
    Context manager for tracking memory usage of a code block.
    
    Usage:
        with memory_tracking_context("brain_update"):
            # code to monitor
    """
    profiler = get_memory_profiler()
    
    gc.collect()
    before_snapshot = profiler.take_snapshot()
    
    yield
    
    gc.collect()
    after_snapshot = profiler.take_snapshot()
    
    mem_diff = after_snapshot.total_memory_mb - before_snapshot.total_memory_mb
    if abs(mem_diff) > 1:  # More than 1MB change
        logger.info(f"Memory change in '{name}': {mem_diff:+.2f}MB")
