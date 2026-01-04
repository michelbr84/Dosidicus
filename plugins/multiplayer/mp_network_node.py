# File: mp_network_node.py

from __future__ import annotations

import uuid
import time
import socket
import queue # Retaining import
import zlib
import json
import threading
import logging # Ensure logging is imported

from typing import Dict, Any, Optional, List, Tuple, cast

# Import constants
from .mp_constants import MULTICAST_GROUP, MULTICAST_PORT, MAX_PACKET_SIZE, SHARED_SECRET
from .packet_validator import PacketValidator

# Import security manager for rate limiting and replay protection
try:
    from .network_utilities import get_security_manager, SecurityManager
    _HAS_SECURITY_MANAGER = True
except ImportError:
    _HAS_SECURITY_MANAGER = False


class NetworkNode:
    node_id: str
    logger: logging.Logger
    local_ip: str
    socket: Optional[socket.socket]
    initialized: bool
    is_connected: bool
    _is_listening_active: bool
    listener_thread: Optional[threading.Thread]
    last_connection_attempt: float
    connection_retry_interval: float
    auto_reconnect: bool
    use_compression: bool
    incoming_queue: queue.Queue[Dict[str, Any]]
    queue_lock: threading.Lock
    known_nodes: Dict[str, Tuple[str, float, Dict[str, Any]]]
    last_sync_time: float
    debug_mode: bool
    utils: Optional[Any]
    security_mgr: Optional[Any]

    def __init__(self, node_id: Optional[str] = None, logger: Optional[logging.Logger] = None):
        """
        Represents a networked node in the multiplayer system.

        Args:
            node_id (str, optional): Unique identifier for this node.
                                     Generated if not provided.
            logger (logging.Logger, optional): Logger instance to use.
                                               A default one is created if not provided.
        """
        try:
            # Attempt to use NetworkUtilities if available (from a previous iteration)
            from plugins.multiplayer.network_utilities import NetworkUtilities
            self.node_id = node_id or NetworkUtilities.generate_node_id()
            self.utils = NetworkUtilities
        except ImportError:
            self.node_id = node_id or f"squid_{uuid.uuid4().hex[:8]}"
            self.utils = None # Mark utils as unavailable

        # Initialize security manager for rate limiting and replay protection
        if _HAS_SECURITY_MANAGER:
            self.security_mgr = get_security_manager(SHARED_SECRET)
        else:
            self.security_mgr = None

        self.local_ip = self._get_local_ip()
        self.socket = None
        self.initialized = False # Socket structure initialized (IP_ADD_MEMBERSHIP etc.)
        self.is_connected = False # Socket bound and ready for I/O
        
        self._is_listening_active = False # Flag to control the listening loop
        self.listener_thread = None      # Thread object for the listening loop

        self.last_connection_attempt = 0
        self.connection_retry_interval = 5.0 # seconds
        self.auto_reconnect = True # Flag to control auto-reconnect attempts
        self.use_compression = True # Flag to control message compression

        self.incoming_queue = queue.Queue() # Thread-safe queue for received messages
        self.queue_lock = threading.Lock() # Used with incoming_message_queue in one of the versions, ensure consistency

        self.known_nodes = {} # Stores info about other detected nodes
        self.last_sync_time = 0 # Timestamp of the last sync operation
        self.debug_mode = False # Controlled by MultiplayerPlugin
        
        # Rate limiting tracking (for sources without full security manager)
        self._rate_limit_counters: Dict[str, List[float]] = {}
        self._last_security_cleanup = time.time()

        if logger is not None:
            self.logger = logger
        else:
            _logger_name = f"{__name__}.NetworkNode.{self.node_id[:4]}" # More specific logger name
            self.logger = logging.getLogger(_logger_name)
            if not self.logger.handlers: # Avoid adding multiple handlers if logger is passed around
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
                # Initial level, can be updated by MultiplayerPlugin if debug_mode changes
                self.logger.setLevel(logging.DEBUG if self.debug_mode else logging.INFO)
        
        self.initialize_socket_structure() # Initialize socket when a NetworkNode is created


    def _get_local_ip(self):
        """Tries to get the primary local IP that can connect externally."""
        try:
            # This creates a dummy socket and connects to a public DNS server (doesn't send data)
            # to determine the preferred outgoing IP address.
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0.1) # Prevent long blocking if network is down
                s.connect(("8.8.8.8", 80)) # Google's public DNS server
                local_ip = s.getsockname()[0]
            return local_ip
        except Exception as e:
            self.logger.warning(f"Error getting local IP: {e}. Defaulting to 127.0.0.1 for same-machine testing or if no external network.")
            return '127.0.0.1' # Fallback, might only work for same-machine communication

    def initialize_socket_structure(self):
        """Initializes the socket, sets options, binds, and joins the multicast group."""
        if self.is_connected and self.socket: # Check if already properly set up
            self.logger.info("Socket structure already initialized and connected.")
            return True
            
        try:
            if self.socket: # If socket exists but not connected, close it first
                try:
                    self.socket.close()
                except Exception: pass # Ignore errors on close if already closed
            
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # SO_REUSEPORT allows multiple processes to bind to the same port, useful for testing on one machine
            if hasattr(socket, "SO_REUSEPORT"):
                try:
                    self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)  # type: ignore
                except OSError as e:
                    if self.debug_mode: self.logger.debug(f"SO_REUSEPORT not supported or error setting it: {e}")

            try:
                self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 0)
                if self.debug_mode: self.logger.debug("Multicast loopback enabled.")
            except socket.error as e_loop:
                self.logger.warning(f"Could not enable multicast loopback: {e_loop}. May impact same-machine testing.")

            self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2) # Time-to-live for multicast packets

            max_bind_attempts = 3
            current_attempt = 0
            bind_port = MULTICAST_PORT # Start with default port
            bind_success = False

            # Attempt to bind, incrementing port on failure (for local testing)
            while current_attempt < max_bind_attempts:
                try:
                    self.socket.bind(('', bind_port)) # Bind to all interfaces on this port
                    bind_success = True
                    self.logger.info(f"Socket bound successfully to port {bind_port}.")
                    break
                except OSError as bind_error:
                    current_attempt += 1
                    self.logger.warning(f"Port {bind_port} in use (Attempt {current_attempt}/{max_bind_attempts}). Error: {bind_error}")
                    if current_attempt >= max_bind_attempts:
                        self.logger.error(f"Critical error: Could not bind socket after {max_bind_attempts} attempts.")
                        self.is_connected = False
                        self.initialized = False
                        return False
                    bind_port += 1 # Try next port if available

            if not bind_success: # Should be caught above, but as a safeguard
                self.is_connected = False
                self.initialized = False
                return False
            
            # Join the multicast group
            # Using "0.0.0.0" for imr_interface to listen on all available interfaces for the group
            mreq_struct = socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton("0.0.0.0")
            self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq_struct)
            
            self.socket.settimeout(0.1) # Non-blocking recvfrom

            self.is_connected = True  # Socket is bound and ready
            self.initialized = True # Full structure (options, group) is set up
            self.last_connection_attempt = time.time()
            self.logger.info(f"Socket structure initialized on {self.local_ip} (listening on all interfaces, port {bind_port}) for multicast group {MULTICAST_GROUP}.")
            return True

        except Exception as e:
            self.logger.error(f"Error initializing socket structure: {e}", exc_info=self.debug_mode)
            if self.socket:
                try: self.socket.close()
                except: pass
            self.socket = None
            self.is_connected = False
            self.initialized = False
            return False

    def _listen_for_multicast(self):
        """Dedicated thread function to listen for incoming multicast packets."""
        self.logger.info(f"Listener thread started for node {self.node_id} on IP {self.local_ip}.")
        while self._is_listening_active: # Loop controlled by flag
            if not self.is_connected or not self.socket:
                self.logger.warning("Listening loop: Socket not connected or available. Attempting to reconnect...")
                if not self.try_reconnect(): # This will call initialize_socket_structure
                    self.logger.error("Listening loop: Reconnect failed. Pausing before retry.")
                    time.sleep(self.connection_retry_interval) 
                    continue # Retry connection

            try:
                raw_data, addr = cast(socket.socket, self.socket).recvfrom(MAX_PACKET_SIZE)

                if raw_data:
                    # Use the thread-safe queue for passing data to the main thread
                    self.incoming_queue.put({'raw_data': raw_data, 'addr': addr})
            except socket.timeout:
                continue # Normal behavior for non-blocking socket, allows checking _is_listening_active
            except OSError as e: # Handle socket closed or other OS errors
                if self._is_listening_active: # Log only if we weren't expecting closure
                    self.logger.error(f"Socket OS error in listener thread: {e}", exc_info=True)
                self.is_connected = False # Assume connection is lost if OS error occurs
                # No break here, rely on try_reconnect in the next iteration if _is_listening_active is still true
            except Exception as e: # Catch any other unexpected errors
                if self._is_listening_active:
                     self.logger.error(f"Unexpected error in listener thread: {e}", exc_info=True)
                time.sleep(0.1) # Brief pause before retrying or exiting based on flag

        self.logger.info(f"Listener thread stopped for node {self.node_id}.")


    def is_listening(self):
        """Checks if the listener thread is active and alive."""
        return self._is_listening_active and self.listener_thread is not None and self.listener_thread.is_alive()

    def start_listening(self):
        """Starts the multicast listener thread if not already running."""
        if self.is_listening():
            self.logger.info("Attempted to start listening, but already listening.")
            return True # Already doing its job

        # Ensure socket is initialized and connected before starting to listen
        if not self.initialized or not self.is_connected:
            self.logger.warning("Socket not initialized or connected. Attempting to initialize before listening.")
            if not self.initialize_socket_structure():
                self.logger.error("Failed to initialize socket structure. Cannot start listening.")
                return False
        
        self.logger.info("Starting network listener thread...")
        try:
            self._is_listening_active = True # Set flag before starting thread
            self.listener_thread = threading.Thread(target=self._listen_for_multicast, daemon=True)
            self.listener_thread.name = f"MPNodeListener-{self.node_id[:4]}" # Helpful for debugging threads
            self.listener_thread.start()
            self.logger.info("Listener thread started successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start listener thread: {e}", exc_info=self.debug_mode)
            self._is_listening_active = False # Reset flag on error
            return False

    def stop_listening(self):
        """Stops the multicast listener thread."""
        if not self._is_listening_active and (self.listener_thread is None or not self.listener_thread.is_alive()):
            # If the flag is already false and thread is gone or never started.
            self.logger.info("Listener already stopped or was never started.")
            return

        self.logger.info("Stopping listener thread...")
        self._is_listening_active = False # Signal the loop to terminate
        
        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=2.0) # Wait for the thread to finish
            if self.listener_thread.is_alive():
                # This might happen if socket.recvfrom() is stuck, though timeout should prevent it.
                self.logger.warning("Listener thread did not stop in time (join timeout).")
            else:
                self.logger.info("Listener thread joined successfully.")
        else:
            self.logger.info("Listener thread was not active or did not exist at explicit stop.")
            
        self.listener_thread = None # Clear the thread object


    def try_reconnect(self):
        """Attempts to re-establish the socket connection and restart listening if needed."""
        if self.is_listening(): # If already listening, assume connection is fine
            return True

        current_time = time.time()
        if current_time - self.last_connection_attempt < self.connection_retry_interval:
            # Avoid rapid reconnection attempts
            return False 

        self.logger.info("Attempting to reconnect and restart listener...")
        self.last_connection_attempt = current_time
        
        self.stop_listening() # Ensure any old listener is stopped

        if self.initialize_socket_structure(): # Re-initialize socket (binds, joins group)
            return self.start_listening()      # Start listening again
        else:
            self.logger.error("Reconnect failed: Could not re-initialize socket structure.")
            return False

    def send_message(self, message_type: str, payload: Dict[str, Any]):
        """Sends a single message to the multicast group."""
        if not self.is_connected: # Check if socket is ready
            self.logger.warning(f"Cannot send '{message_type}', socket not connected.")
            if self.auto_reconnect and not self.try_reconnect(): # Attempt to reconnect if enabled
                self.logger.error(f"Send failed for '{message_type}': Reconnect attempt failed.")
                return False
            elif not self.is_connected: # If still not connected after attempt
                 self.logger.error(f"Send failed for '{message_type}': Still not connected after reconnect check.")
                 return False

        # Construct the full message with metadata
        message_data: Dict[str, Any] = {
            'node_id': self.node_id,       # Sender's ID
            'timestamp': time.time(),    # Time of sending
            'type': message_type,        # Type of message (e.g., "squid_exit")
            'payload': payload           # The actual data payload
        }

        try:
            # Encrypt the message
            encrypted_data = self.utils.encrypt_message(message_data, SHARED_SECRET)
            # Sign the encrypted data
            signature = self.utils.sign_message(encrypted_data, SHARED_SECRET)
            # Combine signature + encrypted data
            data_to_send = signature + encrypted_data

            if self.use_compression:
                # Compress the signed and encrypted data
                data_to_send = zlib.compress(data_to_send)
                if self.debug_mode and message_type.upper() in ["SQUID_EXIT", "SQUID_RETURN"]:
                    self.logger.debug(f"DEBUG_COMPRESS (send): Type: {message_type}. Encrypted: {len(signature + encrypted_data)}, Compressed: {len(data_to_send)}")

            if len(data_to_send) > MAX_PACKET_SIZE:
                self.logger.warning(f"Message '{message_type}' size ({len(data_to_send)}) exceeds MAX_PACKET_SIZE. May fail or be fragmented (UDP handles this, but can be less reliable).")

            if self.socket: # Ensure socket object exists
                self.socket.sendto(data_to_send, (MULTICAST_GROUP, MULTICAST_PORT))
                if self.debug_mode and message_type not in ['object_sync', 'squid_move', 'heartbeat']: # Avoid flooding logs
                    self.logger.debug(f"Sent '{message_type}' ({len(data_to_send)} bytes).")
                return True
            else:
                self.logger.error(f"Cannot send '{message_type}', socket is None.")
                return False
        except socket.error as sock_err: # Specific socket errors
            self.logger.error(f"Socket error sending message '{message_type}': {sock_err}")
            self.is_connected = False # Assume connection is broken
            self.stop_listening() # Stop listener as connection is likely bad
        except Exception as e: # Other errors (encryption, signing etc.)
            self.logger.error(f"Error sending message '{message_type}': {e}", exc_info=self.debug_mode)
        return False

    def send_message_batch(self, messages: List[Tuple[str, Dict[str, Any]]]):
        """Sends a batch of messages in a single packet."""
        # Connection check similar to send_message
        if not self.is_connected:
            self.logger.warning("Cannot send batch, socket not connected.")
            if self.auto_reconnect and not self.try_reconnect():
                self.logger.error("Send batch failed: Reconnect attempt failed.")
                return False
            elif not self.is_connected:
                 self.logger.error("Send batch failed: Still not connected after reconnect check.")
                 return False

        # Structure for batch message
        batch_data: Dict[str, Any] = {
            'node_id': self.node_id,
            'timestamp': time.time(),
            'batch': True, # Indicates this packet contains multiple messages
            'messages': [{'type': msg_type, 'payload': payload} for msg_type, payload in messages]
        }

        try:
            # Encrypt the batch data
            encrypted_data = self.utils.encrypt_message(batch_data, SHARED_SECRET)
            # Sign the encrypted data
            signature = self.utils.sign_message(encrypted_data, SHARED_SECRET)
            # Combine signature + encrypted data
            data_to_send = signature + encrypted_data

            if self.use_compression:
                data_to_send = zlib.compress(data_to_send)

            if len(data_to_send) > MAX_PACKET_SIZE:
                self.logger.warning(f"Batch message size ({len(data_to_send)}) exceeds MAX_PACKET_SIZE. Transmission may fail.")

            if self.socket:
                self.socket.sendto(data_to_send, (MULTICAST_GROUP, MULTICAST_PORT))
                if self.debug_mode:
                    self.logger.debug(f"Sent batch message ({len(data_to_send)} bytes) with {len(messages)} sub-messages.")
                return True
            else:
                self.logger.error("Cannot send batch, socket is None.")
                return False
        except socket.error as sock_err:
            self.logger.error(f"Socket error sending message batch: {sock_err}")
            self.is_connected = False
            self.stop_listening()
        except Exception as e:
            self.logger.error(f"Error sending message batch: {e}", exc_info=self.debug_mode)
        return False

    def receive_messages(self) -> List[Tuple[Dict[str, Any], Tuple[str, int]]]:
        """
        Processes all currently queued raw datagrams from the listener thread.
        This should be called by the main application thread.
        Returns:
            list: A list of (message_dict, address_tuple) for successfully decoded messages.
        """
        if not self.is_connected and not self.initialized : # If socket isn't even set up
            # This case might occur if receive_messages is called before successful initialization
            # or after a critical failure.
            # self.logger.debug("receive_messages called but socket not initialized/connected.")
            return [] 

        received_messages_this_call: List[Tuple[Dict[str, Any], Tuple[str, int]]] = []
        
        # Periodic security cleanup (every 60 seconds)
        current_time = time.time()
        if current_time - self._last_security_cleanup > 60:
            self._cleanup_security_state()
            self._last_security_cleanup = current_time
        
        # Process all items currently in the queue
        while not self.incoming_queue.empty():
            try:
                item = self.incoming_queue.get_nowait() # Get item from queue
                raw_data = item['raw_data']
                addr = item['addr']
            except queue.Empty: # Should not happen with while not empty(), but as safeguard
                break
            except Exception as e_q: # Should not happen for basic queue ops
                self.logger.error(f"Error getting item from incoming_queue: {e_q}")
                continue

            # Rate limiting check
            source_ip = addr[0]
            if not self._check_rate_limit(source_ip):
                if self.debug_mode:
                    self.logger.warning(f"Rate limit exceeded for {source_ip}, dropping packet")
                continue


            # Peek at sender_node_id from raw data if possible (for debug log context)
            temp_node_id_peek = "unknown_at_raw_recv"
            try: # This peeking is best-effort for logging, might fail if data is not as expected
                peek_data_bytes = raw_data
                if self.use_compression: # Try decompressing a copy for peeking
                    try: peek_data_bytes = zlib.decompress(raw_data)
                    except zlib.error: pass # If not zlib compressed, peek_data_bytes remains raw_data
                
                j_peek = json.loads(peek_data_bytes.decode('utf-8', errors='ignore'))
                temp_node_id_peek = j_peek.get('node_id', 'peek_decode_fail')
            except: # Broad except as peeking can fail in many ways
                temp_node_id_peek = 'peek_failed_entirely'


            # Log raw reception if it's not from self (based on peek)
            if temp_node_id_peek != self.node_id:
                if self.debug_mode: print(f"DEBUG_RAW_RECEIVE (Node {self.node_id}) from {addr} (Peeked Sender: {temp_node_id_peek}). Size: {len(raw_data)}. Data[:60]: {raw_data[:60]}")
            
            message_dict = None
            decoded_successfully = False
            # Try decoding with security
            try:
                data_to_process = raw_data
                if self.use_compression:
                    try:
                        data_to_process = zlib.decompress(raw_data)
                    except zlib.error:
                        # If decompression fails, assume uncompressed
                        pass

                # Extract signature and encrypted data
                signature_length = 32  # SHA256 HMAC is 32 bytes
                if len(data_to_process) < signature_length:
                    if self.debug_mode: self.logger.warning(f"Packet too short from {addr}")
                    continue
                signature = data_to_process[:signature_length]
                encrypted_data = data_to_process[signature_length:]

                # Verify signature
                if not self.utils.verify_signature(encrypted_data, signature, SHARED_SECRET):
                    if self.debug_mode: self.logger.warning(f"Invalid signature from {addr}")
                    continue

                # Decrypt
                message_dict = self.utils.decrypt_message(encrypted_data, SHARED_SECRET)
                decoded_successfully = True

                # Validate the message
                is_valid, error_msg = PacketValidator.validate_message(message_dict)
                if not is_valid:
                    if self.debug_mode: self.logger.warning(f"Message validation failed from {addr}: {error_msg}")
                    continue

            except Exception as e_decode:
                if self.debug_mode: self.logger.warning(f"Failed to decode/verify/decrypt/validate from {addr} (Sender: {temp_node_id_peek}). Error: {e_decode}. Data: {raw_data[:80]}")
                continue

            if not decoded_successfully:
                continue
            
            final_sender_node_id = cast(str, message_dict['node_id'])
            
            # Critical filter: Ignore messages from self
            if final_sender_node_id == self.node_id:
                continue 

            # Log decoded message details
            if self.debug_mode:
                payload_keys_str = list(message_dict.get('payload', {}).keys()) if isinstance(message_dict.get('payload'), dict) else 'Payload_Not_Dict'
                print(f"DEBUG_DECODED (Node {self.node_id}) from {addr}: Type '{message_dict.get('type', 'N/A')}', From Node '{final_sender_node_id}', PayloadKeys: {payload_keys_str}")
                if message_dict.get('type') == 'squid_exit': # Specific debug for SQUID_EXIT payload
                    print(f"DEBUG_SQUID_EXIT_PAYLOAD_RECEIVED: {message_dict.get('payload')}")
            
            # Update known_nodes (this is a simplified version, a more robust presence system might be needed)
            # The payload of interest for squid's last known state might be deeper, e.g., message_dict['payload']['payload'] for SQUID_EXIT
            squid_info_for_known_nodes: Dict[str, Any] = message_dict.get('payload', {})
            if message_dict.get('type') == 'squid_exit' and isinstance(squid_info_for_known_nodes.get('payload'), dict):
                squid_info_for_known_nodes = cast(Dict[str, Any], squid_info_for_known_nodes.get('payload'))

            self.known_nodes[final_sender_node_id] = (addr[0], time.time(), squid_info_for_known_nodes)
            
            # Add the fully processed message and its original address to the list for the caller
            received_messages_this_call.append((message_dict, addr))

        return received_messages_this_call


    def process_messages(self, plugin_manager_ref: Any) -> None:
        """
        Retrieves messages from the internal queue (filled by receive_messages via listener thread)
        and triggers hooks in the PluginManager.
        This method is intended to be called by the main application thread.
        """
        while not self.incoming_queue.empty(): # Drain the queue
            try:
                # Item from queue is expected to be {'raw_data': ..., 'addr': ...} from _listen_for_multicast
                # NO, item from queue should be (decoded_message_dict, addr) if receive_messages puts decoded ones.
                # Let's clarify: _listen_for_multicast puts raw data.
                # receive_messages (called by this process_messages or similar) decodes them.
                # This process_messages should be working with DECODED messages.

                # The current structure has receive_messages called by process_messages.
                # So, call receive_messages first to get decoded messages.
                decoded_messages_and_addrs = self.receive_messages() # This call processes the queue internally.

                for message_data, addr in decoded_messages_and_addrs:
                    # Now message_data is a decoded dict
                    if 'type' not in message_data or 'node_id' not in message_data:
                        if self.debug_mode: self.logger.debug(f"process_messages: Discarding malformed message: {message_data}")
                        continue

                    # Redundant self-check, receive_messages should have handled this.
                    # if message_data['node_id'] == self.node_id: 
                    #     continue 

                    message_type = message_data.get('type', 'unknown_message')
                    hook_name = f"on_network_{message_type}" # Convention for hook names

                    if self.debug_mode: 
                        print(f"DEBUG_STEP_2A: NetworkNode {self.node_id} attempting to trigger hook: '{hook_name}' for msg type '{message_type}' from node {message_data['node_id']}")
                    
                    # Trigger hook via PluginManager
                    if hasattr(plugin_manager_ref, 'trigger_hook'): 
                        plugin_manager_ref.trigger_hook(
                            hook_name, 
                            node=self,          # Pass this NetworkNode instance
                            message=message_data, # Pass the decoded message dictionary
                            addr=addr            # Pass the original address tuple
                        )
                    # Fallback if PluginManager has a different direct processing method (less common for hook systems)
                    elif hasattr(plugin_manager_ref, '_process_network_message'): 
                       plugin_manager_ref._process_network_message(message_data, addr)
                    else: # Log if no way to dispatch the message
                        if self.debug_mode: self.logger.warning(f"Plugin manager has no trigger_hook or _process_network_message method for hook {hook_name}")
                
                break # process_messages should ideally process one batch from receive_messages at a time.

            except Exception as e: # Catch any errors during the processing loop
                self.logger.error(f"Error in process_messages loop: {e}", exc_info=self.debug_mode)
                break # Exit loop on error to avoid continuous failure on same bad data

    def _check_rate_limit(self, source_ip: str) -> bool:
        """
        Check if a source IP is within rate limits.
        
        Returns:
            True if within limits, False if rate limited
        """
        # Try to use SecurityManager first (centralized tracking)
        if self.security_mgr and hasattr(self.security_mgr, 'check_rate_limit'):
            return self.security_mgr.check_rate_limit(source_ip)
        
        # Fallback to local rate limiting
        current_time = time.time()
        window = 1.0  # 1 second window
        max_packets = 60  # Max packets per second per source
        
        if source_ip not in self._rate_limit_counters:
            self._rate_limit_counters[source_ip] = []
        
        # Remove old timestamps
        self._rate_limit_counters[source_ip] = [
            t for t in self._rate_limit_counters[source_ip]
            if current_time - t < window
        ]
        
        # Check limit
        if len(self._rate_limit_counters[source_ip]) >= max_packets:
            return False
        
        # Record this packet
        self._rate_limit_counters[source_ip].append(current_time)
        return True
    
    def _cleanup_security_state(self) -> None:
        """
        Periodic cleanup of security-related state to prevent memory growth.
        Should be called periodically (e.g., every 60 seconds).
        """
        current_time = time.time()
        
        # Clean up old rate limit counters
        window = 2.0  # Keep 2 seconds of history
        for source_ip in list(self._rate_limit_counters.keys()):
            self._rate_limit_counters[source_ip] = [
                t for t in self._rate_limit_counters[source_ip]
                if current_time - t < window
            ]
            # Remove empty entries
            if not self._rate_limit_counters[source_ip]:
                del self._rate_limit_counters[source_ip]
        
        # Clean up security manager state if available
        if self.security_mgr and hasattr(self.security_mgr, 'cleanup_old_state'):
            self.security_mgr.cleanup_old_state()
        
        # Clean up old known_nodes (inactive for more than 5 minutes)
        inactive_threshold = 300  # 5 minutes
        for node_id in list(self.known_nodes.keys()):
            _, last_seen, _ = self.known_nodes[node_id]
            if current_time - last_seen > inactive_threshold:
                del self.known_nodes[node_id]
                if self.debug_mode:
                    self.logger.debug(f"Removed inactive node: {node_id}")

    def close(self):
        """Cleans up the network node, stops listening, and closes the socket."""
        self.logger.info(f"Closing network node {self.node_id}...")
        self.auto_reconnect = False # Prevent any further reconnect attempts during closure
        
        self.stop_listening() # Signal listener thread to stop and wait for it
        
        # Clean up security state
        self._rate_limit_counters.clear()
        if self.security_mgr:
            self.security_mgr = None
               
        if self.socket:
            socket_was_initialized_and_connected = self.initialized and self.is_connected
            self.is_connected = False # Mark as not connected
            self.initialized = False  # Mark as not initialized

            # Attempt to leave multicast group if socket was properly set up
            if socket_was_initialized_and_connected and self.local_ip: 
                try:
                    # Use "0.0.0.0" for imr_interface when leaving, consistent with joining
                    mreq_leave_struct = socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton("0.0.0.0")
                    self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq_leave_struct)
                    self.logger.info("Left multicast group.")
                except socket.error as e_mcast_leave: 
                    if self.debug_mode: self.logger.debug(f"Socket error leaving multicast group (may be normal if already disconnected): {e_mcast_leave}")
                except AttributeError: # Can happen if local_ip was problematic
                    if self.debug_mode: self.logger.debug("AttributeError leaving multicast group (IP likely invalid during shutdown).")
                except Exception as e_general_leave: # Catch any other unexpected errors
                     if self.debug_mode: self.logger.error(f"Unexpected error leaving multicast group: {e_general_leave}", exc_info=True)
            try:
                self.socket.close()
                self.logger.info("Socket closed.")
            except Exception as e_sock_close:
                if self.debug_mode: self.logger.debug(f"Error closing socket (may already be closed): {e_sock_close}")
            self.socket = None # Clear socket reference
            
        self.logger.info(f"Network node {self.node_id} closed.")
