import os
import sqlite3
import logging
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

PLATFORM_BLESS = "lularoe_bless"
_KEY_ENV = "LULA_KEY"


def _get_fernet():
    key = os.environ.get(_KEY_ENV)
    if not key:
        raise RuntimeError(
            f"Environment variable {_KEY_ENV} is not set. "
            f"Run `python credential_manager.py generate-key` to create one."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def _ensure_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Credentials (
            platform          TEXT PRIMARY KEY,
            username          TEXT NOT NULL,
            encrypted_password BLOB NOT NULL,
            updated_at        TEXT NOT NULL
        )
    """)
    conn.commit()


def save_credentials(db_path, platform, username, password):
    f = _get_fernet()
    encrypted = f.encrypt(password.encode())
    conn = sqlite3.connect(db_path)
    try:
        _ensure_table(conn)
        conn.execute(
            "INSERT OR REPLACE INTO Credentials "
            "(platform, username, encrypted_password, updated_at) VALUES (?,?,?,?)",
            (platform, username, encrypted, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        logger.info("Credentials saved for platform: %s", platform)
    finally:
        conn.close()


def get_credentials(db_path, platform):
    """Return (username, password) tuple or None if not stored."""
    conn = sqlite3.connect(db_path)
    try:
        _ensure_table(conn)
        row = conn.execute(
            "SELECT username, encrypted_password FROM Credentials WHERE platform = ?",
            (platform,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return None

    f = _get_fernet()
    try:
        password = f.decrypt(row[1]).decode()
    except InvalidToken:
        logger.error("Failed to decrypt credentials — LULA_KEY may have changed.")
        return None

    return row[0], password


def delete_credentials(db_path, platform):
    conn = sqlite3.connect(db_path)
    try:
        _ensure_table(conn)
        conn.execute("DELETE FROM Credentials WHERE platform = ?", (platform,))
        conn.commit()
    finally:
        conn.close()


def generate_key():
    """Print a new Fernet key suitable for use as LULA_KEY."""
    return Fernet.generate_key().decode()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "generate-key":
        key = generate_key()
        print(f"Add this to your environment:\n\nexport LULA_KEY={key}")
    else:
        print("Usage: python credential_manager.py generate-key")
