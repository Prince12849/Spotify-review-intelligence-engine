"""Scrape official Spotify Community discussions discovered via public search.

Spotify Community blocks direct access to its internal search endpoint for many
automated clients. This scraper avoids that endpoint completely. It discovers
official Community discussion URLs through public search engines, then visits
each Community page to extract discussion content.
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import pandas as pd
from bs4 import BeautifulSoup

from base_scraper import BaseScraper, ScrapingBlockedError


COMMUNITY_BASE_URL = "https://community.spotify.com"
COMMUNITY_DOMAIN = "community.spotify.com"
DUCKDUCKGO_HTML_URL = "https://duckduckgo.com/html/"
BING_SEARCH_URL = "https://www.bing.com/search"
OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "spotify_community_reviews.csv"

SEARCH_TERMS = (
    "Discover Weekly",
    "music discovery",
    "recommendations",
    "Daily Mix",
    "recommendation algorithm",
    "playlists",
    "new music",
    "recommended songs",
)

MAX_SEARCH_RESULTS_PER_QUERY = 50


class SpotifyCommunityScraper(BaseScraper):
    """Scraper for official Spotify Community pages found by public search."""

    def __init__(self) -> None:
        super().__init__(OUTPUT_PATH)
        self.discussions_extracted = 0
        self.fallback_records_by_url: dict[str, dict[str, str]] = {}

    def is_official_community_url(self, url: str) -> bool:
        """Return True only for official Spotify Community URLs."""
        parsed = urlparse(url)
        return parsed.netloc.lower().endswith(COMMUNITY_DOMAIN)

    def is_likely_discussion_url(self, url: str) -> bool:
        """Keep only Spotify Community URLs that look like discussion pages."""
        if not self.is_official_community_url(url):
            return False

        path = urlparse(url).path
        discussion_markers = ("/t5/", "/td-p/", "/m-p/", "/idi-p/", "/ba-p/")
        excluded_markers = (
            "/user/viewprofilepage",
            "/plugins/",
            "/login",
            "/register",
        )
        return any(marker in path for marker in discussion_markers) and not any(
            marker in path for marker in excluded_markers
        )

    def decode_search_redirect_url(self, url: str) -> str:
        """Decode public-search redirect links into direct target URLs."""
        parsed = urlparse(url)
        query_values = parse_qs(parsed.query)

        for parameter_name in ("uddg", "url", "u"):
            redirect_target = query_values.get(parameter_name, [""])[0]
            if redirect_target:
                return unquote(redirect_target)

        return url

    def extract_board_from_url(self, url: str) -> str:
        """Infer a board/category from Spotify Community URL segments."""
        path_parts = [part for part in urlparse(url).path.split("/") if part]
        if "t5" in path_parts:
            t5_index = path_parts.index("t5")
            if len(path_parts) > t5_index + 1:
                return self.clean_text(path_parts[t5_index + 1].replace("-", " "))
        return ""

    def extract_first_text(self, soup: BeautifulSoup, selectors: tuple[str, ...]) -> str:
        """Return cleaned text from the first selector with content."""
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = self.clean_text(element.get_text(" ", strip=True))
                if text:
                    return text
        return ""

    def extract_first_attr(
        self,
        soup: BeautifulSoup,
        selectors: tuple[tuple[str, str], ...],
    ) -> str:
        """Return a cleaned attribute from the first matching selector."""
        for selector, attribute_name in selectors:
            element = soup.select_one(selector)
            if element and element.get(attribute_name):
                return self.clean_text(element.get(attribute_name))
        return ""

    def make_record(
        self,
        *,
        title: str,
        body: str,
        url: str,
        date: str = "",
        board_category: str = "",
        author: str = "",
    ) -> dict[str, str] | None:
        """Create one cleaned discussion record."""
        normalized_url = self.normalize_url(url)
        if not normalized_url or not self.is_official_community_url(normalized_url):
            return None

        cleaned_title = self.clean_text(title)
        cleaned_body = self.clean_text(body)
        if not cleaned_title and not cleaned_body:
            return None

        return {
            "discussion_title": cleaned_title,
            "discussion_body": cleaned_body,
            "board_category": self.clean_text(board_category),
            "author": self.clean_text(author),
            "date": self.clean_text(date),
            "url": normalized_url,
        }

    def extract_duckduckgo_results(self, soup: BeautifulSoup) -> list[dict[str, str]]:
        """Extract official Community records from DuckDuckGo HTML results."""
        records: list[dict[str, str]] = []

        for result in soup.select(".result")[:MAX_SEARCH_RESULTS_PER_QUERY]:
            title_link = result.select_one(".result__a")
            snippet_element = result.select_one(".result__snippet")
            if not title_link:
                continue

            decoded_url = self.decode_search_redirect_url(title_link.get("href", ""))
            normalized_url = self.normalize_url(decoded_url)
            if not self.is_likely_discussion_url(normalized_url):
                continue

            record = self.make_record(
                title=title_link.get_text(" ", strip=True),
                body=snippet_element.get_text(" ", strip=True) if snippet_element else "",
                url=normalized_url,
                board_category=self.extract_board_from_url(normalized_url),
            )
            if record:
                records.append(record)

        return records

    def extract_bing_results(self, soup: BeautifulSoup) -> list[dict[str, str]]:
        """Extract official Community records from Bing HTML results."""
        records: list[dict[str, str]] = []

        for result in soup.select("li.b_algo")[:MAX_SEARCH_RESULTS_PER_QUERY]:
            title_link = result.select_one("h2 a[href]")
            snippet_element = result.select_one(".b_caption p")
            if not title_link:
                continue

            decoded_url = self.decode_search_redirect_url(title_link.get("href", ""))
            normalized_url = self.normalize_url(decoded_url)
            if not self.is_likely_discussion_url(normalized_url):
                continue

            record = self.make_record(
                title=title_link.get_text(" ", strip=True),
                body=snippet_element.get_text(" ", strip=True) if snippet_element else "",
                url=normalized_url,
                board_category=self.extract_board_from_url(normalized_url),
            )
            if record:
                records.append(record)

        return records

    def search_duckduckgo(self, query: str) -> list[dict[str, str]]:
        """Search DuckDuckGo for official Spotify Community records."""
        response = self.fetch(
            DUCKDUCKGO_HTML_URL,
            params={"q": query, "kl": "us-en"},
        )
        soup = BeautifulSoup(response.text, "html.parser")
        return self.extract_duckduckgo_results(soup)

    def search_bing(self, query: str) -> list[dict[str, str]]:
        """Search Bing for official Spotify Community records."""
        response = self.fetch(BING_SEARCH_URL, params={"q": query, "count": 50})
        soup = BeautifulSoup(response.text, "html.parser")
        return self.extract_bing_results(soup)

    def collect_links_from_public_search(self) -> list[str]:
        """Collect Spotify Community discussion URLs from public search engines."""
        links_by_url: dict[str, str] = {}

        for search_term in SEARCH_TERMS:
            query = f"site:{COMMUNITY_DOMAIN} {search_term}"
            self.logger.info("Public search query: %s", query)

            query_records: list[dict[str, str]] = []
            for engine_name, search_function in (
                ("DuckDuckGo", self.search_duckduckgo),
                ("Bing", self.search_bing),
            ):
                try:
                    query_records = search_function(query)
                except ScrapingBlockedError as exc:
                    self.logger.warning("%s blocked query '%s': %s", engine_name, query, exc)
                    continue
                except Exception as exc:
                    self.logger.warning(
                        "%s failed query '%s': %s: %s",
                        engine_name,
                        query,
                        type(exc).__name__,
                        exc,
                    )
                    continue

                self.logger.info(
                    "%s returned %s official Community links for '%s'",
                    engine_name,
                    len(query_records),
                    search_term,
                )

                if query_records:
                    break

            for record in query_records:
                normalized_url = self.normalize_url(record["url"])
                if normalized_url:
                    links_by_url[normalized_url] = normalized_url
                    self.fallback_records_by_url[normalized_url] = record

        return list(links_by_url.values())

    def parse_discussion_page(self, url: str) -> dict[str, str] | None:
        """Visit and parse one official Spotify Community discussion page."""
        try:
            response = self.fetch(url)
        except Exception as exc:
            self.logger.warning("Discussion page failed: %s (%s: %s)", url, type(exc).__name__, exc)
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        title = self.extract_first_text(
            soup,
            (
                "h1",
                ".lia-message-subject",
                ".lia-thread-topic-title",
                "[data-testid='post-title']",
                "title",
            ),
        )
        body = self.extract_first_text(
            soup,
            (
                ".lia-message-body-content",
                ".lia-message-body",
                ".lia-message-view-topic-message .lia-message-body-content",
                "[itemprop='text']",
                "article",
                "main",
            ),
        )
        date = self.extract_first_attr(
            soup,
            (
                ("time[datetime]", "datetime"),
                ("meta[property='article:published_time']", "content"),
                ("meta[itemprop='datePublished']", "content"),
            ),
        )
        if not date:
            date = self.extract_first_text(soup, (".local-date", ".lia-message-post-date", "time"))

        author = self.extract_first_text(
            soup,
            (
                ".lia-user-name-link",
                ".lia-user-name",
                "[itemprop='author']",
                ".UserName",
            ),
        )

        board_category = self.extract_first_text(
            soup,
            (
                ".lia-breadcrumb li:last-child a",
                ".lia-breadcrumb a:last-child",
                "[aria-label='Breadcrumb'] a:last-child",
            ),
        )
        if not board_category:
            board_category = self.extract_board_from_url(url)

        return self.make_record(
            title=title,
            body=body,
            date=date,
            url=url,
            board_category=board_category,
            author=author,
        )

    def collect(self) -> tuple[pd.DataFrame, int]:
        """Collect Spotify Community discussions and remove duplicate URLs."""
        records_by_url: dict[str, dict[str, str]] = {}
        discussion_links = self.collect_links_from_public_search()

        self.logger.info("Unique official Community links discovered: %s", len(discussion_links))

        for discussion_url in discussion_links:
            record = self.parse_discussion_page(discussion_url)
            if not record:
                record = self.fallback_records_by_url.get(self.normalize_url(discussion_url))
                if record:
                    self.logger.info(
                        "Using public-search fallback text for blocked page: %s",
                        discussion_url,
                    )
                else:
                    continue

            dedupe_key = self.normalize_url(record["url"])
            if dedupe_key and dedupe_key not in records_by_url:
                records_by_url[dedupe_key] = record
                self.discussions_extracted += 1

        dataframe = pd.DataFrame(
            records_by_url.values(),
            columns=[
                "discussion_title",
                "discussion_body",
                "board_category",
                "author",
                "date",
                "url",
            ],
        )
        cleaned_dataframe, duplicates_removed = self.remove_duplicate_urls(dataframe)
        return cleaned_dataframe, duplicates_removed

    def run(self) -> tuple[pd.DataFrame, int]:
        """Run the full Spotify Community scraping workflow."""
        dataframe, duplicates_removed = self.collect()
        self.save_dataframe(dataframe)
        return dataframe, duplicates_removed


def main() -> None:
    """Run the scraper and print a concise summary."""
    scraper = SpotifyCommunityScraper()

    try:
        dataframe, duplicates_removed = scraper.run()
        print(f"Pages visited: {scraper.pages_visited}")
        print(f"Discussions extracted: {scraper.discussions_extracted}")
        print(f"Duplicate discussions removed: {duplicates_removed}")
        print(f"Final records saved: {len(dataframe)}")
        print(f"Saved output to: {scraper.output_path}")
    except Exception as exc:
        print(f"Failed to scrape Spotify Community: {type(exc).__name__}: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
