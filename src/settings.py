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
WEEKLY_PLAN_PATH = CONFIG_DIR / "weekly_plan.yaml"

# Liberation Serif Bold is a free Times New Roman equivalent.
# Try system path (GitHub Actions ubuntu), then local fonts/ folder.
_SERIF_CANDIDATES = [
    Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"),
    FONTS_DIR / "LiberationSerif-Bold.ttf",
    FONTS_DIR / "Roboto-Bold.ttf",  # fallback if neither serif variant exists
]
DEFAULT_FONT_PATH: Path = next(
    (p for p in _SERIF_CANDIDATES if p.exists()),
    _SERIF_CANDIDATES[-1],
)


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value
