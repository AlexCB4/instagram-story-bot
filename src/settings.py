from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
CONFIG_DIR = REPO_ROOT / "config"
ASSETS_DIR = REPO_ROOT / "assets"
OWNED_ASSETS_DIR = ASSETS_DIR / "owned"
FONTS_DIR = REPO_ROOT / "fonts"
OUTPUT_DIR = REPO_ROOT / "output"
DEFAULT_FONT_PATH = FONTS_DIR / "Roboto-Bold.ttf"
WEEKLY_PLAN_PATH = CONFIG_DIR / "weekly_plan.yaml"


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value
