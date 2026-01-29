"""Input validation and sanitization for CGC API."""

from __future__ import annotations

import re
import os
from pathlib import Path
from typing import Any
from fnmatch import fnmatch


class SQLValidationError(Exception):
    """Raised when SQL validation fails."""
    pass


class PathValidationError(Exception):
    """Raised when path validation fails."""
    pass


class InputValidationError(Exception):
    """Raised when input validation fails."""
    pass


# Patterns for safe identifiers (table names, column names, etc.)
SAFE_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
SAFE_IDENTIFIER_WITH_DOT = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_.]*$')

# SQL keywords that should never appear in user-provided identifiers
DANGEROUS_SQL_PATTERNS = [
    r'--',           # SQL comment
    r'/\*',          # Block comment start
    r'\*/',          # Block comment end
    r';',            # Statement terminator
    r'\'',           # Single quote (potential injection)
    r'"',            # Double quote
    r'\\',           # Backslash
    r'\x00',         # Null byte
]


def validate_source_id(source_id: str) -> str:
    """Validate a source ID.

    Args:
        source_id: The source ID to validate

    Returns:
        The validated source ID

    Raises:
        InputValidationError: If validation fails
    """
    if not source_id:
        raise InputValidationError("Source ID cannot be empty")

    if len(source_id) > 64:
        raise InputValidationError("Source ID too long (max 64 characters)")

    if not SAFE_IDENTIFIER_PATTERN.match(source_id):
        raise InputValidationError(
            "Source ID must start with a letter or underscore and contain only "
            "alphanumeric characters and underscores"
        )

    return source_id


def validate_entity_name(entity: str) -> str:
    """Validate an entity name (table name, file path).

    Args:
        entity: The entity name to validate

    Returns:
        The validated entity name

    Raises:
        InputValidationError: If validation fails
    """
    if not entity:
        raise InputValidationError("Entity name cannot be empty")

    if len(entity) > 256:
        raise InputValidationError("Entity name too long (max 256 characters)")

    # Detect if someone accidentally passed a JSON object as the entity
    stripped = entity.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        # Use ValueError for Pydantic v2 compatibility (converts to 422 error)
        raise ValueError(
            "Entity appears to be a JSON object. Please pass just the filename string, "
            "not the entire object. Example: 'myfile.txt' instead of '{\"entity\": \"myfile.txt\"}'"
        )

    # Check for dangerous patterns
    for pattern in DANGEROUS_SQL_PATTERNS:
        if re.search(pattern, entity):
            raise InputValidationError(f"Entity name contains forbidden pattern")

    return entity


def validate_field_name(field: str) -> str:
    """Validate a field/column name.

    Args:
        field: The field name to validate

    Returns:
        The validated field name

    Raises:
        InputValidationError: If validation fails
    """
    if not field:
        raise InputValidationError("Field name cannot be empty")

    if len(field) > 128:
        raise InputValidationError("Field name too long (max 128 characters)")

    if not SAFE_IDENTIFIER_WITH_DOT.match(field):
        raise InputValidationError(
            "Field name must start with a letter or underscore and contain only "
            "alphanumeric characters, underscores, and dots"
        )

    return field


def validate_path(
    path: str,
    allowed_paths: list[str] | None = None,
    blocked_paths: list[str] | None = None,
) -> Path:
    """Validate and resolve a filesystem path.

    Args:
        path: The path to validate
        allowed_paths: List of allowed path patterns (glob-style)
        blocked_paths: List of blocked path patterns (glob-style)

    Returns:
        The resolved, validated Path object

    Raises:
        PathValidationError: If validation fails
    """
    from cgc.security.config import get_security_config

    if allowed_paths is None or blocked_paths is None:
        config = get_security_config()
        if allowed_paths is None:
            allowed_paths = config.allowed_paths
        if blocked_paths is None:
            blocked_paths = config.blocked_paths

    if not path:
        raise PathValidationError("Path cannot be empty")

    # Resolve to absolute path
    try:
        resolved = Path(path).resolve()
    except Exception as e:
        raise PathValidationError(f"Invalid path: {e}")

    resolved_str = str(resolved)

    # Check for path traversal attempts
    if ".." in path:
        raise PathValidationError("Path traversal (..) not allowed")

    # Check blocked paths first
    for blocked in blocked_paths:
        # Handle glob patterns
        if "*" in blocked:
            if fnmatch(resolved_str, blocked) or fnmatch(resolved_str.lower(), blocked.lower()):
                raise PathValidationError(f"Access to path is blocked")
        else:
            blocked_resolved = str(Path(blocked).expanduser().resolve())
            if resolved_str.startswith(blocked_resolved) or resolved_str.lower().startswith(blocked_resolved.lower()):
                raise PathValidationError(f"Access to path is blocked")

    # Check filename for sensitive patterns
    filename = resolved.name.lower()
    sensitive_names = ['.env', '.git', '.ssh', 'id_rsa', 'credentials', 'secrets', 'password', 'apikey', 'api_key']
    for sensitive in sensitive_names:
        if sensitive in filename:
            raise PathValidationError(f"Access to sensitive files is blocked")

    # If allowed_paths is specified and non-empty, path must match
    if allowed_paths:
        is_allowed = False
        for allowed in allowed_paths:
            if "*" in allowed:
                if fnmatch(resolved_str, allowed) or fnmatch(resolved_str.lower(), allowed.lower()):
                    is_allowed = True
                    break
            else:
                allowed_resolved = str(Path(allowed).expanduser().resolve())
                if resolved_str.startswith(allowed_resolved) or resolved_str.lower().startswith(allowed_resolved.lower()):
                    is_allowed = True
                    break

        if not is_allowed:
            raise PathValidationError(f"Path not in allowed list")

    return resolved


def is_safe_sql(sql: str, allow_mutations: bool = False) -> tuple[bool, str | None]:
    """Check if a SQL query is safe to execute.

    Args:
        sql: The SQL query to check
        allow_mutations: Whether to allow INSERT/UPDATE/DELETE

    Returns:
        Tuple of (is_safe, error_message)
    """
    from cgc.security.config import get_security_config
    config = get_security_config()

    sql_upper = sql.upper().strip()

    # Check for blocked keywords
    for keyword in config.blocked_sql_keywords:
        # Use word boundary matching to avoid false positives
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, sql_upper):
            return False, f"Blocked SQL keyword: {keyword}"

    # Check for multiple statements
    if ';' in sql.strip().rstrip(';'):
        return False, "Multiple SQL statements not allowed"

    # If raw SQL not allowed, only permit SELECT
    if not config.allow_raw_sql and not allow_mutations:
        if not sql_upper.startswith('SELECT'):
            return False, "Only SELECT queries allowed"

    # Check for dangerous patterns
    dangerous_patterns = [
        (r'INTO\s+OUTFILE', "INTO OUTFILE not allowed"),
        (r'INTO\s+DUMPFILE', "INTO DUMPFILE not allowed"),
        (r'LOAD_FILE', "LOAD_FILE not allowed"),
        (r'BENCHMARK\s*\(', "BENCHMARK not allowed"),
        (r'SLEEP\s*\(', "SLEEP not allowed"),
        (r'WAITFOR', "WAITFOR not allowed"),
        (r'@@', "System variables not allowed"),
        (r'INFORMATION_SCHEMA', "INFORMATION_SCHEMA access restricted"),
        (r'pg_', "PostgreSQL system tables access restricted"),
        (r'sqlite_', "SQLite system tables access restricted"),
    ]

    for pattern, message in dangerous_patterns:
        if re.search(pattern, sql_upper):
            return False, message

    return True, None


def sanitize_sql(sql: str) -> str:
    """Sanitize a SQL query for safe execution.

    Note: This is NOT a replacement for parameterized queries!
    Use this only for additional defense-in-depth.

    Args:
        sql: The SQL query to sanitize

    Returns:
        The sanitized SQL query

    Raises:
        SQLValidationError: If the query cannot be made safe
    """
    # Check if SQL is safe first
    is_safe, error = is_safe_sql(sql)
    if not is_safe:
        raise SQLValidationError(error or "SQL validation failed")

    # Remove comments
    sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)

    # Remove trailing semicolons
    sql = sql.strip().rstrip(';')

    return sql


def validate_connection_string(connection: str, source_type: str) -> str:
    """Validate a database connection string.

    Args:
        connection: The connection string
        source_type: The type of source (postgres, mysql, etc.)

    Returns:
        The validated connection string

    Raises:
        InputValidationError: If validation fails
    """
    if not connection:
        raise InputValidationError("Connection string cannot be empty")

    # Check for obvious injection attempts
    dangerous = ['`', '$', '|', '&&', '||', '\n', '\r']
    for char in dangerous:
        if char in connection:
            raise InputValidationError(f"Connection string contains forbidden character")

    # Validate based on source type
    if source_type in ('postgres', 'mysql', 'pgvector'):
        # Should look like a URL
        if not (connection.startswith('postgresql://') or
                connection.startswith('postgres://') or
                connection.startswith('mysql://') or
                connection.startswith('mysql+') or
                connection.startswith('postgresql+')):
            raise InputValidationError(
                f"Invalid connection string format for {source_type}"
            )

    elif source_type == 'sqlite':
        # Should be a file path or sqlite:// URL
        if not (connection.startswith('sqlite://') or
                connection.endswith('.db') or
                connection.endswith('.sqlite') or
                connection.endswith('.sqlite3')):
            raise InputValidationError(
                "SQLite connection should be a .db/.sqlite file or sqlite:// URL"
            )

    elif source_type == 'filesystem':
        # Validate as path
        validate_path(connection)

    elif source_type in ('qdrant', 'pinecone', 'mongodb'):
        # Should be a URL
        if not (connection.startswith('http://') or
                connection.startswith('https://') or
                connection.startswith('mongodb://') or
                connection.startswith('mongodb+srv://')):
            # Could also be just a host:port
            if ':' not in connection and '.' not in connection and connection != 'localhost':
                raise InputValidationError(
                    f"Invalid connection string format for {source_type}"
                )

    return connection


def mask_credentials(text: str) -> str:
    """Mask credentials in a string (for logging).

    Args:
        text: Text potentially containing credentials

    Returns:
        Text with credentials masked
    """
    # Mask passwords in connection strings
    text = re.sub(
        r'(://[^:]+:)[^@]+(@)',
        r'\1****\2',
        text
    )

    # Mask API keys
    text = re.sub(
        r'(api_key["\']?\s*[:=]\s*["\']?)[^"\'\s,}]+',
        r'\1****',
        text,
        flags=re.IGNORECASE
    )

    # Mask bearer tokens
    text = re.sub(
        r'(Bearer\s+)[^\s]+',
        r'\1****',
        text,
        flags=re.IGNORECASE
    )

    # Mask common credential patterns
    patterns = [
        (r'(password["\']?\s*[:=]\s*["\']?)[^"\'\s,}]+', r'\1****'),
        (r'(secret["\']?\s*[:=]\s*["\']?)[^"\'\s,}]+', r'\1****'),
        (r'(token["\']?\s*[:=]\s*["\']?)[^"\'\s,}]+', r'\1****'),
        (r'(key["\']?\s*[:=]\s*["\']?)[^"\'\s,}]+', r'\1****'),
    ]

    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text
