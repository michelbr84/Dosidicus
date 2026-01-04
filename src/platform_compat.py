# src/platform_compat.py
"""
Platform Compatibility Module - Cross-platform abstractions for Linux and macOS support.
"""

import os
import sys
import platform
import logging
import subprocess
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class PlatformInfo:
    """Information about the current platform."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize platform detection."""
        self.system = platform.system().lower()
        self.release = platform.release()
        self.version = platform.version()
        self.machine = platform.machine()
        self.python_version = platform.python_version()
        
        # Detect specific OS variants
        self.is_windows = self.system == 'windows'
        self.is_linux = self.system == 'linux'
        self.is_macos = self.system == 'darwin'
        self.is_unix = self.is_linux or self.is_macos
        
        # Detect desktop environment on Linux
        self.desktop_env = None
        if self.is_linux:
            self.desktop_env = os.environ.get('XDG_CURRENT_DESKTOP', 
                              os.environ.get('DESKTOP_SESSION', 'unknown'))
        
        logger.info(f"Platform detected: {self.system} ({self.machine})")
    
    def get_info(self) -> Dict[str, Any]:
        """Get platform information dictionary."""
        return {
            'system': self.system,
            'release': self.release,
            'version': self.version,
            'machine': self.machine,
            'python_version': self.python_version,
            'is_windows': self.is_windows,
            'is_linux': self.is_linux,
            'is_macos': self.is_macos,
            'desktop_env': self.desktop_env
        }


class PathHandler:
    """Cross-platform path handling utilities."""
    
    def __init__(self):
        self.platform = PlatformInfo()
    
    def get_app_data_dir(self) -> Path:
        """Get the appropriate application data directory."""
        if self.platform.is_windows:
            base = os.environ.get('APPDATA', os.path.expanduser('~'))
            return Path(base) / 'Dosidicus'
        elif self.platform.is_macos:
            return Path.home() / 'Library' / 'Application Support' / 'Dosidicus'
        else:  # Linux and others
            xdg_data = os.environ.get('XDG_DATA_HOME', 
                                      os.path.expanduser('~/.local/share'))
            return Path(xdg_data) / 'dosidicus'
    
    def get_config_dir(self) -> Path:
        """Get the appropriate configuration directory."""
        if self.platform.is_windows:
            base = os.environ.get('APPDATA', os.path.expanduser('~'))
            return Path(base) / 'Dosidicus'
        elif self.platform.is_macos:
            return Path.home() / 'Library' / 'Preferences' / 'Dosidicus'
        else:  # Linux
            xdg_config = os.environ.get('XDG_CONFIG_HOME',
                                        os.path.expanduser('~/.config'))
            return Path(xdg_config) / 'dosidicus'
    
    def get_cache_dir(self) -> Path:
        """Get the appropriate cache directory."""
        if self.platform.is_windows:
            base = os.environ.get('LOCALAPPDATA', 
                                  os.environ.get('APPDATA', os.path.expanduser('~')))
            return Path(base) / 'Dosidicus' / 'Cache'
        elif self.platform.is_macos:
            return Path.home() / 'Library' / 'Caches' / 'Dosidicus'
        else:  # Linux
            xdg_cache = os.environ.get('XDG_CACHE_HOME',
                                       os.path.expanduser('~/.cache'))
            return Path(xdg_cache) / 'dosidicus'
    
    def get_log_dir(self) -> Path:
        """Get the appropriate log directory."""
        if self.platform.is_windows:
            return self.get_app_data_dir() / 'logs'
        elif self.platform.is_macos:
            return Path.home() / 'Library' / 'Logs' / 'Dosidicus'
        else:  # Linux
            return self.get_cache_dir() / 'logs'
    
    def normalize_path(self, path: str) -> str:
        """Normalize a path for the current platform."""
        return str(Path(path).resolve())
    
    def ensure_dir(self, path: Path) -> bool:
        """Ensure a directory exists, creating it if necessary."""
        try:
            path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Failed to create directory {path}: {e}")
            return False


class FontFallback:
    """Font fallback system for cross-platform font support."""
    
    # Font preferences by platform
    FONT_PREFERENCES = {
        'windows': {
            'ui': ['Segoe UI', 'Tahoma', 'Arial'],
            'mono': ['Consolas', 'Courier New', 'Lucida Console'],
            'emoji': ['Segoe UI Emoji', 'Segoe UI Symbol']
        },
        'darwin': {  # macOS
            'ui': ['SF Pro Text', 'Helvetica Neue', 'Helvetica'],
            'mono': ['SF Mono', 'Menlo', 'Monaco'],
            'emoji': ['Apple Color Emoji']
        },
        'linux': {
            'ui': ['Ubuntu', 'Noto Sans', 'DejaVu Sans', 'Liberation Sans'],
            'mono': ['Ubuntu Mono', 'DejaVu Sans Mono', 'Liberation Mono'],
            'emoji': ['Noto Color Emoji', 'Symbola', 'OpenMoji']
        }
    }
    
    def __init__(self):
        self.platform = PlatformInfo()
        self._available_fonts: Optional[List[str]] = None
    
    def get_font_family(self, font_type: str = 'ui') -> str:
        """
        Get the best available font for the given type.
        
        Args:
            font_type: 'ui', 'mono', or 'emoji'
            
        Returns:
            Best available font family name
        """
        prefs = self.FONT_PREFERENCES.get(
            self.platform.system, 
            self.FONT_PREFERENCES['linux']
        )
        
        candidates = prefs.get(font_type, prefs.get('ui', ['sans-serif']))
        
        # Try to detect available fonts
        available = self._get_available_fonts()
        
        for font in candidates:
            if available is None or font.lower() in [f.lower() for f in available]:
                return font
        
        # Fallback
        fallbacks = {
            'ui': 'sans-serif',
            'mono': 'monospace',
            'emoji': 'sans-serif'
        }
        return fallbacks.get(font_type, 'sans-serif')
    
    def _get_available_fonts(self) -> Optional[List[str]]:
        """Get list of available system fonts (best effort)."""
        if self._available_fonts is not None:
            return self._available_fonts
        
        try:
            # Try using fc-list on Linux/macOS
            if self.platform.is_unix:
                result = subprocess.run(
                    ['fc-list', ':', 'family'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    fonts = set()
                    for line in result.stdout.split('\n'):
                        for font in line.split(','):
                            fonts.add(font.strip())
                    self._available_fonts = list(fonts)
                    return self._available_fonts
        except Exception:
            pass
        
        return None


class NetworkCompat:
    """Cross-platform network interface utilities."""
    
    def __init__(self):
        self.platform = PlatformInfo()
    
    def get_local_ip(self) -> str:
        """Get local IP address in a cross-platform way."""
        import socket
        
        try:
            # Create a socket and connect to an external address
            # This doesn't actually send data but determines the outgoing interface
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0.5)
                s.connect(('8.8.8.8', 80))
                return s.getsockname()[0]
        except Exception:
            pass
        
        # Fallback: try to get from hostname
        try:
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        except Exception:
            pass
        
        return '127.0.0.1'
    
    def get_network_interfaces(self) -> List[Dict[str, Any]]:
        """Get list of network interfaces."""
        interfaces = []
        
        try:
            import socket
            hostname = socket.gethostname()
            
            # Get all addresses for this host
            try:
                addrs = socket.getaddrinfo(hostname, None, socket.AF_INET)
                for addr in addrs:
                    ip = addr[4][0]
                    if not ip.startswith('127.'):
                        interfaces.append({
                            'name': 'default',
                            'ip': ip,
                            'family': 'ipv4'
                        })
            except Exception:
                pass
            
        except Exception as e:
            logger.warning(f"Failed to enumerate network interfaces: {e}")
        
        # Always include loopback
        interfaces.append({
            'name': 'loopback',
            'ip': '127.0.0.1',
            'family': 'ipv4'
        })
        
        return interfaces
    
    def is_multicast_available(self) -> bool:
        """Check if multicast is likely available."""
        import socket
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            sock.close()
            return True
        except Exception:
            return False


class ProcessCompat:
    """Cross-platform process and thread utilities."""
    
    def __init__(self):
        self.platform = PlatformInfo()
    
    def set_process_priority(self, priority: str = 'normal') -> bool:
        """
        Set process priority.
        
        Args:
            priority: 'low', 'normal', or 'high'
            
        Returns:
            True if successful
        """
        try:
            if self.platform.is_windows:
                import ctypes
                
                priorities = {
                    'low': 0x00004000,    # BELOW_NORMAL_PRIORITY_CLASS
                    'normal': 0x00000020,  # NORMAL_PRIORITY_CLASS
                    'high': 0x00008000     # ABOVE_NORMAL_PRIORITY_CLASS
                }
                
                handle = ctypes.windll.kernel32.GetCurrentProcess()
                ctypes.windll.kernel32.SetPriorityClass(
                    handle, 
                    priorities.get(priority, 0x00000020)
                )
                return True
                
            else:  # Unix
                import os
                
                nice_values = {
                    'low': 10,
                    'normal': 0,
                    'high': -5
                }
                
                os.nice(nice_values.get(priority, 0))
                return True
                
        except Exception as e:
            logger.warning(f"Failed to set process priority: {e}")
            return False
    
    def get_cpu_count(self) -> int:
        """Get the number of CPUs available."""
        try:
            return os.cpu_count() or 1
        except Exception:
            return 1
    
    def get_memory_info(self) -> Dict[str, int]:
        """Get memory information (best effort)."""
        info = {'available': 0, 'total': 0}
        
        try:
            if self.platform.is_linux:
                with open('/proc/meminfo', 'r') as f:
                    for line in f:
                        if line.startswith('MemTotal:'):
                            info['total'] = int(line.split()[1]) * 1024
                        elif line.startswith('MemAvailable:'):
                            info['available'] = int(line.split()[1]) * 1024
            
            elif self.platform.is_macos:
                # Use vm_stat on macOS
                result = subprocess.run(
                    ['vm_stat'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    # Parse vm_stat output (simplified)
                    pass
            
            elif self.platform.is_windows:
                import ctypes
                
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ('dwLength', ctypes.c_ulong),
                        ('dwMemoryLoad', ctypes.c_ulong),
                        ('ullTotalPhys', ctypes.c_ulonglong),
                        ('ullAvailPhys', ctypes.c_ulonglong),
                        ('ullTotalPageFile', ctypes.c_ulonglong),
                        ('ullAvailPageFile', ctypes.c_ulonglong),
                        ('ullTotalVirtual', ctypes.c_ulonglong),
                        ('ullAvailVirtual', ctypes.c_ulonglong),
                        ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
                    ]
                
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(stat)
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                
                info['total'] = stat.ullTotalPhys
                info['available'] = stat.ullAvailPhys
                
        except Exception as e:
            logger.warning(f"Failed to get memory info: {e}")
        
        return info


# Convenience singleton instances
_platform_info = None
_path_handler = None
_font_fallback = None
_network_compat = None
_process_compat = None


def get_platform_info() -> PlatformInfo:
    """Get platform info singleton."""
    global _platform_info
    if _platform_info is None:
        _platform_info = PlatformInfo()
    return _platform_info


def get_path_handler() -> PathHandler:
    """Get path handler singleton."""
    global _path_handler
    if _path_handler is None:
        _path_handler = PathHandler()
    return _path_handler


def get_font_fallback() -> FontFallback:
    """Get font fallback singleton."""
    global _font_fallback
    if _font_fallback is None:
        _font_fallback = FontFallback()
    return _font_fallback


def get_network_compat() -> NetworkCompat:
    """Get network compat singleton."""
    global _network_compat
    if _network_compat is None:
        _network_compat = NetworkCompat()
    return _network_compat


def get_process_compat() -> ProcessCompat:
    """Get process compat singleton."""
    global _process_compat
    if _process_compat is None:
        _process_compat = ProcessCompat()
    return _process_compat
