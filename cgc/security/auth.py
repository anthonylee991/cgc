"""API Key authentication for CGC API."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Security, Request
from fastapi.security import APIKeyHeader, APIKeyQuery


# API Key header/query parameter names
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
API_KEY_QUERY = APIKeyQuery(name="api_key", auto_error=False)


@dataclass
class APIKey:
    """Represents an API key with metadata."""

    key_hash: str  # SHA-256 hash of the actual key
    name: str  # Human-readable name
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_used: str | None = None
    expires_at: str | None = None  # ISO format, None = never expires
    permissions: list[str] = field(default_factory=lambda: ["*"])  # Allowed operations
    rate_limit: int | None = None  # Override global rate limit
    allowed_sources: list[str] = field(default_factory=lambda: ["*"])  # Allowed source IDs
    active: bool = True

    def to_dict(self) -> dict:
        return {
            "key_hash": self.key_hash,
            "name": self.name,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "expires_at": self.expires_at,
            "permissions": self.permissions,
            "rate_limit": self.rate_limit,
            "allowed_sources": self.allowed_sources,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "APIKey":
        return cls(**data)

    def is_expired(self) -> bool:
        """Check if the key has expired."""
        if self.expires_at is None:
            return False
        return datetime.fromisoformat(self.expires_at) < datetime.now()

    def has_permission(self, operation: str) -> bool:
        """Check if the key has permission for an operation."""
        if "*" in self.permissions:
            return True
        return operation in self.permissions

    def can_access_source(self, source_id: str) -> bool:
        """Check if the key can access a source."""
        if "*" in self.allowed_sources:
            return True
        return source_id in self.allowed_sources


class APIKeyStore:
    """Manages API keys storage and validation."""

    def __init__(self, keys_file: str = "~/.cgc/api_keys.json"):
        self.keys_file = Path(keys_file).expanduser()
        self._keys: dict[str, APIKey] = {}
        self._load()

    def _load(self) -> None:
        """Load keys from file."""
        if self.keys_file.exists():
            try:
                data = json.loads(self.keys_file.read_text())
                self._keys = {k: APIKey.from_dict(v) for k, v in data.items()}
            except Exception:
                self._keys = {}

    def _save(self) -> None:
        """Save keys to file."""
        self.keys_file.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v.to_dict() for k, v in self._keys.items()}
        self.keys_file.write_text(json.dumps(data, indent=2))
        # Restrict file permissions (owner read/write only)
        try:
            os.chmod(self.keys_file, 0o600)
        except Exception:
            pass  # May fail on Windows

    def create_key(
        self,
        name: str,
        permissions: list[str] | None = None,
        expires_days: int | None = None,
        allowed_sources: list[str] | None = None,
    ) -> tuple[str, APIKey]:
        """Create a new API key.

        Returns:
            Tuple of (plaintext_key, APIKey object)

        The plaintext key is only available at creation time!
        """
        # Generate secure random key
        plaintext_key = f"cgc_{secrets.token_urlsafe(32)}"
        key_hash = hash_api_key(plaintext_key)

        # Calculate expiration
        expires_at = None
        if expires_days:
            from datetime import timedelta
            expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()

        api_key = APIKey(
            key_hash=key_hash,
            name=name,
            permissions=permissions or ["*"],
            expires_at=expires_at,
            allowed_sources=allowed_sources or ["*"],
        )

        self._keys[key_hash] = api_key
        self._save()

        return plaintext_key, api_key

    def validate_key(self, plaintext_key: str) -> APIKey | None:
        """Validate an API key and return the APIKey object if valid."""
        if not plaintext_key:
            return None

        key_hash = hash_api_key(plaintext_key)
        api_key = self._keys.get(key_hash)

        if api_key is None:
            return None

        if not api_key.active:
            return None

        if api_key.is_expired():
            return None

        # Update last used
        api_key.last_used = datetime.now().isoformat()
        self._save()

        return api_key

    def revoke_key(self, key_hash: str) -> bool:
        """Revoke an API key."""
        if key_hash in self._keys:
            self._keys[key_hash].active = False
            self._save()
            return True
        return False

    def delete_key(self, key_hash: str) -> bool:
        """Delete an API key."""
        if key_hash in self._keys:
            del self._keys[key_hash]
            self._save()
            return True
        return False

    def list_keys(self) -> list[APIKey]:
        """List all API keys (without revealing hashes)."""
        return list(self._keys.values())


def hash_api_key(key: str) -> str:
    """Hash an API key using SHA-256."""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a new random API key."""
    return f"cgc_{secrets.token_urlsafe(32)}"


# Singleton store instance
_store: APIKeyStore | None = None


def get_key_store() -> APIKeyStore:
    """Get the global API key store."""
    global _store
    if _store is None:
        from cgc.security.config import get_security_config
        config = get_security_config()
        _store = APIKeyStore(config.api_keys_file)
    return _store


async def get_api_key(
    api_key_header: str = Security(API_KEY_HEADER),
    api_key_query: str = Security(API_KEY_QUERY),
) -> str | None:
    """Extract API key from request (header or query parameter)."""
    return api_key_header or api_key_query


async def verify_api_key(
    request: Request,
    api_key: str | None = Security(get_api_key),
) -> APIKey:
    """Verify API key and return the APIKey object.

    Raises HTTPException if authentication fails.
    """
    from cgc.security.config import get_security_config
    config = get_security_config()

    # If auth is not required, return a permissive key
    if not config.require_auth:
        return APIKey(
            key_hash="",
            name="anonymous",
            permissions=["*"],
            allowed_sources=["*"],
        )

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide via X-API-Key header or api_key query parameter.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    store = get_key_store()
    validated_key = store.validate_key(api_key)

    if validated_key is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Store the validated key in request state for later use
    request.state.api_key = validated_key

    return validated_key


class APIKeyAuth:
    """Dependency for API key authentication with permission checking."""

    def __init__(self, required_permission: str | None = None):
        self.required_permission = required_permission

    async def __call__(
        self,
        request: Request,
        api_key: APIKey = Security(verify_api_key),
    ) -> APIKey:
        """Verify API key and check permissions."""
        if self.required_permission:
            if not api_key.has_permission(self.required_permission):
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission denied: {self.required_permission}",
                )
        return api_key
