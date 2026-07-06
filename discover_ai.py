"""DiscoverAI Streamlit prototype.

Run with:
    streamlit run discover_ai.py
"""

from __future__ import annotations

import time

import streamlit as st

from discover_ai_config import (
    APP_NAME,
    DEFAULT_PROMPT,
    FEEDBACK_OPTIONS,
    PROMPT_CHIPS,
    TAGLINE,
    THINKING_MESSAGES,
)
from discover_ai_intent import IntentAnalyzer, IntentProfile
from discover_ai_recommendations import RecommendationEngine
from discover_ai_ui import (
    card,
    comparison_column,
    format_chip_label,
    format_feedback_label,
    hero,
    inject_styles,
    render_ideas_header,
    render_insight_panel,
    render_intent_profile,
    render_recommendation_card,
    render_sidebar_nav,
    render_step_card,
    section_heading,
    thinking_html,
)


st.set_page_config(
    page_title=APP_NAME,
    page_icon="DA",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_state() -> None:
    """Initialize Streamlit session state."""
    defaults = {
        "prompt": DEFAULT_PROMPT,
        "started": False,
        "profile": None,
        "recommendations": [],
        "feedback_mode": False,
        "last_adjustment": None,
        # UI-only state below: language preference is captured as another
        # facet of "current intent" and echoed back on recommendation cards.
        # It does not alter ranking — the recommendation engine is untouched.
        "language": "Auto",
        # UI-only state: per-card thumbs up/down, purely visual confirmation.
        "card_feedback": {},
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


@st.cache_resource(show_spinner=False)
def get_intent_analyzer() -> IntentAnalyzer:
    """Return a cached intent analyzer."""
    return IntentAnalyzer()


@st.cache_resource(show_spinner=False)
def get_recommendation_engine() -> RecommendationEngine:
    """Return a cached recommendation engine."""
    return RecommendationEngine()


def run_discovery(adjustment: str | None = None) -> None:
    """Analyze intent and generate recommendations."""
    thinking_placeholder = st.empty()
    total_steps = len(THINKING_MESSAGES)
    for step, message in enumerate(THINKING_MESSAGES, start=1):
        thinking_placeholder.markdown(thinking_html(message, step, total_steps), unsafe_allow_html=True)
        time.sleep(0.85)
    thinking_placeholder.empty()

    analyzer = get_intent_analyzer()
    engine = get_recommendation_engine()
    profile = analyzer.analyze(st.session_state.prompt, adjustment=adjustment)
    recommendations = engine.recommend(profile)

    st.session_state.profile = profile
    st.session_state.recommendations = recommendations
    st.session_state.started = True
    st.session_state.feedback_mode = False
    st.session_state.last_adjustment = adjustment
    st.session_state.card_feedback = {}


def render_prompt_chips() -> None:
    """Render clickable quick prompt chips, highlighting the active one."""
    chip_items = list(PROMPT_CHIPS.items())
    rows = [chip_items[index : index + 4] for index in range(0, len(chip_items), 4)]
    for row in rows:
        cols = st.columns(len(row))
        for col, (label, prompt_text) in zip(cols, row, strict=False):
            is_active = st.session_state.prompt.strip() == prompt_text.strip()
            with col:
                clicked = st.button(
                    format_chip_label(label),
                    use_container_width=True,
                    type="primary" if is_active else "secondary",
                    key=f"chip_{label}",
                )
                if clicked:
                    st.session_state.prompt = prompt_text
                    st.rerun()


def render_landing() -> None:
    """Render landing and first-time experience."""
    hero()
    card(
        "<h3>Spotify already knows what you've listened to.</h3>"
        "<p>DiscoverAI wants to know what you want to hear right now.</p>"
    )
    st.write("")

    with st.container(border=True):
        col_input, col_btn = st.columns([5, 1.4])
        with col_input:
            st.session_state.prompt = st.text_area(
                "Describe your current vibe",
                value=st.session_state.prompt,
                placeholder=DEFAULT_PROMPT,
                label_visibility="collapsed",
            )
        with col_btn:
            discover_clicked = st.button(
                "✨ Discover Music",
                use_container_width=True,
                type="primary",
            )

    if discover_clicked:
        if st.session_state.prompt.strip():
            run_discovery()
            st.rerun()
        else:
            st.warning("Describe a vibe or choose a quick prompt to begin.")

    st.write("")
    st.session_state.language = render_ideas_header(st.session_state.language)
    render_prompt_chips()

    render_insight_panel()

    if st.button("Start Discovering", use_container_width=True):
        run_discovery()
        st.rerun()


def render_results() -> None:
    """Render intent understanding, recommendations, and feedback."""
    profile: IntentProfile | None = st.session_state.profile
    if profile is None:
        render_landing()
        return

    st.markdown(f"<h1 style='margin-bottom:0.15rem;'>{APP_NAME}</h1>", unsafe_allow_html=True)
    st.caption(TAGLINE)

    st.subheader("What DiscoverAI understood")
    render_intent_profile(profile)

    st.write("")
    card(
        f"<h3>Intent Summary</h3><p>{profile.intent_summary}</p>"
        "<p>Instead of recommending songs you usually play, DiscoverAI selected tracks "
        "matching your current intent while introducing unfamiliar artists gradually.</p>"
    )

    st.write("")
    section_heading(
        "Handpicked for your",
        f"{profile.activity} moment",
        f"Matched to a {profile.mood.lower()} mood and {profile.energy.lower()} energy right now "
        "— not your listening history.",
    )

    recommendations = st.session_state.recommendations
    indexed = list(enumerate(recommendations))
    for row_start in range(0, len(indexed), 2):
        cols = st.columns(2)
        row_items = indexed[row_start : row_start + 2]
        for col, (idx, recommendation) in zip(cols, row_items, strict=False):
            with col:
                render_recommendation_card(recommendation, idx, st.session_state.language)

    st.write("")
    st.subheader("Did we understand your vibe?")
    col1, col2 = st.columns(2)
    if col1.button("✅ Perfect", use_container_width=True, type="primary"):
        st.success("Great. DiscoverAI will keep this balance for the next discovery session.")
    if col2.button("🔧 Needs Improvement", use_container_width=True):
        st.session_state.feedback_mode = True

    if st.session_state.feedback_mode:
        st.caption("Tune the discovery direction")
        feedback_cols = st.columns(len(FEEDBACK_OPTIONS))
        for col, option in zip(feedback_cols, FEEDBACK_OPTIONS, strict=False):
            with col:
                if st.button(format_feedback_label(option), use_container_width=True, key=f"fb_{option}"):
                    run_discovery(adjustment=option)
                    st.rerun()

    st.write("")
    if st.button("↺ Start Over", use_container_width=True):
        st.session_state.started = False
        st.session_state.feedback_mode = False
        st.rerun()


def render_about() -> None:
    """Render the About DiscoverAI page."""
    st.title("About DiscoverAI")
    card(
        "<h3>The Problem</h3>"
        "<p>Traditional recommendation systems rely mainly on historical listening behaviour. "
        "That can make discovery feel repetitive when the user's current context changes.</p>"
        "<h3>DiscoverAI</h3>"
        "<p>DiscoverAI understands current intent: mood, activity, context, energy and "
        "willingness to explore. The result is intent-driven discovery.</p>"
    )
    st.write("")
    col1, col2 = st.columns(2)
    with col1:
        comparison_column("Traditional Discovery", ["History", "Repeat Songs", "Manual Search"])
    with col2:
        comparison_column(
            "DiscoverAI",
            ["Intent", "AI Understanding", "Meaningful Discovery"],
            positive=True,
        )


def render_how_it_works() -> None:
    """Render the How It Works page."""
    st.title("How It Works")
    steps = [
        ("User Intent", "The user describes their current vibe in one short prompt."),
        ("AI Intent Analysis", "DiscoverAI extracts activity, mood, energy, genres and exploration level."),
        ("Recommendation Engine", "The engine ranks tracks against the current intent profile."),
        ("Explainable Recommendations", "Every recommendation explains why it matches the moment."),
        ("Feedback Loop", "The user can tune energy, familiarity, novelty or genre direction."),
    ]
    for number, (title, description) in enumerate(steps, start=1):
        render_step_card(number, title, description)


def render_shell() -> None:
    """Render navigation and selected app page."""
    inject_styles()
    init_state()

    page = render_sidebar_nav(["Experience", "About", "How It Works"])

    if page == "About":
        render_about()
    elif page == "How It Works":
        render_how_it_works()
    elif st.session_state.started:
        render_results()
    else:
        render_landing()


if __name__ == "__main__":
    render_shell()
