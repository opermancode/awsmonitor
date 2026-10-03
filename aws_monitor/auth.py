"""App-password handling (PBKDF2, stdlib only)."""
import hashlib
import json
import os
import secrets

from .config import config_file

_ITERATIONS = 200_000


def _load_cfg() -> dict:
    f = config_file()
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cfg(cfg: dict) -> None:
    config_file().write_text(json.dumps(cfg), encoding="utf-8")


def has_password() -> bool:
    return bool(_load_cfg().get("pw_hash"))


def _hash(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return dk.hex()


def set_password(new_password: str) -> None:
    if len(new_password) < 4:
        raise ValueError("Password must be at least 4 characters.")
    cfg = _load_cfg()
    salt = secrets.token_bytes(16)
    cfg["pw_salt"] = salt.hex()
    cfg["pw_hash"] = _hash(new_password, salt)
    # separate salt for credential encryption
    if "enc_salt" not in cfg:
        cfg["enc_salt"] = secrets.token_bytes(16).hex()
    _save_cfg(cfg)


def verify_password(password: str) -> bool:
    cfg = _load_cfg()
    try:
        salt = bytes.fromhex(cfg["pw_salt"])
        return secrets.compare_digest(_hash(password, salt), cfg["pw_hash"])
    except Exception:
        return False


def change_password(old_password: str, new_password: str) -> None:
    from . import secure_store

    if not verify_password(old_password):
        raise ValueError("Current password is incorrect.")
    if len(new_password) < 4:
        raise ValueError("New password must be at least 4 characters.")
    # re-encrypt saved creds under the new password so they stay readable
    creds = None
    try:
        creds = secure_store.load_creds(old_password)
    except Exception:
        creds = None
    set_password(new_password)
    if creds:
        secure_store.save_creds(new_password, creds[0], creds[1])
