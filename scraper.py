"""Download recent Spotify Android reviews from Google Play."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from google_play_scraper import Sort, reviews

from base_scraper import BaseScraper


APP_PACKAGE_NAME = "com.spotify.music"
REVIEW_COUNT = 500
OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "spotify_reviews.csv"


class PlayStoreScraper(BaseScraper):
    """Scraper for Spotify Android reviews on Google Play."""

    def __init__(self) -> None:
        super().__init__(OUTPUT_PATH)

    def collect(self) -> pd.DataFrame:
        """Fetch Spotify reviews and return them as a pandas DataFrame."""
        raw_reviews, _continuation_token = reviews(
            APP_PACKAGE_NAME,
            lang="en",
            country="us",
            sort=Sort.NEWEST,
            count=REVIEW_COUNT,
        )

        selected_fields = [
            {
                "review_text": self.clean_text(review.get("content")),
                "rating": review.get("score"),
                "review_date": review.get("at"),
                "thumbs_up_count": review.get("thumbsUpCount"),
                "app_version": review.get("reviewCreatedVersion"),
            }
            for review in raw_reviews
        ]

        return pd.DataFrame(selected_fields)

    def run(self) -> pd.DataFrame:
        """Run the Google Play review download workflow."""
        review_dataframe = self.collect()
        self.save_dataframe(review_dataframe)
        return review_dataframe


def main() -> None:
    """Run the scraper and print a concise summary."""
    scraper = PlayStoreScraper()

    try:
        review_dataframe = scraper.run()
        print(f"Total reviews downloaded: {len(review_dataframe)}")
        print("First 5 reviews:")
        print(review_dataframe.head())
    except Exception as exc:
        print(f"Failed to download Spotify reviews: {type(exc).__name__}: {exc}")
        print(
            "The download may fail if Google Play is unavailable, the network is "
            "blocked, the app package cannot be reached, or google-play-scraper "
            "receives an unexpected response from Google Play."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
