# src/reinforcement_learning.py
"""
Reinforcement Learning Module - Q-Learning and reward systems for enhanced squid learning.
"""

import time
import random
import math
import logging
from typing import Dict, List, Optional, Any, Tuple
from collections import deque
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Experience:
    """A single experience tuple for replay."""
    state: Dict[str, float]
    action: str
    reward: float
    next_state: Dict[str, float]
    done: bool
    timestamp: float


class RewardSystem:
    """
    Tracks and calculates rewards for squid behaviors.
    
    Rewards are based on:
    - Health maintenance (hunger, cleanliness, etc.)
    - Exploration and curiosity satisfaction
    - Social interactions
    - Learning and memory formation
    """
    
    # Reward weights for different behaviors
    REWARD_WEIGHTS = {
        'eat_food': 1.0,
        'satisfy_hunger': 2.0,
        'maintain_cleanliness': 0.5,
        'rest_when_tired': 1.5,
        'explore_new_area': 0.8,
        'learn_new_pattern': 2.0,
        'positive_interaction': 1.2,
        'avoid_danger': 1.5,
        'survive_timestep': 0.1,
    }
    
    # Penalty weights
    PENALTY_WEIGHTS = {
        'starving': -2.0,
        'exhausted': -1.5,
        'sick': -2.5,
        'dirty': -0.5,
        'high_anxiety': -1.0,
        'ignored_food': -0.3,
    }
    
    def __init__(self, decay_rate: float = 0.99):
        """
        Initialize reward system.
        
        Args:
            decay_rate: Discount factor for future rewards
        """
        self.decay_rate = decay_rate
        self.cumulative_reward = 0.0
        self.episode_rewards: List[float] = []
        self.reward_history: deque = deque(maxlen=1000)
        self._last_state: Optional[Dict[str, float]] = None
    
    def calculate_reward(self, 
                        current_state: Dict[str, float],
                        action_taken: str,
                        previous_state: Optional[Dict[str, float]] = None) -> float:
        """
        Calculate reward for an action based on state transition.
        
        Args:
            current_state: Current squid state
            action_taken: Action that was performed
            previous_state: State before the action
            
        Returns:
            Calculated reward value
        """
        prev = previous_state or self._last_state or current_state
        reward = 0.0
        
        # Survival reward
        reward += self.REWARD_WEIGHTS['survive_timestep']
        
        # Check for improvements
        if current_state.get('hunger', 50) < prev.get('hunger', 50):
            reward += self.REWARD_WEIGHTS['satisfy_hunger']
        
        if current_state.get('cleanliness', 50) > prev.get('cleanliness', 50):
            reward += self.REWARD_WEIGHTS['maintain_cleanliness']
        
        if current_state.get('sleepiness', 50) < prev.get('sleepiness', 50):
            if prev.get('sleepiness', 50) > 70:  # Was tired
                reward += self.REWARD_WEIGHTS['rest_when_tired']
        
        if current_state.get('curiosity', 50) < prev.get('curiosity', 50):
            reward += self.REWARD_WEIGHTS['explore_new_area']
        
        # Action-specific rewards
        if action_taken == 'eat' and current_state.get('is_eating'):
            reward += self.REWARD_WEIGHTS['eat_food']
        
        # Check for penalties
        if current_state.get('hunger', 50) > 90:
            reward += self.PENALTY_WEIGHTS['starving']
        
        if current_state.get('sleepiness', 50) > 90:
            reward += self.PENALTY_WEIGHTS['exhausted']
        
        if current_state.get('is_sick'):
            reward += self.PENALTY_WEIGHTS['sick']
        
        if current_state.get('cleanliness', 50) < 20:
            reward += self.PENALTY_WEIGHTS['dirty']
        
        if current_state.get('anxiety', 50) > 80:
            reward += self.PENALTY_WEIGHTS['high_anxiety']
        
        # Store for next calculation
        self._last_state = current_state.copy()
        
        # Track reward
        self.cumulative_reward += reward
        self.reward_history.append((time.time(), reward))
        
        return reward
    
    def get_episode_return(self) -> float:
        """Get the total return for the current episode."""
        return self.cumulative_reward
    
    def end_episode(self) -> float:
        """End the current episode and return total reward."""
        episode_return = self.cumulative_reward
        self.episode_rewards.append(episode_return)
        self.cumulative_reward = 0.0
        return episode_return
    
    def get_average_reward(self, window: int = 100) -> float:
        """Get average reward over recent episodes."""
        if not self.episode_rewards:
            return 0.0
        recent = self.episode_rewards[-window:]
        return sum(recent) / len(recent)


class QLearningAgent:
    """
    Q-Learning agent for decision optimization.
    
    Uses a simplified state representation and discretized Q-table
    for efficient learning in the squid simulation environment.
    """
    
    # Discretization levels for continuous states
    STATE_BINS = 5  # Low, Medium-Low, Medium, Medium-High, High
    
    # Available actions
    ACTIONS = [
        'move_random',
        'seek_food',
        'flee',
        'rest',
        'explore',
        'interact',
        'clean',
        'wait'
    ]
    
    def __init__(self,
                 learning_rate: float = 0.1,
                 discount_factor: float = 0.95,
                 exploration_rate: float = 0.3,
                 exploration_decay: float = 0.995,
                 min_exploration: float = 0.05):
        """
        Initialize Q-Learning agent.
        
        Args:
            learning_rate: Alpha - rate of Q-value updates
            discount_factor: Gamma - importance of future rewards
            exploration_rate: Epsilon - initial exploration probability
            exploration_decay: Rate of exploration decay
            min_exploration: Minimum exploration rate
        """
        self.alpha = learning_rate
        self.gamma = discount_factor
        self.epsilon = exploration_rate
        self.epsilon_decay = exploration_decay
        self.epsilon_min = min_exploration
        
        # Q-table: state_key -> {action: q_value}
        self.q_table: Dict[str, Dict[str, float]] = {}
        
        # State features to consider
        self.state_features = ['hunger', 'happiness', 'sleepiness', 'anxiety', 'cleanliness']
        
        # Learning statistics
        self.total_updates = 0
        self.action_counts: Dict[str, int] = {a: 0 for a in self.ACTIONS}
    
    def _discretize_state(self, state: Dict[str, float]) -> str:
        """
        Convert continuous state to discrete state key.
        
        Args:
            state: Continuous state dictionary
            
        Returns:
            String key for Q-table lookup
        """
        discretized = []
        
        for feature in self.state_features:
            value = state.get(feature, 50)
            
            # Handle boolean values
            if isinstance(value, bool):
                value = 100 if value else 0
            
            # Discretize to bins
            if value < 20:
                bin_idx = 0
            elif value < 40:
                bin_idx = 1
            elif value < 60:
                bin_idx = 2
            elif value < 80:
                bin_idx = 3
            else:
                bin_idx = 4
            
            discretized.append(str(bin_idx))
        
        return '_'.join(discretized)
    
    def get_action(self, state: Dict[str, float], explore: bool = True) -> str:
        """
        Select an action using epsilon-greedy strategy.
        
        Args:
            state: Current state
            explore: Whether to use exploration
            
        Returns:
            Selected action string
        """
        state_key = self._discretize_state(state)
        
        # Exploration: random action
        if explore and random.random() < self.epsilon:
            action = random.choice(self.ACTIONS)
        else:
            # Exploitation: best known action
            action = self._get_best_action(state_key)
        
        self.action_counts[action] += 1
        return action
    
    def _get_best_action(self, state_key: str) -> str:
        """Get the best action for a state based on Q-values."""
        if state_key not in self.q_table:
            # Initialize with small random values
            self.q_table[state_key] = {a: random.uniform(-0.1, 0.1) for a in self.ACTIONS}
        
        q_values = self.q_table[state_key]
        max_q = max(q_values.values())
        
        # Get all actions with max Q-value (tie-breaking randomly)
        best_actions = [a for a, q in q_values.items() if q == max_q]
        return random.choice(best_actions)
    
    def update(self, state: Dict[str, float], action: str, 
               reward: float, next_state: Dict[str, float], done: bool = False) -> float:
        """
        Update Q-value using the Q-learning update rule.
        
        Q(s,a) = Q(s,a) + α * (r + γ * max(Q(s',a')) - Q(s,a))
        
        Args:
            state: Previous state
            action: Action taken
            reward: Reward received
            next_state: Resulting state
            done: Whether episode ended
            
        Returns:
            TD error
        """
        state_key = self._discretize_state(state)
        next_state_key = self._discretize_state(next_state)
        
        # Initialize Q-values if needed
        if state_key not in self.q_table:
            self.q_table[state_key] = {a: 0.0 for a in self.ACTIONS}
        if next_state_key not in self.q_table:
            self.q_table[next_state_key] = {a: 0.0 for a in self.ACTIONS}
        
        # Current Q-value
        current_q = self.q_table[state_key].get(action, 0.0)
        
        # Max Q-value for next state
        if done:
            max_next_q = 0.0
        else:
            max_next_q = max(self.q_table[next_state_key].values())
        
        # TD target and error
        td_target = reward + self.gamma * max_next_q
        td_error = td_target - current_q
        
        # Update Q-value
        new_q = current_q + self.alpha * td_error
        self.q_table[state_key][action] = new_q
        
        self.total_updates += 1
        return td_error
    
    def decay_exploration(self) -> float:
        """Decay exploration rate and return new value."""
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
        return self.epsilon
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get learning statistics."""
        return {
            'total_updates': self.total_updates,
            'states_explored': len(self.q_table),
            'exploration_rate': self.epsilon,
            'action_distribution': self.action_counts.copy()
        }
    
    def save_q_table(self) -> Dict[str, Any]:
        """Serialize Q-table for saving."""
        return {
            'q_table': self.q_table.copy(),
            'epsilon': self.epsilon,
            'total_updates': self.total_updates
        }
    
    def load_q_table(self, data: Dict[str, Any]) -> None:
        """Load Q-table from saved data."""
        self.q_table = data.get('q_table', {})
        self.epsilon = data.get('epsilon', self.epsilon)
        self.total_updates = data.get('total_updates', 0)


class ExperienceReplayBuffer:
    """
    Experience replay buffer for more stable learning.
    
    Stores experiences and provides random sampling for batch updates.
    """
    
    def __init__(self, capacity: int = 10000):
        """
        Initialize replay buffer.
        
        Args:
            capacity: Maximum number of experiences to store
        """
        self.buffer: deque = deque(maxlen=capacity)
        self.capacity = capacity
    
    def add(self, experience: Experience) -> None:
        """Add an experience to the buffer."""
        self.buffer.append(experience)
    
    def add_tuple(self, state: Dict[str, float], action: str, reward: float,
                  next_state: Dict[str, float], done: bool = False) -> None:
        """Add experience as individual components."""
        exp = Experience(
            state=state.copy(),
            action=action,
            reward=reward,
            next_state=next_state.copy(),
            done=done,
            timestamp=time.time()
        )
        self.add(exp)
    
    def sample(self, batch_size: int) -> List[Experience]:
        """
        Sample a random batch of experiences.
        
        Args:
            batch_size: Number of experiences to sample
            
        Returns:
            List of Experience objects
        """
        batch_size = min(batch_size, len(self.buffer))
        return random.sample(list(self.buffer), batch_size)
    
    def __len__(self) -> int:
        return len(self.buffer)
    
    def is_ready(self, min_size: int = 100) -> bool:
        """Check if buffer has enough experiences for training."""
        return len(self.buffer) >= min_size
    
    def clear(self) -> None:
        """Clear all experiences."""
        self.buffer.clear()


class ReinforcementLearningIntegration:
    """
    Integration layer connecting RL components to the squid brain.
    """
    
    def __init__(self):
        self.reward_system = RewardSystem()
        self.q_agent = QLearningAgent()
        self.replay_buffer = ExperienceReplayBuffer()
        
        self._last_state: Optional[Dict[str, float]] = None
        self._last_action: Optional[str] = None
        self._episode_steps = 0
        self._total_episodes = 0
    
    def step(self, current_state: Dict[str, float], 
             action_taken: Optional[str] = None) -> Tuple[str, float]:
        """
        Perform one learning step.
        
        Args:
            current_state: Current squid state
            action_taken: Action that was taken (or None to request one)
            
        Returns:
            Tuple of (suggested_action, reward)
        """
        reward = 0.0
        
        # Calculate reward for previous action
        if self._last_state is not None and self._last_action is not None:
            reward = self.reward_system.calculate_reward(
                current_state, 
                self._last_action,
                self._last_state
            )
            
            # Update Q-table
            self.q_agent.update(
                self._last_state,
                self._last_action,
                reward,
                current_state
            )
            
            # Store experience
            self.replay_buffer.add_tuple(
                self._last_state,
                self._last_action,
                reward,
                current_state
            )
        
        # Get suggested action
        suggested_action = self.q_agent.get_action(current_state)
        
        # Store for next step
        self._last_state = current_state.copy()
        self._last_action = action_taken or suggested_action
        self._episode_steps += 1
        
        # Periodic batch learning from replay
        if len(self.replay_buffer) >= 100 and self._episode_steps % 10 == 0:
            self._batch_update()
        
        return suggested_action, reward
    
    def _batch_update(self, batch_size: int = 32) -> None:
        """Perform batch update from replay buffer."""
        experiences = self.replay_buffer.sample(batch_size)
        
        for exp in experiences:
            self.q_agent.update(
                exp.state,
                exp.action,
                exp.reward,
                exp.next_state,
                exp.done
            )
    
    def end_episode(self) -> Dict[str, Any]:
        """End the current episode and return statistics."""
        episode_return = self.reward_system.end_episode()
        self.q_agent.decay_exploration()
        
        stats = {
            'episode': self._total_episodes,
            'steps': self._episode_steps,
            'return': episode_return,
            'exploration_rate': self.q_agent.epsilon,
            'q_stats': self.q_agent.get_statistics()
        }
        
        self._episode_steps = 0
        self._total_episodes += 1
        self._last_state = None
        self._last_action = None
        
        logger.info(f"Episode {stats['episode']} complete: return={episode_return:.2f}")
        return stats
    
    def get_save_data(self) -> Dict[str, Any]:
        """Get data for saving."""
        return {
            'q_table': self.q_agent.save_q_table(),
            'total_episodes': self._total_episodes
        }
    
    def load_save_data(self, data: Dict[str, Any]) -> None:
        """Load saved data."""
        if 'q_table' in data:
            self.q_agent.load_q_table(data['q_table'])
        self._total_episodes = data.get('total_episodes', 0)
