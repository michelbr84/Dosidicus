import unittest
import json
import time
from plugins.multiplayer.network_utilities import NetworkUtilities
from plugins.multiplayer.packet_validator import PacketValidator
from plugins.multiplayer.mp_constants import SHARED_SECRET

class TestSecurity(unittest.TestCase):

    def test_encrypt_decrypt_message(self):
        """Test that encrypting and decrypting a message works correctly."""
        message = {
            'node_id': 'test_node',
            'timestamp': 1234567890.0,
            'type': 'heartbeat',
            'payload': {'status': 'active'}
        }
        encrypted = NetworkUtilities.encrypt_message(message, SHARED_SECRET)
        decrypted = NetworkUtilities.decrypt_message(encrypted, SHARED_SECRET)
        self.assertEqual(message, decrypted)

    def test_sign_verify_message(self):
        """Test that signing and verifying a message works correctly."""
        data = b'test data'
        signature = NetworkUtilities.sign_message(data, SHARED_SECRET)
        self.assertTrue(NetworkUtilities.verify_signature(data, signature, SHARED_SECRET))

    def test_verify_invalid_signature(self):
        """Test that verifying with invalid signature fails."""
        data = b'test data'
        invalid_signature = b'invalid' * 8  # 32 bytes
        self.assertFalse(NetworkUtilities.verify_signature(data, invalid_signature, SHARED_SECRET))

    def test_validate_valid_message(self):
        """Test validation of a valid message."""
        message = {
            'node_id': 'squid_abc123',
            'timestamp': time.time(),
            'type': 'heartbeat',
            'payload': {'status': 'active'}
        }
        is_valid, error = PacketValidator.validate_message(message)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_invalid_node_id(self):
        """Test validation fails for invalid node_id."""
        message = {
            'node_id': 'invalid@node',
            'timestamp': 1234567890.0,
            'type': 'heartbeat',
            'payload': {}
        }
        is_valid, error = PacketValidator.validate_message(message)
        self.assertFalse(is_valid)
        self.assertIn('node_id', error)

    def test_validate_old_timestamp(self):
        """Test validation fails for old timestamp."""
        import time
        old_time = time.time() - 4000  # More than 1 hour ago
        message = {
            'node_id': 'squid_abc123',
            'timestamp': old_time,
            'type': 'heartbeat',
            'payload': {}
        }
        is_valid, error = PacketValidator.validate_message(message)
        self.assertFalse(is_valid)
        self.assertIn('timestamp', error)

    def test_validate_unknown_message_type(self):
        """Test validation fails for unknown message type."""
        message = {
            'node_id': 'squid_abc123',
            'timestamp': 1234567890.0,
            'type': 'unknown_type',
            'payload': {}
        }
        is_valid, error = PacketValidator.validate_message(message)
        self.assertFalse(is_valid)
        self.assertIn('message type', error)

    def test_validate_squid_exit_payload(self):
        """Test validation of squid_exit payload."""
        payload = {
            'payload': {
                'node_id': 'squid_abc123',
                'direction': 'left',
                'position': {'x': 100, 'y': 200},
                'color': [255, 0, 0]
            }
        }
        is_valid, error = PacketValidator.validate_squid_exit(payload)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_invalid_squid_exit_direction(self):
        """Test validation fails for invalid squid_exit direction."""
        payload = {
            'payload': {
                'node_id': 'squid_abc123',
                'direction': 'invalid',
                'position': {'x': 100, 'y': 200},
                'color': [255, 0, 0]
            }
        }
        is_valid, error = PacketValidator.validate_squid_exit(payload)
        self.assertFalse(is_valid)
        self.assertIn('direction', error)

    def test_sanitize_object_data(self):
        """Test sanitization of object data."""
        objects = [
            {'id': 'obj1', 'type': 'rock', 'x': 100, 'y': 200, 'filename': '../secret.txt'},
            {'id': 'obj2', 'type': 'food', 'x': 150, 'y': 250, 'filename': 'food.png', 'scale': 2.0}
        ]
        sanitized = PacketValidator.sanitize_object_data(objects)
        self.assertEqual(len(sanitized), 2)
        self.assertEqual(sanitized[0]['filename'], 'secret.txt')  # Basename
        self.assertEqual(sanitized[1]['scale'], 1.0)  # Clamped

if __name__ == '__main__':
    unittest.main()