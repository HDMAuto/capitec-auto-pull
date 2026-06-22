"""Load and validate config.yaml into a list of Branch records."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml


class ConfigError(Exception):
    """Raised when config.yaml is missing or malformed."""


@dataclass(frozen=True)
class Branch:
    branch_code: str
    username: str
    password: str


_REQUIRED = ("branch_code", "username", "password")


def load_branches(path: str | Path) -> list[Branch]:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    data = yaml.safe_load(path.read_text()) or {}
    raw = data.get("branches") or []
    if not raw:
        raise ConfigError("Config must define at least one branch")

    branches: list[Branch] = []
    for i, entry in enumerate(raw):
        entry = entry or {}
        for field in _REQUIRED:
            if not entry.get(field):
                raise ConfigError(
                    f"Branch #{i + 1} is missing required field: {field}"
                )
        branches.append(
            Branch(
                branch_code=str(entry["branch_code"]),
                username=str(entry["username"]),
                password=str(entry["password"]),
            )
        )
    return branches