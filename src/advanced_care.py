# src/advanced_care.py
"""
Advanced Care Module - Enhanced care options for squid wellbeing.
"""

import time
import random
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CareType(Enum):
    """Types of care actions available."""
    GROOMING = "grooming"
    TRAINING = "training"
    SOCIAL = "social"
    ENRICHMENT = "enrichment"
    MASSAGE = "massage"
    MUSIC = "music"


@dataclass
class CareSession:
    """Represents an ongoing care session."""
    care_type: CareType
    started_at: float
    duration: float
    intensity: float  # 0.0 to 1.0
    target_attributes: List[str]


@dataclass
class CareResult:
    """Result of a completed care session."""
    care_type: CareType
    duration: float
    effects: Dict[str, float]
    bonus_applied: bool
    bonus_type: Optional[str]


class CareAction:
    """A single care action with its effects."""
    
    def __init__(self, 
                 name: str,
                 care_type: CareType,
                 base_duration: float,
                 effects: Dict[str, float],
                 cooldown: float = 0.0,
                 description: str = ""):
        """
        Initialize care action.
        
        Args:
            name: Display name of the action
            care_type: Category of care
            base_duration: How long the action takes (seconds)
            effects: Attribute changes when completed
            cooldown: Time before action can be used again
            description: Description of the action
        """
        self.name = name
        self.care_type = care_type
        self.base_duration = base_duration
        self.effects = effects
        self.cooldown = cooldown
        self.description = description
        self.last_used = 0.0
    
    def is_available(self) -> bool:
        """Check if action is off cooldown."""
        return time.time() - self.last_used >= self.cooldown
    
    def get_remaining_cooldown(self) -> float:
        """Get remaining cooldown time."""
        elapsed = time.time() - self.last_used
        return max(0, self.cooldown - elapsed)
    
    def apply(self, squid_state: Dict[str, float], intensity: float = 1.0) -> Dict[str, float]:
        """
        Apply this care action.
        
        Args:
            squid_state: Current squid state
            intensity: How intensely to apply (0.0-1.0)
            
        Returns:
            Dictionary of attribute changes
        """
        changes = {}
        
        for attr, base_change in self.effects.items():
            change = base_change * intensity
            
            # Apply diminishing returns if already high
            current = squid_state.get(attr, 50)
            if base_change > 0 and current > 80:
                change *= 0.5
            elif base_change < 0 and current < 20:
                change *= 0.5
            
            changes[attr] = change
        
        self.last_used = time.time()
        return changes


class AdvancedCareSystem:
    """
    Manages advanced care options for squid wellbeing.
    
    Features:
    - Multiple care types with different effects
    - Care sessions with progress tracking
    - Combo bonuses for related care
    - Cooldowns and availability management
    """
    
    # Define all available care actions
    CARE_ACTIONS = {
        # Grooming
        'gentle_brush': CareAction(
            name="Gentle Brushing",
            care_type=CareType.GROOMING,
            base_duration=10.0,
            effects={'cleanliness': 15, 'happiness': 5, 'anxiety': -5},
            cooldown=60.0,
            description="Gently brush your squid's tentacles"
        ),
        'deep_clean': CareAction(
            name="Deep Clean",
            care_type=CareType.GROOMING,
            base_duration=20.0,
            effects={'cleanliness': 30, 'happiness': 3},
            cooldown=300.0,
            description="Thorough cleaning for a sparkling squid"
        ),
        'ink_maintenance': CareAction(
            name="Ink Maintenance",
            care_type=CareType.GROOMING,
            base_duration=15.0,
            effects={'cleanliness': 10, 'health': 5},
            cooldown=180.0,
            description="Help maintain healthy ink production"
        ),
        
        # Training
        'memory_drill': CareAction(
            name="Memory Drill",
            care_type=CareType.TRAINING,
            base_duration=30.0,
            effects={'intelligence': 10, 'sleepiness': 10},
            cooldown=300.0,
            description="Practice pattern recognition"
        ),
        'agility_training': CareAction(
            name="Agility Training",
            care_type=CareType.TRAINING,
            base_duration=25.0,
            effects={'agility': 15, 'hunger': 10, 'sleepiness': 5},
            cooldown=240.0,
            description="Improve movement speed and reflexes"
        ),
        'problem_solving': CareAction(
            name="Problem Solving",
            care_type=CareType.TRAINING,
            base_duration=35.0,
            effects={'intelligence': 15, 'curiosity': -10, 'sleepiness': 15},
            cooldown=360.0,
            description="Challenge with puzzles and problems"
        ),
        
        # Social
        'gentle_talk': CareAction(
            name="Gentle Conversation",
            care_type=CareType.SOCIAL,
            base_duration=15.0,
            effects={'happiness': 10, 'anxiety': -10, 'trust': 5},
            cooldown=120.0,
            description="Talk soothingly to your squid"
        ),
        'play_session': CareAction(
            name="Play Session",
            care_type=CareType.SOCIAL,
            base_duration=20.0,
            effects={'happiness': 20, 'anxiety': -5, 'sleepiness': 10, 'hunger': 5},
            cooldown=180.0,
            description="Interactive play time"
        ),
        'bonding_time': CareAction(
            name="Bonding Time",
            care_type=CareType.SOCIAL,
            base_duration=30.0,
            effects={'trust': 15, 'happiness': 10, 'anxiety': -15},
            cooldown=300.0,
            description="Quiet quality time together"
        ),
        
        # Enrichment
        'new_toy': CareAction(
            name="New Toy",
            care_type=CareType.ENRICHMENT,
            base_duration=5.0,
            effects={'curiosity': -20, 'happiness': 15},
            cooldown=600.0,
            description="Introduce a new object to explore"
        ),
        'environment_change': CareAction(
            name="Environment Change",
            care_type=CareType.ENRICHMENT,
            base_duration=10.0,
            effects={'curiosity': -15, 'anxiety': 5},
            cooldown=1800.0,
            description="Rearrange the environment"
        ),
        'sensory_experience': CareAction(
            name="Sensory Experience",
            care_type=CareType.ENRICHMENT,
            base_duration=15.0,
            effects={'curiosity': -25, 'happiness': 5, 'intelligence': 3},
            cooldown=900.0,
            description="New textures, scents, or lights"
        ),
        
        # Massage/Relaxation
        'tentacle_massage': CareAction(
            name="Tentacle Massage",
            care_type=CareType.MASSAGE,
            base_duration=20.0,
            effects={'anxiety': -20, 'happiness': 10, 'sleepiness': 5},
            cooldown=300.0,
            description="Relaxing tentacle massage"
        ),
        'warm_compress': CareAction(
            name="Warm Compress",
            care_type=CareType.MASSAGE,
            base_duration=15.0,
            effects={'anxiety': -10, 'health': 5},
            cooldown=600.0,
            description="Soothing warmth therapy"
        ),
        
        # Music/Sound
        'calming_music': CareAction(
            name="Calming Music",
            care_type=CareType.MUSIC,
            base_duration=60.0,
            effects={'anxiety': -15, 'happiness': 5},
            cooldown=300.0,
            description="Play soothing underwater sounds"
        ),
        'stimulating_music': CareAction(
            name="Stimulating Music",
            care_type=CareType.MUSIC,
            base_duration=45.0,
            effects={'happiness': 10, 'curiosity': -5, 'sleepiness': -10},
            cooldown=300.0,
            description="Energetic music for activity"
        ),
    }
    
    # Combo bonuses when using related care types
    COMBO_BONUSES = {
        (CareType.GROOMING, CareType.MASSAGE): {'happiness': 5, 'trust': 3},
        (CareType.TRAINING, CareType.ENRICHMENT): {'intelligence': 5},
        (CareType.SOCIAL, CareType.MUSIC): {'happiness': 8, 'anxiety': -5},
        (CareType.MASSAGE, CareType.MUSIC): {'anxiety': -10, 'sleepiness': 10},
    }
    
    def __init__(self):
        """Initialize advanced care system."""
        self.current_session: Optional[CareSession] = None
        self.session_history: List[CareResult] = []
        self.recent_care_types: List[CareType] = []  # Last 3 care types used
        self._callbacks: Dict[str, List[Callable]] = {}
    
    def get_available_actions(self) -> List[Dict[str, Any]]:
        """Get list of all care actions with availability status."""
        actions = []
        
        for action_id, action in self.CARE_ACTIONS.items():
            actions.append({
                'id': action_id,
                'name': action.name,
                'type': action.care_type.value,
                'duration': action.base_duration,
                'description': action.description,
                'available': action.is_available(),
                'cooldown_remaining': action.get_remaining_cooldown(),
                'effects': action.effects.copy()
            })
        
        return actions
    
    def get_actions_by_type(self, care_type: CareType) -> List[Dict[str, Any]]:
        """Get care actions of a specific type."""
        return [
            a for a in self.get_available_actions()
            if a['type'] == care_type.value
        ]
    
    def start_care_session(self, action_id: str, 
                          intensity: float = 1.0) -> Optional[Dict[str, Any]]:
        """
        Start a care session.
        
        Args:
            action_id: ID of the care action
            intensity: Intensity level (0.0-1.0)
            
        Returns:
            Session info or None if action not available
        """
        if action_id not in self.CARE_ACTIONS:
            logger.warning(f"Unknown care action: {action_id}")
            return None
        
        action = self.CARE_ACTIONS[action_id]
        
        if not action.is_available():
            logger.info(f"Action on cooldown: {action_id}")
            return None
        
        if self.current_session:
            logger.warning("Care session already in progress")
            return None
        
        self.current_session = CareSession(
            care_type=action.care_type,
            started_at=time.time(),
            duration=action.base_duration,
            intensity=max(0.1, min(1.0, intensity)),
            target_attributes=list(action.effects.keys())
        )
        
        self._trigger_callback('session_started', {
            'action_id': action_id,
            'action_name': action.name,
            'duration': action.base_duration
        })
        
        return {
            'action_id': action_id,
            'action_name': action.name,
            'duration': action.base_duration,
            'started_at': self.current_session.started_at
        }
    
    def update_session(self) -> Optional[float]:
        """
        Update current care session.
        
        Returns:
            Progress (0.0-1.0) or None if no session
        """
        if not self.current_session:
            return None
        
        elapsed = time.time() - self.current_session.started_at
        progress = min(1.0, elapsed / self.current_session.duration)
        
        return progress
    
    def complete_care_session(self, action_id: str, 
                             squid_state: Dict[str, float]) -> Optional[CareResult]:
        """
        Complete the current care session and apply effects.
        
        Args:
            action_id: ID of the care action
            squid_state: Current squid state
            
        Returns:
            Care result with effects applied
        """
        if not self.current_session:
            return None
        
        action = self.CARE_ACTIONS.get(action_id)
        if not action:
            return None
        
        # Calculate effects
        effects = action.apply(squid_state, self.current_session.intensity)
        
        # Check for combo bonus
        bonus_applied = False
        bonus_type = None
        
        if self.recent_care_types:
            last_type = self.recent_care_types[-1]
            combo_key = tuple(sorted([last_type, action.care_type], key=lambda x: x.value))
            
            if combo_key in self.COMBO_BONUSES:
                bonus_effects = self.COMBO_BONUSES[combo_key]
                for attr, bonus in bonus_effects.items():
                    if attr in effects:
                        effects[attr] += bonus
                    else:
                        effects[attr] = bonus
                
                bonus_applied = True
                bonus_type = f"{last_type.value}+{action.care_type.value}"
        
        # Update history
        self.recent_care_types.append(action.care_type)
        if len(self.recent_care_types) > 3:
            self.recent_care_types.pop(0)
        
        result = CareResult(
            care_type=action.care_type,
            duration=time.time() - self.current_session.started_at,
            effects=effects,
            bonus_applied=bonus_applied,
            bonus_type=bonus_type
        )
        
        self.session_history.append(result)
        self.current_session = None
        
        self._trigger_callback('session_completed', {
            'result': result,
            'effects': effects
        })
        
        return result
    
    def cancel_session(self) -> bool:
        """Cancel the current care session."""
        if not self.current_session:
            return False
        
        self.current_session = None
        self._trigger_callback('session_cancelled', {})
        return True
    
    def get_recommended_care(self, squid_state: Dict[str, float]) -> List[str]:
        """
        Get recommended care actions based on squid state.
        
        Args:
            squid_state: Current squid state
            
        Returns:
            List of recommended action IDs
        """
        recommendations = []
        
        # Check each attribute and recommend appropriate care
        if squid_state.get('cleanliness', 50) < 40:
            recommendations.append('gentle_brush')
        
        if squid_state.get('anxiety', 50) > 70:
            recommendations.append('tentacle_massage')
            recommendations.append('calming_music')
        
        if squid_state.get('happiness', 50) < 40:
            recommendations.append('play_session')
            recommendations.append('gentle_talk')
        
        if squid_state.get('curiosity', 50) > 80:
            recommendations.append('new_toy')
            recommendations.append('sensory_experience')
        
        if squid_state.get('trust', 50) < 30:
            recommendations.append('bonding_time')
            recommendations.append('gentle_talk')
        
        # Filter to only available actions
        available_recommendations = [
            r for r in recommendations
            if r in self.CARE_ACTIONS and self.CARE_ACTIONS[r].is_available()
        ]
        
        return available_recommendations[:3]  # Return top 3
    
    def get_care_statistics(self) -> Dict[str, Any]:
        """Get care history statistics."""
        if not self.session_history:
            return {
                'total_sessions': 0,
                'total_care_time': 0,
                'favorite_type': None,
                'combos_triggered': 0
            }
        
        total_time = sum(r.duration for r in self.session_history)
        combos = sum(1 for r in self.session_history if r.bonus_applied)
        
        # Count care types
        type_counts: Dict[CareType, int] = {}
        for result in self.session_history:
            type_counts[result.care_type] = type_counts.get(result.care_type, 0) + 1
        
        favorite = max(type_counts, key=type_counts.get) if type_counts else None
        
        return {
            'total_sessions': len(self.session_history),
            'total_care_time': total_time,
            'favorite_type': favorite.value if favorite else None,
            'combos_triggered': combos,
            'type_breakdown': {t.value: c for t, c in type_counts.items()}
        }
    
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
                logger.error(f"Care callback error: {e}")
