"""Encrypted license persistence using AES-256-GCM + SQLite."""

from __future__ import annotations

import base64
import json
import os
import sqlite3
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from cgc.licensing.tier import License

APP_SECRET = b"cgc-desktop-v1-2026"
PBKDF2_ITERATIONS = 100_000
SALT_LENGTH = 16
NONCE_LENGTH = 12


def _default_db_path() -> Path:
    """Default license database path: ~/.cgc/license.db"""
    cgc_dir = Path.home() / ".cgc"
    cgc_dir.mkdir(parents=True, exist_ok=True)
    return cgc_dir / "license.db"


def _derive_key(salt: bytes) -> bytes:
    """Derive a 256-bit AES key from the app secret + salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(APP_SECRET)


def _encrypt(plaintext: bytes, salt: bytes) -> tuple[bytes, bytes]:
    """Encrypt with AES-256-GCM. Returns (nonce, ciphertext)."""
    key = _derive_key(salt)
    nonce = os.urandom(NONCE_LENGTH)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce, ciphertext


def _decrypt(nonce: bytes, ciphertext: bytes, salt: bytes) -> bytes:
    """Decrypt AES-256-GCM ciphertext."""
    key = _derive_key(salt)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


class LicenseStore:
    """Encrypted license storage backed by SQLite."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or _default_db_path()
        self._init_db()

    def _init_db(self):
        """Create the license table if it doesn't exist."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS license (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    encrypted_data TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    salt TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def save(self, license: License) -> None:
        """Encrypt and save a license record."""
        plaintext = json.dumps(license.to_dict()).encode("utf-8")
        salt = os.urandom(SALT_LENGTH)
        nonce, ciphertext = _encrypt(plaintext, salt)

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """INSERT INTO license (id, encrypted_data, nonce, salt)
                   VALUES (1, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       encrypted_data = excluded.encrypted_data,
                       nonce = excluded.nonce,
                       salt = excluded.salt""",
                (
                    base64.b64encode(ciphertext).decode(),
                    base64.b64encode(nonce).decode(),
                    base64.b64encode(salt).decode(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def load(self) -> License | None:
        """Load and decrypt the stored license. Returns None if not found."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(
                "SELECT encrypted_data, nonce, salt FROM license WHERE id = 1"
            ).fetchone()

            if not row:
                return None

            ciphertext = base64.b64decode(row[0])
            nonce = base64.b64decode(row[1])
            salt = base64.b64decode(row[2])

            plaintext = _decrypt(nonce, ciphertext, salt)
            data = json.loads(plaintext.decode("utf-8"))
            return License.from_dict(data)
        except Exception:
            return None
        finally:
            conn.close()

    def clear(self) -> None:
        """Remove stored license."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("DELETE FROM license WHERE id = 1")
            conn.commit()
        finally:
            conn.close()
