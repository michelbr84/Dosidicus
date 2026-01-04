# src/mini_games.py
"""
Mini-Games Module - Interactive games for squid training and entertainment.
"""

import time
import random
import logging
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class GameState(Enum):
    """State of a mini-game."""
    NOT_STARTED = "not_started"
    PLAYING = "playing"
    PAUSED = "paused"
    WON = "won"
    LOST = "lost"


@dataclass
class GameResult:
    """Result of a completed mini-game."""
    game_type: str
    score: int
    max_score: int
    time_taken: float
    rewards: Dict[str, float]
    success: bool


class MiniGameBase(ABC):
    """Base class for all mini-games."""
    
    def __init__(self, difficulty: int = 1):
        """
        Initialize mini-game.
        
        Args:
            difficulty: Difficulty level (1-5)
        """
        self.difficulty = max(1, min(5, difficulty))
        self.state = GameState.NOT_STARTED
        self.score = 0
        self.max_score = 100
        self.start_time = 0.0
        self.time_limit = 60.0  # Default 60 seconds
        self._callbacks: Dict[str, List[Callable]] = {}
    
    @property
    @abstractmethod
    def game_type(self) -> str:
        """Return the type of this game."""
        pass
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name for this game."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Description of the game."""
        pass
    
    @abstractmethod
    def generate_challenge(self) -> Dict[str, Any]:
        """Generate a new challenge/puzzle."""
        pass
    
    @abstractmethod
    def check_answer(self, answer: Any) -> Tuple[bool, int]:
        """Check if answer is correct. Returns (is_correct, points_earned)."""
        pass
    
    @abstractmethod
    def get_display_data(self) -> Dict[str, Any]:
        """Get data for UI display."""
        pass
    
    def start(self) -> Dict[str, Any]:
        """Start the game."""
        self.state = GameState.PLAYING
        self.score = 0
        self.start_time = time.time()
        challenge = self.generate_challenge()
        self._trigger_callback('game_started', challenge)
        return challenge
    
    def submit_answer(self, answer: Any) -> Tuple[bool, int]:
        """Submit an answer."""
        if self.state != GameState.PLAYING:
            return False, 0
        
        correct, points = self.check_answer(answer)
        if correct:
            self.score += points
            self._trigger_callback('correct_answer', {'points': points})
        else:
            self._trigger_callback('wrong_answer', {})
        
        return correct, points
    
    def update(self) -> Optional[GameResult]:
        """Update game state. Returns result if game ended."""
        if self.state != GameState.PLAYING:
            return None
        
        elapsed = time.time() - self.start_time
        if elapsed >= self.time_limit:
            return self.end_game(won=self.score >= self.max_score * 0.6)
        
        return None
    
    def end_game(self, won: bool = False) -> GameResult:
        """End the game and return result."""
        self.state = GameState.WON if won else GameState.LOST
        
        result = GameResult(
            game_type=self.game_type,
            score=self.score,
            max_score=self.max_score,
            time_taken=time.time() - self.start_time,
            rewards=self._calculate_rewards(),
            success=won
        )
        
        self._trigger_callback('game_ended', result)
        return result
    
    def _calculate_rewards(self) -> Dict[str, float]:
        """Calculate rewards based on performance."""
        score_ratio = self.score / max(1, self.max_score)
        
        return {
            'happiness': score_ratio * 10 * self.difficulty,
            'intelligence': score_ratio * 5 * self.difficulty,
            'curiosity_reduction': score_ratio * -15
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
                logger.error(f"Callback error: {e}")


class MemoryGame(MiniGameBase):
    """
    Pattern matching memory game - improves squid memory.
    
    Show a sequence of colors/patterns, then ask player to repeat it.
    """
    
    COLORS = ['red', 'blue', 'green', 'yellow', 'purple', 'orange']
    
    def __init__(self, difficulty: int = 1):
        super().__init__(difficulty)
        self.sequence: List[str] = []
        self.player_sequence: List[str] = []
        self.sequence_length = 3 + difficulty
        self.current_round = 0
        self.max_rounds = 5
        self.max_score = self.max_rounds * 20
    
    @property
    def game_type(self) -> str:
        return "memory"
    
    @property
    def display_name(self) -> str:
        return "Memory Match"
    
    @property
    def description(self) -> str:
        return "Remember and repeat the color sequence to improve your squid's memory!"
    
    def generate_challenge(self) -> Dict[str, Any]:
        """Generate a new color sequence."""
        self.sequence = [random.choice(self.COLORS) for _ in range(self.sequence_length)]
        self.player_sequence = []
        self.current_round += 1
        
        return {
            'round': self.current_round,
            'sequence': self.sequence,
            'sequence_length': len(self.sequence),
            'display_time': 0.5 + self.sequence_length * 0.3
        }
    
    def check_answer(self, answer: List[str]) -> Tuple[bool, int]:
        """Check if the sequence matches."""
        self.player_sequence = answer
        
        if self.player_sequence == self.sequence:
            points = 20 + (self.difficulty * 5)
            
            # Bonus for long sequences
            if len(self.sequence) > 5:
                points += (len(self.sequence) - 5) * 3
            
            # Generate next challenge if not at max rounds
            if self.current_round < self.max_rounds:
                self.sequence_length += 1  # Increase difficulty
                self.generate_challenge()
            
            return True, points
        
        return False, 0
    
    def get_display_data(self) -> Dict[str, Any]:
        return {
            'game_type': self.game_type,
            'round': self.current_round,
            'max_rounds': self.max_rounds,
            'score': self.score,
            'sequence_length': len(self.sequence),
            'colors_available': self.COLORS
        }


class CatchGame(MiniGameBase):
    """
    Quick reaction catch game - improves squid agility.
    
    Click/tap falling food items before they disappear.
    """
    
    ITEM_TYPES = [
        {'name': 'fish', 'points': 10, 'speed': 1.0},
        {'name': 'shrimp', 'points': 15, 'speed': 1.2},
        {'name': 'special_fish', 'points': 25, 'speed': 1.5},
        {'name': 'bomb', 'points': -20, 'speed': 0.8}  # Avoid this!
    ]
    
    def __init__(self, difficulty: int = 1):
        super().__init__(difficulty)
        self.active_items: List[Dict[str, Any]] = []
        self.items_spawned = 0
        self.items_caught = 0
        self.items_missed = 0
        self.spawn_rate = 1.5 - (difficulty * 0.2)  # Faster at higher difficulty
        self.last_spawn = 0.0
        self.max_score = 200
        self.time_limit = 30.0
    
    @property
    def game_type(self) -> str:
        return "catch"
    
    @property
    def display_name(self) -> str:
        return "Food Catch"
    
    @property
    def description(self) -> str:
        return "Catch falling food items! Avoid the bombs! Train your squid's reflexes."
    
    def generate_challenge(self) -> Dict[str, Any]:
        """Spawn a new item."""
        # Choose item type (bombs less common)
        weights = [0.4, 0.3, 0.2, 0.1]
        item_type = random.choices(self.ITEM_TYPES, weights=weights)[0]
        
        item = {
            'id': self.items_spawned,
            'type': item_type['name'],
            'points': item_type['points'],
            'x': random.uniform(0.1, 0.9),  # Position 10%-90% of screen
            'y': 0.0,
            'speed': item_type['speed'] * (1 + self.difficulty * 0.1),
            'spawn_time': time.time()
        }
        
        self.active_items.append(item)
        self.items_spawned += 1
        self.last_spawn = time.time()
        
        return item
    
    def check_answer(self, answer: Dict[str, Any]) -> Tuple[bool, int]:
        """Check if an item was caught."""
        item_id = answer.get('item_id')
        click_x = answer.get('x', 0)
        click_y = answer.get('y', 0)
        
        for item in self.active_items:
            if item['id'] == item_id:
                # Item caught!
                self.active_items.remove(item)
                self.items_caught += 1
                
                points = item['points']
                
                # Bonus for fast catches
                reaction_time = time.time() - item['spawn_time']
                if reaction_time < 1.0:
                    points = int(points * 1.5)
                
                return True, points
        
        return False, 0
    
    def update(self) -> Optional[GameResult]:
        """Update game, spawn new items, remove missed items."""
        result = super().update()
        if result:
            return result
        
        current_time = time.time()
        
        # Spawn new items periodically
        if current_time - self.last_spawn > self.spawn_rate:
            self.generate_challenge()
        
        # Update item positions and remove missed items
        for item in self.active_items[:]:
            elapsed = current_time - item['spawn_time']
            item['y'] = elapsed * item['speed'] * 0.3  # Move down
            
            if item['y'] > 1.0:  # Off screen
                self.active_items.remove(item)
                if item['points'] > 0:  # Don't count bombs as missed
                    self.items_missed += 1
        
        return None
    
    def get_display_data(self) -> Dict[str, Any]:
        return {
            'game_type': self.game_type,
            'score': self.score,
            'items_caught': self.items_caught,
            'items_missed': self.items_missed,
            'active_items': self.active_items,
            'time_remaining': max(0, self.time_limit - (time.time() - self.start_time))
        }


class PuzzleGame(MiniGameBase):
    """
    Logic puzzle game - improves squid cognitive abilities.
    
    Solve simple logic puzzles (pattern completion, simple math, etc.)
    """
    
    PUZZLE_TYPES = ['pattern', 'math', 'sequence', 'comparison']
    
    def __init__(self, difficulty: int = 1):
        super().__init__(difficulty)
        self.current_puzzle: Optional[Dict[str, Any]] = None
        self.puzzles_solved = 0
        self.max_puzzles = 10
        self.max_score = self.max_puzzles * 15
        self.time_limit = 90.0
    
    @property
    def game_type(self) -> str:
        return "puzzle"
    
    @property
    def display_name(self) -> str:
        return "Brain Teasers"
    
    @property
    def description(self) -> str:
        return "Solve puzzles to boost your squid's intelligence!"
    
    def generate_challenge(self) -> Dict[str, Any]:
        """Generate a new puzzle."""
        puzzle_type = random.choice(self.PUZZLE_TYPES)
        
        if puzzle_type == 'pattern':
            puzzle = self._generate_pattern_puzzle()
        elif puzzle_type == 'math':
            puzzle = self._generate_math_puzzle()
        elif puzzle_type == 'sequence':
            puzzle = self._generate_sequence_puzzle()
        else:
            puzzle = self._generate_comparison_puzzle()
        
        self.current_puzzle = puzzle
        return puzzle
    
    def _generate_pattern_puzzle(self) -> Dict[str, Any]:
        """Generate a pattern completion puzzle."""
        patterns = [
            {'sequence': ['🔴', '🔵', '🔴', '🔵', '?'], 'answer': '🔴'},
            {'sequence': ['⬛', '⬛', '⬜', '⬛', '⬛', '?'], 'answer': '⬜'},
            {'sequence': ['🌙', '⭐', '⭐', '🌙', '⭐', '?'], 'answer': '⭐'},
        ]
        
        pattern = random.choice(patterns)
        
        # Generate wrong answers
        all_symbols = ['🔴', '🔵', '⬛', '⬜', '🌙', '⭐', '🟢', '🟡']
        wrong_answers = random.sample([s for s in all_symbols if s != pattern['answer']], 3)
        options = [pattern['answer']] + wrong_answers
        random.shuffle(options)
        
        return {
            'type': 'pattern',
            'question': 'What comes next?',
            'sequence': pattern['sequence'],
            'options': options,
            'answer': pattern['answer']
        }
    
    def _generate_math_puzzle(self) -> Dict[str, Any]:
        """Generate a simple math puzzle."""
        a = random.randint(1, 5 * self.difficulty)
        b = random.randint(1, 5 * self.difficulty)
        
        operations = ['+', '-', '*']
        op = random.choice(operations)
        
        if op == '+':
            answer = a + b
        elif op == '-':
            a, b = max(a, b), min(a, b)  # Ensure positive result
            answer = a - b
        else:
            answer = a * b
        
        # Generate wrong answers
        wrong_answers = [
            answer + random.randint(1, 5),
            answer - random.randint(1, min(5, max(1, answer))),
            answer + random.randint(-3, 3)
        ]
        wrong_answers = [w for w in wrong_answers if w != answer and w >= 0][:3]
        
        while len(wrong_answers) < 3:
            wrong_answers.append(answer + random.randint(1, 10))
        
        options = [answer] + wrong_answers[:3]
        random.shuffle(options)
        
        return {
            'type': 'math',
            'question': f'What is {a} {op} {b}?',
            'options': options,
            'answer': answer
        }
    
    def _generate_sequence_puzzle(self) -> Dict[str, Any]:
        """Generate a number sequence puzzle."""
        # Arithmetic sequence
        start = random.randint(1, 10)
        step = random.randint(1, 5)
        
        sequence = [start + i * step for i in range(4)]
        answer = start + 4 * step
        
        wrong_answers = [answer + random.randint(1, 5) for _ in range(3)]
        options = [answer] + wrong_answers
        random.shuffle(options)
        
        return {
            'type': 'sequence',
            'question': 'What number comes next?',
            'sequence': sequence + ['?'],
            'options': options,
            'answer': answer
        }
    
    def _generate_comparison_puzzle(self) -> Dict[str, Any]:
        """Generate a comparison puzzle."""
        items = [
            ('🐟', random.randint(1, 10)),
            ('🦐', random.randint(1, 10)),
            ('🐙', random.randint(1, 10))
        ]
        
        max_item = max(items, key=lambda x: x[1])
        
        return {
            'type': 'comparison',
            'question': 'Which has the most?',
            'items': [(item[0], item[1]) for item in items],
            'options': [item[0] for item in items],
            'answer': max_item[0]
        }
    
    def check_answer(self, answer: Any) -> Tuple[bool, int]:
        """Check if the puzzle answer is correct."""
        if not self.current_puzzle:
            return False, 0
        
        correct = answer == self.current_puzzle['answer']
        
        if correct:
            self.puzzles_solved += 1
            points = 15 + (self.difficulty * 3)
            
            if self.puzzles_solved < self.max_puzzles:
                self.generate_challenge()
            
            return True, points
        
        return False, -5  # Penalty for wrong answer
    
    def get_display_data(self) -> Dict[str, Any]:
        return {
            'game_type': self.game_type,
            'score': self.score,
            'puzzles_solved': self.puzzles_solved,
            'max_puzzles': self.max_puzzles,
            'current_puzzle': self.current_puzzle,
            'time_remaining': max(0, self.time_limit - (time.time() - self.start_time))
        }


class MiniGameManager:
    """
    Manages mini-game instances and tracks progress.
    """
    
    GAME_CLASSES = {
        'memory': MemoryGame,
        'catch': CatchGame,
        'puzzle': PuzzleGame
    }
    
    def __init__(self):
        self.current_game: Optional[MiniGameBase] = None
        self.game_history: List[GameResult] = []
        self.total_games_played = 0
        self.total_score = 0
    
    def get_available_games(self) -> List[Dict[str, str]]:
        """Get list of available mini-games."""
        return [
            {'type': 'memory', 'name': 'Memory Match', 
             'description': 'Remember and repeat color sequences'},
            {'type': 'catch', 'name': 'Food Catch', 
             'description': 'Catch falling food items'},
            {'type': 'puzzle', 'name': 'Brain Teasers', 
             'description': 'Solve logic puzzles'},
        ]
    
    def start_game(self, game_type: str, difficulty: int = 1) -> Optional[Dict[str, Any]]:
        """
        Start a new mini-game.
        
        Args:
            game_type: Type of game to start
            difficulty: Difficulty level (1-5)
            
        Returns:
            Initial challenge data, or None if game type not found
        """
        if game_type not in self.GAME_CLASSES:
            logger.warning(f"Unknown game type: {game_type}")
            return None
        
        # End any current game
        if self.current_game and self.current_game.state == GameState.PLAYING:
            self.end_current_game()
        
        # Create and start new game
        game_class = self.GAME_CLASSES[game_type]
        self.current_game = game_class(difficulty)
        
        return self.current_game.start()
    
    def submit_answer(self, answer: Any) -> Tuple[bool, int]:
        """Submit an answer to the current game."""
        if not self.current_game:
            return False, 0
        
        return self.current_game.submit_answer(answer)
    
    def update(self) -> Optional[GameResult]:
        """Update current game and return result if ended."""
        if not self.current_game:
            return None
        
        return self.current_game.update()
    
    def end_current_game(self) -> Optional[GameResult]:
        """End the current game."""
        if not self.current_game:
            return None
        
        result = self.current_game.end_game()
        self.game_history.append(result)
        self.total_games_played += 1
        self.total_score += result.score
        
        self.current_game = None
        return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall mini-game statistics."""
        if not self.game_history:
            return {
                'total_games': 0,
                'total_score': 0,
                'win_rate': 0,
                'favorite_game': None
            }
        
        wins = sum(1 for r in self.game_history if r.success)
        
        # Count game types
        game_counts: Dict[str, int] = {}
        for result in self.game_history:
            game_counts[result.game_type] = game_counts.get(result.game_type, 0) + 1
        
        favorite = max(game_counts, key=game_counts.get) if game_counts else None
        
        return {
            'total_games': self.total_games_played,
            'total_score': self.total_score,
            'win_rate': wins / len(self.game_history) if self.game_history else 0,
            'games_won': wins,
            'favorite_game': favorite,
            'recent_results': [r.game_type for r in self.game_history[-10:]]
        }
