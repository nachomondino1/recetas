"""Enriquecimiento puntual: bajar una foto de portada desde la fuente enlazada.

Para recetas sin `foto` en el frontmatter pero con `fuente` (o un link en el
cuerpo) a YouTube o a una página con `og:image`, descarga esa imagen a
`images/<id>/cover.jpg` e imprime el valor a escribir a mano en el frontmatter
(este script no edita los .md — el merge curado lo hace Claude, ver
DATA_FLOW_PLAYBOOK Arquetipo C).

Uso: .venv/bin/python -m src.fetch_covers
"""

from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

from src import config

UA = "Mozilla/5.0 (compatible; recetas-cover-fetcher/1.0)"
YOUTUBE_RE = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{6,})")
OG_IMAGE_RE = re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE)
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?(.*)", re.DOTALL)

YOUTUBE_THUMB_VARIANTS = ["maxresdefault", "sddefault", "hqdefault"]


def _fetch(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 200:
                return None
            return resp.read()
    except Exception:
        return None


def _fetch_text(url: str) -> str | None:
    data = _fetch(url)
    if data is None:
        return None
    return data.decode("utf-8", errors="replace")


def youtube_thumbnail(video_id: str) -> bytes | None:
    for variant in YOUTUBE_THUMB_VARIANTS:
        data = _fetch(f"https://img.youtube.com/vi/{video_id}/{variant}.jpg")
        if data and len(data) > 2000:
            return data
    return None


def og_image(page_url: str) -> bytes | None:
    html = _fetch_text(page_url)
    if not html:
        return None
    match = OG_IMAGE_RE.search(html)
    if not match:
        return None
    return _fetch(match.group(1))


def find_source_urls(front: dict, body: str) -> list[str]:
    urls = []
    fuente = front.get("fuente")
    if isinstance(fuente, str) and fuente.startswith("http"):
        urls.append(fuente)
    urls.extend(re.findall(r"https?://\S+", body))
    seen, out = set(), []
    for u in urls:
        u = u.rstrip(").,")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def cover_for_recipe(rid: str, front: dict, body: str) -> bytes | None:
    urls = find_source_urls(front, body)
    for url in urls:
        yt_match = YOUTUBE_RE.search(url)
        if yt_match:
            data = youtube_thumbnail(yt_match.group(1))
            if data:
                return data
    for url in urls:
        if YOUTUBE_RE.search(url):
            continue
        data = og_image(url)
        if data:
            return data
    return None


def main() -> int:
    import yaml

    recipes_dir = config.RECIPES_DIR
    images_dir = config.IMAGES_DIR
    results = []
    for path in sorted(recipes_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        match = FRONTMATTER_RE.match(text)
        if not match:
            continue
        front_raw, body = match.groups()
        front = yaml.safe_load(front_raw) or {}
        rid = path.stem
        if front.get("foto"):
            continue
        data = cover_for_recipe(rid, front, body)
        if data is None:
            results.append((rid, None))
            continue
        dest = images_dir / rid / "cover.jpg"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        results.append((rid, f"{rid}/cover.jpg"))

    for rid, foto in results:
        if foto:
            print(f"OK   {rid}: images/{foto} ({(images_dir / foto).stat().st_size} bytes)")
        else:
            print(f"MISS {rid}: no se encontró imagen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
