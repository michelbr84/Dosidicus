# In plugins/multiplayer/network_utilities.py

import json
import zlib
import socket # Make sure socket is imported if get_local_ip uses it
import time   # Make sure time is imported if is_node_active uses it
import uuid   # Make sure uuid is imported if generate_node_id uses it
import logging
from collections import deque
from typing import Dict, Any, Union, List, Tuple, Optional, Set
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding, hashes, hmac
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
import os
import base64

# Import security constants
try:
    from .mp_constants import (
        HKDF_ENCRYPTION_CONTEXT, HKDF_SIGNING_CONTEXT,
        NONCE_WINDOW_SIZE, TIMESTAMP_MAX_DRIFT,
        RATE_LIMIT_WINDOW, RATE_LIMIT_MAX_PACKETS, RATE_LIMIT_BURST
    )
except ImportError:
    # Fallback defaults if constants not available
    HKDF_ENCRYPTION_CONTEXT = b'dosidicus_encrypt_v1'
    HKDF_SIGNING_CONTEXT = b'dosidicus_sign_v1'
    NONCE_WINDOW_SIZE = 1000
    TIMESTAMP_MAX_DRIFT = 300
    RATE_LIMIT_WINDOW = 1.0
    RATE_LIMIT_MAX_PACKETS = 50
    RATE_LIMIT_BURST = 10

logger = logging.getLogger(__name__)


class SecurityManager:
    """
    Manages security state for network communications including:
    - Key derivation using HKDF
    - Nonce tracking for replay protection
    - Rate limiting per source
    """
    
    def __init__(self, master_secret: bytes):
        """Initialize security manager with master secret."""
        self._master_secret = master_secret
        self._encryption_key: Optional[bytes] = None
        self._signing_key: Optional[bytes] = None
        
        # Replay protection: track seen nonces per node
        self._seen_nonces: Dict[str, deque] = {}
        
        # Rate limiting: track packets per source
        self._rate_limits: Dict[str, List[float]] = {}
        
        # Derive keys on initialization
        self._derive_keys()
    
    def _derive_keys(self) -> None:
        """Derive encryption and signing keys using HKDF."""
        backend = default_backend()
        
        # Derive encryption key
        hkdf_encrypt = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=HKDF_ENCRYPTION_CONTEXT,
            backend=backend
        )
        self._encryption_key = hkdf_encrypt.derive(self._master_secret)
        
        # Derive signing key (use fresh HKDF instance)
        hkdf_sign = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=HKDF_SIGNING_CONTEXT,
            backend=backend
        )
        self._signing_key = hkdf_sign.derive(self._master_secret)
    
    @property
    def encryption_key(self) -> bytes:
        """Get the derived encryption key."""
        if self._encryption_key is None:
            self._derive_keys()
        return self._encryption_key  # type: ignore
    
    @property
    def signing_key(self) -> bytes:
        """Get the derived signing key."""
        if self._signing_key is None:
            self._derive_keys()
        return self._signing_key  # type: ignore
    
    def generate_nonce(self) -> bytes:
        """Generate a cryptographically secure random nonce."""
        return os.urandom(16)
    
    def check_nonce(self, node_id: str, nonce: bytes) -> bool:
        """
        Check if a nonce has been seen before (replay protection).
        
        Returns True if nonce is valid (not seen before), False if replay detected.
        """
        if node_id not in self._seen_nonces:
            self._seen_nonces[node_id] = deque(maxlen=NONCE_WINDOW_SIZE)
        
        nonce_hex = nonce.hex()
        if nonce_hex in self._seen_nonces[node_id]:
            logger.warning(f"Replay attack detected from node {node_id}")
            return False
        
        self._seen_nonces[node_id].append(nonce_hex)
        return True
    
    def check_timestamp(self, timestamp: float) -> bool:
        """
        Check if timestamp is within acceptable drift range.
        
        Returns True if timestamp is valid, False otherwise.
        """
        current_time = time.time()
        drift = abs(current_time - timestamp)
        
        if drift > TIMESTAMP_MAX_DRIFT:
            logger.warning(f"Timestamp drift too large: {drift:.1f}s (max: {TIMESTAMP_MAX_DRIFT}s)")
            return False
        
        return True
    
    def check_rate_limit(self, source_ip: str) -> bool:
        """
        Check if source is within rate limits.
        
        Returns True if within limits, False if rate limited.
        """
        current_time = time.time()
        
        if source_ip not in self._rate_limits:
            self._rate_limits[source_ip] = []
        
        # Remove old timestamps outside the window
        window_start = current_time - RATE_LIMIT_WINDOW
        self._rate_limits[source_ip] = [
            t for t in self._rate_limits[source_ip] if t > window_start
        ]
        
        # Check if over limit
        packet_count = len(self._rate_limits[source_ip])
        if packet_count >= RATE_LIMIT_MAX_PACKETS + RATE_LIMIT_BURST:
            logger.warning(f"Rate limit exceeded for {source_ip}: {packet_count} packets")
            return False
        
        # Record this packet
        self._rate_limits[source_ip].append(current_time)
        return True
    
    def cleanup_old_state(self) -> None:
        """Periodically clean up old tracking data to prevent memory growth."""
        current_time = time.time()
        
        # Clean up rate limit tracking (keep only recent data)
        window_start = current_time - RATE_LIMIT_WINDOW * 2
        for source_ip in list(self._rate_limits.keys()):
            self._rate_limits[source_ip] = [
                t for t in self._rate_limits[source_ip] if t > window_start
            ]
            if not self._rate_limits[source_ip]:
                del self._rate_limits[source_ip]


# Global security manager instance (initialized lazily)
_security_manager: Optional[SecurityManager] = None


def get_security_manager(master_secret: bytes) -> SecurityManager:
    """Get or create the global security manager."""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager(master_secret)
    return _security_manager




class NetworkUtilities:
    """
    A collection of static utility methods for network operations
    including message compression, decompression, and node ID generation.
    """

    @staticmethod
    def get_local_ip() -> str:
        """
        Attempts to discover the local IP address of the machine.
        Fallback to '127.0.0.1' if discovery fails.
        """
        try:
            # Create a temporary socket to connect to an external server (doesn't send data)
            temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            temp_socket.settimeout(0.5) # Prevent long blocking
            # Google's public DNS server is a common choice for this
            temp_socket.connect(('8.8.8.8', 80))
            local_ip = temp_socket.getsockname()[0]
            temp_socket.close()
            return local_ip
        except socket.error: # Catch socket-specific errors
            # Fallback if the above method fails (e.g., no network, firewall)
            try:
                # Get hostname and resolve it
                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)
                return local_ip
            except socket.gaierror: # getaddrinfo error
                return '127.0.0.1' # Ultimate fallback
        except Exception:
            # Catch any other unexpected errors
            return '127.0.0.1'


    @staticmethod
    def compress_message(message: Dict[str, Any]) -> bytes:
        """Compress a message dictionary to bytes using JSON and zlib."""
        is_squid_exit_message = message.get('type') == 'squid_exit'
        
        # Optional: More detailed logging for all messages for debugging structure
        # print("--- Debug: Attempting to compress message (NetworkUtilities) ---")
        # for key, value in message.items():
        #     print(f"  Key: {key}, Type: {type(value)}")
        #     if isinstance(value, dict):
        #         for sub_key, sub_value in value.items():
        #             print(f"    SubKey: {sub_key}, SubType: {type(sub_value)}")
        # print("--- End of debug statements for message content (NetworkUtilities) ---")

        if is_squid_exit_message:
            # Using json.dumps for pretty printing complex nested structures for the log
            try:
                message_for_log = json.dumps(message, indent=2)
            except TypeError: # Handle non-serializable items if any for logging
                message_for_log = str(message) # Fallback to string representation
            print(f"DEBUG_COMPRESS: Compressing SQUID_EXIT. Full message data: {message_for_log}")

        serialized_msg = None # Initialize to handle potential early error
        try:
            serialized_msg = json.dumps(message).encode('utf-8')
            if is_squid_exit_message:
                print(f"DEBUG_COMPRESS: SQUID_EXIT serialized size: {len(serialized_msg)}")
            
            compressed_msg = zlib.compress(serialized_msg)
            if is_squid_exit_message:
                compression_ratio = len(compressed_msg) / len(serialized_msg) if len(serialized_msg) > 0 else 0
                print(f"DEBUG_COMPRESS: SQUID_EXIT compressed size: {len(compressed_msg)}. Compression ratio: {compression_ratio:.2f}")
            return compressed_msg

        except TypeError as te:
            error_detail = f"TypeError during JSON serialization for SQUID_EXIT: {te}. Message keys: {list(message.keys())}" if is_squid_exit_message else f"TypeError during JSON serialization: {te}. Message keys: {list(message.keys())}"
            print(f"DEBUG_COMPRESS_ERROR: {error_detail}")
            # Fallback: return an error message, still as bytes
            return json.dumps({"error": "json_type_error", "details": str(te), "original_type": message.get('type')}).encode('utf-8')
        except zlib.error as ze:
            error_detail = f"zlib compression error for SQUID_EXIT: {ze}. Sending uncompressed." if is_squid_exit_message else f"zlib compression error: {ze}. Sending uncompressed."
            print(f"DEBUG_COMPRESS_ERROR: {error_detail}")
            if serialized_msg: # If serialization succeeded before zlib error
                return serialized_msg 
            else: # Should not happen if TypeError is caught, but as a safeguard
                return json.dumps({"error": "zlib_error_and_serialization_failed", "details": str(ze), "original_type": message.get('type')}).encode('utf-8')
        except Exception as e:
            error_detail = f"General error compressing SQUID_EXIT: {e}" if is_squid_exit_message else f"General error compressing message: {e}"
            print(f"DEBUG_COMPRESS_ERROR: {error_detail}")
            return json.dumps({"error": "compression_failure", "details": str(e), "original_type": message.get('type')}).encode('utf-8')

    @staticmethod
    def decompress_message(compressed_msg: bytes) -> Union[Dict[str, Any], None]:
        """Decompress bytes to a message dictionary using zlib and JSON."""
        if not compressed_msg:
            print("DEBUG_DECOMPRESS_ERROR: Received empty message for decompression.")
            return None

        # Crude check on raw/compressed bytes to see if it *might* be a squid_exit message for targeted logging
        # This check is heuristic and might not always be accurate before decompression.
        is_potentially_squid_exit = b'"type": "squid_exit"' in compressed_msg or \
                                    b'squid_exit' in compressed_msg # More generic check
        
        if is_potentially_squid_exit:
            print(f"DEBUG_DECOMPRESS: Potential SQUID_EXIT raw data received (first 100 bytes): {compressed_msg[:100]}")

        decompressed_data_str = None
        message_dict = None

        try:
            # Attempt zlib decompression first
            try:
                decompressed_bytes = zlib.decompress(compressed_msg)
                if is_potentially_squid_exit:
                     print(f"DEBUG_DECOMPRESS: SQUID_EXIT (potential) successfully zlib decompressed. Decompressed size: {len(decompressed_bytes)}")
                decompressed_data_str = decompressed_bytes.decode('utf-8')
                message_dict = json.loads(decompressed_data_str)
            except zlib.error as ze_decompress:
                # If zlib fails, assume it's uncompressed JSON
                if is_potentially_squid_exit:
                    print(f"DEBUG_DECOMPRESS: zlib.error for SQUID_EXIT (potential) ('{ze_decompress}'). Assuming uncompressed JSON.")
                decompressed_data_str = compressed_msg.decode('utf-8') # Use original msg as string
                message_dict = json.loads(decompressed_data_str)
            except UnicodeDecodeError as ude: # Catch if decode after zlib fails
                print(f"DEBUG_DECOMPRESS_ERROR: UnicodeDecodeError after zlib success (or if it was uncompressed non-UTF8). Details: {ude}. Data (first 100 bytes of error source): {decompressed_bytes[:100] if 'decompressed_bytes' in locals() else compressed_msg[:100]}")
                return {"error": "unicode_decode_error_post_zlib", "details": str(ude)}

            # After successful JSON load, confirm and log if it's a squid_exit
            if isinstance(message_dict, dict) and message_dict.get('type') == 'squid_exit':
                # Using json.dumps for pretty printing complex nested structures for the log
                try:
                    message_for_log = json.dumps(message_dict, indent=2)
                except TypeError:
                    message_for_log = str(message_dict) # Fallback
                print(f"DEBUG_DECOMPRESS: Successfully decoded SQUID_EXIT message: {message_for_log}")
            
            return message_dict

        except UnicodeDecodeError as ude_uncompressed: # If decode of presumed uncompressed fails
            print(f"DEBUG_DECOMPRESS_ERROR: UnicodeDecodeError (assuming uncompressed). Details: {ude_uncompressed}. Raw data (first 100 bytes): {compressed_msg[:100]}")
            return {"error": "unicode_decode_error_uncompressed", "details": str(ude_uncompressed)}
        except json.JSONDecodeError as jde:
            # The data fed to json.loads here is `decompressed_data_str`
            print(f"DEBUG_DECOMPRESS_ERROR: JSONDecodeError. Details: {jde}. Data fed to json.loads (first 100 chars): {decompressed_data_str[:100] if decompressed_data_str else 'N/A'}")
            return {"error": "json_decode_error", "details": str(jde)}
        except Exception as e: # Catch-all for other unexpected errors
            print(f"DEBUG_DECOMPRESS_ERROR: General Exception during decompression. Details: {e}. Raw data (first 100 bytes): {compressed_msg[:100]}")
            return {"error": "general_decompression_failure", "details": str(e)}

    @staticmethod
    def generate_node_id(prefix: str = "squid") -> str:
        """Generate a unique node identifier with a given prefix."""
        # Generate a UUID and take a portion of its hex representation for brevity
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def encrypt_message(message: Dict[str, Any], key: bytes) -> bytes:
        """
        Encrypt a message dictionary using AES-CBC with PKCS7 padding.
        
        Note: For enhanced security with replay protection, use secure_encrypt_message instead.
        """
        try:
            # Serialize to JSON
            data = json.dumps(message).encode('utf-8')
            # Pad the data
            padder = padding.PKCS7(algorithms.AES.block_size).padder()
            padded_data = padder.update(data) + padder.finalize()
            # Generate IV
            iv = os.urandom(16)
            # Encrypt
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            encryptor = cipher.encryptor()
            encrypted = encryptor.update(padded_data) + encryptor.finalize()
            # Return IV + encrypted data, base64 encoded for easy transmission
            return base64.b64encode(iv + encrypted)
        except Exception as e:
            raise ValueError(f"Encryption failed: {e}")

    @staticmethod
    def decrypt_message(encrypted_data: bytes, key: bytes) -> Dict[str, Any]:
        """
        Decrypt bytes to a message dictionary using AES-CBC.
        
        Note: For enhanced security with replay protection, use secure_decrypt_message instead.
        """
        try:
            # Decode from base64
            data = base64.b64decode(encrypted_data)
            # Extract IV
            iv = data[:16]
            encrypted = data[16:]
            # Decrypt
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(encrypted) + decryptor.finalize()
            # Unpad
            unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
            data = unpadder.update(padded_data) + unpadder.finalize()
            # Deserialize from JSON
            return json.loads(data.decode('utf-8'))
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")

    @staticmethod
    def secure_encrypt_message(message: Dict[str, Any], security_mgr: 'SecurityManager') -> bytes:
        """
        Encrypt a message with full security suite:
        - Uses derived encryption key from SecurityManager
        - Includes nonce for replay protection
        - Adds timestamp for freshness
        
        Returns: base64-encoded encrypted data with embedded nonce
        """
        try:
            # Generate nonce and embed in message
            nonce = security_mgr.generate_nonce()
            secure_message = {
                '_nonce': base64.b64encode(nonce).decode('ascii'),
                '_timestamp': time.time(),
                'data': message
            }
            
            # Serialize to JSON
            data = json.dumps(secure_message).encode('utf-8')
            
            # Pad the data
            padder = padding.PKCS7(algorithms.AES.block_size).padder()
            padded_data = padder.update(data) + padder.finalize()
            
            # Generate IV (different from nonce - IV is for CBC mode)
            iv = os.urandom(16)
            
            # Encrypt using derived key
            cipher = Cipher(
                algorithms.AES(security_mgr.encryption_key), 
                modes.CBC(iv), 
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            encrypted = encryptor.update(padded_data) + encryptor.finalize()
            
            # Return IV + encrypted data, base64 encoded
            return base64.b64encode(iv + encrypted)
        except Exception as e:
            raise ValueError(f"Secure encryption failed: {e}")

    @staticmethod
    def secure_decrypt_message(
        encrypted_data: bytes, 
        security_mgr: 'SecurityManager',
        node_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Decrypt a message with full security validation:
        - Uses derived encryption key from SecurityManager
        - Validates nonce for replay protection
        - Validates timestamp for freshness
        
        Returns: Decrypted message data, or None if security validation fails
        """
        try:
            # Decode from base64
            data = base64.b64decode(encrypted_data)
            
            # Extract IV
            iv = data[:16]
            encrypted = data[16:]
            
            # Decrypt using derived key
            cipher = Cipher(
                algorithms.AES(security_mgr.encryption_key), 
                modes.CBC(iv), 
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(encrypted) + decryptor.finalize()
            
            # Unpad
            unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
            data = unpadder.update(padded_data) + unpadder.finalize()
            
            # Deserialize from JSON
            secure_message = json.loads(data.decode('utf-8'))
            
            # Validate timestamp
            timestamp = secure_message.get('_timestamp')
            if timestamp is None or not security_mgr.check_timestamp(timestamp):
                logger.warning(f"Message from {node_id} failed timestamp validation")
                return None
            
            # Validate nonce (replay protection)
            nonce_b64 = secure_message.get('_nonce')
            if nonce_b64 is None:
                logger.warning(f"Message from {node_id} missing nonce")
                return None
            
            nonce = base64.b64decode(nonce_b64)
            if not security_mgr.check_nonce(node_id, nonce):
                logger.warning(f"Message from {node_id} failed nonce validation (possible replay)")
                return None
            
            # Return the actual message data
            return secure_message.get('data', {})
            
        except Exception as e:
            logger.error(f"Secure decryption failed for {node_id}: {e}")
            return None

    @staticmethod
    def sign_message(data: bytes, key: bytes) -> bytes:
        """Generate HMAC signature for data."""
        h = hmac.HMAC(key, hashes.SHA256(), backend=default_backend())
        h.update(data)
        return h.finalize()

    @staticmethod
    def verify_signature(data: bytes, signature: bytes, key: bytes) -> bool:
        """Verify HMAC signature for data."""
        try:
            h = hmac.HMAC(key, hashes.SHA256(), backend=default_backend())
            h.update(data)
            h.verify(signature)
            return True
        except Exception:
            return False

    @staticmethod
    def is_node_active(last_seen_time: float, threshold: float = 30.0) -> bool: # Increased threshold
        """
        Check if a node is considered active based on its last seen time.
        Args:
            last_seen_time: The timestamp (unix epoch float) when the node was last heard from.
            threshold: The number of seconds without contact after which a node is considered inactive.
        Returns:
            True if the node is active, False otherwise.
        """
        if last_seen_time is None:
            return False # Never seen
        return (time.time() - last_seen_time) < threshold

# Example of a BinaryProtocol class if it were part of this file:
# class BinaryProtocol:
#     @staticmethod
#     def pack_data(*args) -> bytes:
#         # Example: Implement packing logic using struct or similar
#         # This is a placeholder and would need a proper specification
#         packed_bytes = b''
#         for arg in args:
#             if isinstance(arg, int):
#                 packed_bytes += arg.to_bytes(4, 'big', signed=True)
#             elif isinstance(arg, float):
#                 # A more robust solution would use struct.pack
#                 packed_bytes += str(arg).encode('utf-8').ljust(16, b'\0') # Simplistic
#             elif isinstance(arg, str):
#                 packed_bytes += arg.encode('utf-8').ljust(32, b'\0') # Simplistic
#         return packed_bytes

#     @staticmethod
#     def unpack_data(data: bytes) -> tuple:
#         # Example: Implement unpacking logic
#         # This is a placeholder
#         # Assuming a fixed format like: int (4B), float_str (16B), str (32B)
#         num = int.from_bytes(data[0:4], 'big', signed=True)
#         float_val_str = data[4:20].decode('utf-8').strip('\0')
#         str_val = data[20:52].decode('utf-8').strip('\0')
#         return num, float(float_val_str), str_val