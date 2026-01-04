# plugins/multiplayer/matchmaking.py
"""
Matchmaking Service - Peer discovery, ranking, and session management
for enhanced multiplayer experiences.
"""

import time
import random
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class MatchmakingState(Enum):
    """Current state of matchmaking process."""
    IDLE = "idle"
    SEARCHING = "searching"
    FOUND_MATCH = "found_match"
    IN_SESSION = "in_session"
    ERROR = "error"


@dataclass
class PeerInfo:
    """Information about a discovered peer."""
    node_id: str
    ip_address: str
    last_seen: float
    personality: Optional[str] = None
    squid_name: Optional[str] = None
    game_mode: Optional[str] = None
    is_host: bool = False
    latency_ms: float = 0.0
    compatibility_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PeerInfo':
        return cls(**data)


@dataclass  
class GameSession:
    """A multiplayer game session."""
    session_id: str
    host_id: str
    game_mode: str
    created_at: float
    max_players: int = 4
    current_players: List[str] = None
    is_public: bool = True
    password: Optional[str] = None
    
    def __post_init__(self):
        if self.current_players is None:
            self.current_players = []
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MatchmakingService:
    """
    Handles peer discovery, matchmaking, and session management
    for multiplayer gameplay.
    
    Features:
    - LAN peer discovery via multicast
    - Personality-based matching for interesting interactions
    - Session creation and management
    - Latency estimation for optimal pairing
    """
    
    # Personality compatibility matrix (higher = more interesting interaction)
    PERSONALITY_COMPATIBILITY = {
        ('curious', 'curious'): 0.8,
        ('curious', 'playful'): 0.9,
        ('curious', 'lazy'): 0.5,
        ('curious', 'anxious'): 0.6,
        ('playful', 'playful'): 0.7,
        ('playful', 'lazy'): 0.4,
        ('playful', 'anxious'): 0.6,
        ('lazy', 'lazy'): 0.3,
        ('lazy', 'anxious'): 0.5,
        ('anxious', 'anxious'): 0.4,
    }
    
    def __init__(self, network_node=None):
        """
        Initialize matchmaking service.
        
        Args:
            network_node: NetworkNode instance for communication
        """
        self.network_node = network_node
        self.state = MatchmakingState.IDLE
        
        # Discovered peers
        self._peers: Dict[str, PeerInfo] = {}
        self._peer_timeout = 30.0  # Seconds before peer is considered stale
        
        # Session management
        self._current_session: Optional[GameSession] = None
        self._available_sessions: Dict[str, GameSession] = {}
        
        # Matchmaking preferences
        self._preferred_mode: Optional[str] = None
        self._my_personality: Optional[str] = None
        self._my_squid_name: Optional[str] = None
        
        # Search state
        self._search_started: float = 0.0
        self._search_timeout: float = 30.0  # Max time to search
        
        logger.info("MatchmakingService initialized")
    
    def set_local_info(self, personality: str, squid_name: str) -> None:
        """Set information about the local squid."""
        self._my_personality = personality
        self._my_squid_name = squid_name
    
    def start_search(self, game_mode: str = "cooperative") -> bool:
        """
        Start searching for matches.
        
        Args:
            game_mode: Desired game mode to play
            
        Returns:
            True if search started successfully
        """
        if self.state == MatchmakingState.SEARCHING:
            logger.warning("Already searching for matches")
            return False
        
        self.state = MatchmakingState.SEARCHING
        self._preferred_mode = game_mode
        self._search_started = time.time()
        
        # Broadcast availability
        self._broadcast_availability()
        
        logger.info(f"Started matchmaking search for mode: {game_mode}")
        return True
    
    def stop_search(self) -> None:
        """Stop the current matchmaking search."""
        if self.state == MatchmakingState.SEARCHING:
            self.state = MatchmakingState.IDLE
            logger.info("Stopped matchmaking search")
    
    def update(self) -> Optional[PeerInfo]:
        """
        Update matchmaking state. Should be called regularly.
        
        Returns:
            Best matched peer if found, None otherwise
        """
        current_time = time.time()
        
        # Clean up stale peers
        self._cleanup_stale_peers(current_time)
        
        if self.state != MatchmakingState.SEARCHING:
            return None
        
        # Check for timeout
        if current_time - self._search_started > self._search_timeout:
            logger.info("Matchmaking search timed out")
            self.state = MatchmakingState.IDLE
            return None
        
        # Find best match among discovered peers
        best_match = self._find_best_match()
        
        if best_match:
            self.state = MatchmakingState.FOUND_MATCH
            logger.info(f"Found match: {best_match.node_id} (score: {best_match.compatibility_score:.2f})")
        
        return best_match
    
    def register_peer(self, peer_info: Dict[str, Any]) -> None:
        """
        Register a discovered peer.
        
        Args:
            peer_info: Dictionary with peer information
        """
        node_id = peer_info.get('node_id')
        if not node_id:
            return
        
        # Skip self
        if self.network_node and node_id == self.network_node.node_id:
            return
        
        peer = PeerInfo(
            node_id=node_id,
            ip_address=peer_info.get('ip_address', ''),
            last_seen=time.time(),
            personality=peer_info.get('personality'),
            squid_name=peer_info.get('squid_name'),
            game_mode=peer_info.get('game_mode'),
            is_host=peer_info.get('is_host', False)
        )
        
        # Calculate compatibility score
        peer.compatibility_score = self._calculate_compatibility(peer)
        
        self._peers[node_id] = peer
        logger.debug(f"Registered peer: {node_id}")
    
    def create_session(self, game_mode: str, is_public: bool = True, 
                      max_players: int = 4) -> GameSession:
        """
        Create a new game session as host.
        
        Args:
            game_mode: Type of game mode
            is_public: Whether session is publicly visible
            max_players: Maximum number of players
            
        Returns:
            Created GameSession
        """
        import uuid
        
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        host_id = self.network_node.node_id if self.network_node else "local"
        
        session = GameSession(
            session_id=session_id,
            host_id=host_id,
            game_mode=game_mode,
            created_at=time.time(),
            max_players=max_players,
            current_players=[host_id],
            is_public=is_public
        )
        
        self._current_session = session
        self.state = MatchmakingState.IN_SESSION
        
        logger.info(f"Created session: {session_id} (mode: {game_mode})")
        return session
    
    def join_session(self, session_id: str) -> bool:
        """
        Join an existing game session.
        
        Args:
            session_id: ID of session to join
            
        Returns:
            True if joined successfully
        """
        if session_id not in self._available_sessions:
            logger.warning(f"Session not found: {session_id}")
            return False
        
        session = self._available_sessions[session_id]
        
        if len(session.current_players) >= session.max_players:
            logger.warning(f"Session is full: {session_id}")
            return False
        
        my_id = self.network_node.node_id if self.network_node else "local"
        session.current_players.append(my_id)
        
        self._current_session = session
        self.state = MatchmakingState.IN_SESSION
        
        logger.info(f"Joined session: {session_id}")
        return True
    
    def leave_session(self) -> None:
        """Leave the current game session."""
        if self._current_session:
            my_id = self.network_node.node_id if self.network_node else "local"
            
            if my_id in self._current_session.current_players:
                self._current_session.current_players.remove(my_id)
            
            # If we're the host and session is empty, destroy it
            if self._current_session.host_id == my_id:
                logger.info(f"Closing session: {self._current_session.session_id}")
            
            self._current_session = None
            self.state = MatchmakingState.IDLE
            
            logger.info("Left session")
    
    def get_available_peers(self) -> List[PeerInfo]:
        """Get list of available peers for matchmaking."""
        self._cleanup_stale_peers(time.time())
        return list(self._peers.values())
    
    def get_session_info(self) -> Optional[Dict[str, Any]]:
        """Get information about current session."""
        if self._current_session:
            return self._current_session.to_dict()
        return None
    
    def _broadcast_availability(self) -> None:
        """Broadcast our availability for matchmaking."""
        if not self.network_node:
            return
        
        availability_msg = {
            'node_id': self.network_node.node_id,
            'personality': self._my_personality,
            'squid_name': self._my_squid_name,
            'game_mode': self._preferred_mode,
            'is_host': False
        }
        
        # Use the network node to broadcast
        try:
            self.network_node.send_message('matchmaking', availability_msg)
        except Exception as e:
            logger.error(f"Failed to broadcast availability: {e}")
    
    def _cleanup_stale_peers(self, current_time: float) -> None:
        """Remove peers that haven't been seen recently."""
        stale_ids = [
            node_id for node_id, peer in self._peers.items()
            if current_time - peer.last_seen > self._peer_timeout
        ]
        
        for node_id in stale_ids:
            del self._peers[node_id]
            logger.debug(f"Removed stale peer: {node_id}")
    
    def _calculate_compatibility(self, peer: PeerInfo) -> float:
        """
        Calculate compatibility score with a peer.
        
        Higher scores indicate more interesting potential interactions.
        """
        score = 0.5  # Base score
        
        # Personality compatibility
        if self._my_personality and peer.personality:
            key = tuple(sorted([self._my_personality.lower(), peer.personality.lower()]))
            personality_score = self.PERSONALITY_COMPATIBILITY.get(key, 0.5)
            score = 0.6 * personality_score + 0.4 * score
        
        # Game mode matching
        if self._preferred_mode and peer.game_mode:
            if self._preferred_mode == peer.game_mode:
                score += 0.2
        
        # Latency penalty
        if peer.latency_ms > 100:
            score -= min(0.3, peer.latency_ms / 1000)
        
        return max(0.0, min(1.0, score))
    
    def _find_best_match(self) -> Optional[PeerInfo]:
        """Find the best matching peer based on compatibility."""
        if not self._peers:
            return None
        
        # Filter peers with matching game mode
        candidates = [
            peer for peer in self._peers.values()
            if peer.game_mode == self._preferred_mode or not self._preferred_mode
        ]
        
        if not candidates:
            return None
        
        # Sort by compatibility score (descending)
        candidates.sort(key=lambda p: p.compatibility_score, reverse=True)
        
        # Return best match if score is acceptable
        best = candidates[0]
        if best.compatibility_score >= 0.3:
            return best
        
        return None
