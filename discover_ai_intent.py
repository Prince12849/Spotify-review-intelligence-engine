"""Intent analysis for DiscoverAI.

OpenAI support is intentionally modular. If an API key is unavailable or a call
fails, the app uses a deterministic local analyzer so the prototype always runs.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Any

from discover_ai_config import OPENAI_MODEL


@dataclass
class IntentProfile:
    """Structured representation of the user's current listening intent."""

    activity: str
    mood: str
    energy: str
    discovery_level: str
    preferred_genres: list[str]
    intent_summary: str

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable representation of the profile."""
        return asdict(self)


class IntentAnalyzer:
    """Analyze user prompts into current listening intent."""

    def __init__(self) -> None:
        self.openai_client = self._build_openai_client()

    def _build_openai_client(self) -> Any | None:
        """Create an OpenAI client only when credentials and package exist."""
        if not os.getenv("OPENAI_API_KEY"):
            return None
        try:
            from openai import OpenAI
        except ImportError:
            return None
        return OpenAI()

    def analyze(self, prompt: str, adjustment: str | None = None) -> IntentProfile:
        """Analyze a prompt using OpenAI when available, otherwise local rules."""
        prompt = prompt.strip()
        if self.openai_client:
            try:
                return self._analyze_with_openai(prompt, adjustment)
            except Exception:
                return self._analyze_locally(prompt, adjustment)
        return self._analyze_locally(prompt, adjustment)

    def _analyze_with_openai(self, prompt: str, adjustment: str | None) -> IntentProfile:
        """Use OpenAI to produce a structured intent profile."""
        response = self.openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You analyze music discovery intent. Return only JSON with: "
                        "activity, mood, energy, discovery_level, preferred_genres, intent_summary."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "prompt": prompt,
                            "adjustment": adjustment or "",
                            "allowed_energy": ["Low", "Medium", "High"],
                            "allowed_discovery_level": ["Familiar", "Moderate", "Exploratory"],
                        }
                    ),
                },
            ],
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        return self._profile_from_payload(payload, prompt, adjustment)

    def _profile_from_payload(
        self,
        payload: dict[str, Any],
        prompt: str,
        adjustment: str | None,
    ) -> IntentProfile:
        """Validate OpenAI JSON and fill gaps with local analysis."""
        fallback = self._analyze_locally(prompt, adjustment)
        genres = payload.get("preferred_genres")
        if not isinstance(genres, list):
            genres = fallback.preferred_genres

        return IntentProfile(
            activity=str(payload.get("activity") or fallback.activity),
            mood=str(payload.get("mood") or fallback.mood),
            energy=str(payload.get("energy") or fallback.energy),
            discovery_level=str(payload.get("discovery_level") or fallback.discovery_level),
            preferred_genres=[str(genre) for genre in genres[:4]] or fallback.preferred_genres,
            intent_summary=str(payload.get("intent_summary") or fallback.intent_summary),
        )

    def _analyze_locally(self, prompt: str, adjustment: str | None) -> IntentProfile:
        """Infer intent with deterministic keyword rules."""
        lowered = prompt.lower()
        activity = "Open listening"
        mood = "Curious"
        energy = "Medium"
        discovery_level = "Moderate"
        genres = ["Indie", "Alternative", "Lo-Fi"]

        if self._has_any(lowered, ("coding", "code", "programming", "study", "focus", "work")):
            activity, mood, energy = "Coding", "Focused", "Medium"
            genres = ["Lo-Fi", "Ambient", "Instrumental", "Electronic"]
        elif self._has_any(lowered, ("workout", "gym", "run", "training", "cardio")):
            activity, mood, energy = "Workout", "Driven", "High"
            genres = ["Electronic", "Hip Hop", "Pop", "Dance"]
        elif self._has_any(lowered, ("road trip", "drive", "driving", "car")):
            activity, mood, energy = "Road Trip", "Open", "High"
            genres = ["Rock", "Pop", "Country", "Indie"]
        elif self._has_any(lowered, ("party", "friends", "dance", "club")):
            activity, mood, energy = "Party", "Social", "High"
            genres = ["Dance", "Pop", "Afrobeats", "House"]
        elif self._has_any(lowered, ("rain", "rainy", "evening", "night", "cozy")):
            activity, mood, energy = "Rainy Evening", "Reflective", "Low"
            genres = ["Acoustic", "Jazz", "Indie", "Soul"]
        elif self._has_any(lowered, ("relax", "calm", "sleep", "decompress", "chill")):
            activity, mood, energy = "Relax", "Calm", "Low"
            genres = ["Ambient", "Acoustic", "Neo-Soul", "Downtempo"]
        elif self._has_any(lowered, ("coffee", "break", "morning")):
            activity, mood, energy = "Coffee Break", "Warm", "Medium"
            genres = ["Indie", "Soul", "Jazz", "Folk"]

        if self._has_any(lowered, ("surprise", "new artist", "hidden gem", "different")):
            discovery_level = "Exploratory"
        if self._has_any(lowered, ("familiar", "safe", "comfort", "usual")):
            discovery_level = "Familiar"

        if adjustment:
            activity, mood, energy, discovery_level, genres = self._apply_adjustment(
                adjustment,
                activity,
                mood,
                energy,
                discovery_level,
                genres,
            )

        summary = (
            "Instead of relying on past plays, DiscoverAI matched the current "
            f"{activity.lower()} intent with a {mood.lower()} mood, {energy.lower()} "
            f"energy and {discovery_level.lower()} discovery level."
        )
        return IntentProfile(activity, mood, energy, discovery_level, genres[:4], summary)

    @staticmethod
    def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
        """Return True when any keyword appears in text."""
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _apply_adjustment(
        adjustment: str,
        activity: str,
        mood: str,
        energy: str,
        discovery_level: str,
        genres: list[str],
    ) -> tuple[str, str, str, str, list[str]]:
        """Apply feedback controls to the inferred intent profile."""
        if adjustment == "More Energy":
            adjusted_genres = list(dict.fromkeys(["Dance", "Electronic", *genres]))
            return activity, "Energized", "High", discovery_level, adjusted_genres
        if adjustment == "More Calm":
            adjusted_genres = list(dict.fromkeys(["Ambient", "Acoustic", *genres]))
            return activity, "Calm", "Low", discovery_level, adjusted_genres
        if adjustment == "More Familiar":
            return activity, mood, energy, "Familiar", genres
        if adjustment == "More New Artists":
            adjusted_genres = list(dict.fromkeys(["Indie", "Alternative", *genres]))
            return activity, mood, energy, "Exploratory", adjusted_genres
        if adjustment == "Different Genre":
            return activity, mood, energy, discovery_level, ["Jazz", "Soul", "World", "Electronic"]
        return activity, mood, energy, discovery_level, genres
