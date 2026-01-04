import re
import json
import os
import time
import logging
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)

# Security limits
MAX_NODE_ID_LENGTH = 64
MAX_STRING_LENGTH = 1024
MAX_PAYLOAD_DEPTH = 5
MAX_OBJECTS_COUNT = 100
MAX_POSITION_VALUE = 10000  # Reasonable bounds for coordinates


class PacketValidator:
    """
    Utility class to validate network packets for security and integrity.
    
    Provides comprehensive validation including:
    - Structure validation
    - Type checking
    - Size limits
    - Input sanitization
    - Malicious content detection
    """
    
    # Allowed message types (whitelist approach)
    VALID_MESSAGE_TYPES = frozenset([
        'heartbeat', 'squid_move', 'squid_action', 'object_sync', 
        'rock_throw', 'player_join', 'player_leave', 'state_update',
        'squid_exit', 'new_squid_arrival', 'chat', 'ping', 'pong'
    ])
    
    # Valid directions
    VALID_DIRECTIONS = frozenset(['left', 'right', 'up', 'down'])
    
    @staticmethod
    def validate_message(message: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate a message for required fields and proper structure.
        
        Args:
            message: The message to validate
            
        Returns:
            (is_valid, error_message)
        """
        # Check message is a dictionary
        if not isinstance(message, dict):
            return False, "Message must be a dictionary"
        
        # Check for required fields
        required_fields = ['node_id', 'timestamp', 'type', 'payload']
        for field in required_fields:
            if field not in message:
                return False, f"Missing required field: {field}"
        
        # Validate node_id format and length
        node_id = message['node_id']
        if not isinstance(node_id, str):
            return False, "node_id must be a string"
        if len(node_id) > MAX_NODE_ID_LENGTH:
            return False, f"node_id too long (max {MAX_NODE_ID_LENGTH})"
        if not re.match(r'^[a-zA-Z0-9_-]+$', node_id):
            return False, "Invalid node_id format (alphanumeric, underscore, hyphen only)"
        
        # Check timestamp validity
        current_time = time.time()
        msg_time = message['timestamp']
        if not isinstance(msg_time, (int, float)):
            return False, "timestamp must be a number"
        # 5 minute window (configurable via TIMESTAMP_MAX_DRIFT in constants)
        if abs(current_time - msg_time) > 300:
            return False, "Invalid timestamp (outside acceptable window)"
        
        # Validate message type (whitelist)
        msg_type = message['type']
        if not isinstance(msg_type, str):
            return False, "type must be a string"
        if msg_type not in PacketValidator.VALID_MESSAGE_TYPES:
            return False, f"Unknown message type: {msg_type}"
        
        # Validate payload is a dictionary
        payload = message['payload']
        if not isinstance(payload, dict):
            return False, "Payload must be a dictionary"
        
        # Check payload depth to prevent deeply nested attacks
        if not PacketValidator._check_depth(payload, MAX_PAYLOAD_DEPTH):
            return False, f"Payload too deeply nested (max depth: {MAX_PAYLOAD_DEPTH})"
        
        # Type-specific validation
        if msg_type == 'squid_exit':
            return PacketValidator.validate_squid_exit(payload)
        elif msg_type == 'object_sync':
            return PacketValidator.validate_object_sync(payload)
        elif msg_type == 'squid_move':
            return PacketValidator.validate_squid_move(payload)
        elif msg_type == 'rock_throw':
            return PacketValidator.validate_rock_throw(payload)
        elif msg_type == 'chat':
            return PacketValidator.validate_chat(payload)
        
        # Default to valid for types without specific validation
        return True, None
    
    @staticmethod
    def _check_depth(obj: Any, max_depth: int, current_depth: int = 0) -> bool:
        """Check if object nesting depth is within limits."""
        if current_depth > max_depth:
            return False
        
        if isinstance(obj, dict):
            for value in obj.values():
                if not PacketValidator._check_depth(value, max_depth, current_depth + 1):
                    return False
        elif isinstance(obj, list):
            for item in obj:
                if not PacketValidator._check_depth(item, max_depth, current_depth + 1):
                    return False
        
        return True
    
    @staticmethod
    def validate_squid_exit(payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate squid exit payload."""
        # Check for nested payload structure
        if 'payload' not in payload:
            return False, "Missing nested payload in squid_exit message"
        
        exit_data = payload['payload']
        if not isinstance(exit_data, dict):
            return False, "squid_exit nested payload must be a dictionary"
        
        # Check required fields
        required_fields = ['node_id', 'direction', 'position', 'color']
        for field in required_fields:
            if field not in exit_data:
                return False, f"Missing required field in squid_exit: {field}"
        
        # Validate direction
        if exit_data['direction'] not in PacketValidator.VALID_DIRECTIONS:
            return False, f"Invalid exit direction: {exit_data['direction']}"
        
        # Validate position
        is_valid, error = PacketValidator._validate_position(exit_data['position'])
        if not is_valid:
            return False, error
        
        # Validate color
        is_valid, error = PacketValidator._validate_color(exit_data['color'])
        if not is_valid:
            return False, error
        
        return True, None
    
    @staticmethod
    def validate_squid_move(payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate squid move payload."""
        required_fields = ['x', 'y']
        for field in required_fields:
            if field not in payload:
                return False, f"Missing required field in squid_move: {field}"
        
        # Validate coordinates are within bounds
        for coord in ['x', 'y']:
            val = payload.get(coord)
            if not isinstance(val, (int, float)):
                return False, f"{coord} must be a number"
            if abs(val) > MAX_POSITION_VALUE:
                return False, f"{coord} value out of bounds"
        
        # Validate direction if present
        if 'direction' in payload:
            if payload['direction'] not in PacketValidator.VALID_DIRECTIONS:
                return False, f"Invalid direction: {payload['direction']}"
        
        return True, None
    
    @staticmethod
    def validate_rock_throw(payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate rock throw payload."""
        required_fields = ['source_x', 'source_y', 'target_x', 'target_y']
        for field in required_fields:
            if field not in payload:
                return False, f"Missing required field in rock_throw: {field}"
            val = payload[field]
            if not isinstance(val, (int, float)):
                return False, f"{field} must be a number"
            if abs(val) > MAX_POSITION_VALUE:
                return False, f"{field} value out of bounds"
        
        return True, None
    
    @staticmethod
    def validate_chat(payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate chat message payload."""
        if 'message' not in payload:
            return False, "Missing message field in chat"
        
        message = payload['message']
        if not isinstance(message, str):
            return False, "Chat message must be a string"
        
        if len(message) > MAX_STRING_LENGTH:
            return False, f"Chat message too long (max {MAX_STRING_LENGTH})"
        
        # Basic XSS prevention - strip potentially dangerous content
        # Note: This is a simple check; real production would need more robust handling
        dangerous_patterns = ['<script', 'javascript:', 'onerror=', 'onload=']
        message_lower = message.lower()
        for pattern in dangerous_patterns:
            if pattern in message_lower:
                return False, "Chat message contains potentially dangerous content"
        
        return True, None
    
    @staticmethod
    def validate_object_sync(payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate object sync payload."""
        # Check for squid data
        if 'squid' not in payload:
            return False, "Missing squid data in object_sync"
        
        squid = payload['squid']
        if not isinstance(squid, dict):
            return False, "squid must be a dictionary"
        
        # Validate squid position
        is_valid, error = PacketValidator._validate_position(squid, keys=['x', 'y'])
        if not is_valid:
            return False, f"Invalid squid position: {error}"
        
        # Validate direction
        if 'direction' not in squid:
            return False, "Missing squid direction"
        if squid['direction'] not in PacketValidator.VALID_DIRECTIONS:
            return False, f"Invalid squid direction: {squid['direction']}"
        
        # Check for objects array
        if 'objects' not in payload:
            return False, "Missing objects array in object_sync"
        
        objects = payload['objects']
        if not isinstance(objects, list):
            return False, "Objects must be an array"
        
        if len(objects) > MAX_OBJECTS_COUNT:
            return False, f"Too many objects (max {MAX_OBJECTS_COUNT})"
        
        # Validate node_info if present
        if 'node_info' in payload:
            node_info = payload['node_info']
            if not isinstance(node_info, dict) or 'id' not in node_info:
                return False, "Invalid node_info format"
        
        return True, None
    
    @staticmethod
    def _validate_position(data: Dict[str, Any], keys: List[str] = None) -> Tuple[bool, Optional[str]]:
        """Validate position coordinates."""
        if keys is None:
            keys = ['x', 'y']
        
        if not isinstance(data, dict):
            return False, "Position must be a dictionary"
        
        for key in keys:
            if key not in data:
                return False, f"Missing {key} coordinate"
            val = data[key]
            if not isinstance(val, (int, float)):
                return False, f"{key} must be a number"
            if abs(val) > MAX_POSITION_VALUE:
                return False, f"{key} value out of bounds"
        
        return True, None
    
    @staticmethod
    def _validate_color(color: Any) -> Tuple[bool, Optional[str]]:
        """Validate color value."""
        if not isinstance(color, (list, tuple)):
            return False, "Color must be a list or tuple"
        
        if len(color) < 3:
            return False, "Color must have at least 3 components (RGB)"
        
        for i, c in enumerate(color[:3]):
            if not isinstance(c, (int, float)):
                return False, f"Color component {i} must be a number"
            if c < 0 or c > 255:
                return False, f"Color component {i} out of range (0-255)"
        
        return True, None
    
    @staticmethod
    def sanitize_string(s: str, max_length: int = MAX_STRING_LENGTH) -> str:
        """
        Sanitize a string by removing potentially dangerous content.
        
        Args:
            s: The string to sanitize
            max_length: Maximum allowed length
            
        Returns:
            Sanitized string
        """
        if not isinstance(s, str):
            return ""
        
        # Truncate to max length
        s = s[:max_length]
        
        # Remove null bytes and control characters (except newline/tab)
        s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', s)
        
        # Basic HTML entity encoding for < and >
        s = s.replace('<', '&lt;').replace('>', '&gt;')
        
        return s
    
    @staticmethod
    def sanitize_object_data(objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sanitize object data to ensure no malicious content.
        
        Args:
            objects: List of object dictionaries
            
        Returns:
            Sanitized list of objects
        """
        if not isinstance(objects, list):
            return []
        
        sanitized = []
        
        for i, obj in enumerate(objects):
            if i >= MAX_OBJECTS_COUNT:
                logger.warning(f"Truncating objects list at {MAX_OBJECTS_COUNT}")
                break
            
            if not isinstance(obj, dict):
                continue
            
            # Check if required fields exist
            if not all(k in obj for k in ['id', 'type', 'x', 'y']):
                continue
            
            sanitized_obj = {}
            
            # Sanitize ID (alphanumeric only)
            obj_id = obj.get('id', '')
            if isinstance(obj_id, str):
                sanitized_obj['id'] = re.sub(r'[^a-zA-Z0-9_-]', '', obj_id)[:64]
            else:
                sanitized_obj['id'] = str(obj_id)[:64]
            
            # Sanitize type
            obj_type = obj.get('type', '')
            if isinstance(obj_type, str):
                sanitized_obj['type'] = re.sub(r'[^a-zA-Z0-9_-]', '', obj_type)[:32]
            else:
                continue  # Skip objects with invalid type
            
            # Sanitize filename to prevent directory traversal
            if 'filename' in obj:
                filename = obj['filename']
                if isinstance(filename, str):
                    # Remove any path navigation
                    filename = re.sub(r'\.\.[\\/]', '', filename)
                    # Use only the basename
                    filename = os.path.basename(filename)
                    # Only allow safe characters
                    filename = re.sub(r'[^a-zA-Z0-9_.-]', '', filename)
                    sanitized_obj['filename'] = filename[:128]
            
            # Ensure numeric values are valid and bounded
            for coord in ['x', 'y']:
                val = obj.get(coord, 0)
                if isinstance(val, (int, float)):
                    sanitized_obj[coord] = max(-MAX_POSITION_VALUE, min(MAX_POSITION_VALUE, float(val)))
                else:
                    sanitized_obj[coord] = 0.0
            
            # Sanitize scale
            if 'scale' in obj:
                scale = obj['scale']
                if isinstance(scale, (int, float)):
                    sanitized_obj['scale'] = max(0.1, min(5.0, float(scale)))
                else:
                    sanitized_obj['scale'] = 1.0
            
            # Sanitize rotation if present
            if 'rotation' in obj:
                rotation = obj['rotation']
                if isinstance(rotation, (int, float)):
                    sanitized_obj['rotation'] = float(rotation) % 360
                else:
                    sanitized_obj['rotation'] = 0.0
            
            sanitized.append(sanitized_obj)
        
        return sanitized
