"""App-wide paths for AWS Monitor (Windows installer friendly)."""
import os
from pathlib import Path


def app_data_dir() -> Path:
    # %APPDATA%/AWSMonitor  (falls back to ~/.aws_monitor)
    base = os.environ.get("APPDATA")
    if base:
        p = Path(base) / "AWSMonitor"
    else:
        p = Path.home() / ".aws_monitor"
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_file() -> Path:
    return app_data_dir() / "config.json"


def creds_file() -> Path:
    return app_data_dir() / "creds.enc"
