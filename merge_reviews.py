"""Merge Play Store, Reddit, and Spotify Community review datasets.

The script standardizes all source CSV files into one schema and saves the
combined dataset to data/master_reviews.csv.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Callable

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

PLAY_STORE_PATH = DATA_DIR / "spotify_reviews_cleaned.csv"
REDDIT_PATH = DATA_DIR / "reddit_reviews.csv"
SPOTIFY_COMMUNITY_PATH = DATA_DIR / "spotify_community_reviews.csv"
OUTPUT_PATH = DATA_DIR / "master_reviews.csv"

STANDARD_COLUMNS = ["review", "source", "rating", "date", "url"]


def create_logger() -> logging.Logger:
    """Create a consistent console logger for the merge workflow."""
    logger = logging.getLogger("merge_reviews")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)

    return logger


LOGGER = create_logger()


def clean_text(value: object) -> str:
    """Normalize text by removing extra whitespace and missing values."""
    if pd.isna(value):
        return ""
    return " ".join(str(value).replace("\n", " ").split()).strip()


def combine_text(*values: object) -> str:
    """Combine multiple text fields into one clean review string."""
    parts = [clean_text(value) for value in values]
    return " ".join(part for part in parts if part)


def load_csv(path: Path) -> pd.DataFrame:
    """Load a CSV file with a helpful error if it is missing or unreadable."""
    if not path.exists():
        raise FileNotFoundError(
            f"Required input file not found: {path}. "
            "Run the corresponding scraper/cleaner before merging."
        )

    try:
        dataframe = pd.read_csv(path)
    except Exception as exc:
        raise RuntimeError(f"Failed to read {path}: {type(exc).__name__}: {exc}") from exc

    LOGGER.info("Loaded %s records from %s", len(dataframe), path.name)
    return dataframe


def standardize_play_store(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Convert cleaned Google Play reviews to the standard schema."""
    required_columns = {"review_text", "rating", "review_date"}
    missing_columns = required_columns - set(dataframe.columns)
    if missing_columns:
        raise KeyError(
            f"{PLAY_STORE_PATH.name} is missing required columns: "
            f"{', '.join(sorted(missing_columns))}"
        )

    standardized = pd.DataFrame(
        {
            "review": dataframe["review_text"].map(clean_text),
            "source": "google_play",
            "rating": dataframe["rating"],
            "date": dataframe["review_date"].map(clean_text),
            "url": "",
        }
    )
    return standardized[STANDARD_COLUMNS]


def standardize_reddit(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Convert Reddit discussion records to the standard schema."""
    required_columns = {"title", "body", "url", "date"}
    missing_columns = required_columns - set(dataframe.columns)
    if missing_columns:
        raise KeyError(
            f"{REDDIT_PATH.name} is missing required columns: "
            f"{', '.join(sorted(missing_columns))}"
        )

    standardized = pd.DataFrame(
        {
            "review": [
                combine_text(title, body)
                for title, body in zip(dataframe["title"], dataframe["body"], strict=False)
            ],
            "source": "reddit",
            "rating": "",
            "date": dataframe["date"].map(clean_text),
            "url": dataframe["url"].map(clean_text),
        }
    )
    return standardized[STANDARD_COLUMNS]


def standardize_spotify_community(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Convert Spotify Community records to the standard schema."""
    required_columns = {"discussion_title", "discussion_body", "date", "url"}
    missing_columns = required_columns - set(dataframe.columns)
    if missing_columns:
        raise KeyError(
            f"{SPOTIFY_COMMUNITY_PATH.name} is missing required columns: "
            f"{', '.join(sorted(missing_columns))}"
        )

    standardized = pd.DataFrame(
        {
            "review": [
                combine_text(title, body)
                for title, body in zip(
                    dataframe["discussion_title"],
                    dataframe["discussion_body"],
                    strict=False,
                )
            ],
            "source": "spotify_community",
            "rating": "",
            "date": dataframe["date"].map(clean_text),
            "url": dataframe["url"].map(clean_text),
        }
    )
    return standardized[STANDARD_COLUMNS]


def remove_duplicate_reviews(dataframe: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Remove empty reviews and duplicate review text across all sources."""
    before = len(dataframe)
    cleaned_dataframe = dataframe.copy()
    cleaned_dataframe["review"] = cleaned_dataframe["review"].map(clean_text)
    cleaned_dataframe = cleaned_dataframe[cleaned_dataframe["review"] != ""].copy()
    cleaned_dataframe["_normalized_review"] = cleaned_dataframe["review"].str.lower()
    cleaned_dataframe = cleaned_dataframe.drop_duplicates(
        subset=["_normalized_review"],
        keep="first",
    )
    cleaned_dataframe = cleaned_dataframe.drop(columns=["_normalized_review"]).reset_index(drop=True)

    return cleaned_dataframe[STANDARD_COLUMNS], before - len(cleaned_dataframe)


def merge_sources() -> tuple[pd.DataFrame, int]:
    """Load, standardize, merge, and deduplicate all review sources."""
    source_loaders: list[tuple[Path, Callable[[pd.DataFrame], pd.DataFrame]]] = [
        (PLAY_STORE_PATH, standardize_play_store),
        (REDDIT_PATH, standardize_reddit),
        (SPOTIFY_COMMUNITY_PATH, standardize_spotify_community),
    ]

    standardized_frames: list[pd.DataFrame] = []
    for path, standardizer in source_loaders:
        raw_dataframe = load_csv(path)
        standardized_frames.append(standardizer(raw_dataframe))

    merged_dataframe = pd.concat(standardized_frames, ignore_index=True)
    LOGGER.info("Merged %s records before deduplication", len(merged_dataframe))
    return remove_duplicate_reviews(merged_dataframe)


def save_master_reviews(dataframe: pd.DataFrame) -> None:
    """Save the merged master dataset."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    LOGGER.info("Saved merged dataset to %s", OUTPUT_PATH)


def main() -> None:
    """Run the merge workflow and print the required summary."""
    try:
        master_dataframe, duplicates_removed = merge_sources()
        save_master_reviews(master_dataframe)

        records_per_source = master_dataframe["source"].value_counts().to_dict()
        print(f"Records per source: {records_per_source}")
        print(f"Total merged records: {len(master_dataframe)}")
        print(f"Duplicates removed: {duplicates_removed}")
    except Exception as exc:
        LOGGER.error("Merge failed: %s: %s", type(exc).__name__, exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
