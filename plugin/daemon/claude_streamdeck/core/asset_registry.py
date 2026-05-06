"""Asset storage with static-dir loading, dynamic uploads, and resize cache."""

from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)


class AssetNotFoundError(Exception):
    pass


class AssetTooLargeError(Exception):
    pass


class InvalidAssetDataError(Exception):
    pass


@dataclass
class Asset:
    """A loaded asset, either single-frame or animated."""
    name: str
    frames: list[Image.Image]
    frame_durations_ms: list[int]
    size_bytes: int

    @property
    def animated(self) -> bool:
        return len(self.frames) > 1

    @property
    def frame_count(self) -> int:
        return len(self.frames)


class AssetRegistry:
    """Stores assets by name; provides resized variants from a cache."""

    def __init__(
        self,
        static_dir: Optional[Path],
        max_size_bytes: int = 5 * 1024 * 1024,
    ) -> None:
        self._assets: dict[str, Asset] = {}
        self._resize_cache: dict[tuple[str, tuple[int, int], int], Image.Image] = {}
        self._max_size = max_size_bytes
        if static_dir is not None and static_dir.is_dir():
            self._load_static(static_dir)

    def _load_static(self, dir_path: Path) -> None:
        for f in sorted(dir_path.iterdir()):
            if not f.is_file():
                continue
            if f.suffix.lower() not in (".png", ".jpg", ".jpeg", ".gif"):
                continue
            try:
                data = f.read_bytes()
                asset = self._build_asset(f.stem, data)
                self._assets[asset.name] = asset
                logger.info("Loaded static asset: %s", asset.name)
            except Exception:
                logger.exception("Failed to load static asset %s", f)

    def upload(self, name: str, data_b64: str) -> Asset:
        try:
            raw = base64.b64decode(data_b64, validate=True)
        except Exception as e:
            raise InvalidAssetDataError(f"base64 decode failed: {e}") from e
        if len(raw) > self._max_size:
            raise AssetTooLargeError(f"{len(raw)} > {self._max_size}")
        asset = self._build_asset(name, raw)
        # Invalidate any previously cached resizes for this name.
        self._invalidate_resize_cache(name)
        self._assets[name] = asset
        return asset

    def _build_asset(self, name: str, raw: bytes) -> Asset:
        try:
            img = Image.open(io.BytesIO(raw))
            img.load()
        except (UnidentifiedImageError, OSError) as e:
            raise InvalidAssetDataError(f"image decode failed: {e}") from e

        frames: list[Image.Image] = []
        durations: list[int] = []
        try:
            n_frames = getattr(img, "n_frames", 1)
        except Exception:
            n_frames = 1

        for i in range(n_frames):
            img.seek(i)
            frame = img.convert("RGB")
            frames.append(frame.copy())
            duration = img.info.get("duration", 100)
            durations.append(int(duration) if duration else 100)

        return Asset(
            name=name,
            frames=frames,
            frame_durations_ms=durations,
            size_bytes=len(raw),
        )

    def get(self, name: str) -> Asset:
        asset = self._assets.get(name)
        if asset is None:
            raise AssetNotFoundError(name)
        return asset

    def remove(self, name: str) -> None:
        if name in self._assets:
            del self._assets[name]
            self._invalidate_resize_cache(name)

    def list(self) -> list[dict]:
        return [
            {"name": a.name, "animated": a.animated, "size_bytes": a.size_bytes}
            for a in self._assets.values()
        ]

    def get_resized(self, name: str, target_size: tuple[int, int]) -> Image.Image:
        return self.get_resized_frames(name, target_size)[0]

    def get_resized_frames(
        self, name: str, target_size: tuple[int, int]
    ) -> list[Image.Image]:
        asset = self.get(name)
        out: list[Image.Image] = []
        for idx, frame in enumerate(asset.frames):
            key = (name, target_size, idx)
            cached = self._resize_cache.get(key)
            if cached is None:
                cached = frame.resize(target_size, Image.Resampling.LANCZOS)
                self._resize_cache[key] = cached
            out.append(cached)
        return out

    def _invalidate_resize_cache(self, name: str) -> None:
        keys = [k for k in self._resize_cache if k[0] == name]
        for k in keys:
            del self._resize_cache[k]
