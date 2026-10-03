"""Self-update via GitHub Releases (stdlib only, no new dependencies).

Flow: Settings -> Check for updates  (plus a quiet check at startup).
If the latest tag on GitHub is newer than the bundled __version__,
the app downloads the Setup-AWSMonitor-*.exe asset and launches it.
"""
import json
import urllib.request

REPO = "opermancode/awsmonitor"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
TIMEOUT = 12


def get_current_version() -> str:
    from . import __version__

    return __version__


def _norm(v: str) -> tuple:
    v = v.strip().lstrip("vV")
    parts = []
    for p in v.split("."):
        num = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(num) if num else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer(current: str, latest: str) -> bool:
    try:
        return _norm(latest) > _norm(current)
    except Exception:
        return False


def fetch_latest() -> dict:
    """Return {tag, name, notes, assets:[{name, url}]}. Raises RuntimeError."""
    try:
        req = urllib.request.Request(
            API_LATEST, headers={"User-Agent": "AWSMonitor-Updater"}
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"Could not reach GitHub releases: {e}")
    assets = [
        {"name": a.get("name", ""), "url": a.get("browser_download_url", "")}
        for a in data.get("assets", [])
        if a.get("browser_download_url")
    ]
    return {
        "tag": data.get("tag_name", ""),
        "name": data.get("name", ""),
        "notes": data.get("body", "") or "",
        "assets": assets,
    }


def pick_installer(assets: list) -> dict | None:
    """Prefer the Setup installer; fall back to the portable exe."""
    exes = [a for a in assets if a["name"].lower().endswith(".exe")]
    if not exes:
        return None
    for a in exes:
        if a["name"].lower().startswith("setup-awsmonitor"):
            return a
    for a in exes:
        if a["name"].lower() == "awsmonitor.exe":
            return a
    return exes[0]


def download(url: str, dest: str, progress=None) -> str:
    """Download a file. progress(downloaded_bytes, total_bytes)."""
    import urllib.request as _u

    def hook(blocks, block_size, total):
        if progress:
            try:
                progress(blocks * block_size, total if total and total > 0 else 0)
            except Exception:
                pass

    opener = _u.build_opener()
    opener.addheaders = [("User-Agent", "AWSMonitor-Updater")]
    _u.install_opener(opener)
    _u.urlretrieve(url, dest, reporthook=hook if progress else None)
    return dest
