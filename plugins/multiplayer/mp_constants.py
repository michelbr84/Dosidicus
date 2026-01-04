# File: mp_constants.py

# --- Plugin Metadata ---
# These constants describe the plugin to the system and users.
PLUGIN_NAME = "Multiplayer"
PLUGIN_VERSION = "1.3.0"  # Updated for security enhancements
PLUGIN_AUTHOR = "ViciousSquid"
PLUGIN_DESCRIPTION = "Enables network sync for squids and objects (Experimental)"
PLUGIN_REQUIRES = [] # Names of other plugins this one depends on

# --- Network Configuration ---
# These define the network parameters for multicast communication.
MULTICAST_GROUP = '224.3.29.71'   # IP address for the multicast group
MULTICAST_PORT = 10000            # Port number for multicast communication
SYNC_INTERVAL = 1.0               # Default seconds between game state sync broadcasts
MAX_PACKET_SIZE = 1472           # Maximum UDP packet size, to prevent fragmentation

# --- Security Configuration ---
# Base secret for key derivation (HKDF will derive actual keys from this)
# In production, this should be loaded from a secure config or environment variable
SHARED_SECRET = b'dosidicus_multiplayer_secret_key_32'  # 32 bytes for AES-256

# Key derivation context identifiers (for HKDF)
HKDF_ENCRYPTION_CONTEXT = b'dosidicus_encrypt_v1'
HKDF_SIGNING_CONTEXT = b'dosidicus_sign_v1'

# Replay protection settings
NONCE_WINDOW_SIZE = 1000  # Number of recent nonces to track per node
TIMESTAMP_MAX_DRIFT = 300  # Maximum allowed timestamp drift in seconds (5 minutes)

# Rate limiting settings
RATE_LIMIT_WINDOW = 1.0   # Time window in seconds for rate limiting
RATE_LIMIT_MAX_PACKETS = 50  # Maximum packets per window per source
RATE_LIMIT_BURST = 10     # Allow burst of packets above limit briefly

# Authentication timeout
AUTH_TIMEOUT = 30.0  # Seconds before requiring re-authentication

USE_TCP        = False   # default – restored from ini
TCP_IP_LIST    = []      # will be ['192.168.1.50','192.168.1.51',…]
TCP_PORT       = 5008

# --- Visual Settings (Defaults) ---
# These are default visual parameters. The MultiplayerPlugin instance may override these
# based on runtime configuration (e.g., from a settings dialog).
REMOTE_SQUID_OPACITY = 1.0        # Default opacity for remote squids (0.0 to 1.0)
SHOW_REMOTE_LABELS = True         # Default setting for showing labels on remote entities

SHOW_CONNECTION_LINES = True      # Default setting for showing lines connecting to remote squids
