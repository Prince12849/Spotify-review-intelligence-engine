"""Download recent Spotify iOS reviews from the Apple App Store.

This scraper does not depend on the third-party ``app-store-scraper`` package,
which frequently breaks when Apple changes its internal endpoints. Instead it
uses Apple's public RSS "customer reviews" JSON feed directly. This feed is
unauthenticated, does not require an API key, and is the same public feed
Apple serves at itunes.apple.com/{country}/rss/customerreviews/.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd

from base_scraper import BaseScraper, ScrapingBlockedError


APP_ID = "324684580"
COUNTRY = "in"
REVIEW_COUNT = 500
SOURCE_LABEL = "Apple App Store"
MINIMUM_REVIEW_LENGTH = 20

# Apple's public RSS review feed caps out at 10 pages, roughly 50 reviews per
# page. Requesting beyond this limit simply returns the last page again.
MAX_FEED_PAGES = 10
RSS_FEED_URL_TEMPLATE = (
    "https://itunes.apple.com/{country}/rss/customerreviews/"
    "page={page}/id={app_id}/sortby=mostrecent/json"
)

OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "apple_app_reviews.csv"


class AppStoreScraper(BaseScraper):
    """Scraper for Spotify iOS reviews using Apple's public RSS review feed."""

    def __init__(
        self,
        *,
        app_id: str = APP_ID,
        country: str = COUNTRY,
        review_count: int = REVIEW_COUNT,
    ) -> None:
        super().__init__(OUTPUT_PATH)
        self.app_id = app_id
        self.country = country
        self.review_count = review_count

    def build_feed_url(self, page: int) -> str:
        """Build the RSS feed URL for one page of Apple reviews."""
        return RSS_FEED_URL_TEMPLATE.format(
            country=self.country,
            page=page,
            app_id=self.app_id,
        )

    def fetch_feed_page(self, page: int) -> list[dict[str, Any]]:
        """Fetch and parse one page of the Apple RSS review feed."""
        response = self.fetch(self.build_feed_url(page))

        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Apple RSS feed returned a non-JSON response for page {page}: {exc}"
            ) from exc

        return payload.get("feed", {}).get("entry", [])

    @staticmethod
    def extract_label(entry: dict[str, Any], field_name: str) -> str:
        """Return the text label of one RSS entry field, or an empty string."""
        field_value = entry.get(field_name)
        if isinstance(field_value, dict):
            return str(field_value.get("label", ""))
        return ""

    def is_review_entry(self, entry: dict[str, Any]) -> bool:
        """Return whether an RSS entry is an actual review, not app metadata."""
        # The first entry of the feed describes the app itself and has no
        # rating, so requiring a rating label reliably filters it out.
        return bool(self.extract_label(entry, "im:rating"))

    def build_review_text(self, entry: dict[str, Any]) -> str:
        """Combine an entry's title and body into a single review string."""
        title = self.clean_text(self.extract_label(entry, "title"))
        body = self.clean_text(self.extract_label(entry, "content"))

        if title and body and title.lower() not in body.lower():
            return f"{title}. {body}"
        return body or title

    def make_record(self, entry: dict[str, Any]) -> dict[str, Any] | None:
        """Build one normalized record, skipping empty or too-short reviews."""
        if not self.is_review_entry(entry):
            return None

        review_text = self.build_review_text(entry)
        if len(review_text) < MINIMUM_REVIEW_LENGTH:
            return None

        rating_label = self.extract_label(entry, "im:rating")
        try:
            rating: int | str = int(rating_label)
        except ValueError:
            rating = self.clean_text(rating_label)

        review_url = self.normalize_url(self.extract_label(entry, "id"))
        if not review_url.lower().startswith("http"):
            review_url = ""

        return {
            "review": review_text,
            "rating": rating,
            "date": self.clean_text(self.extract_label(entry, "updated")),
            "source": SOURCE_LABEL,
            "url": review_url,
        }

    def fetch_raw_records(self) -> list[dict[str, Any]]:
        """Page through the RSS feed until enough reviews are collected."""
        records: list[dict[str, Any]] = []
        seen_review_ids: set[str] = set()

        for page in range(1, MAX_FEED_PAGES + 1):
            if len(records) >= self.review_count:
                break

            try:
                entries = self.fetch_feed_page(page)
            except ScrapingBlockedError as exc:
                self.logger.warning("Apple RSS feed blocked on page %s: %s", page, exc)
                break
            except Exception as exc:
                self.logger.warning(
                    "Apple RSS feed failed on page %s: %s: %s",
                    page,
                    type(exc).__name__,
                    exc,
                )
                break

            if not entries:
                self.logger.info("No more entries returned after page %s", page - 1)
                break

            new_records_on_page = 0
            for entry in entries:
                entry_id = self.extract_label(entry, "id")
                if entry_id and entry_id in seen_review_ids:
                    continue

                record = self.make_record(entry)
                if record is None:
                    continue

                if entry_id:
                    seen_review_ids.add(entry_id)
                records.append(record)
                new_records_on_page += 1

            self.logger.info(
                "Page %s: %s usable reviews (running total: %s)",
                page,
                new_records_on_page,
                len(records),
            )

            if new_records_on_page == 0:
                # Apple repeats the final page once the feed is exhausted.
                self.logger.info("Page %s had no new reviews; stopping pagination", page)
                break

        return records[: self.review_count]

    def collect(self) -> tuple[pd.DataFrame, int]:
        """Collect Apple App Store reviews and remove duplicate review text."""
        records = self.fetch_raw_records()
        dataframe = pd.DataFrame(records, columns=["review", "rating", "date", "source", "url"])

        before = len(dataframe)
        if not dataframe.empty:
            dataframe = dataframe.drop_duplicates(subset=["review"], keep="first").reset_index(
                drop=True
            )
        duplicates_removed = before - len(dataframe)

        return dataframe, duplicates_removed

    def run(self) -> tuple[pd.DataFrame, int]:
        """Run the Apple App Store review scraping workflow."""
        dataframe, duplicates_removed = self.collect()
        self.save_dataframe(dataframe)
        return dataframe, duplicates_removed


def main() -> None:
    """Run the scraper and print a concise summary."""
    scraper = AppStoreScraper()

    try:
        dataframe, duplicates_removed = scraper.run()
        print(f"Pages visited: {scraper.pages_visited}")
        print(f"Duplicate reviews removed: {duplicates_removed}")
        print(f"Total unique records saved: {len(dataframe)}")
        print(f"Saved output to: {scraper.output_path}")

        if dataframe.empty:
            print(
                "No records were saved. Apple's public RSS review feed may be "
                "unavailable, the network may be blocked, or the app ID may be "
                "incorrect."
            )
    except Exception as exc:
        print(f"Failed to download Spotify App Store reviews: {type(exc).__name__}: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
