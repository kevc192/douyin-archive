"""The provider adapter; keep site-specific behavior isolated in this module."""
import logging
from pathlib import Path
from typing import Any

import yt_dlp

from .browser_provider import BrowserProfileDownloader
from .config import ALLOW_AGE_RESTRICTED, DOWNLOAD_ROOT

logger = logging.getLogger(__name__)


def _clean(value: Any, fallback: str) -> str:
    text = str(value or fallback)
    return "".join("_" if c in '<>:"/\\|?*' else c for c in text).strip(". ")[:100] or fallback


def _media_kind(info: dict[str, Any]) -> str:
    # Douyin note posts expose an ``images`` list; videos do not.
    if info.get("images"):
        return "images"
    return "videos"


class ArchiveDownloader:
    def __init__(self, root: Path = DOWNLOAD_ROOT):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def archive_profile(self, profile_url: str) -> int:
        """Archive all currently accessible Douyin profile entries, skipping known IDs."""
        if "/user/" in profile_url:
            return BrowserProfileDownloader(self.root).archive_profile(profile_url)
        probe_options = {
            "extract_flat": "discard_in_playlist",
            "quiet": True,
            "ignoreerrors": False,
            "noplaylist": False,
        }
        with yt_dlp.YoutubeDL(probe_options) as ydl:
            page = ydl.extract_info(profile_url, download=False)
        if not page:
            raise yt_dlp.utils.DownloadError("No accessible works were found for this Douyin profile.")
        entries = page.get("entries", []) if page else []
        count = 0
        for entry in entries:
            if not entry:
                continue
            if self._archive_entry(entry.get("webpage_url") or entry.get("url")):
                count += 1
        return count

    def _archive_entry(self, url: str | None) -> bool:
        if not url:
            return False
        options = {
            "quiet": True,
            "ignoreerrors": False,
            "no_warnings": True,
            "restrictfilenames": True,
            "windowsfilenames": True,
            "noplaylist": True,
            "overwrites": False,
            "download_archive": str(self.root / ".archive.txt"),
            "age_limit": 18 if ALLOW_AGE_RESTRICTED else 0,
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return False
            author = _clean(info.get("uploader") or info.get("channel"), "unknown-author")
            date = str(info.get("upload_date") or "unknown-date")
            date = f"{date[:4]}-{date[4:6]}-{date[6:8]}" if len(date) == 8 else _clean(date, "unknown-date")
            kind = _media_kind(info)
            title = _clean(info.get("title"), info.get("id", "untitled"))
            target = self.root / author / kind / date
            target.mkdir(parents=True, exist_ok=True)
            options["outtmpl"] = str(target / f"{title} [{info.get('id', 'unknown')}].%(ext)s")
            with yt_dlp.YoutubeDL(options) as download_ydl:
                download_ydl.download([url])
        return True
