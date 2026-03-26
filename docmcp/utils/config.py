"""
Configuration management for DocMCP.

Provides configuration loading, validation, and management.
"""

from __future__ import annotations

import os
import yaml
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

T = TypeVar("T")


@dataclass
class Config:
    """
    Application configuration.
    
    Attributes:
        app_name: Application name
        debug: Debug mode
        log_level: Logging level
        server: Server configuration
        database: Database configuration
        cache: Cache configuration
        storage: Storage configuration
        security: Security configuration
        processing: Processing configuration
    """
    
    # General
    app_name: str = "DocMCP"
    debug: bool = False
    log_level: str = "INFO"
    
    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8080
    server_workers: int = 4
    
    # Database
    database_url: str = "postgresql://localhost/docmcp"
    database_pool_size: int = 10
    
    # Cache
    cache_url: str = "redis://localhost:6379/0"
    cache_ttl: int = 3600
    
    # Storage
    storage_type: str = "local"  # local, s3, minio
    storage_path: str = "/tmp/docmcp/storage"
    storage_bucket: str = "docmcp"
    
    # Security
    secret_key: str = field(default_factory=lambda: os.urandom(32).hex())
    jwt_algorithm: str = "HS256"
    jwt_expiration: int = 3600
    enable_auth: bool = True
    
    # Processing
    max_workers: int = 4
    max_queue_size: int = 1000
    default_timeout: float = 300.0
    max_file_size_mb: int = 100
    
    # Skills
    skills_directory: str = "./skills"
    enable_skill_hot_reload: bool = False
    
    # MCP
    mcp_enabled: bool = True
    mcp_max_connections: int = 1000
    
    # Additional config
    extra: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Config:
        """Create config from dictionary."""
        # Extract known fields
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        config_data = {k: v for k, v in data.items() if k in known_fields}
        extra = {k: v for k, v in data.items() if k not in known_fields}
        
        config_data["extra"] = extra
        return cls(**config_data)
    
    @classmethod
    def from_file(cls, path: Union[str, Path]) -> Config:
        """Load config from file."""
        path = Path(path)
        
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        
        content = path.read_text()
        
        if path.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(content)
        elif path.suffix == ".json":
            data = json.loads(content)
        else:
            raise ValueError(f"Unsupported config format: {path.suffix}")
        
        return cls.from_dict(data)
    
    @classmethod
    def from_env(cls, prefix: str = "DOCMCP_") -> Config:
        """Load config from environment variables."""
        data = {}
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower()
                
                # Try to parse as different types
                if value.lower() in ("true", "false"):
                    data[config_key] = value.lower() == "true"
                elif value.isdigit():
                    data[config_key] = int(value)
                elif "." in value and value.replace(".", "").isdigit():
                    data[config_key] = float(value)
                else:
                    data[config_key] = value
        
        return cls.from_dict(data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        result = asdict(self)
        # Merge extra back into main dict
        extra = result.pop("extra", {})
        result.update(extra)
        return result
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by key."""
        if hasattr(self, key):
            return getattr(self, key)
        return self.extra.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set config value."""
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            self.extra[key] = value


class ConfigManager:
    """
    Configuration manager.
    
    Manages configuration with support for multiple sources and hot-reloading.
    """
    
    def __init__(self, config: Optional[Config] = None):
        self._config = config or Config()
        self._listeners: List[callable] = []
    
    @property
    def config(self) -> Config:
        """Get current configuration."""
        return self._config
    
    def load_from_file(self, path: Union[str, Path]) -> None:
        """Load configuration from file."""
        self._config = Config.from_file(path)
        self._notify_listeners()
    
    def load_from_env(self, prefix: str = "DOCMCP_") -> None:
        """Load configuration from environment variables."""
        env_config = Config.from_env(prefix)
        
        # Merge with existing config
        for key, value in env_config.to_dict().items():
            if value is not None:
                self._config.set(key, value)
        
        self._notify_listeners()
    
    def update(self, updates: Dict[str, Any]) -> None:
        """Update configuration values."""
        for key, value in updates.items():
            self._config.set(key, value)
        self._notify_listeners()
    
    def add_listener(self, callback: callable) -> None:
        """Add a configuration change listener."""
        self._listeners.append(callback)
    
    def remove_listener(self, callback: callable) -> None:
        """Remove a configuration change listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    def _notify_listeners(self) -> None:
        """Notify all listeners of configuration change."""
        for listener in self._listeners:
            try:
                listener(self._config)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Config listener error: {e}")


def load_config(
    file_path: Optional[Union[str, Path]] = None,
    env_prefix: str = "DOCMCP_",
) -> Config:
    """
    Load configuration from multiple sources.
    
    Sources are loaded in order (later sources override earlier):
        1. Default values
        2. Config file (if provided)
        3. Environment variables
    
    Args:
        file_path: Path to config file
        env_prefix: Environment variable prefix
        
    Returns:
        Loaded configuration
    """
    config = Config()
    
    # Load from file
    if file_path:
        file_config = Config.from_file(file_path)
        for key, value in file_config.to_dict().items():
            if value is not None:
                config.set(key, value)
    
    # Load from environment
    env_config = Config.from_env(env_prefix)
    for key, value in env_config.to_dict().items():
        if value is not None:
            config.set(key, value)
    
    return config
