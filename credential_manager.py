import os
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


def _get_conn():
    from app.db import get_conn
    return get_conn()


def save_credentials(user_id, platform, username, password):
    import binascii
    f = _get_fernet()
    encrypted = f.encrypt(password.encode())
    conn = _get_conn()
    try:
        cred_id = binascii.b2a_hex(os.urandom(12)).decode()
        conn.execute(
            "INSERT INTO Credentials "
            "(CredentialID, UserID, platform, username, encrypted_password, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (UserID, platform) DO UPDATE SET "
            "username = EXCLUDED.username, "
            "encrypted_password = EXCLUDED.encrypted_password, "
            "updated_at = EXCLUDED.updated_at",
            (cred_id, user_id, platform, username, encrypted,
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        logger.info("Credentials saved for platform: %s user: %s", platform, user_id)
    finally:
        conn.close()


def get_credentials(user_id, platform):
    """Return (username, password) tuple or None if not stored."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT username, encrypted_password FROM Credentials "
            "WHERE UserID = %s AND platform = %s",
            (user_id, platform),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return None

    f = _get_fernet()
    try:
        encrypted = row['encrypted_password']
        if isinstance(encrypted, memoryview):
            encrypted = bytes(encrypted)
        password = f.decrypt(encrypted).decode()
    except InvalidToken:
        logger.error("Failed to decrypt credentials — LULA_KEY may have changed.")
        return None

    return row['username'], password


def delete_credentials(user_id, platform):
    conn = _get_conn()
    try:
        conn.execute(
            "DELETE FROM Credentials WHERE UserID = %s AND platform = %s",
            (user_id, platform)
        )
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
