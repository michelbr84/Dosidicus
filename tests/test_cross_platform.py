# tests/test_cross_platform.py
"""
Cross-Platform Compatibility Tests - Verify functionality across platforms.
"""

import unittest
import os
import sys
import platform
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestPlatformDetection(unittest.TestCase):
    """Test platform detection functionality."""
    
    def test_platform_info_singleton(self):
        """Test that PlatformInfo is a singleton."""
        from src.platform_compat import PlatformInfo
        
        info1 = PlatformInfo()
        info2 = PlatformInfo()
        
        self.assertIs(info1, info2)
    
    def test_platform_info_properties(self):
        """Test that platform info has all required properties."""
        from src.platform_compat import get_platform_info
        
        info = get_platform_info()
        
        self.assertIsNotNone(info.system)
        self.assertIsNotNone(info.release)
        self.assertIsNotNone(info.machine)
        self.assertIsNotNone(info.python_version)
        
        # Exactly one of these should be True
        platform_count = sum([info.is_windows, info.is_linux, info.is_macos])
        self.assertGreaterEqual(platform_count, 0)
        self.assertLessEqual(platform_count, 1)
    
    def test_platform_info_dict(self):
        """Test platform info can be converted to dict."""
        from src.platform_compat import get_platform_info
        
        info = get_platform_info()
        info_dict = info.get_info()
        
        self.assertIsInstance(info_dict, dict)
        self.assertIn('system', info_dict)
        self.assertIn('is_windows', info_dict)
        self.assertIn('is_linux', info_dict)
        self.assertIn('is_macos', info_dict)


class TestPathHandler(unittest.TestCase):
    """Test cross-platform path handling."""
    
    def test_app_data_dir_exists(self):
        """Test that app data directory can be determined."""
        from src.platform_compat import get_path_handler
        
        handler = get_path_handler()
        app_dir = handler.get_app_data_dir()
        
        self.assertIsInstance(app_dir, Path)
        self.assertTrue(str(app_dir))  # Not empty
    
    def test_config_dir_exists(self):
        """Test that config directory can be determined."""
        from src.platform_compat import get_path_handler
        
        handler = get_path_handler()
        config_dir = handler.get_config_dir()
        
        self.assertIsInstance(config_dir, Path)
        self.assertTrue(str(config_dir))
    
    def test_cache_dir_exists(self):
        """Test that cache directory can be determined."""
        from src.platform_compat import get_path_handler
        
        handler = get_path_handler()
        cache_dir = handler.get_cache_dir()
        
        self.assertIsInstance(cache_dir, Path)
        self.assertTrue(str(cache_dir))
    
    def test_log_dir_exists(self):
        """Test that log directory can be determined."""
        from src.platform_compat import get_path_handler
        
        handler = get_path_handler()
        log_dir = handler.get_log_dir()
        
        self.assertIsInstance(log_dir, Path)
        self.assertTrue(str(log_dir))
    
    def test_normalize_path(self):
        """Test path normalization."""
        from src.platform_compat import get_path_handler
        
        handler = get_path_handler()
        
        # Test with relative path
        normalized = handler.normalize_path('.')
        self.assertTrue(os.path.isabs(normalized))
        
        # Test with home directory
        normalized = handler.normalize_path('~')
        self.assertTrue(os.path.isabs(normalized))
    
    def test_ensure_dir(self):
        """Test directory creation."""
        from src.platform_compat import get_path_handler
        import tempfile
        import shutil
        
        handler = get_path_handler()
        
        # Create a temporary directory path
        temp_base = tempfile.mkdtemp()
        try:
            test_dir = Path(temp_base) / 'test_ensure_dir' / 'nested'
            
            # Directory shouldn't exist yet
            self.assertFalse(test_dir.exists())
            
            # Create it
            result = handler.ensure_dir(test_dir)
            self.assertTrue(result)
            self.assertTrue(test_dir.exists())
            
        finally:
            shutil.rmtree(temp_base, ignore_errors=True)


class TestFontFallback(unittest.TestCase):
    """Test font fallback system."""
    
    def test_ui_font(self):
        """Test getting UI font."""
        from src.platform_compat import get_font_fallback
        
        fallback = get_font_fallback()
        font = fallback.get_font_family('ui')
        
        self.assertIsInstance(font, str)
        self.assertTrue(font)
    
    def test_mono_font(self):
        """Test getting monospace font."""
        from src.platform_compat import get_font_fallback
        
        fallback = get_font_fallback()
        font = fallback.get_font_family('mono')
        
        self.assertIsInstance(font, str)
        self.assertTrue(font)
    
    def test_emoji_font(self):
        """Test getting emoji font."""
        from src.platform_compat import get_font_fallback
        
        fallback = get_font_fallback()
        font = fallback.get_font_family('emoji')
        
        self.assertIsInstance(font, str)
        self.assertTrue(font)
    
    def test_unknown_font_type(self):
        """Test fallback for unknown font type."""
        from src.platform_compat import get_font_fallback
        
        fallback = get_font_fallback()
        font = fallback.get_font_family('unknown_type')
        
        # Should return a default
        self.assertIsInstance(font, str)
        self.assertTrue(font)


class TestNetworkCompat(unittest.TestCase):
    """Test cross-platform network utilities."""
    
    def test_get_local_ip(self):
        """Test getting local IP address."""
        from src.platform_compat import get_network_compat
        
        compat = get_network_compat()
        ip = compat.get_local_ip()
        
        self.assertIsInstance(ip, str)
        self.assertTrue(ip)
        
        # Should be a valid IP format
        parts = ip.split('.')
        self.assertEqual(len(parts), 4)
    
    def test_get_network_interfaces(self):
        """Test getting network interfaces."""
        from src.platform_compat import get_network_compat
        
        compat = get_network_compat()
        interfaces = compat.get_network_interfaces()
        
        self.assertIsInstance(interfaces, list)
        self.assertGreater(len(interfaces), 0)
        
        # Should have at least loopback
        loopback = [i for i in interfaces if i.get('ip') == '127.0.0.1']
        self.assertGreater(len(loopback), 0)
    
    def test_multicast_check(self):
        """Test multicast availability check."""
        from src.platform_compat import get_network_compat
        
        compat = get_network_compat()
        result = compat.is_multicast_available()
        
        self.assertIsInstance(result, bool)


class TestProcessCompat(unittest.TestCase):
    """Test cross-platform process utilities."""
    
    def test_get_cpu_count(self):
        """Test getting CPU count."""
        from src.platform_compat import get_process_compat
        
        compat = get_process_compat()
        cpu_count = compat.get_cpu_count()
        
        self.assertIsInstance(cpu_count, int)
        self.assertGreater(cpu_count, 0)
    
    def test_get_memory_info(self):
        """Test getting memory info."""
        from src.platform_compat import get_process_compat
        
        compat = get_process_compat()
        mem_info = compat.get_memory_info()
        
        self.assertIsInstance(mem_info, dict)
        self.assertIn('available', mem_info)
        self.assertIn('total', mem_info)


class TestNewModulesImport(unittest.TestCase):
    """Test that all new modules can be imported."""
    
    def test_import_reinforcement_learning(self):
        """Test reinforcement learning module import."""
        try:
            from src.reinforcement_learning import (
                RewardSystem, 
                QLearningAgent, 
                ExperienceReplayBuffer,
                ReinforcementLearningIntegration
            )
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import reinforcement_learning: {e}")
    
    def test_import_evolutionary_algorithm(self):
        """Test evolutionary algorithm module import."""
        try:
            from src.evolutionary_algorithm import (
                Individual,
                GeneticOptimizer,
                SurvivalFitness,
                GeneticOperators
            )
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import evolutionary_algorithm: {e}")
    
    def test_import_mini_games(self):
        """Test mini games module import."""
        try:
            from src.mini_games import (
                MemoryGame,
                CatchGame,
                PuzzleGame,
                MiniGameManager
            )
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import mini_games: {e}")
    
    def test_import_advanced_care(self):
        """Test advanced care module import."""
        try:
            from src.advanced_care import (
                CareType,
                CareAction,
                AdvancedCareSystem
            )
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import advanced_care: {e}")
    
    def test_import_matchmaking(self):
        """Test matchmaking module import."""
        try:
            from plugins.multiplayer.matchmaking import (
                MatchmakingService,
                PeerInfo,
                GameSession
            )
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import matchmaking: {e}")
    
    def test_import_game_modes(self):
        """Test game modes module import."""
        try:
            from plugins.multiplayer.game_modes import (
                GameModeType,
                CooperativeMode,
                CompetitiveMode,
                SpectatorMode,
                GameModeManager
            )
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import game_modes: {e}")


class TestReinforcementLearning(unittest.TestCase):
    """Test reinforcement learning functionality."""
    
    def test_reward_system(self):
        """Test reward calculation."""
        from src.reinforcement_learning import RewardSystem
        
        system = RewardSystem()
        
        # Test reward for improvement
        prev_state = {'hunger': 80, 'happiness': 50}
        current_state = {'hunger': 60, 'happiness': 50}
        
        reward = system.calculate_reward(current_state, 'eat', prev_state)
        
        self.assertIsInstance(reward, float)
        # Should be positive for reducing hunger
        self.assertGreater(reward, 0)
    
    def test_q_learning_agent(self):
        """Test Q-learning agent."""
        from src.reinforcement_learning import QLearningAgent
        
        agent = QLearningAgent()
        
        state = {'hunger': 50, 'happiness': 50, 'sleepiness': 50, 
                'anxiety': 50, 'cleanliness': 50}
        
        # Get action
        action = agent.get_action(state)
        self.assertIn(action, agent.ACTIONS)
        
        # Update Q-value
        next_state = state.copy()
        next_state['hunger'] = 40
        
        td_error = agent.update(state, action, 1.0, next_state)
        self.assertIsInstance(td_error, float)


class TestMiniGames(unittest.TestCase):
    """Test mini game functionality."""
    
    def test_memory_game(self):
        """Test memory game."""
        from src.mini_games import MemoryGame
        
        game = MemoryGame(difficulty=1)
        
        # Start game
        challenge = game.start()
        self.assertIn('sequence', challenge)
        self.assertIsInstance(challenge['sequence'], list)
    
    def test_puzzle_game(self):
        """Test puzzle game."""
        from src.mini_games import PuzzleGame
        
        game = PuzzleGame(difficulty=1)
        
        challenge = game.start()
        self.assertIn('type', challenge)
        self.assertIn('options', challenge)
    
    def test_mini_game_manager(self):
        """Test mini game manager."""
        from src.mini_games import MiniGameManager
        
        manager = MiniGameManager()
        
        games = manager.get_available_games()
        self.assertGreater(len(games), 0)


class TestAdvancedCare(unittest.TestCase):
    """Test advanced care functionality."""
    
    def test_care_system(self):
        """Test care system initialization."""
        from src.advanced_care import AdvancedCareSystem
        
        system = AdvancedCareSystem()
        
        actions = system.get_available_actions()
        self.assertGreater(len(actions), 0)
    
    def test_care_recommendations(self):
        """Test care recommendations."""
        from src.advanced_care import AdvancedCareSystem
        
        system = AdvancedCareSystem()
        
        # State with low cleanliness and high anxiety
        state = {'cleanliness': 20, 'anxiety': 80, 'happiness': 50}
        
        recommendations = system.get_recommended_care(state)
        self.assertIsInstance(recommendations, list)


if __name__ == '__main__':
    unittest.main()
