import os
import hmac
import hashlib
import base64
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

# Secret key for token signing (can be configured via environment variable)
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jace-haus-msp-super-secret-key-2026-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
PBKDF2_ITERATIONS = 100000


def hash_password(password: str) -> str:
    """
    Hash a password securely using PBKDF2-HMAC-SHA256 with a random salt.
    Format: pbkdf2:sha256:iterations$salt_hex$hash_hex
    """
    if not password:
        raise ValueError("Password cannot be empty")
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS
    )
    return f"pbkdf2:sha256:{PBKDF2_ITERATIONS}${salt.hex()}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a stored PBKDF2-HMAC-SHA256 hash using constant-time comparison.
    """
    if not plain_password or not hashed_password:
        return False

    try:
        parts = hashed_password.split("$")
        if len(parts) != 3:
            return False
        
        algorithm_info, salt_hex, hash_hex = parts
        _, _, iterations_str = algorithm_info.split(":")
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(hash_hex)

        actual_key = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt,
            iterations
        )
        return hmac.compare_digest(actual_key, expected_key)
    except Exception:
        return False


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _base64url_decode(data: str) -> bytes:
    padding = "=" * (4 - (len(data) % 4)) if len(data) % 4 != 0 else ""
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create an HMAC-SHA256 signed JWT token.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp())
    })

    header = {"alg": ALGORITHM, "typ": "JWT"}
    
    header_json = json.dumps(header, separators=(",", ":")).encode("utf-8")
    payload_json = json.dumps(to_encode, separators=(",", ":")).encode("utf-8")

    header_b64 = _base64url_encode(header_json)
    payload_b64 = _base64url_encode(payload_json)

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(
        SECRET_KEY.encode("utf-8"),
        signing_input,
        hashlib.sha256
    ).digest()
    signature_b64 = _base64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify and decode an HMAC-SHA256 signed JWT token.
    Returns the payload dictionary if valid, or None if expired or invalid.
    """
    if not token or not isinstance(token, str):
        return None

    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, signature_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")

        expected_sig = hmac.new(
            SECRET_KEY.encode("utf-8"),
            signing_input,
            hashlib.sha256
        ).digest()
        actual_sig = _base64url_decode(signature_b64)

        if not hmac.compare_digest(actual_sig, expected_sig):
            return None

        payload_bytes = _base64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        # Check expiration
        exp = payload.get("exp")
        if exp is not None:
            now_ts = int(datetime.now(timezone.utc).timestamp())
            if now_ts > exp:
                return None  # Token expired

        return payload
    except Exception:
        return None
