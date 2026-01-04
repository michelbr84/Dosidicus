# Dosidicus API Reference

This document provides detailed API documentation for developers extending or integrating with Dosidicus.

---

## Table of Contents

1. [Core Modules](#core-modules)
2. [Brain System](#brain-system)
3. [AI & Learning](#ai--learning)
4. [Game Systems](#game-systems)
5. [Multiplayer](#multiplayer)
6. [Platform Utilities](#platform-utilities)

---

## Core Modules

### `tamagotchi_logic.py`

Main game logic controller.

```python
class TamagotchiLogic:
    """Main game state and logic controller."""
    
    def __init__(self, parent_window):
        """Initialize game logic with parent window."""
        
    def update(self) -> None:
        """Called each game tick to update state."""
        
    def feed(self, food_type: str = "normal") -> bool:
        """Feed the squid. Returns success."""
        
    def clean(self) -> bool:
        """Clean the squid. Returns success."""
        
    def play(self) -> bool:
        """Play with the squid. Returns success."""
        
    def give_medicine(self) -> bool:
        """Give medicine if sick. Returns success."""
        
    def save_game(self, filename: str) -> bool:
        """Save current game state."""
        
    def load_game(self, filename: str) -> bool:
        """Load game from file."""
```

### `squid.py`

Squid entity and behavior.

```python
class Squid:
    """The digital pet squid entity."""
    
    # Properties
    hunger: float        # 0-100, higher = more hungry
    happiness: float     # 0-100, higher = happier
    cleanliness: float   # 0-100, higher = cleaner
    sleepiness: float    # 0-100, higher = more tired
    anxiety: float       # 0-100, higher = more anxious
    is_sick: bool        # Whether squid is currently sick
    personality: str     # "curious", "playful", "lazy", "anxious"
    
    def get_state(self) -> Dict[str, Any]:
        """Get current squid state as dictionary."""
        
    def update(self, delta_time: float) -> None:
        """Update squid state for one tick."""
        
    def set_personality(self, personality: str) -> None:
        """Set squid personality type."""
```

---

## Brain System

### `brain_widget.py`

Neural network visualization and management.

```python
class BrainWidget(QWidget):
    """Widget for visualizing and editing the neural network."""
    
    # Signals
    neuron_clicked = pyqtSignal(str)  # Neuron name
    learning_occurred = pyqtSignal(dict)  # Learning event data
    
    def add_neuron(self, name: str, position: Tuple[float, float], 
                   neuron_type: str = "hidden") -> bool:
        """Add a new neuron to the network."""
        
    def add_connection(self, source: str, target: str, 
                       weight: float = 0.5) -> bool:
        """Add connection between neurons."""
        
    def get_neuron_state(self, name: str) -> float:
        """Get activation level of a neuron (0-100)."""
        
    def set_neuron_state(self, name: str, value: float) -> None:
        """Set activation level of a neuron."""
        
    def save_brain(self, filename: str) -> bool:
        """Save current brain configuration."""
        
    def load_brain(self, filename: str) -> bool:
        """Load brain configuration from file."""
```

### `brain_worker.py`

Background processing for brain computations.

```python
class BrainWorker(QThread):
    """Background thread for expensive brain operations."""
    
    # Signals
    neurogenesis_result = pyqtSignal(dict)
    hebbian_result = pyqtSignal(dict)
    state_update_result = pyqtSignal(dict)
    
    def update_cache(self, state: Dict, weights: Dict, 
                     positions: Dict, config: Any) -> None:
        """Update cached brain state for processing."""
        
    def queue_hebbian_learning(self) -> None:
        """Queue Hebbian learning computation."""
        
    def queue_neurogenesis_check(self, context: Dict) -> None:
        """Queue neurogenesis condition check."""
```

---

## AI & Learning

### `reinforcement_learning.py`

Reinforcement learning components.

```python
class RewardSystem:
    """Tracks and calculates rewards for behaviors."""
    
    def calculate_reward(self, current_state: Dict[str, float],
                        action_taken: str,
                        previous_state: Optional[Dict] = None) -> float:
        """Calculate reward for state transition."""
        
    def end_episode(self) -> float:
        """End episode and return total reward."""
        
    def get_average_reward(self, window: int = 100) -> float:
        """Get average reward over recent episodes."""


class QLearningAgent:
    """Q-Learning agent for decision optimization."""
    
    ACTIONS = ['move_random', 'seek_food', 'flee', 'rest', 
               'explore', 'interact', 'clean', 'wait']
    
    def get_action(self, state: Dict[str, float], 
                   explore: bool = True) -> str:
        """Select action using epsilon-greedy strategy."""
        
    def update(self, state: Dict, action: str, reward: float,
               next_state: Dict, done: bool = False) -> float:
        """Update Q-value. Returns TD error."""
        
    def save_q_table(self) -> Dict[str, Any]:
        """Serialize Q-table for saving."""
        
    def load_q_table(self, data: Dict[str, Any]) -> None:
        """Load Q-table from saved data."""


class ExperienceReplayBuffer:
    """Buffer for experience replay learning."""
    
    def add_tuple(self, state: Dict, action: str, reward: float,
                  next_state: Dict, done: bool = False) -> None:
        """Add experience to buffer."""
        
    def sample(self, batch_size: int) -> List[Experience]:
        """Sample random batch of experiences."""
        
    def is_ready(self, min_size: int = 100) -> bool:
        """Check if buffer has enough experiences."""
```

### `evolutionary_algorithm.py`

Genetic optimization for neural networks.

```python
class GeneticOptimizer:
    """Genetic algorithm optimizer for evolving neural weights."""
    
    def __init__(self, population_size: int = 50,
                 elite_fraction: float = 0.1,
                 mutation_rate: float = 0.1):
        """Initialize optimizer with parameters."""
        
    def initialize_population(self, template_genome: Dict[str, float]) -> None:
        """Initialize population from template."""
        
    def evaluate_population(self, 
                           eval_func: Callable[[Individual], Dict]) -> None:
        """Evaluate fitness of all individuals."""
        
    def evolve(self) -> List[Individual]:
        """Perform one generation of evolution."""
        
    def get_best_individual(self) -> Optional[Individual]:
        """Get best individual in population."""
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get evolution statistics."""


class GeneticOperators:
    """Genetic operators for crossover and mutation."""
    
    @staticmethod
    def crossover_uniform(parent1: Dict, parent2: Dict,
                         crossover_rate: float = 0.5) -> Dict:
        """Uniform crossover between parents."""
        
    @staticmethod
    def crossover_blend(parent1: Dict, parent2: Dict,
                       alpha: float = 0.5) -> Dict:
        """Blend crossover between parents."""
        
    @staticmethod
    def mutate_gaussian(genome: Dict, mutation_rate: float = 0.1,
                       mutation_strength: float = 0.1) -> Dict:
        """Apply Gaussian mutation to genome."""
```

---

## Game Systems

### `mini_games.py`

Interactive mini-games.

```python
class MiniGameManager:
    """Manages mini-game instances and progress."""
    
    def get_available_games(self) -> List[Dict[str, str]]:
        """Get list of available games."""
        
    def start_game(self, game_type: str, 
                   difficulty: int = 1) -> Optional[Dict]:
        """Start a new mini-game. Returns initial challenge."""
        
    def submit_answer(self, answer: Any) -> Tuple[bool, int]:
        """Submit answer. Returns (correct, points)."""
        
    def update(self) -> Optional[GameResult]:
        """Update current game. Returns result if ended."""
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall mini-game statistics."""


class MemoryGame(MiniGameBase):
    """Pattern matching memory game."""
    
    def generate_challenge(self) -> Dict[str, Any]:
        """Generate color sequence challenge."""
        
    def check_answer(self, answer: List[str]) -> Tuple[bool, int]:
        """Check if sequence matches."""


class CatchGame(MiniGameBase):
    """Quick reaction catching game."""
    
    def generate_challenge(self) -> Dict[str, Any]:
        """Spawn new falling item."""
        
    def check_answer(self, answer: Dict) -> Tuple[bool, int]:
        """Check if item was caught."""


class PuzzleGame(MiniGameBase):
    """Logic puzzle game."""
    
    def generate_challenge(self) -> Dict[str, Any]:
        """Generate puzzle (pattern, math, sequence, comparison)."""
        
    def check_answer(self, answer: Any) -> Tuple[bool, int]:
        """Check puzzle answer."""
```

### `advanced_care.py`

Advanced care system.

```python
class AdvancedCareSystem:
    """Manages advanced care options."""
    
    def get_available_actions(self) -> List[Dict[str, Any]]:
        """Get all care actions with availability."""
        
    def start_care_session(self, action_id: str,
                          intensity: float = 1.0) -> Optional[Dict]:
        """Start a care session."""
        
    def complete_care_session(self, action_id: str,
                             squid_state: Dict) -> Optional[CareResult]:
        """Complete session and apply effects."""
        
    def get_recommended_care(self, 
                            squid_state: Dict) -> List[str]:
        """Get recommended care based on state."""
        
    def get_care_statistics(self) -> Dict[str, Any]:
        """Get care history statistics."""
```

---

## Multiplayer

### `matchmaking.py`

Peer discovery and matchmaking.

```python
class MatchmakingService:
    """Handles peer discovery and session management."""
    
    def set_local_info(self, personality: str, squid_name: str) -> None:
        """Set local squid information."""
        
    def start_search(self, game_mode: str = "cooperative") -> bool:
        """Start searching for matches."""
        
    def stop_search(self) -> None:
        """Stop current search."""
        
    def update(self) -> Optional[PeerInfo]:
        """Update matchmaking. Returns match if found."""
        
    def register_peer(self, peer_info: Dict[str, Any]) -> None:
        """Register a discovered peer."""
        
    def create_session(self, game_mode: str, 
                      is_public: bool = True) -> GameSession:
        """Create new game session as host."""
        
    def join_session(self, session_id: str) -> bool:
        """Join existing session."""
        
    def leave_session(self) -> None:
        """Leave current session."""
```

### `game_modes.py`

Multiplayer game modes.

```python
class GameModeManager:
    """Manages game mode instances."""
    
    def start_mode(self, mode_type: GameModeType, 
                   **kwargs) -> GameModeBase:
        """Start a new game mode."""
        
    def stop_current_mode(self) -> Optional[Dict[str, Any]]:
        """Stop current mode and return results."""
        
    def update(self, delta_time: float) -> None:
        """Update current game mode."""
        
    def process_action(self, node_id: str, action: str,
                      data: Dict) -> bool:
        """Process player action."""
        
    @staticmethod
    def get_available_modes() -> List[Dict[str, str]]:
        """Get list of available game modes."""


class CooperativeMode(GameModeBase):
    """Cooperative team-based mode."""
    
    shared_food_pool: int
    team_happiness: int
    collaboration_bonus: float
    
    def process_player_action(self, node_id: str, action: str,
                             data: Dict) -> bool:
        """Handle: share_food, take_food, boost_learning, contribute_challenge."""


class CompetitiveMode(GameModeBase):
    """Competitive game modes."""
    
    game_type: str  # "food_race", "territory", "speed"
    time_limit: float
    
    def process_player_action(self, node_id: str, action: str,
                             data: Dict) -> bool:
        """Handle: collect_food, claim_territory, speed_checkpoint."""
```

---

## Platform Utilities

### `platform_compat.py`

Cross-platform compatibility.

```python
def get_platform_info() -> PlatformInfo:
    """Get platform information singleton."""
    
def get_path_handler() -> PathHandler:
    """Get path handler singleton."""
    
def get_font_fallback() -> FontFallback:
    """Get font fallback singleton."""
    
def get_network_compat() -> NetworkCompat:
    """Get network compat singleton."""


class PlatformInfo:
    """Platform detection information."""
    
    system: str         # "windows", "linux", "darwin"
    is_windows: bool
    is_linux: bool
    is_macos: bool
    desktop_env: str    # Linux desktop environment
    
    def get_info(self) -> Dict[str, Any]:
        """Get all platform info as dictionary."""


class PathHandler:
    """Cross-platform path handling."""
    
    def get_app_data_dir(self) -> Path:
        """Get application data directory."""
        
    def get_config_dir(self) -> Path:
        """Get configuration directory."""
        
    def get_cache_dir(self) -> Path:
        """Get cache directory."""
        
    def get_log_dir(self) -> Path:
        """Get log directory."""
        
    def normalize_path(self, path: str) -> str:
        """Normalize path for current platform."""
        
    def ensure_dir(self, path: Path) -> bool:
        """Ensure directory exists."""


class FontFallback:
    """Font fallback system."""
    
    def get_font_family(self, font_type: str = 'ui') -> str:
        """Get best available font. Types: 'ui', 'mono', 'emoji'."""


class NetworkCompat:
    """Cross-platform network utilities."""
    
    def get_local_ip(self) -> str:
        """Get local IP address."""
        
    def get_network_interfaces(self) -> List[Dict[str, Any]]:
        """Get list of network interfaces."""
        
    def is_multicast_available(self) -> bool:
        """Check if multicast is available."""
```

---

## Plugin Development

### Creating a Plugin

```python
# plugins/my_plugin/__init__.py

from plugins.base_plugin import BasePlugin

class MyPlugin(BasePlugin):
    """Custom plugin example."""
    
    name = "My Plugin"
    version = "1.0.0"
    
    def on_load(self) -> None:
        """Called when plugin is loaded."""
        self.register_handler('squid_update', self.on_squid_update)
        
    def on_unload(self) -> None:
        """Called when plugin is unloaded."""
        pass
        
    def on_squid_update(self, squid_state: Dict) -> None:
        """Handle squid state update."""
        pass
```

### Available Hooks

| Hook | Description | Parameters |
|------|-------------|------------|
| `game_start` | Game started | None |
| `game_save` | Game saving | filename |
| `game_load` | Game loading | filename |
| `squid_update` | Squid state changed | squid_state |
| `neuron_added` | New neuron created | neuron_name, position |
| `learning_event` | Learning occurred | learning_data |

---

*For more details, see the source code or contact the developers.*
