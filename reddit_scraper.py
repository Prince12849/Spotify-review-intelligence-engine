"""Scrape public Reddit discussion pages about Spotify discovery.

This script does not use the Reddit API and does not require credentials. It
tries public Reddit search endpoints first, then falls back to public web search
results if direct Reddit scraping is blocked.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import pandas as pd
from bs4 import BeautifulSoup

from base_scraper import BaseScraper, ScrapingBlockedError


OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "reddit_reviews.csv"

SEARCH_TERMS = (
    "Spotify recommendations",
    "Discover Weekly",
    "music discovery",
    "repetitive recommendations",
    "Daily Mix",
)

REDDIT_SEARCH_JSON_URL = "https://www.reddit.com/search.json"
OLD_REDDIT_SEARCH_URL = "https://old.reddit.com/search/"
DUCKDUCKGO_HTML_URL = "https://duckduckgo.com/html/"
REDDIT_BASE_URL = "https://www.reddit.com"

REDDIT_JSON_LIMIT = 100
OLD_REDDIT_LIMIT = 100
WEB_SEARCH_LIMIT = 100
DELETED_MARKERS = {"[deleted]", "[removed]"}


class RedditScraper(BaseScraper):
    """No-auth public scraper for Reddit discussion search results."""

    def __init__(self) -> None:
        super().__init__(OUTPUT_PATH)

    def is_usable_text(self, value: str) -> bool:
        """Return whether text is meaningful and not a deleted Reddit marker."""
        text = self.clean_text(value)
        return bool(text) and text.lower() not in DELETED_MARKERS

    def timestamp_to_iso(self, timestamp: Any) -> str:
        """Convert a Unix timestamp to an ISO-8601 UTC datetime string."""
        if timestamp in (None, ""):
            return ""
        try:
            return datetime.fromtimestamp(float(timestamp), tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OSError):
            return ""

    def make_record(
        self,
        title: str,
        body: str,
        url: str,
        date: str = "",
    ) -> dict[str, str] | None:
        """Build one normalized record, skipping empty or deleted results."""
        cleaned_title = self.clean_text(title)
        cleaned_body = self.clean_text(body)
        cleaned_url = self.normalize_url(url)

        if not cleaned_url:
            return None
        if not self.is_usable_text(cleaned_title) and not self.is_usable_text(cleaned_body):
            return None

        return {
            "title": cleaned_title,
            "body": cleaned_body,
            "url": cleaned_url,
            "date": self.clean_text(date),
        }

    def search_reddit_json(self, search_term: str) -> list[dict[str, str]]:
        """Search Reddit's public JSON results without authentication."""
        response = self.fetch(
            REDDIT_SEARCH_JSON_URL,
            params={
                "q": search_term,
                "sort": "relevance",
                "t": "all",
                "limit": REDDIT_JSON_LIMIT,
                "type": "link",
                "raw_json": 1,
            },
        )

        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Reddit JSON response could not be decoded: {exc}") from exc

        records: list[dict[str, str]] = []
        for child in payload.get("data", {}).get("children", []):
            post = child.get("data", {})
            record = self.make_record(
                title=post.get("title", ""),
                body=post.get("selftext", ""),
                url=self.absolute_url(REDDIT_BASE_URL, post.get("permalink", "")),
                date=self.timestamp_to_iso(post.get("created_utc")),
            )
            if record:
                records.append(record)

        return records

    def search_old_reddit_html(self, search_term: str) -> list[dict[str, str]]:
        """Search old.reddit.com HTML pages as a direct scraping fallback."""
        response = self.fetch(
            OLD_REDDIT_SEARCH_URL,
            params={
                "q": search_term,
                "sort": "relevance",
                "t": "all",
                "limit": OLD_REDDIT_LIMIT,
            },
        )
        soup = BeautifulSoup(response.text, "html.parser")

        records: list[dict[str, str]] = []
        for post in soup.select("div.thing"):
            title_element = post.select_one("a.title")
            comments_element = post.select_one("a.comments")
            time_element = post.select_one("time")
            body_element = post.select_one(".expando .usertext-body")

            comments_url = comments_element.get("href", "") if comments_element else ""
            record = self.make_record(
                title=title_element.get_text(" ", strip=True) if title_element else "",
                body=body_element.get_text(" ", strip=True) if body_element else "",
                url=self.absolute_url(REDDIT_BASE_URL, comments_url),
                date=time_element.get("datetime", "") if time_element else "",
            )
            if record:
                records.append(record)

        return records

    def decode_duckduckgo_url(self, url: str) -> str:
        """Decode DuckDuckGo redirect links into their target URLs."""
        parsed = urlparse(url)
        query_values = parse_qs(parsed.query)
        redirect_target = query_values.get("uddg", [""])[0]
        return unquote(redirect_target) if redirect_target else url

    def search_public_web(self, search_term: str) -> list[dict[str, str]]:
        """Use public web search when Reddit direct scraping is unavailable."""
        response = self.fetch(
            DUCKDUCKGO_HTML_URL,
            params={"q": f"site:reddit.com {search_term}", "kl": "us-en"},
        )
        soup = BeautifulSoup(response.text, "html.parser")

        records: list[dict[str, str]] = []
        for result in soup.select(".result")[:WEB_SEARCH_LIMIT]:
            title_element = result.select_one(".result__a")
            snippet_element = result.select_one(".result__snippet")

            if not title_element:
                continue

            result_url = self.decode_duckduckgo_url(title_element.get("href", ""))
            if "reddit.com" not in result_url.lower():
                continue

            record = self.make_record(
                title=title_element.get_text(" ", strip=True),
                body=snippet_element.get_text(" ", strip=True) if snippet_element else "",
                url=result_url,
                date="",
            )
            if record:
                records.append(record)

        return records

    def collect(self) -> tuple[pd.DataFrame, int]:
        """Collect Reddit records through public, no-auth search strategies."""
        records_by_url: dict[str, dict[str, str]] = {}

        search_strategies = (
            ("reddit_json", self.search_reddit_json),
            ("old_reddit_html", self.search_old_reddit_html),
            ("public_web_search", self.search_public_web),
        )

        for search_term in SEARCH_TERMS:
            self.logger.info("Searching for: %s", search_term)

            for strategy_name, strategy in search_strategies:
                try:
                    records = strategy(search_term)
                except ScrapingBlockedError as exc:
                    self.logger.warning("%s blocked for '%s': %s", strategy_name, search_term, exc)
                    continue
                except Exception as exc:
                    self.logger.warning(
                        "%s failed for '%s': %s: %s",
                        strategy_name,
                        search_term,
                        type(exc).__name__,
                        exc,
                    )
                    continue

                for record in records:
                    dedupe_key = self.normalize_url(record["url"])
                    if dedupe_key and dedupe_key not in records_by_url:
                        records_by_url[dedupe_key] = record

                self.logger.info(
                    "%s found %s records for '%s'. Unique total: %s",
                    strategy_name,
                    len(records),
                    search_term,
                    len(records_by_url),
                )

                if records:
                    break

        dataframe = pd.DataFrame(records_by_url.values(), columns=["title", "body", "url", "date"])
        cleaned_dataframe, duplicates_removed = self.remove_duplicate_urls(dataframe)
        return cleaned_dataframe, duplicates_removed

    def run(self) -> tuple[pd.DataFrame, int]:
        """Run the no-auth Reddit scraping workflow."""
        dataframe, duplicates_removed = self.collect()
        self.save_dataframe(dataframe)
        return dataframe, duplicates_removed


def main() -> None:
    """Run the Reddit scraper and print a concise summary."""
    scraper = RedditScraper()

    try:
        dataframe, duplicates_removed = scraper.run()
        print(f"Pages visited: {scraper.pages_visited}")
        print(f"Duplicate discussions removed: {duplicates_removed}")
        print(f"Total unique records saved: {len(dataframe)}")
        print(f"Saved output to: {scraper.output_path}")

        if dataframe.empty:
            print(
                "No records were saved. Public Reddit pages and fallback public "
                "search may be blocking automated requests from this network."
            )
    except Exception as exc:
        print(f"Failed to scrape Reddit discussions: {type(exc).__name__}: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
