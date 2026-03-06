"""Security configuration for CGC API."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SecurityConfig:
    """Security configuration.

    Can be loaded from:
    1. Environment variables (CGC_*)
    2. Config file (~/.cgc/security.json)
    3. Programmatic defaults
    """

    # Authentication
    require_auth: bool = True
    api_keys_file: str = "~/.cgc/api_keys.json"

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100  # requests per window
    rate_limit_window_seconds: int = 60  # window size

    # SQL safety
    allow_raw_sql: bool = False  # If False, only SELECT is allowed
    sql_max_rows: int = 10000  # Maximum rows returned
    sql_timeout_seconds: int = 30  # Query timeout
    blocked_sql_keywords: list[str] = field(default_factory=lambda: [
        "DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE", "INSERT", "UPDATE",
        "GRANT", "REVOKE", "EXEC", "EXECUTE", "xp_", "sp_", "--", "/*", "*/",
    ])

    # Filesystem safety
    allowed_paths: list[str] = field(default_factory=list)  # Empty = any (dangerous!)
    blocked_paths: list[str] = field(default_factory=lambda: [
        "/etc", "/var", "/root", "/home", "/usr",
        "C:\\Windows", "C:\\Program Files", "C:\\Users\\*\\AppData",
        ".env", ".git", ".ssh", "id_rsa", "credentials", "secrets",
    ])
    max_file_size_mb: int = 100  # Maximum file size to process

    # Network safety
    allowed_origins: list[str] = field(default_factory=lambda: ["http://localhost:*"])
    bind_host: str = "127.0.0.1"  # Default to localhost only
    bind_port: int = 8420

    # Request limits
    max_request_size_mb: int = 10
    max_query_results: int = 10000
    request_timeout_seconds: int = 60

    # Logging
    log_requests: bool = True
    log_queries: bool = True
    mask_credentials: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "require_auth": self.require_auth,
            "api_keys_file": self.api_keys_file,
            "rate_limit_enabled": self.rate_limit_enabled,
            "rate_limit_requests": self.rate_limit_requests,
            "rate_limit_window_seconds": self.rate_limit_window_seconds,
            "allow_raw_sql": self.allow_raw_sql,
            "sql_max_rows": self.sql_max_rows,
            "sql_timeout_seconds": self.sql_timeout_seconds,
            "blocked_sql_keywords": self.blocked_sql_keywords,
            "allowed_paths": self.allowed_paths,
            "blocked_paths": self.blocked_paths,
            "max_file_size_mb": self.max_file_size_mb,
            "allowed_origins": self.allowed_origins,
            "bind_host": self.bind_host,
            "bind_port": self.bind_port,
            "max_request_size_mb": self.max_request_size_mb,
            "max_query_results": self.max_query_results,
            "request_timeout_seconds": self.request_timeout_seconds,
            "log_requests": self.log_requests,
            "log_queries": self.log_queries,
            "mask_credentials": self.mask_credentials,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SecurityConfig:
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})

    def save(self, path: str | None = None) -> Path:
        """Save configuration to file."""
        if path is None:
            path = "~/.cgc/security.json"

        filepath = Path(path).expanduser()
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(json.dumps(self.to_dict(), indent=2))
        return filepath


def load_security_config(path: str | None = None) -> SecurityConfig:
    """Load security configuration from file and environment.

    Priority (highest to lowest):
    1. Environment variables (CGC_*)
    2. Config file
    3. Defaults
    """
    config = SecurityConfig()

    # Try to load from file
    if path is None:
        path = os.environ.get("CGC_SECURITY_CONFIG", "~/.cgc/security.json")

    filepath = Path(path).expanduser()
    if filepath.exists():
        try:
            data = json.loads(filepath.read_text())
            config = SecurityConfig.from_dict(data)
        except Exception:
            pass  # Use defaults

    # Override with environment variables
    env_mappings = {
        "CGC_REQUIRE_AUTH": ("require_auth", lambda x: x.lower() == "true"),
        "CGC_API_KEYS_FILE": ("api_keys_file", str),
        "CGC_RATE_LIMIT_ENABLED": ("rate_limit_enabled", lambda x: x.lower() == "true"),
        "CGC_RATE_LIMIT_REQUESTS": ("rate_limit_requests", int),
        "CGC_RATE_LIMIT_WINDOW": ("rate_limit_window_seconds", int),
        "CGC_ALLOW_RAW_SQL": ("allow_raw_sql", lambda x: x.lower() == "true"),
        "CGC_SQL_MAX_ROWS": ("sql_max_rows", int),
        "CGC_SQL_TIMEOUT": ("sql_timeout_seconds", int),
        "CGC_ALLOWED_PATHS": ("allowed_paths", lambda x: x.split(",")),
        "CGC_BLOCKED_PATHS": ("blocked_paths", lambda x: x.split(",")),
        "CGC_MAX_FILE_SIZE_MB": ("max_file_size_mb", int),
        "CGC_ALLOWED_ORIGINS": ("allowed_origins", lambda x: x.split(",")),
        "CGC_BIND_HOST": ("bind_host", str),
        "CGC_BIND_PORT": ("bind_port", int),
        "CGC_LOG_REQUESTS": ("log_requests", lambda x: x.lower() == "true"),
        "CGC_LOG_QUERIES": ("log_queries", lambda x: x.lower() == "true"),
    }

    for env_var, (attr, converter) in env_mappings.items():
        value = os.environ.get(env_var)
        if value is not None:
            try:
                setattr(config, attr, converter(value))
            except Exception:
                pass  # Keep default

    return config


# Singleton config instance
_config: SecurityConfig | None = None


def get_security_config() -> SecurityConfig:
    """Get the global security configuration."""
    global _config
    if _config is None:
        _config = load_security_config()
    return _config


def set_security_config(config: SecurityConfig) -> None:
    """Set the global security configuration."""
    global _config
    _config = config
