"""Configuration for the DiscoverAI Streamlit prototype."""

from __future__ import annotations


APP_NAME = "DiscoverAI"
TAGLINE = "Describe your vibe. We'll handle the discovery."
DEFAULT_PROMPT = "I'm coding for the next 3 hours..."

OPENAI_MODEL = "gpt-4o-mini"
MAX_RECOMMENDATIONS = 6

THINKING_MESSAGES = (
    "Understanding your mood...",
    "Finding your intent...",
    "Balancing familiarity with discovery...",
    "Looking beyond your usual favourites...",
    "Finding hidden gems...",
)

PROMPT_CHIPS = {
    "Coding": "I'm coding for the next 3 hours and need focused music with minimal vocals.",
    "Workout": "I need high-energy music for a tough workout.",
    "Coffee Break": "I'm taking a coffee break and want something warm, relaxed and fresh.",
    "Road Trip": "I'm going on a road trip and want music that feels open and energetic.",
    "Party": "I'm hosting friends and need upbeat music that keeps the room moving.",
    "Relax": "I want to relax and decompress without anything too intense.",
    "Rainy Evening": "It's a rainy evening and I want cozy, reflective music.",
    "Surprise Me": "Surprise me with something I would not normally find on my own.",
}

FEEDBACK_OPTIONS = (
    "More Energy",
    "More Calm",
    "More Familiar",
    "More New Artists",
    "Different Genre",
)


# ---------------------------------------------------------------------------
# Presentation-only data below. Nothing here touches intent analysis or
# recommendation logic — it only decorates existing values for the UI layer
# (icons, flags, copy). Safe to extend without affecting business logic.
# ---------------------------------------------------------------------------

# Quick-prompt chip icons, keyed to the existing PROMPT_CHIPS labels.
CHIP_ICONS: dict[str, str] = {
    "Coding": "💻",
    "Workout": "🏃",
    "Coffee Break": "☕",
    "Road Trip": "🚗",
    "Party": "🎉",
    "Relax": "😌",
    "Rainy Evening": "🌧️",
    "Surprise Me": "🎲",
}

# Feedback tuning icons, keyed to the existing FEEDBACK_OPTIONS labels.
FEEDBACK_ICONS: dict[str, str] = {
    "More Energy": "🔥",
    "More Calm": "🌙",
    "More Familiar": "🔁",
    "More New Artists": "🌱",
    "Different Genre": "🎼",
}

# Sidebar navigation icons, keyed to page names used in discover_ai.py.
NAV_ICONS: dict[str, str] = {
    "Experience": "🏠",
    "About": "💡",
    "How It Works": "🧭",
}

# Language preference options. Purely a UI/intent-capture layer — language is
# treated as another dimension of "what the user wants right now", alongside
# mood, activity and energy. "Auto" lets DiscoverAI infer from the prompt.
LANGUAGES: dict[str, str] = {
    "Auto": "🌍",
    "English": "🇬🇧",
    "Hindi": "🇮🇳",
    "Tamil": "🇮🇳",
    "Telugu": "🇮🇳",
    "Kannada": "🇮🇳",
    "Malayalam": "🇮🇳",
    "Bengali": "🇧🇩",
    "Punjabi": "🇮🇳",
    "Korean": "🇰🇷",
    "Japanese": "🇯🇵",
    "Spanish": "🇪🇸",
}
