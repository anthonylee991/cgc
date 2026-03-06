"""Security module for CGC API."""

from cgc.security.auth import (
    APIKeyAuth,
    generate_api_key,
    get_api_key,
    hash_api_key,
    verify_api_key,
)
from cgc.security.config import SecurityConfig, load_security_config
from cgc.security.middleware import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from cgc.security.validation import (
    PathValidationError,
    SQLValidationError,
    is_safe_sql,
    sanitize_sql,
    validate_entity_name,
    validate_field_name,
    validate_path,
    validate_source_id,
)

__all__ = [
    # Auth
    "APIKeyAuth",
    "get_api_key",
    "verify_api_key",
    "generate_api_key",
    "hash_api_key",
    # Config
    "SecurityConfig",
    "load_security_config",
    # Middleware
    "RateLimitMiddleware",
    "SecurityHeadersMiddleware",
    # Validation
    "validate_source_id",
    "validate_entity_name",
    "validate_field_name",
    "validate_path",
    "sanitize_sql",
    "is_safe_sql",
    "SQLValidationError",
    "PathValidationError",
]
