"""Shared scraper utilities for the Spotify Review Intelligence Engine."""

from __future__ import annotations

import logging
import random
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from requests import Response
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36 SpotifyReviewEngine/1.0"
)


class ScrapingBlockedError(RuntimeError):
    """Raised when a website blocks or rate-limits a scraper request."""


class BaseScraper:
    """Reusable base class for HTTP scraping, cleaning, logging, and saving."""

    blocked_status_codes = {401, 403, 429, 503}

    def __init__(
        self,
        output_path: Path,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        request_delay_range: tuple[float, float] = (1.0, 2.0),
        request_timeout_seconds: int = 20,
    ) -> None:
        self.base_dir = Path(__file__).resolve().parent
        self.output_path = output_path
        self.request_delay_range = request_delay_range
        self.request_timeout_seconds = request_timeout_seconds
        self.pages_visited = 0
        self.logger = self._create_logger(self.__class__.__name__)
        self.session = self._create_session(user_agent)

    def _create_logger(self, logger_name: str) -> logging.Logger:
        """Create a consistent console logger for all scrapers."""
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            logger.addHandler(handler)

        return logger

    def _create_session(self, user_agent: str) -> requests.Session:
        """Create an HTTP session with retries for transient failures."""
        retry_strategy = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=1.5,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=("GET",),
            raise_on_status=False,
        )

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        session.mount("https://", HTTPAdapter(max_retries=retry_strategy))
        session.mount("http://", HTTPAdapter(max_retries=retry_strategy))
        return session

    def delay(self) -> None:
        """Sleep between requests to reduce load on public websites."""
        min_delay, max_delay = self.request_delay_range
        time.sleep(random.uniform(min_delay, max_delay))

    def fetch(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        count_page: bool = True,
    ) -> Response:
        """Fetch a URL with retries, blocking detection, and clear errors."""
        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self.request_timeout_seconds,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Request failed for {url}: {exc}") from exc

        if count_page:
            self.pages_visited += 1

        if response.status_code in self.blocked_status_codes:
            raise ScrapingBlockedError(
                f"HTTP {response.status_code} block or rate limit at {response.url}"
            )

        if self.looks_like_challenge_page(response.text):
            raise ScrapingBlockedError(
                f"JavaScript or anti-bot challenge detected at {response.url}"
            )

        response.raise_for_status()
        self.delay()
        return response

    @staticmethod
    def looks_like_challenge_page(html: str) -> bool:
        """Detect common anti-bot challenge pages."""
        lowered = html.lower()
        challenge_markers = (
            "enable javascript and cookies to continue",
            "cf_chl_opt",
            "challenge-platform",
            "just a moment...",
        )
        return any(marker in lowered for marker in challenge_markers)

    @staticmethod
    def clean_text(value: Any) -> str:
        """Remove tags/newlines/extra whitespace from extracted text."""
        if value is None:
            return ""
        return " ".join(str(value).replace("\n", " ").split()).strip()

    @staticmethod
    def normalize_url(url: str) -> str:
        """Normalize URLs so duplicate discussions collapse reliably."""
        value = BaseScraper.clean_text(url)
        if not value:
            return ""

        parsed = urlparse(value)
        normalized = parsed._replace(query="", fragment="").geturl()
        return normalized.rstrip("/")

    @staticmethod
    def absolute_url(base_url: str, href: str) -> str:
        """Convert a relative link into an absolute URL."""
        return urljoin(base_url, BaseScraper.clean_text(href))

    def save_dataframe(self, dataframe: pd.DataFrame) -> None:
        """Save a DataFrame to CSV, creating the data directory if needed."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        dataframe.to_csv(self.output_path, index=False, encoding="utf-8")

    def remove_duplicate_urls(self, dataframe: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        """Remove duplicate URL records and return the cleaned frame plus count."""
        if dataframe.empty or "url" not in dataframe.columns:
            return dataframe, 0

        before = len(dataframe)
        cleaned_dataframe = dataframe.copy()
        cleaned_dataframe["url"] = cleaned_dataframe["url"].map(self.normalize_url)
        cleaned_dataframe = cleaned_dataframe.drop_duplicates(
            subset=["url"],
            keep="first",
        ).reset_index(drop=True)
        return cleaned_dataframe, before - len(cleaned_dataframe)
