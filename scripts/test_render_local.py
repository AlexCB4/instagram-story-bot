from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.render import create_story
from src.settings import DEFAULT_FONT_PATH, OUTPUT_DIR, OWNED_ASSETS_DIR

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def pick_background(explicit_path: str | None) -> Path:
    if explicit_path:
        path = Path(explicit_path)
        if not path.exists():
            raise FileNotFoundError(f"Background image not found: {path}")
        return path

    candidates = [p for p in OWNED_ASSETS_DIR.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES]
    if not candidates:
        raise RuntimeError(f"No image files found in: {OWNED_ASSETS_DIR}")
    return random.choice(candidates)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate local preview stories (top and bottom text variants).")
    parser.add_argument("--background", help="Path to background image. If omitted, picks random image from assets/owned.")
    parser.add_argument("--title", default="Feliz domingo!", help="Title text for preview.")
    parser.add_argument("--subtitle", default="Tómate un momento para recargar energía para la semana.", help="Subtitle text for preview.")
    parser.add_argument("--brand", default="@parterre_c", help="Brand text for preview.")
    parser.add_argument("--seed", type=int, help="Optional random seed for deterministic color/image choice.")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    background = pick_background(args.background)
    output_dir = OUTPUT_DIR / "local_test"
    output_dir.mkdir(parents=True, exist_ok=True)

    top_path = output_dir / "preview_top.png"
    bottom_path = output_dir / "preview_bottom.png"

    create_story(
        background_path=background,
        output_path=top_path,
        title_text=args.title,
        subtitle_text=args.subtitle,
        brand_text=args.brand,
        font_path=DEFAULT_FONT_PATH,
        text_position="top",
    )

    create_story(
        background_path=background,
        output_path=bottom_path,
        title_text=args.title,
        subtitle_text=args.subtitle,
        brand_text=args.brand,
        font_path=DEFAULT_FONT_PATH,
        text_position="bottom",
    )

    print(f"Background: {background}")
    print(f"Top variant: {top_path}")
    print(f"Bottom variant: {bottom_path}")


if __name__ == "__main__":
    main()
