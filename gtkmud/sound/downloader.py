"""Async sound file downloader with caching."""

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None

logger = logging.getLogger(__name__)


class SoundDownloader:
    """Downloads and caches remote sound files.

    Sound files are cached in the XDG cache directory to avoid
    re-downloading on subsequent sessions.
    """

    def __init__(self, cache_dir: Path):
        """Initialize the downloader.

        Args:
            cache_dir: Directory for caching downloaded files.
        """
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._downloading: set[str] = set()  # Track URLs being downloaded

    async def close(self):
        """Close resources (no-op, sessions are per-request now)."""
        pass

    def get_cache_path(self, url: str, filename: str) -> Path:
        """Get the local cache path for a remote file.

        Uses a hash of the URL to create a unique cache entry.

        Args:
            url: Base URL of the sound server.
            filename: Filename/path from the MSP trigger.

        Returns:
            Path to the cached file location.
        """
        # Create a hash of the full URL for cache key
        full_url = f"{url.rstrip('/')}/{filename}"
        url_hash = hashlib.sha256(full_url.encode()).hexdigest()[:16]

        # Preserve file extension
        ext = Path(filename).suffix or ".wav"
        cache_filename = f"{url_hash}{ext}"

        return self._cache_dir / cache_filename

    def is_cached(self, url: str, filename: str) -> bool:
        """Check if a file is already cached.

        Args:
            url: Base URL of the sound server.
            filename: Filename from MSP trigger.

        Returns:
            True if file exists in cache.
        """
        return self.get_cache_path(url, filename).exists()

    async def get_sound(self, url: str, filename: str) -> Optional[Path]:
        """Get a sound file, downloading if necessary.

        Args:
            url: Base URL of the sound server.
            filename: Filename from MSP trigger.

        Returns:
            Path to the local file, or None if download failed.
        """
        cache_path = self.get_cache_path(url, filename)

        # Return cached file if it exists
        if cache_path.exists():
            logger.debug(f"Using cached sound: {cache_path}")
            return cache_path

        # Check if already downloading (simple guard, not perfect but avoids duplicates)
        full_url = f"{url.rstrip('/')}/{filename}"
        if full_url in self._downloading:
            # Wait a bit and check if file appeared
            for _ in range(50):  # Wait up to 5 seconds
                await asyncio.sleep(0.1)
                if cache_path.exists():
                    return cache_path
            return None

        # Mark as downloading
        self._downloading.add(full_url)

        try:
            await self._download(full_url, cache_path)
            if cache_path.exists():
                return cache_path
        except Exception as e:
            logger.error(f"Failed to download sound: {e}")
        finally:
            self._downloading.discard(full_url)

        return None

    async def _download(self, url: str, dest: Path) -> None:
        """Download a file.

        Args:
            url: Full URL to download.
            dest: Destination path.
        """
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not installed, cannot download sounds")
            return

        logger.info(f"Downloading sound: {url}")

        try:
            # Create a fresh session for this download to avoid event loop issues
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"Download failed: HTTP {response.status}")
                        return

                    # Check content type
                    content_type = response.headers.get("Content-Type", "")
                    if not any(t in content_type.lower() for t in
                              ["audio", "octet-stream", "application/x-"]):
                        logger.warning(f"Unexpected content type: {content_type}")

                    # Download to temp file first
                    temp_path = dest.with_suffix(".tmp")
                    with open(temp_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)

                    # Move to final location
                    temp_path.rename(dest)
                    logger.info(f"Downloaded sound to: {dest}")

        except aiohttp.ClientError as e:
            logger.error(f"Download error: {e}")
        except IOError as e:
            logger.error(f"File error: {e}")

    def clear_cache(self):
        """Clear all cached sound files."""
        for file in self._cache_dir.iterdir():
            if file.is_file():
                try:
                    file.unlink()
                except OSError:
                    pass
        logger.info("Sound cache cleared")

    def get_cache_size(self) -> int:
        """Get total size of cached files in bytes."""
        return sum(
            f.stat().st_size for f in self._cache_dir.iterdir()
            if f.is_file()
        )
