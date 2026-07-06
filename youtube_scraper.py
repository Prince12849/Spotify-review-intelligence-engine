"""Collect Spotify-related YouTube comments using the YouTube Data API v3.

This scraper does not touch YouTube's HTML. It uses Google's official
``commentThreads`` REST endpoint, which requires an API key with the YouTube
Data API v3 enabled. The key is read from the ``YOUTUBE_API_KEY`` environment
variable and is never hardcoded.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from base_scraper import BaseScraper, ScrapingBlockedError


# Replace these with the actual Spotify-related YouTube video IDs you want to
# analyze (e.g. official Spotify feature announcements, review videos, or
# tutorials where viewers discuss music discovery and recommendations).
VIDEO_IDS: tuple[str, ...] = (
    "IVAeoXbE9ZY",
    "YlxlsQVLw3E",
    "ZcmJxli8WS8"
)

MAX_COMMENTS_PER_VIDEO = 200
SOURCE_LABEL = "YouTube"
MINIMUM_COMMENT_LENGTH = 20

YOUTUBE_API_BASE_URL = "https://www.googleapis.com/youtube/v3/commentThreads"
YOUTUBE_API_KEY_ENV_VAR = "YOUTUBE_API_KEY"
COMMENTS_PER_PAGE = 100

OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "youtube_reviews.csv"


class YouTubeScraper(BaseScraper):
    """Scraper for Spotify-related YouTube comments via the official API."""

    def __init__(
        self,
        *,
        video_ids: tuple[str, ...] = VIDEO_IDS,
        max_comments_per_video: int = MAX_COMMENTS_PER_VIDEO,
    ) -> None:
        super().__init__(OUTPUT_PATH)
        self.video_ids = video_ids
        self.max_comments_per_video = max_comments_per_video
        self.api_key = os.getenv(YOUTUBE_API_KEY_ENV_VAR, "")

        if not self.api_key:
            raise RuntimeError(
                f"{YOUTUBE_API_KEY_ENV_VAR} environment variable is not set. "
                "Set it to a valid YouTube Data API v3 key before running this scraper."
            )

    def is_usable_comment(self, comment_text: str) -> bool:
        """Return whether a cleaned comment is long enough to keep."""
        return bool(comment_text) and len(comment_text) >= MINIMUM_COMMENT_LENGTH

    @staticmethod
    def build_comment_url(video_id: str, comment_id: str) -> str:
        """Build a direct link to a YouTube comment, or blank if unavailable."""
        cleaned_comment_id = BaseScraper.clean_text(comment_id)
        if not cleaned_comment_id:
            return ""

        cleaned_video_id = BaseScraper.clean_text(video_id)
        return f"https://www.youtube.com/watch?v={cleaned_video_id}&lc={cleaned_comment_id}"

    def fetch_comment_page(
        self,
        video_id: str,
        page_token: str | None,
    ) -> dict[str, Any]:
        """Fetch one page of top-level comment threads for a video."""
        params: dict[str, Any] = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": COMMENTS_PER_PAGE,
            "order": "relevance",
            "textFormat": "plainText",
            "key": self.api_key,
        }
        if page_token:
            params["pageToken"] = page_token

        response = self.fetch(YOUTUBE_API_BASE_URL, params=params)

        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"YouTube API returned a non-JSON response for video {video_id}: {exc}"
            ) from exc

    def extract_comment_record(
        self,
        item: dict[str, Any],
        video_id: str,
    ) -> dict[str, Any] | None:
        """Build one normalized record from a commentThreads API item."""
        top_level_comment = item.get("snippet", {}).get("topLevelComment", {})
        comment_id = top_level_comment.get("id", "")
        snippet = top_level_comment.get("snippet", {})

        comment_text = self.clean_text(snippet.get("textDisplay", ""))
        if not self.is_usable_comment(comment_text):
            return None

        return {
            "review": comment_text,
            "rating": "",
            "date": self.clean_text(snippet.get("publishedAt", "")),
            "source": SOURCE_LABEL,
            "url": self.build_comment_url(video_id, comment_id),
        }

    def collect_video_comments(
        self,
        video_id: str,
        seen_comment_ids: set[str],
    ) -> list[dict[str, Any]]:
        """Page through comment threads for one video up to the configured cap."""
        records: list[dict[str, Any]] = []
        page_token: str | None = None

        while len(records) < self.max_comments_per_video:
            try:
                payload = self.fetch_comment_page(video_id, page_token)
            except ScrapingBlockedError as exc:
                self.logger.warning("YouTube API blocked for video %s: %s", video_id, exc)
                break
            except Exception as exc:
                self.logger.warning(
                    "YouTube API failed for video %s: %s: %s",
                    video_id,
                    type(exc).__name__,
                    exc,
                )
                break

            items = payload.get("items", [])
            if not items:
                break

            for item in items:
                comment_id = item.get("snippet", {}).get("topLevelComment", {}).get("id", "")
                if comment_id and comment_id in seen_comment_ids:
                    continue

                record = self.extract_comment_record(item, video_id)
                if record is None:
                    continue

                if comment_id:
                    seen_comment_ids.add(comment_id)
                records.append(record)

                if len(records) >= self.max_comments_per_video:
                    break

            page_token = payload.get("nextPageToken")
            if not page_token:
                break

        self.logger.info("Video %s: collected %s comments", video_id, len(records))
        return records

    def collect(self) -> tuple[pd.DataFrame, int]:
        """Collect comments across all configured videos and remove duplicates."""
        seen_comment_ids: set[str] = set()
        all_records: list[dict[str, Any]] = []

        for video_id in self.video_ids:
            self.logger.info("Collecting comments for video: %s", video_id)
            all_records.extend(self.collect_video_comments(video_id, seen_comment_ids))

        dataframe = pd.DataFrame(
            all_records,
            columns=["review", "rating", "date", "source", "url"],
        )

        before = len(dataframe)
        if not dataframe.empty:
            dataframe = dataframe.drop_duplicates(subset=["review"], keep="first").reset_index(
                drop=True
            )
        duplicates_removed = before - len(dataframe)

        return dataframe, duplicates_removed

    def run(self) -> tuple[pd.DataFrame, int]:
        """Run the full YouTube comment scraping workflow."""
        dataframe, duplicates_removed = self.collect()
        self.save_dataframe(dataframe)
        return dataframe, duplicates_removed


def main() -> None:
    """Run the scraper and print a concise summary."""
    try:
        scraper = YouTubeScraper()
    except RuntimeError as exc:
        print(f"Failed to start YouTube scraper: {exc}")
        sys.exit(1)

    try:
        dataframe, duplicates_removed = scraper.run()
        print(f"Pages visited: {scraper.pages_visited}")
        print(f"Duplicate comments removed: {duplicates_removed}")
        print(f"Total unique records saved: {len(dataframe)}")
        print(f"Saved output to: {scraper.output_path}")

        if dataframe.empty:
            print(
                "No records were saved. Check that VIDEO_IDS contains valid video "
                "IDs, that comments are enabled on those videos, and that the "
                "YouTube Data API quota has not been exceeded."
            )
    except Exception as exc:
        print(f"Failed to collect YouTube comments: {type(exc).__name__}: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
