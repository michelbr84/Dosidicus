# mobile_multiplayer.py - Adapted multiplayer logic for mobile Toga app

import threading
import time
import uuid
import logging
from typing import Dict, Any, Tuple

from mp_network_node import NetworkNode
from mp_constants import SYNC_INTERVAL

class MobileMultiplayer:
    def __init__(self, app_instance: Any) -> None:
        self.app: Any = app_instance  # Reference to the Kivy app
        self.logger = logging.getLogger("MobileMultiplayer")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        # Network components
        self.node_id: str = f"mobile_{uuid.uuid4().hex[:6]}"
        self.network_node: NetworkNode = NetworkNode(node_id=self.node_id, logger=self.logger)
        self.network_node.debug_mode = False  # Disable debug for mobile

        # State
        self.is_active: bool = False
        self.remote_players: Dict[str, Dict[str, Any]] = {}
        self.sync_thread: threading.Thread | None = None
        self.message_thread: threading.Thread | None = None

        # Simple game state (for demo)
        self.local_player: Dict[str, Any] = {
            'x': 100,
            'y': 100,
            'name': f"Player_{self.node_id[-4:]}",
            'color': (0, 255, 0)  # Green for local
        }

    def start(self) -> bool:
        """Start the multiplayer system."""
        if self.is_active:
            return False

        self.logger.info("Starting mobile multiplayer...")

        # Initialize network
        if not self.network_node.initialize_socket_structure():
            self.logger.error("Failed to initialize network")
            return False

        if not self.network_node.start_listening():
            self.logger.error("Failed to start listening")
            return False

        self.is_active = True

        # Start background threads
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()

        self.message_thread = threading.Thread(target=self._message_loop, daemon=True)
        self.message_thread.start()

        # Send initial presence
        self._send_player_update()

        self.logger.info(f"Mobile multiplayer started. Node ID: {self.node_id}")
        return True

    def stop(self) -> None:
        """Stop the multiplayer system."""
        if not self.is_active:
            return

        self.logger.info("Stopping mobile multiplayer...")
        self.is_active = False

        # Send leave message
        self.network_node.send_message('player_leave', {
            'node_id': self.node_id,
            'reason': 'app_closed'
        })

        # Stop network
        self.network_node.close()

        self.logger.info("Mobile multiplayer stopped.")

    def update_local_position(self, x: float, y: float) -> None:
        """Update local player position."""
        self.local_player['x'] = x
        self.local_player['y'] = y
        if self.is_active:
            self._send_player_update()

    def _send_player_update(self) -> None:
        """Send local player state to network."""
        if not self.is_active:
            return

        payload: Dict[str, Any] = {
            'player_data': self.local_player.copy(),
            'timestamp': time.time()
        }
        self.network_node.send_message('player_update', payload)

    def _sync_loop(self) -> None:
        """Background thread for periodic sync."""
        while self.is_active:
            try:
                self._send_player_update()
                time.sleep(SYNC_INTERVAL)
            except Exception as e:
                self.logger.error(f"Error in sync loop: {e}")
                time.sleep(1)

    def _message_loop(self) -> None:
        """Background thread for processing incoming messages."""
        while self.is_active:
            try:
                # Process network messages
                self.network_node.process_messages(self)
                time.sleep(0.1)  # Process frequently
            except Exception as e:
                self.logger.error(f"Error in message loop: {e}")
                time.sleep(1)

    def on_network_player_update(self, node: NetworkNode, message: Dict[str, Any], addr: Tuple[str, int]) -> None:
        """Handle incoming player updates."""
        payload: Dict[str, Any] = message.get('payload', {})
        player_data = payload.get('player_data', {})
        sender_id = message.get('node_id')

        if not sender_id or sender_id == self.node_id or not isinstance(player_data, dict):
            return  # Ignore own messages or invalid data

        # Update remote player data
        self.remote_players[sender_id] = player_data
        self.logger.debug(f"Updated remote player {sender_id}: {player_data}")

        # Update UI on main thread
        self.app.call_soon(self.app.update_remote_players)

    def on_network_player_leave(self, node: NetworkNode, message: Dict[str, Any], addr: Tuple[str, int]) -> None:
        """Handle player leaving."""
        payload: Dict[str, Any] = message.get('payload', {})
        sender_id = payload.get('node_id')

        if sender_id and sender_id in self.remote_players:
            del self.remote_players[sender_id]
            self.logger.info(f"Player {sender_id} left")

            # Update UI
            self.app.call_soon(self.app.update_remote_players)

    def trigger_hook(self, hook_name: str, **kwargs: Any) -> None:
        """Simple hook system for network messages."""
        method_name = hook_name.replace('on_network_', 'on_network_')
        if hasattr(self, method_name):
            method = getattr(self, method_name)
            method(**kwargs)
        else:
            self.logger.debug(f"No handler for hook: {hook_name}")

    def get_all_players(self) -> Dict[str, Dict[str, Any]]:
        """Get all players (local + remote)."""
        players = {self.node_id: self.local_player.copy()}
        players.update(self.remote_players)
        return players