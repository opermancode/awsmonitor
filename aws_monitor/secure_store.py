"""Encrypted AWS credential storage. Key = PBKDF2(app_password)."""
import base64
import hashlib
import json
import os

from .config import config_file, creds_file

_ITERATIONS = 200_000


def _enc_salt() -> bytes:
    try:
        cfg = json.loads(config_file().read_text(encoding="utf-8"))
        return bytes.fromhex(cfg["enc_salt"])
    except Exception:
        # no password set yet -> ephemeral salt (callers should set password first)
        return b"aws-monitor-default-salt"


def _fernet(password: str):
    from cryptography.fernet import Fernet

    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), _enc_salt(), _ITERATIONS, dklen=32
    )
    return Fernet(base64.urlsafe_b64encode(dk))


def save_creds(app_password: str, access_key: str, secret_key: str) -> None:
    f = _fernet(app_password)
    payload = json.dumps({"access": access_key.strip(), "secret": secret_key.strip()})
    creds_file().write_bytes(f.encrypt(payload.encode("utf-8")))


def load_creds(app_password: str) -> tuple[str, str]:
    from cryptography.fernet import InvalidToken

    raw = creds_file().read_bytes()
    try:
        data = json.loads(_fernet(app_password).decrypt(raw).decode("utf-8"))
    except InvalidToken as e:
        raise ValueError("Incorrect app password.") from e
    return data.get("access", ""), data.get("secret", "")


def has_saved_creds() -> bool:
    try:
        return creds_file().exists() and creds_file().stat().st_size > 0
    except Exception:
        return False


def clear_creds() -> None:
    try:
        if creds_file().exists():
            os.remove(creds_file())
    except Exception:
        pass
