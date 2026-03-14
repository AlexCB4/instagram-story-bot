from __future__ import annotations

from pathlib import Path

import requests


def search_image(api_key: str, query: str, orientation: str = "portrait") -> dict[str, str]:
    response = requests.get(
        "https://api.pexels.com/v1/search",
        headers={"Authorization": api_key},
        params={"query": query, "orientation": orientation, "per_page": 10},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    photos = payload.get("photos", [])
    if not photos:
        raise RuntimeError(f"No Pexels images found for query: {query}")
    photo = photos[0]
    return {
        "url": photo["src"].get("large2x") or photo["src"]["original"],
        "photographer": photo.get("photographer", "Unknown"),
        "attribution": f"Photo by {photo.get('photographer', 'Unknown')} on Pexels",
    }


def download_image(url: str, output_path: str | Path) -> Path:
    destination = Path(output_path)
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    destination.write_bytes(response.content)
    return destination
