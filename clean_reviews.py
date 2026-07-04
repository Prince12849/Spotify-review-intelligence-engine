"""Clean downloaded Spotify review data."""

from pathlib import Path

import pandas as pd


INPUT_PATH = Path("data") / "spotify_reviews.csv"
OUTPUT_PATH = Path("data") / "spotify_reviews_cleaned.csv"
REVIEW_TEXT_COLUMN = "review_text"


def load_reviews(input_path: Path) -> pd.DataFrame:
    """Load reviews from CSV with a clear error if the file is missing."""
    if not input_path.exists():
        raise FileNotFoundError(
            f"Input file not found: {input_path}. Run scraper.py before cleaning."
        )

    return pd.read_csv(input_path)


def clean_reviews(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Remove empty and duplicate reviews, then normalize review whitespace."""
    if REVIEW_TEXT_COLUMN not in dataframe.columns:
        raise KeyError(f"Required column missing from input CSV: {REVIEW_TEXT_COLUMN}")

    cleaned_dataframe = dataframe.copy()
    cleaned_dataframe[REVIEW_TEXT_COLUMN] = (
        cleaned_dataframe[REVIEW_TEXT_COLUMN].fillna("").astype(str).str.strip()
    )
    cleaned_dataframe = cleaned_dataframe[cleaned_dataframe[REVIEW_TEXT_COLUMN] != ""]
    cleaned_dataframe = cleaned_dataframe.drop_duplicates()

    return cleaned_dataframe


def save_cleaned_reviews(dataframe: pd.DataFrame, output_path: Path) -> None:
    """Save cleaned reviews to CSV, creating the output directory if needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(output_path, index=False, encoding="utf-8")


def main() -> None:
    """Run the review cleaning workflow."""
    try:
        review_dataframe = load_reviews(INPUT_PATH)
        total_before_cleaning = len(review_dataframe)

        cleaned_dataframe = clean_reviews(review_dataframe)
        save_cleaned_reviews(cleaned_dataframe, OUTPUT_PATH)

        print(f"Total reviews before cleaning: {total_before_cleaning}")
        print(f"Total reviews after cleaning: {len(cleaned_dataframe)}")
    except Exception as exc:
        print(f"Failed to clean Spotify reviews: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
