#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configuration handling for dbus-wattcycle-ble."""

import logging
import re

logger = logging.getLogger(__name__)


def parse_simple_yaml(content):
    """Simple YAML parser for systems without PyYAML.
    
    This handles basic YAML structures including:
    - key: value pairs
    - nested dictionaries
    - Basic type conversion (int, float, bool, str)
    """
    def parse_value(v):
        v = v.strip()
        if v.lower() == 'true':
            return True
        if v.lower() == 'false':
            return False
        try:
            return int(v)
        except ValueError:
            try:
                return float(v)
            except ValueError:
                # Remove quotes if present
                return v.strip('"\' ')

    config = {}
    stack = [config]
    
    for line in content.split('\n'):
        # Remove comments and strip
        line = line.split('#')[0].rstrip()
        if not line:
            continue
            
        indent = len(line) - len(line.lstrip())
        level = indent // 2
        stripped = line.strip()
        
        # Adjust stack based on indentation
        while len(stack) > level + 1:
            stack.pop()
        
        current = stack[-1]
        
        # Check for key: value pair
        if ':' in stripped:
            parts = stripped.split(':', 1)
            key = parts[0].strip()
            value_str = parts[1].strip() if len(parts) > 1 else ''
            
            if value_str:
                # Has a value
                current[key] = parse_value(value_str)
            else:
                # No value, create nested dict
                current[key] = {}
                stack.append(current[key])
    
    return config


class Config:
    """Configuration manager for dbus-wattcycle-ble."""
    
    DEFAULT_CONFIG = {
        'battery': {
            'mac_address': None,
            'name': 'Wattcycle Battery',
            'device_instance': 1,
            'poll_interval': 5000,
            'reconnect_delay': 10
        },
        'logging': {
            'level': 'INFO',
            'file': None
        }
    }
    
    def __init__(self, config_file):
        """Load and validate configuration from file.
        
        Args:
            config_file: Path to YAML configuration file
            
        Raises:
            ValueError: If required fields are missing
            IOError: If config file cannot be read
        """
        self.config_file = config_file
        
        # Start with defaults
        self._config = self._deep_copy(self.DEFAULT_CONFIG)
        
        # Load from file
        with open(config_file, 'r') as f:
            file_config = parse_simple_yaml(f.read())
        
        # Merge with defaults
        self._config = self._deep_merge(self._config, file_config)
        
        # Validate
        self._validate()
        
        logger.info(f"Configuration loaded from {config_file}")
    
    def _deep_copy(self, obj):
        """Deep copy a dictionary/list structure."""
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(item) for item in obj]
        return obj
    
    def _deep_merge(self, base, override):
        """Deep merge override dict into base dict."""
        result = self._deep_copy(base)
        
        if not isinstance(override, dict):
            return override
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = self._deep_copy(value)
        
        return result
    
    def _validate(self):
        """Validate required configuration fields."""
        battery = self._config.get('battery', {})
        
        if not battery.get('mac_address'):
            raise ValueError("battery.mac_address is required in config file")
        
        # Validate MAC address format (basic check)
        mac = battery['mac_address']
        mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
        if not mac_pattern.match(mac):
            raise ValueError(f"Invalid MAC address format: {mac}")
        
        # Validate numeric fields
        device_instance = battery.get('device_instance', 1)
        if not isinstance(device_instance, int) or device_instance < 0:
            raise ValueError("battery.device_instance must be a non-negative integer")
        
        poll_interval = battery.get('poll_interval', 5000)
        if not isinstance(poll_interval, int) or poll_interval < 1000:
            raise ValueError("battery.poll_interval must be at least 1000 milliseconds")
        
        reconnect_delay = battery.get('reconnect_delay', 10)
        if not isinstance(reconnect_delay, int) or reconnect_delay < 1:
            raise ValueError("battery.reconnect_delay must be at least 1 second")
        
        # Validate logging level
        logging_config = self._config.get('logging', {})
        level = logging_config.get('level', 'INFO').upper()
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if level not in valid_levels:
            raise ValueError(f"logging.level must be one of: {', '.join(valid_levels)}")
    
    def get(self, key, default=None):
        """Get a configuration value by dot notation.
        
        Args:
            key: Configuration key in dot notation (e.g., 'battery.mac_address')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    @property
    def mac_address(self):
        """Battery MAC address."""
        return self._config['battery']['mac_address']
    
    @property
    def battery_name(self):
        """Battery display name."""
        return self._config['battery'].get('name', 'Wattcycle Battery')
    
    @property
    def device_instance(self):
        """DBus device instance ID."""
        return self._config['battery']['device_instance']
    
    @property
    def poll_interval(self):
        """Polling interval in milliseconds."""
        return self._config['battery']['poll_interval']
    
    @property
    def poll_interval_seconds(self):
        """Polling interval in seconds."""
        return self._config['battery']['poll_interval'] / 1000.0
    
    @property
    def reconnect_delay(self):
        """Reconnection delay in seconds."""
        return self._config['battery']['reconnect_delay']
    
    @property
    def log_level(self):
        """Logging level."""
        return self._config['logging']['level']
    
    @property
    def log_file(self):
        """Optional log file path."""
        return self._config['logging'].get('file')
    
    def __repr__(self):
        return f"Config(mac_address={self.mac_address}, device_instance={self.device_instance})"
