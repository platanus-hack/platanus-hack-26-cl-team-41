"""Loads config.toml into a plain dict with defaults filled in."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config.toml"


def load(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path else DEFAULT_PATH
    with p.open("rb") as f:
        cfg = tomllib.load(f)
    cfg["_dir"] = str(p.resolve().parent)
    return cfg
