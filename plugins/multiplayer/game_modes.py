# plugins/multiplayer/game_modes.py
"""
Game Modes - Different multiplayer gameplay modes for varied experiences.
"""

import time
import random
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class GameModeType(Enum):
    """Available game mode types."""
    COOPERATIVE = "cooperative"
    COMPETITIVE = "competitive"
    SPECTATOR = "spectator"
    SANDBOX = "sandbox"


@dataclass
class GameEvent:
    """An event that occurred during gameplay."""
    event_type: str
    source_node: str
    target_node: Optional[str]
    data: Dict[str, Any]
    timestamp: float


class GameModeBase(ABC):
    """Base class for all game modes."""
    
    def __init__(self, session_id: str, local_node_id: str):
        self.session_id = session_id
        self.local_node_id = local_node_id
        self.is_active = False
        self.start_time = 0.0
        self.events: List[GameEvent] = []
        self.scores: Dict[str, int] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}
    
    @property
    @abstractmethod
    def mode_type(self) -> GameModeType:
        """Return the type of this game mode."""
        pass
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name for this mode."""
        pass
    
    @abstractmethod
    def on_start(self) -> None:
        """Called when the game mode starts."""
        pass
    
    @abstractmethod
    def on_update(self, delta_time: float) -> None:
        """Called each frame/update cycle."""
        pass
    
    @abstractmethod
    def on_end(self) -> Dict[str, Any]:
        """Called when the game mode ends. Returns results."""
        pass
    
    @abstractmethod
    def process_player_action(self, node_id: str, action: str, data: Dict[str, Any]) -> bool:
        """Process an action from a player. Returns success."""
        pass
    
    def start(self) -> None:
        """Start the game mode."""
        self.is_active = True
        self.start_time = time.time()
        self.events.clear()
        self.scores.clear()
        self.on_start()
        logger.info(f"Started game mode: {self.display_name}")
    
    def stop(self) -> Dict[str, Any]:
        """Stop the game mode and return results."""
        self.is_active = False
        results = self.on_end()
        logger.info(f"Ended game mode: {self.display_name}")
        return results
    
    def update(self, delta_time: float) -> None:
        """Update the game mode."""
        if self.is_active:
            self.on_update(delta_time)
    
    def record_event(self, event_type: str, source: str, 
                    target: Optional[str] = None, data: Dict[str, Any] = None) -> None:
        """Record a game event."""
        event = GameEvent(
            event_type=event_type,
            source_node=source,
            target_node=target,
            data=data or {},
            timestamp=time.time()
        )
        self.events.append(event)
        
        # Keep events bounded
        if len(self.events) > 1000:
            self.events = self.events[-500:]
        
        # Notify handlers
        if event_type in self._event_handlers:
            for handler in self._event_handlers[event_type]:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"Event handler error: {e}")
    
    def on_event(self, event_type: str, handler: Callable[[GameEvent], None]) -> None:
        """Register an event handler."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    def add_score(self, node_id: str, points: int) -> None:
        """Add points to a player's score."""
        if node_id not in self.scores:
            self.scores[node_id] = 0
        self.scores[node_id] += points
    
    def get_elapsed_time(self) -> float:
        """Get elapsed time since mode started."""
        if not self.is_active:
            return 0.0
        return time.time() - self.start_time


class CooperativeMode(GameModeBase):
    """
    Cooperative Mode - Squids share resources and learn together.
    
    Features:
    - Shared food pool
    - Collaborative learning boosts
    - Group happiness bonuses
    - Team challenges
    """
    
    def __init__(self, session_id: str, local_node_id: str):
        super().__init__(session_id, local_node_id)
        self.shared_food_pool = 0
        self.team_happiness = 50
        self.collaboration_bonus = 1.0
        self.active_challenge: Optional[Dict[str, Any]] = None
        self.challenge_progress = 0
    
    @property
    def mode_type(self) -> GameModeType:
        return GameModeType.COOPERATIVE
    
    @property
    def display_name(self) -> str:
        return "Cooperative Mode"
    
    def on_start(self) -> None:
        self.shared_food_pool = 50
        self.team_happiness = 50
        self.collaboration_bonus = 1.0
        self._generate_challenge()
    
    def on_update(self, delta_time: float) -> None:
        # Update team happiness based on individual squids
        # (Would integrate with actual squid state in real implementation)
        
        # Decay collaboration bonus slowly
        self.collaboration_bonus = max(1.0, self.collaboration_bonus - 0.001 * delta_time)
        
        # Check if challenge completed
        if self.active_challenge and self.challenge_progress >= self.active_challenge['target']:
            self._complete_challenge()
    
    def on_end(self) -> Dict[str, Any]:
        return {
            'mode': 'cooperative',
            'final_food_pool': self.shared_food_pool,
            'team_happiness': self.team_happiness,
            'scores': self.scores.copy(),
            'challenges_completed': sum(1 for e in self.events if e.event_type == 'challenge_complete'),
            'total_time': self.get_elapsed_time()
        }
    
    def process_player_action(self, node_id: str, action: str, data: Dict[str, Any]) -> bool:
        if action == 'share_food':
            amount = data.get('amount', 1)
            self.shared_food_pool += amount
            self.add_score(node_id, amount * 10)
            self.collaboration_bonus += 0.1
            self.record_event('food_shared', node_id, data={'amount': amount})
            return True
        
        elif action == 'take_food':
            amount = min(data.get('amount', 1), self.shared_food_pool)
            if amount > 0:
                self.shared_food_pool -= amount
                self.record_event('food_taken', node_id, data={'amount': amount})
                return True
            return False
        
        elif action == 'boost_learning':
            # When one squid learns, others get a small boost
            self.record_event('learning_boost', node_id)
            self.collaboration_bonus += 0.05
            return True
        
        elif action == 'contribute_challenge':
            if self.active_challenge:
                contribution = data.get('amount', 1)
                self.challenge_progress += contribution
                self.add_score(node_id, contribution * 5)
                return True
            return False
        
        return False
    
    def _generate_challenge(self) -> None:
        """Generate a team challenge."""
        challenges = [
            {'name': 'Group Feeding', 'target': 100, 'reward_food': 50, 'reward_points': 500},
            {'name': 'Learning Together', 'target': 50, 'reward_food': 25, 'reward_points': 300},
            {'name': 'Happy Squad', 'target': 75, 'reward_food': 30, 'reward_points': 400},
        ]
        self.active_challenge = random.choice(challenges)
        self.challenge_progress = 0
        logger.info(f"New challenge: {self.active_challenge['name']}")
    
    def _complete_challenge(self) -> None:
        """Complete the current challenge."""
        if not self.active_challenge:
            return
        
        self.shared_food_pool += self.active_challenge['reward_food']
        
        # Distribute points to all players
        points_per_player = self.active_challenge['reward_points'] // max(1, len(self.scores))
        for node_id in self.scores:
            self.add_score(node_id, points_per_player)
        
        self.record_event('challenge_complete', 'team', data=self.active_challenge)
        logger.info(f"Challenge completed: {self.active_challenge['name']}")
        
        # Generate new challenge
        self._generate_challenge()


class CompetitiveMode(GameModeBase):
    """
    Competitive Mode - Squids compete in various challenges.
    
    Game Types:
    - Food Race: Collect the most food
    - Territory: Claim and hold areas
    - Speed Challenge: Fastest squid wins
    """
    
    def __init__(self, session_id: str, local_node_id: str, game_type: str = "food_race"):
        super().__init__(session_id, local_node_id)
        self.game_type = game_type
        self.time_limit = 120.0  # 2 minutes
        self.food_collected: Dict[str, int] = {}
        self.territories: Dict[str, str] = {}  # territory_id -> owner_node_id
        self.winner: Optional[str] = None
    
    @property
    def mode_type(self) -> GameModeType:
        return GameModeType.COMPETITIVE
    
    @property
    def display_name(self) -> str:
        type_names = {
            'food_race': 'Food Race',
            'territory': 'Territory Control',
            'speed': 'Speed Challenge'
        }
        return type_names.get(self.game_type, 'Competitive Mode')
    
    def on_start(self) -> None:
        self.food_collected.clear()
        self.territories.clear()
        self.winner = None
        
        # Initialize territories for territory mode
        if self.game_type == 'territory':
            for i in range(4):
                self.territories[f'zone_{i}'] = None
    
    def on_update(self, delta_time: float) -> None:
        elapsed = self.get_elapsed_time()
        
        # Check time limit
        if elapsed >= self.time_limit:
            self._determine_winner()
            self.is_active = False
    
    def on_end(self) -> Dict[str, Any]:
        if not self.winner:
            self._determine_winner()
        
        return {
            'mode': 'competitive',
            'game_type': self.game_type,
            'winner': self.winner,
            'scores': self.scores.copy(),
            'food_collected': self.food_collected.copy(),
            'territories': self.territories.copy(),
            'total_time': self.get_elapsed_time()
        }
    
    def process_player_action(self, node_id: str, action: str, data: Dict[str, Any]) -> bool:
        if action == 'collect_food':
            amount = data.get('amount', 1)
            if node_id not in self.food_collected:
                self.food_collected[node_id] = 0
            self.food_collected[node_id] += amount
            self.add_score(node_id, amount * 10)
            self.record_event('food_collected', node_id, data={'amount': amount})
            return True
        
        elif action == 'claim_territory':
            territory_id = data.get('territory_id')
            if territory_id and territory_id in self.territories:
                old_owner = self.territories[territory_id]
                self.territories[territory_id] = node_id
                self.add_score(node_id, 50)
                
                if old_owner and old_owner != node_id:
                    self.record_event('territory_captured', node_id, old_owner, 
                                    data={'territory': territory_id})
                else:
                    self.record_event('territory_claimed', node_id, 
                                    data={'territory': territory_id})
                return True
            return False
        
        elif action == 'speed_checkpoint':
            checkpoint = data.get('checkpoint', 0)
            time_taken = data.get('time', 0)
            self.add_score(node_id, max(100 - int(time_taken * 10), 10))
            self.record_event('checkpoint_reached', node_id, 
                            data={'checkpoint': checkpoint, 'time': time_taken})
            return True
        
        return False
    
    def _determine_winner(self) -> None:
        """Determine the winner based on game type."""
        if self.game_type == 'food_race':
            if self.food_collected:
                self.winner = max(self.food_collected, key=self.food_collected.get)
        
        elif self.game_type == 'territory':
            # Count territories per player
            territory_counts: Dict[str, int] = {}
            for owner in self.territories.values():
                if owner:
                    territory_counts[owner] = territory_counts.get(owner, 0) + 1
            if territory_counts:
                self.winner = max(territory_counts, key=territory_counts.get)
        
        elif self.game_type == 'speed':
            # Highest score wins (based on checkpoint times)
            if self.scores:
                self.winner = max(self.scores, key=self.scores.get)
        
        if self.winner:
            logger.info(f"Winner determined: {self.winner}")


class SpectatorMode(GameModeBase):
    """
    Spectator Mode - Watch other squids without participating.
    
    Features:
    - Read-only view of the game
    - Can switch between watching different squids
    - Statistics display
    """
    
    def __init__(self, session_id: str, local_node_id: str):
        super().__init__(session_id, local_node_id)
        self.watching_node: Optional[str] = None
        self.available_nodes: List[str] = []
        self.statistics: Dict[str, Any] = {}
    
    @property
    def mode_type(self) -> GameModeType:
        return GameModeType.SPECTATOR
    
    @property
    def display_name(self) -> str:
        return "Spectator Mode"
    
    def on_start(self) -> None:
        self.watching_node = None
        self.available_nodes.clear()
        self.statistics.clear()
    
    def on_update(self, delta_time: float) -> None:
        # Update statistics about watched squid
        pass
    
    def on_end(self) -> Dict[str, Any]:
        return {
            'mode': 'spectator',
            'total_watch_time': self.get_elapsed_time(),
            'nodes_watched': len(set(e.target_node for e in self.events if e.target_node))
        }
    
    def process_player_action(self, node_id: str, action: str, data: Dict[str, Any]) -> bool:
        if action == 'switch_view':
            target = data.get('target_node')
            if target and target in self.available_nodes:
                self.watching_node = target
                self.record_event('view_switched', node_id, target)
                return True
            return False
        
        return False
    
    def add_watchable_node(self, node_id: str) -> None:
        """Add a node that can be watched."""
        if node_id not in self.available_nodes:
            self.available_nodes.append(node_id)
    
    def remove_watchable_node(self, node_id: str) -> None:
        """Remove a node from watchable list."""
        if node_id in self.available_nodes:
            self.available_nodes.remove(node_id)
            if self.watching_node == node_id:
                self.watching_node = self.available_nodes[0] if self.available_nodes else None


class GameModeManager:
    """
    Manages game mode instances and transitions.
    """
    
    def __init__(self, session_id: str, local_node_id: str):
        self.session_id = session_id
        self.local_node_id = local_node_id
        self.current_mode: Optional[GameModeBase] = None
        self._mode_history: List[str] = []
    
    def create_mode(self, mode_type: GameModeType, **kwargs) -> GameModeBase:
        """Create a new game mode instance."""
        if mode_type == GameModeType.COOPERATIVE:
            return CooperativeMode(self.session_id, self.local_node_id)
        elif mode_type == GameModeType.COMPETITIVE:
            game_type = kwargs.get('game_type', 'food_race')
            return CompetitiveMode(self.session_id, self.local_node_id, game_type)
        elif mode_type == GameModeType.SPECTATOR:
            return SpectatorMode(self.session_id, self.local_node_id)
        else:
            raise ValueError(f"Unknown game mode type: {mode_type}")
    
    def start_mode(self, mode_type: GameModeType, **kwargs) -> GameModeBase:
        """Start a new game mode, stopping any current mode."""
        if self.current_mode and self.current_mode.is_active:
            self.current_mode.stop()
        
        self.current_mode = self.create_mode(mode_type, **kwargs)
        self.current_mode.start()
        self._mode_history.append(mode_type.value)
        
        return self.current_mode
    
    def stop_current_mode(self) -> Optional[Dict[str, Any]]:
        """Stop the current game mode and return results."""
        if self.current_mode:
            results = self.current_mode.stop()
            self.current_mode = None
            return results
        return None
    
    def update(self, delta_time: float) -> None:
        """Update the current game mode."""
        if self.current_mode:
            self.current_mode.update(delta_time)
    
    def process_action(self, node_id: str, action: str, data: Dict[str, Any]) -> bool:
        """Process a player action in the current mode."""
        if self.current_mode:
            return self.current_mode.process_player_action(node_id, action, data)
        return False
    
    @staticmethod
    def get_available_modes() -> List[Dict[str, str]]:
        """Get list of available game modes."""
        return [
            {'type': 'cooperative', 'name': 'Cooperative Mode', 
             'description': 'Work together, share resources, complete team challenges'},
            {'type': 'competitive', 'name': 'Food Race', 
             'description': 'Compete to collect the most food'},
            {'type': 'competitive_territory', 'name': 'Territory Control', 
             'description': 'Claim and hold territory zones'},
            {'type': 'spectator', 'name': 'Spectator Mode', 
             'description': 'Watch other squids play'},
        ]
