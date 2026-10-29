"""Security and password hashing utilities."""

import bcrypt


def get_password_hash(password: str) -> str:
    """Hash a plaintext password using bcrypt with automatic salt generation."""
    if not password:
        raise ValueError("Password cannot be empty.")
    pwd_bytes = password.encode("utf-8")
    if len(pwd_bytes) > 72:
        raise ValueError("Password cannot exceed 72 bytes when encoded.")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash safely."""
    if not plain_password or not hashed_password:
        return False
    try:
        pwd_bytes = plain_password.encode("utf-8")
        # Bcrypt cannot verify passwords > 72 bytes; safely return False without raising
        if len(pwd_bytes) > 72:
            return False
        return bcrypt.checkpw(
            pwd_bytes,
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False
