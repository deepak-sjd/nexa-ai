"""
Password hashing, access tokens and Google sign-in verification.

No extra packages: scrypt and HMAC come from the standard library, and
`google-auth` is already installed as a dependency of `google-genai`.
"""

import base64
import hashlib
import hmac
import json
import os
import time

from app.core.config import settings

# ------------------------------------------------------------
# PASSWORDS (scrypt)
# ------------------------------------------------------------

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    salt = os.urandom(16)

    digest = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=32,
    )

    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64e(salt)}${_b64e(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False

    try:
        scheme, n, r, p, salt, expected = stored.split("$")

        if scheme != "scrypt":
            return False

        digest = hashlib.scrypt(
            password.encode(),
            salt=_b64d(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=32,
        )

        return hmac.compare_digest(digest, _b64d(expected))
    except Exception:
        return False


# ------------------------------------------------------------
# ACCESS TOKENS (HS256 JWT)
# ------------------------------------------------------------

def _sign(signing_input: str) -> str:
    return _b64e(
        hmac.new(
            settings.jwt_secret.encode(),
            signing_input.encode(),
            hashlib.sha256,
        ).digest()
    )


def create_access_token(user_id: int) -> str:
    now = int(time.time())

    header = {"alg": "HS256", "typ": "JWT"}

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + settings.jwt_expire_minutes * 60,
    }

    signing_input = ".".join(
        _b64e(json.dumps(part, separators=(",", ":")).encode())
        for part in (header, payload)
    )

    return f"{signing_input}.{_sign(signing_input)}"


def decode_access_token(token: str) -> int | None:
    """Returns the user id, or None if the token is invalid/expired."""
    try:
        header_b64, payload_b64, signature = token.split(".")

        if json.loads(_b64d(header_b64)).get("alg") != "HS256":
            return None

        if not hmac.compare_digest(
            _sign(f"{header_b64}.{payload_b64}"), signature
        ):
            return None

        payload = json.loads(_b64d(payload_b64))

        if int(payload["exp"]) < time.time():
            return None

        return int(payload["sub"])
    except Exception:
        return None


# ------------------------------------------------------------
# GOOGLE SIGN-IN
# ------------------------------------------------------------

def verify_google_credential(credential: str) -> dict:
    """Validates a Google ID token. Raises ValueError if it's not valid."""
    if not settings.google_client_id:
        raise ValueError("Google sign-in is not configured.")

    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    info = id_token.verify_oauth2_token(
        credential,
        google_requests.Request(),
        settings.google_client_id,
    )

    if not info.get("email") or not info.get("email_verified"):
        raise ValueError("Google account email is not verified.")

    return info