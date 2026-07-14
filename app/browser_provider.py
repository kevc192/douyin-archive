"""Read publicly visible Douyin works through a user-managed Chrome session."""
from __future__ import annotations

import socket
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from playwright.sync_api import Error as PlaywrightError, sync_playwright

from .config import BROWSER_CDP_URL, PROFILE_SCROLL_ROUNDS


class BrowserSessionError(RuntimeError):
    pass


def _cdp_url() -> str:
    """Resolve Docker Desktop's host alias to IPv4 before Playwright's Node client sees it."""
    parsed = urlsplit(BROWSER_CDP_URL)
    if not parsed.hostname:
        return BROWSER_CDP_URL
    host = socket.gethostbyname(parsed.hostname)
    netloc = f"{host}:{parsed.port}" if parsed.port else host
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def browser_status() -> dict[str, Any]:
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(_cdp_url(), timeout=10_000)
            contexts = browser.contexts
            result = {"connected": True, "contexts": len(contexts), "pages": sum(len(context.pages) for context in contexts)}
            browser.close()
            return result
    except PlaywrightError as exc:
        return {"connected": False, "message": f"Chrome session unavailable: {exc}"}


def _safe_name(value: Any, fallback: str) -> str:
    text = str(value or fallback)
    return "".join("_" if char in '<>:"/\\|?*' else char for char in text).strip(". ")[:100] or fallback


def _walk_awemes(value: Any):
    if isinstance(value, dict):
        if value.get("aweme_id") and (value.get("video") or value.get("images")):
            yield value
            return
        for child in value.values():
            yield from _walk_awemes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_awemes(child)


def _first_url(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("url_list", "url_list_v2"):
            urls = value.get(key)
            if isinstance(urls, list) and urls:
                return str(urls[0])
        for child in value.values():
            found = _first_url(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _first_url(child)
            if found:
                return found
    return None


class BrowserProfileDownloader:
    """Downloads data already exposed to an interactive, user-authenticated Chrome page."""

    def __init__(self, root: Path):
        self.root = root
        self.archive_file = root / ".browser-archive.txt"

    def archive_profile(self, profile_url: str) -> int:
        self.root.mkdir(parents=True, exist_ok=True)
        works, cookies = self._collect_works(profile_url)
        if not works:
            raise BrowserSessionError("No accessible works were found. Open the profile in Chrome, sign in if required, then retry.")
        archived = self._read_archive()
        downloaded = 0
        for work in works:
            work_id = str(work.get("aweme_id"))
            if not work_id or work_id in archived:
                continue
            self._download_work(work, cookies)
            with self.archive_file.open("a", encoding="utf-8") as handle:
                handle.write(f"{work_id}\n")
            downloaded += 1
        return downloaded

    def _read_archive(self) -> set[str]:
        if not self.archive_file.exists():
            return set()
        return {line.strip() for line in self.archive_file.read_text(encoding="utf-8").splitlines() if line.strip()}

    def _collect_works(self, profile_url: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        works: dict[str, dict[str, Any]] = {}
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.connect_over_cdp(_cdp_url(), timeout=15_000)
                if not browser.contexts:
                    raise BrowserSessionError("Chrome has no browser context. Start Chrome normally with remote debugging enabled.")
                context = browser.contexts[0]

                def capture(response) -> None:
                    # Endpoint names change frequently. Inspect JSON from Douyin only,
                    # then keep exclusively objects that have a downloadable work shape.
                    if "douyin.com" not in response.url.lower():
                        return
                    content_type = response.headers.get("content-type", "").lower()
                    if "json" not in content_type:
                        return
                    try:
                        for work in _walk_awemes(response.json()):
                            works[str(work["aweme_id"])] = work
                    except Exception:
                        return

                page = context.new_page()
                page.on("response", capture)
                page.goto(profile_url, wait_until="domcontentloaded", timeout=60_000)
                page.wait_for_timeout(3_000)
                previous_height = 0
                for _ in range(PROFILE_SCROLL_ROUNDS):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(1_500)
                    height = page.evaluate("document.body.scrollHeight")
                    if height == previous_height:
                        break
                    previous_height = height
                cookies = context.cookies(["https://www.douyin.com"])
                page.close()
                browser.close()
        except PlaywrightError as exc:
            raise BrowserSessionError(f"Unable to connect to Chrome at {BROWSER_CDP_URL}: {exc}") from exc
        return list(works.values()), cookies

    def _download_work(self, work: dict[str, Any], cookies: list[dict[str, Any]]) -> None:
        author = _safe_name(work.get("author", {}).get("nickname"), "unknown-author")
        created_at = work.get("create_time")
        date = datetime.fromtimestamp(int(created_at)).strftime("%Y-%m-%d") if created_at else "unknown-date"
        title = _safe_name(work.get("desc"), str(work["aweme_id"]))
        headers = {
            "Cookie": "; ".join(f"{cookie['name']}={cookie['value']}" for cookie in cookies),
            "Referer": "https://www.douyin.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
        }
        image_urls = [_first_url(image) for image in work.get("images") or []]
        urls = [url for url in image_urls if url]
        category = "images" if urls else "videos"
        if not urls:
            urls = [_first_url(work.get("video", {}).get("play_addr"))]
        urls = [url for url in urls if url]
        if not urls:
            raise BrowserSessionError(f"Work {work['aweme_id']} did not expose a downloadable media URL.")
        target = self.root / author / category / date
        target.mkdir(parents=True, exist_ok=True)
        for index, url in enumerate(urls, start=1):
            extension = self._extension(url, "jpg" if category == "images" else "mp4")
            suffix = f"_{index}" if len(urls) > 1 else ""
            self._fetch(url, target / f"{title} [{work['aweme_id']}]{suffix}.{extension}", headers)

    @staticmethod
    def _extension(url: str, fallback: str) -> str:
        suffix = Path(urlparse(url).path).suffix.lstrip(".").lower()
        return suffix if suffix and len(suffix) <= 5 else fallback

    @staticmethod
    def _fetch(url: str, destination: Path, headers: dict[str, str]) -> None:
        if destination.exists() and destination.stat().st_size > 0:
            return
        temporary = destination.with_suffix(f"{destination.suffix}.part")
        temporary.unlink(missing_ok=True)
        request = Request(url, headers=headers)
        with urlopen(request, timeout=90) as response, temporary.open("wb") as handle:
            while chunk := response.read(1024 * 1024):
                handle.write(chunk)
        temporary.replace(destination)
