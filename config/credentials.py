from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(os.environ.get("RUNTIME_CONFIG_DIR", str(Path.home() / ".autonomous_runtime")))
CREDENTIALS_PATH = CONFIG_DIR / "credentials.json"


def _ensure_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_credentials() -> dict[str, Any]:
    """Returns the saved config, e.g. {"provider": "openrouter", "model": "...",
    "openrouter_api_key": "sk-or-...", ...}. Empty dict if nothing saved yet."""
    if not CREDENTIALS_PATH.exists():
        return {}
    try:
        return json.loads(CREDENTIALS_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_connection(provider: str, api_key: str, model: str | None = None, base_url: str | None = None) -> None:
    """Persist a provider connection to disk, chmod 600 (owner read/write only)."""
    _ensure_dir()
    data = load_credentials()
    data["provider"] = provider
    data[f"{provider}_api_key"] = api_key
    if model:
        data["model"] = model
    if base_url:
        data[f"{provider}_base_url"] = base_url
    CREDENTIALS_PATH.write_text(json.dumps(data, indent=2))
    os.chmod(CREDENTIALS_PATH, stat.S_IRUSR | stat.S_IWUSR)  # 600


def clear_connection() -> None:
    if CREDENTIALS_PATH.exists():
        CREDENTIALS_PATH.unlink()


def current_connection_summary() -> str:
    data = load_credentials()
    if not data or "provider" not in data:
        return "No provider connected yet. Use /connect <provider> <api_key> to set one up."
    provider = data["provider"]
    key = data.get(f"{provider}_api_key", "")
    masked = (key[:6] + "..." + key[-4:]) if len(key) > 12 else "***"
    model = data.get("model", "(default)")
    return f"Connected: provider={provider} model={model} key={masked}"
