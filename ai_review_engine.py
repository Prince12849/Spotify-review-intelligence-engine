"""AI-powered review intelligence engine for Spotify feedback.

The script enriches data/master_reviews.csv with sentiment, themes, inferred
user goals, pain points, feature requests, and confidence scores. It uses the
OpenAI API when OPENAI_API_KEY is available and automatically falls back to a
rule-based NLP engine when an API key or API client is unavailable.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
from tqdm import tqdm


BASE_DIR = Path(__file__).resolve().parent
INPUT_PATH = BASE_DIR / "data" / "master_reviews.csv"
OUTPUT_PATH = BASE_DIR / "data" / "master_reviews_ai.csv"
SUMMARY_PATH = BASE_DIR / "output" / "summary.json"

REQUIRED_COLUMNS = {"review", "source", "rating", "date", "url"}
ENRICHMENT_COLUMNS = [
    "sentiment",
    "theme",
    "user_goal",
    "pain_point",
    "feature_request",
    "confidence_score",
]

VALID_SENTIMENTS = {"Positive", "Neutral", "Negative"}
VALID_THEMES = {
    "Recommendation Fatigue",
    "Music Discovery",
    "Discover Weekly",
    "Daily Mix",
    "New Artists",
    "Repetitive Songs",
    "Personalization",
    "Playlist Variety",
    "Algorithm Quality",
    "Playlist Issues",
    "Ads",
    "Premium",
    "Search",
    "Performance",
    "Algorithm",
    "UI/UX",
    "Other",
}

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BATCH_SIZE = int(os.getenv("OPENAI_BATCH_SIZE", "8"))
MAX_REVIEW_CHARS_FOR_AI = int(os.getenv("MAX_REVIEW_CHARS_FOR_AI", "3000"))
TOP_N_SUMMARY_ITEMS = 10


def create_logger() -> logging.Logger:
    """Create a consistent console logger for the enrichment workflow."""
    logger = logging.getLogger("ai_review_engine")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)

    return logger


LOGGER = create_logger()


def clean_text(value: object) -> str:
    """Normalize missing values, HTML leftovers, and extra whitespace."""
    if pd.isna(value):
        return ""
    text = re.sub(r"<[^>]+>", " ", str(value))
    return " ".join(text.replace("\n", " ").split()).strip()


def safe_float(value: object, default: float = 0.0) -> float:
    """Convert a value to float, returning a default on failure."""
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp_confidence(value: object) -> float:
    """Clamp confidence scores into the required 0 to 1 range."""
    return round(max(0.0, min(1.0, safe_float(value, 0.5))), 2)


def keyword_score(text: str, keywords: tuple[str, ...]) -> int:
    """Count keyword matches using word boundaries to avoid false positives."""
    lowered = text.lower()
    score = 0

    for keyword in keywords:
        cleaned_keyword = keyword.lower().strip()
        if not cleaned_keyword:
            continue

        escaped_keyword = re.escape(cleaned_keyword).replace(r"\ ", r"\s+")
        prefix = r"\b" if cleaned_keyword[0].isalnum() else ""
        suffix = r"\b" if cleaned_keyword[-1].isalnum() else ""
        if re.search(f"{prefix}{escaped_keyword}{suffix}", lowered):
            score += 1

    return score


class RuleBasedReviewAnalyzer:
    """Local NLP fallback for deterministic review intelligence."""

    theme_keywords: dict[str, tuple[str, ...]] = {
        "Discover Weekly": (
            "discover weekly",
            "discovery weekly",
            "weekly discovery",
            "discover playlist",
            "weekly playlist",
            "monday playlist",
            "reset discover weekly",
            "discover weekly playlist",
        ),
        "Daily Mix": (
            "daily mix",
            "daily mixes",
            "daylist",
            "made for you mix",
            "mixes",
            "my mix",
            "genre mix",
            "artist mix",
        ),
        "Repetitive Songs": (
            "same songs",
            "same song",
            "same tracks",
            "same track",
            "same music",
            "same artists",
            "same artist",
            "on repeat",
            "keeps playing",
            "keep playing",
            "played again",
            "over and over",
            "too repetitive",
            "repeated songs",
            "repeating songs",
        ),
        "Recommendation Fatigue": (
            "same songs",
            "same music",
            "same artists",
            "repetitive",
            "repeat",
            "stale",
            "terrible recommendations",
            "bad recommendations",
            "too similar",
            "recommendations are bad",
            "recommendations suck",
            "recommendations worse",
            "recommendations have gotten worse",
            "stop recommending",
            "tired of recommendations",
            "not interested",
            "irrelevant recommendations",
            "recommend the same",
        ),
        "Personalization": (
            "personalized",
            "personalisation",
            "personalization",
            "my taste",
            "my tastes",
            "taste profile",
            "listening history",
            "based on my listening",
            "because i listened",
            "not my taste",
            "doesn't fit me",
            "does not fit me",
            "train spotify",
            "reset my taste",
            "exclude",
            "hide artist",
            "not interested",
        ),
        "Playlist Variety": (
            "variety",
            "more variety",
            "playlist variety",
            "different genres",
            "genre variety",
            "diverse",
            "diversity",
            "fresh playlist",
            "fresh songs",
            "new tracks",
            "mix of songs",
            "same playlist",
            "playlist is stale",
        ),
        "Music Discovery": (
            "discover",
            "discovery",
            "discover weekly",
            "discover new",
            "new music",
            "music discovery",
            "find new",
            "similar songs",
            "similar artists",
            "recommended songs",
            "suggested",
            "recommend songs",
            "song recommendations",
            "new songs",
            "fresh music",
            "music recommendations",
            "discover artists",
            "discover more",
            "explore music",
            "music suggestions",
            "suggest songs",
            "suggested songs",
            "music",
            "song",
            "songs",
            "track",
            "tracks",
            "listen",
            "listening",
        ),
        "New Artists": (
            "artists",
            "new artists",
            "similar artists",
            "artist recommendations",
            "recommend artists",
            "unknown artists",
            "indie artists",
            "emerging artists",
            "find artists",
            "discover artists",
            "artists like",
            "more artists",
        ),
        "Algorithm Quality": (
            "algorithm",
            "recommendation algorithm",
            "algorithmic",
            "recommendation engine",
            "ai recommendations",
            "machine learning",
            "not accurate",
            "inaccurate",
            "irrelevant",
            "doesn't understand",
            "does not understand",
            "quality of recommendations",
            "recommendation quality",
            "better algorithm",
        ),
        "Playlist Issues": (
            "playlist",
            "daily mix",
            "mix",
            "queue",
            "shuffle",
            "save songs",
            "library",
            "liked songs",
            "collaborative playlist",
            "playlist folder",
            "add to playlist",
            "remove from playlist",
            "playlist management",
            "playlist disappeared",
            "playlist order",
        ),
        "Ads": (
            "ad",
            "ads",
            "advert",
            "commercial",
            "interrupt",
            "interruption",
            "sponsored",
            "ad break",
            "too many ads",
            "every song",
            "between songs",
        ),
        "Premium": (
            "premium",
            "subscription",
            "pay",
            "paid",
            "free version",
            "trial",
            "family plan",
            "duo",
            "student plan",
            "billing",
            "price",
            "cost",
        ),
        "Search": (
            "search",
            "find song",
            "lookup",
            "filter",
            "browse",
            "sort",
            "advanced search",
            "lyrics search",
            "hum",
            "humming",
            "whistling",
        ),
        "Performance": (
            "crash",
            "bug",
            "slow",
            "lag",
            "freeze",
            "buffer",
            "loading",
            "offline",
            "glitch",
            "error",
            "not working",
            "won't play",
            "stops playing",
            "disconnect",
        ),
        "Algorithm": (
            "algorithm",
            "recommendation algorithm",
            "recommend",
            "recommendation",
            "recommendations",
            "recommended",
            "personalized",
            "suggestion",
            "suggestions",
            "for you",
            "made for you",
        ),
        "UI/UX": (
            "navigation",
            "buttons",
            "interface",
            "design",
            "layout",
            "menu",
            "settings",
            "dark mode",
            "scrolling",
            "animations",
            "ui",
            "button",
            "home screen",
            "home page",
            "tab",
            "feature moved",
            "hard to use",
            "easy to use",
        ),
    }

    positive_keywords = (
        "great",
        "good",
        "love",
        "excellent",
        "amazing",
        "best",
        "enjoy",
        "helpful",
        "game-changer",
        "incredible",
    )

    high_priority_themes = (
        "Music Discovery",
        "Recommendation Fatigue",
        "Discover Weekly",
        "Daily Mix",
        "Repetitive Songs",
        "Personalization",
        "New Artists",
        "Playlist Variety",
        "Algorithm Quality",
    )
    negative_keywords = (
        "bad",
        "terrible",
        "hate",
        "annoying",
        "frustrating",
        "worse",
        "broken",
        "issue",
        "problem",
        "ads",
        "crash",
        "repetitive",
        "boring",
    )

    goal_by_theme = {
        "Recommendation Fatigue": "Improve recommendations",
        "Music Discovery": "Discover new music",
        "Discover Weekly": "Use Discover Weekly to find better weekly music",
        "Daily Mix": "Enjoy personalized Daily Mix playlists",
        "New Artists": "Find similar or new artists",
        "Repetitive Songs": "Avoid hearing the same songs repeatedly",
        "Personalization": "Tune Spotify to personal taste",
        "Playlist Variety": "Get more variety in playlists",
        "Algorithm Quality": "Improve recommendation accuracy",
        "Playlist Issues": "Build playlists",
        "Ads": "Listen without interruptions",
        "Premium": "Evaluate or manage Premium",
        "Search": "Find specific music faster",
        "Performance": "Use Spotify reliably",
        "Algorithm": "Improve recommendations",
        "UI/UX": "Navigate Spotify more easily",
        "Other": "Use Spotify more effectively",
    }

    feature_by_theme = {
        "Recommendation Fatigue": "More diverse recommendations",
        "Music Discovery": "Better new music discovery tools",
        "Discover Weekly": "More control over Discover Weekly",
        "Daily Mix": "More diverse and editable Daily Mixes",
        "New Artists": "Better similar-artist discovery",
        "Repetitive Songs": "Limit repeated songs in recommendations",
        "Personalization": "Taste profile controls and reset options",
        "Playlist Variety": "More varied playlist generation",
        "Algorithm Quality": "Explain and improve recommendation logic",
        "Playlist Issues": "Better playlist controls",
        "Ads": "Fewer and less repetitive ads",
        "Premium": "Clearer Premium value and controls",
        "Search": "Improved search and filtering",
        "Performance": "More reliable app performance",
        "Algorithm": "Better recommendation controls",
        "UI/UX": "Cleaner and easier navigation",
        "Other": "General product improvement",
    }

    pain_by_theme = {
        "Recommendation Fatigue": "The user feels Spotify recommendations have become repetitive.",
        "Music Discovery": "The user wants an easier way to discover music they will enjoy.",
        "Discover Weekly": "The user is frustrated that Discover Weekly does not match their taste.",
        "Daily Mix": "The user feels Daily Mix playlists are not varied or useful enough.",
        "New Artists": "The user wants better ways to find artists they have not heard before.",
        "Repetitive Songs": "The user is tired of hearing the same songs repeatedly.",
        "Personalization": "The user feels Spotify is not learning or respecting their preferences.",
        "Playlist Variety": "The user wants playlists with more variety and fresher tracks.",
        "Algorithm Quality": "The user feels Spotify's recommendation algorithm is inaccurate.",
        "Playlist Issues": "The user is frustrated by playlist or library management limitations.",
        "Ads": "The user is frustrated by ads interrupting the listening experience.",
        "Premium": "The user is unsure whether Premium delivers enough value.",
        "Search": "The user struggles to find the music they want quickly.",
        "Performance": "The user is frustrated by reliability or performance problems.",
        "Algorithm": "The user feels the recommendation algorithm is not aligned with their taste.",
        "UI/UX": "The user finds the interface or navigation harder than expected.",
        "Other": "The user has a general Spotify experience issue.",
    }

    goal_keywords: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("Discover new music", ("discover new", "new music", "fresh music", "new songs")),
        ("Find similar artists", ("similar artists", "artists like", "artist recommendations")),
        ("Improve recommendations", ("recommendation", "recommendations", "recommended", "algorithm")),
        ("Avoid repetitive songs", ("same songs", "repeat", "repetitive", "over and over")),
        ("Personalize listening experience", ("my taste", "taste profile", "personalized", "listening history")),
        ("Use Discover Weekly effectively", ("discover weekly", "weekly discovery")),
        ("Enjoy better Daily Mixes", ("daily mix", "daily mixes", "made for you mix")),
        ("Build playlists", ("playlist", "liked songs", "library", "queue")),
        ("Listen without interruptions", ("ads", "commercial", "interrupt", "ad break")),
        ("Find specific music faster", ("search", "find song", "filter", "browse")),
    )

    feature_request_keywords: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("More diverse recommendations", ("variety", "diverse", "different genres", "same songs")),
        ("Explain why a song was recommended", ("why recommended", "why this song", "because i listened")),
        ("Recommendation reset controls", ("reset", "start over", "clear history", "taste profile")),
        ("Mood-based discovery", ("mood", "vibe", "activity", "workout", "sleep", "focus")),
        ("AI discovery coach", ("ai", "coach", "assistant", "guide me", "help me discover")),
        ("Better recommendation controls", ("not interested", "exclude", "hide artist", "stop recommending")),
        ("Better similar-artist discovery", ("similar artists", "artists like", "new artists")),
        ("More varied Daily Mixes", ("daily mix", "daily mixes", "mixes")),
        ("More control over Discover Weekly", ("discover weekly", "weekly playlist")),
        ("Fewer and less repetitive ads", ("ads", "commercial", "ad break")),
        ("Better playlist controls", ("playlist", "queue", "shuffle", "save songs")),
        ("Improved search and filtering", ("search", "filter", "sort", "browse")),
    )

    def analyze(self, review: str, rating: object = "") -> dict[str, Any]:
        """Analyze one review using transparent keyword and rating rules."""
        review_text = clean_text(review)
        lowered = review_text.lower()

        theme = self.infer_theme(lowered)
        sentiment = self.infer_sentiment(lowered, rating)
        confidence = self.infer_confidence(lowered, rating, theme)

        return {
            "sentiment": sentiment,
            "theme": theme,
            "user_goal": self.infer_user_goal(lowered, theme),
            "pain_point": self.pain_by_theme[theme],
            "feature_request": self.infer_feature_request(lowered, theme),
            "confidence_score": confidence,
        }

    def infer_theme(self, lowered_review: str) -> str:
        """Infer the dominant theme from keyword evidence."""
        # Route discovery/recommendation language before considering UI/UX.
        if keyword_score(lowered_review, self.theme_keywords["Discover Weekly"]) > 0:
            return "Discover Weekly"
        if keyword_score(lowered_review, self.theme_keywords["Daily Mix"]) > 0:
            return "Daily Mix"
        if keyword_score(lowered_review, self.theme_keywords["Personalization"]) > 0:
            return "Personalization"
        if keyword_score(lowered_review, self.theme_keywords["Recommendation Fatigue"]) > 0:
            return "Recommendation Fatigue"
        if keyword_score(
            lowered_review,
            (
                "discover",
                "discovery",
                "recommend",
                "recommendation",
                "recommendations",
                "recommended",
                "suggested",
                "similar songs",
                "artists",
                "new music",
            ),
        ) > 0:
            return "Music Discovery"

        scores = {
            theme: keyword_score(lowered_review, keywords)
            for theme, keywords in self.theme_keywords.items()
        }
        priority_scores = {
            theme: scores[theme]
            for theme in self.high_priority_themes
            if scores.get(theme, 0) > 0
        }
        if priority_scores:
            return max(priority_scores.items(), key=lambda item: item[1])[0]

        best_theme, best_score = max(scores.items(), key=lambda item: item[1])
        return best_theme if best_score > 0 else "Other"

    def infer_user_goal(self, lowered_review: str, theme: str) -> str:
        """Infer the user's goal from explicit keywords before using theme defaults."""
        for goal, keywords in self.goal_keywords:
            if keyword_score(lowered_review, keywords) > 0:
                return goal
        return self.goal_by_theme[theme]

    def infer_feature_request(self, lowered_review: str, theme: str) -> str:
        """Infer a likely feature request from specific product need keywords."""
        for feature_request, keywords in self.feature_request_keywords:
            if keyword_score(lowered_review, keywords) > 0:
                return feature_request
        return self.feature_by_theme[theme]

    def infer_sentiment(self, lowered_review: str, rating: object) -> str:
        """Infer sentiment from rating first, then keyword polarity."""
        numeric_rating = safe_float(rating, default=-1)
        if numeric_rating >= 4:
            return "Positive"
        if 0 <= numeric_rating <= 2:
            return "Negative"
        if numeric_rating == 3:
            return "Neutral"

        positive_score = keyword_score(lowered_review, self.positive_keywords)
        negative_score = keyword_score(lowered_review, self.negative_keywords)

        if positive_score > negative_score:
            return "Positive"
        if negative_score > positive_score:
            return "Negative"
        return "Neutral"

    def infer_confidence(self, lowered_review: str, rating: object, theme: str) -> float:
        """Estimate confidence from review length, rating, and theme evidence."""
        confidence = 0.45
        if len(lowered_review) > 40:
            confidence += 0.15
        if len(lowered_review) > 160:
            confidence += 0.1
        if safe_float(rating, default=-1) >= 0:
            confidence += 0.1
        if theme != "Other":
            confidence += 0.15
        return clamp_confidence(confidence)


class OpenAIReviewAnalyzer:
    """OpenAI-backed analyzer with automatic fallback on any batch failure."""

    def __init__(self, fallback_analyzer: RuleBasedReviewAnalyzer) -> None:
        self.fallback_analyzer = fallback_analyzer
        self.client = self._create_client()

    def _create_client(self) -> Any | None:
        """Create an OpenAI client only when both key and package are available."""
        if not os.getenv("OPENAI_API_KEY"):
            LOGGER.info("OPENAI_API_KEY not found. Using rule-based NLP fallback.")
            return None

        try:
            from openai import OpenAI
        except ImportError:
            LOGGER.warning("OpenAI package is not installed. Using rule-based fallback.")
            return None

        return OpenAI()

    @property
    def enabled(self) -> bool:
        """Return whether OpenAI enrichment is available."""
        return self.client is not None

    def analyze_batch(self, review_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Analyze one batch with OpenAI, falling back if anything fails."""
        if not self.enabled:
            return [
                self.fallback_analyzer.analyze(row.get("review", ""), row.get("rating", ""))
                for row in review_rows
            ]

        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a product review intelligence analyst. "
                            "Return only valid JSON. Classify Spotify reviews "
                            "using concise, business-friendly labels."
                        ),
                    },
                    {
                        "role": "user",
                        "content": self._build_prompt(review_rows),
                    },
                ],
            )
            content = response.choices[0].message.content or "{}"
            payload = json.loads(content)
            return self._validate_openai_items(payload, review_rows)
        except Exception as exc:
            LOGGER.warning(
                "OpenAI batch failed; using rule-based fallback for %s reviews: %s: %s",
                len(review_rows),
                type(exc).__name__,
                exc,
            )
            return [
                self.fallback_analyzer.analyze(row.get("review", ""), row.get("rating", ""))
                for row in review_rows
            ]

    def _build_prompt(self, review_rows: list[dict[str, Any]]) -> str:
        """Build a compact JSON prompt for one batch."""
        compact_reviews = []
        for row in review_rows:
            compact_reviews.append(
                {
                    "id": row["id"],
                    "source": row.get("source", ""),
                    "rating": row.get("rating", ""),
                    "review": clean_text(row.get("review", ""))[:MAX_REVIEW_CHARS_FOR_AI],
                }
            )

        return json.dumps(
            {
                "task": "Enrich every review with product intelligence fields.",
                "allowed_sentiments": sorted(VALID_SENTIMENTS),
                "allowed_themes": sorted(VALID_THEMES),
                "required_output_schema": {
                    "items": [
                        {
                            "id": "same id as input",
                            "sentiment": "Positive | Neutral | Negative",
                            "theme": "one allowed theme",
                            "user_goal": "short inferred user goal",
                            "pain_point": "one concise sentence",
                            "feature_request": "short inferred feature request",
                            "confidence_score": "number between 0 and 1",
                        }
                    ]
                },
                "reviews": compact_reviews,
            },
            ensure_ascii=True,
        )

    def _validate_openai_items(
        self,
        payload: dict[str, Any],
        review_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Validate OpenAI JSON and fill invalid rows with fallback results."""
        raw_items = payload.get("items", [])
        items_by_id = {
            str(item.get("id")): item
            for item in raw_items
            if isinstance(item, dict) and item.get("id") is not None
        }

        validated_items: list[dict[str, Any]] = []
        for row in review_rows:
            row_id = str(row["id"])
            raw_item = items_by_id.get(row_id)

            if raw_item is None:
                validated_items.append(
                    self.fallback_analyzer.analyze(row.get("review", ""), row.get("rating", ""))
                )
                continue

            validated_items.append(self._validate_item(raw_item, row))

        return validated_items

    def _validate_item(self, item: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
        """Normalize one OpenAI result and replace invalid values."""
        fallback = self.fallback_analyzer.analyze(row.get("review", ""), row.get("rating", ""))

        sentiment = clean_text(item.get("sentiment"))
        theme = clean_text(item.get("theme"))

        return {
            "sentiment": sentiment if sentiment in VALID_SENTIMENTS else fallback["sentiment"],
            "theme": theme if theme in VALID_THEMES else fallback["theme"],
            "user_goal": clean_text(item.get("user_goal")) or fallback["user_goal"],
            "pain_point": clean_text(item.get("pain_point")) or fallback["pain_point"],
            "feature_request": clean_text(item.get("feature_request")) or fallback["feature_request"],
            "confidence_score": clamp_confidence(item.get("confidence_score", fallback["confidence_score"])),
        }


def load_master_reviews() -> pd.DataFrame:
    """Load the master review dataset and validate its schema."""
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_PATH}. Run merge_reviews.py first."
        )

    dataframe = pd.read_csv(INPUT_PATH)
    missing_columns = REQUIRED_COLUMNS - set(dataframe.columns)
    if missing_columns:
        raise KeyError(
            f"{INPUT_PATH.name} is missing required columns: "
            f"{', '.join(sorted(missing_columns))}"
        )

    dataframe = dataframe.copy()
    dataframe["review"] = dataframe["review"].map(clean_text)
    dataframe = dataframe[dataframe["review"] != ""].reset_index(drop=True)
    LOGGER.info("Loaded %s reviews from %s", len(dataframe), INPUT_PATH.name)
    return dataframe


def rows_for_analysis(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert the DataFrame into compact dictionaries for batch analysis."""
    rows: list[dict[str, Any]] = []
    for index, row in dataframe.iterrows():
        rows.append(
            {
                "id": str(index),
                "review": row.get("review", ""),
                "source": row.get("source", ""),
                "rating": row.get("rating", ""),
            }
        )
    return rows


def batch_items(items: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    """Split rows into stable batches for progress tracking and API calls."""
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def enrich_reviews(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Generate intelligence fields for every review."""
    fallback_analyzer = RuleBasedReviewAnalyzer()
    analyzer = OpenAIReviewAnalyzer(fallback_analyzer)
    rows = rows_for_analysis(dataframe)
    batches = batch_items(rows, max(1, OPENAI_BATCH_SIZE))
    enrichment_results: list[dict[str, Any]] = []

    mode = "OpenAI" if analyzer.enabled else "rule-based"
    LOGGER.info("Starting %s enrichment for %s reviews", mode, len(rows))

    for batch in tqdm(batches, desc="Enriching reviews", unit="batch"):
        enrichment_results.extend(analyzer.analyze_batch(batch))

    enriched_dataframe = dataframe.copy()
    for column in ENRICHMENT_COLUMNS:
        enriched_dataframe[column] = [result[column] for result in enrichment_results]

    enriched_dataframe["confidence_score"] = enriched_dataframe["confidence_score"].map(clamp_confidence)
    return enriched_dataframe


def top_counts(series: pd.Series, limit: int = TOP_N_SUMMARY_ITEMS) -> dict[str, int]:
    """Return top non-empty value counts as plain JSON-serializable ints."""
    cleaned_values = [clean_text(value) for value in series.tolist()]
    counts = Counter(value for value in cleaned_values if value)
    return {key: int(value) for key, value in counts.most_common(limit)}


def build_summary(enriched_dataframe: pd.DataFrame) -> dict[str, Any]:
    """Build summary metrics for the enriched dataset."""
    return {
        "total_reviews": int(len(enriched_dataframe)),
        "sentiment_distribution": top_counts(enriched_dataframe["sentiment"], limit=20),
        "theme_distribution": top_counts(enriched_dataframe["theme"], limit=20),
        "top_user_goals": top_counts(enriched_dataframe["user_goal"]),
        "top_pain_points": top_counts(enriched_dataframe["pain_point"]),
        "top_feature_requests": top_counts(enriched_dataframe["feature_request"]),
    }


def save_outputs(enriched_dataframe: pd.DataFrame, summary: dict[str, Any]) -> None:
    """Save the enriched CSV and summary JSON outputs."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    enriched_dataframe.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    with SUMMARY_PATH.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, ensure_ascii=False)

    LOGGER.info("Saved enriched dataset to %s", OUTPUT_PATH)
    LOGGER.info("Saved summary report to %s", SUMMARY_PATH)


def main() -> None:
    """Run the AI review intelligence workflow."""
    try:
        master_dataframe = load_master_reviews()
        enriched_dataframe = enrich_reviews(master_dataframe)
        summary = build_summary(enriched_dataframe)
        save_outputs(enriched_dataframe, summary)

        print(f"Total reviews enriched: {summary['total_reviews']}")
        print(f"Sentiment distribution: {summary['sentiment_distribution']}")
        print(f"Theme distribution: {summary['theme_distribution']}")
        print(f"Saved enriched dataset: {OUTPUT_PATH}")
        print(f"Saved summary JSON: {SUMMARY_PATH}")
    except Exception as exc:
        LOGGER.error("AI review engine failed: %s: %s", type(exc).__name__, exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
