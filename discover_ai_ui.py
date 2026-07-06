"""Reusable UI components for DiscoverAI.

This module owns the entire presentation layer: styling, layout primitives
and rendering helpers. It intentionally knows nothing about how intent is
inferred or how recommendations are ranked — it only ever receives finished
`IntentProfile` / `Recommendation` objects and renders them.

Design language: dark, editorial, Spotify-grade. The guiding product idea —
"this app understands what you want right now, not just what you've played
before" — is reinforced visually everywhere: the hero copy, the intent
cards, the section headings above recommendations, and the loading state.
"""

from __future__ import annotations

import html

import streamlit as st

from discover_ai_config import (
    APP_NAME,
    CHIP_ICONS,
    FEEDBACK_ICONS,
    LANGUAGES,
    NAV_ICONS,
    TAGLINE,
)
from discover_ai_intent import IntentProfile
from discover_ai_recommendations import Recommendation

# Small internal display maps. Purely cosmetic — not business logic.
_FIELD_ICONS = {
    "Activity": "🎯",
    "Mood": "🎭",
    "Energy": "⚡",
    "Discovery Level": "🧭",
    "Preferred Genres": "🎵",
}

_ENERGY_LEVELS = {"Low": 1, "Medium": 2, "High": 3}

_ART_GRADIENTS = [
    "linear-gradient(135deg,#1DB954 0%,#1F6FEB 60%,#8B5CF6 100%)",
    "linear-gradient(135deg,#F97362 0%,#C23FC2 55%,#5B5BE8 100%)",
    "linear-gradient(135deg,#00C2A8 0%,#1F6FEB 65%,#1DB954 100%)",
    "linear-gradient(135deg,#FFB84D 0%,#F9548A 55%,#8B5CF6 100%)",
    "linear-gradient(135deg,#5B5BE8 0%,#1DB954 65%,#00C2A8 100%)",
    "linear-gradient(135deg,#F9548A 0%,#8B5CF6 55%,#1F6FEB 100%)",
]


# ---------------------------------------------------------------------------
# Global styles
# ---------------------------------------------------------------------------


def inject_styles() -> None:
    """Inject the full DiscoverAI visual system."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Sora:wght@600;700;800&display=swap');

        :root{
            --green:#1DB954;
            --green-bright:#22E06B;
            --bg-0:#060607;
            --bg-1:#0D0E10;
            --surface:rgba(255,255,255,0.045);
            --surface-hover:rgba(255,255,255,0.075);
            --border:rgba(255,255,255,0.09);
            --border-strong:rgba(255,255,255,0.18);
            --text-1:#F5F6F7;
            --text-2:rgba(245,246,247,0.66);
            --text-3:rgba(245,246,247,0.40);
            --radius-s:10px;
            --radius-m:16px;
            --radius-l:22px;
            --radius-pill:999px;
            --ease:cubic-bezier(.16,1,.3,1);
            --shadow-card:0 20px 45px -20px rgba(0,0,0,0.55);
            --shadow-glow:0 0 0 1px rgba(29,185,84,0.35), 0 12px 32px -8px rgba(29,185,84,0.35);
        }

        html, body, [class*="css"]{
            font-family:'Manrope', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        /* ---------- App shell ---------- */
        .stApp{
            background:
                radial-gradient(circle at 12% -10%, rgba(29,185,84,0.16), transparent 38%),
                radial-gradient(circle at 88% 8%, rgba(139,92,246,0.10), transparent 40%),
                linear-gradient(180deg, var(--bg-0) 0%, var(--bg-1) 55%, #08090A 100%);
            color:var(--text-1);
        }
        #MainMenu, footer, header [data-testid="stToolbar"], [data-testid="stDecoration"]{
            visibility:hidden;
            height:0;
        }
        .block-container{
            max-width:1220px;
            padding-top:1.6rem;
            padding-bottom:4rem;
        }
        ::selection{ background:rgba(29,185,84,0.35); color:#fff; }
        *:focus-visible{ outline:2px solid var(--green); outline-offset:2px; }
        ::-webkit-scrollbar{ width:10px; height:10px; }
        ::-webkit-scrollbar-thumb{ background:rgba(255,255,255,0.14); border-radius:999px; }
        ::-webkit-scrollbar-thumb:hover{ background:rgba(255,255,255,0.24); }

        h1,h2,h3{ font-family:'Sora','Manrope',sans-serif; letter-spacing:-0.01em; }

        /* ---------- Sidebar ---------- */
        [data-testid="stSidebar"]{
            background:linear-gradient(180deg,#0A0B0C 0%, #08090A 100%);
            border-right:1px solid var(--border);
        }
        [data-testid="stSidebar"] .block-container{ padding-top:1.6rem; }

        .brand{ display:flex; align-items:center; gap:0.65rem; padding:0 0.2rem 1.6rem; }
        .brand-mark{
            width:38px; height:38px; border-radius:11px; flex-shrink:0;
            background:linear-gradient(135deg,var(--green) 0%, #14532d 130%);
            display:flex; align-items:center; justify-content:center;
            font-family:'Sora',sans-serif; font-weight:800; font-size:0.82rem; color:#06130A;
            box-shadow:0 8px 20px -6px rgba(29,185,84,0.55);
        }
        .brand-name{ font-family:'Sora',sans-serif; font-weight:700; font-size:1.02rem; color:var(--text-1); }
        .brand-name span{ color:var(--green-bright); }
        .brand-sub{ font-size:0.72rem; color:var(--text-3); letter-spacing:0.02em; }

        [data-testid="stSidebar"] [role="radiogroup"]{ gap:0.15rem; }
        [data-testid="stSidebar"] [role="radiogroup"] label{
            padding:0.55rem 0.75rem;
            border-radius:var(--radius-s);
            transition:background 0.18s var(--ease), color 0.18s var(--ease);
            width:100%;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label:hover{ background:var(--surface-hover); }
        [data-testid="stSidebar"] [role="radiogroup"] label[data-checked="true"],
        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){
            background:rgba(29,185,84,0.12);
            box-shadow:inset 2px 0 0 var(--green);
        }
        [data-testid="stSidebar"] [role="radiogroup"] p{ font-size:0.92rem; font-weight:600; }

        .ai-callout{
            margin-top:1.6rem;
            padding:1.1rem 1.1rem 1.25rem;
            border-radius:var(--radius-m);
            background:linear-gradient(160deg, rgba(29,185,84,0.14), rgba(139,92,246,0.08));
            border:1px solid rgba(29,185,84,0.28);
            position:relative;
            overflow:hidden;
        }
        .ai-callout-icon{ font-size:1.2rem; margin-bottom:0.35rem; }
        .ai-callout-title{ font-family:'Sora',sans-serif; font-weight:700; font-size:0.92rem; color:var(--text-1); margin-bottom:0.3rem; }
        .ai-callout-text{ font-size:0.78rem; line-height:1.45; color:var(--text-2); }
        .waveform{ display:flex; align-items:flex-end; gap:3px; height:22px; margin-top:0.85rem; opacity:0.85; }
        .waveform span{
            width:4px; border-radius:2px; background:var(--green-bright);
            animation:wave 1.4s ease-in-out infinite;
        }
        .waveform span:nth-child(1){ height:40%; animation-delay:0s; }
        .waveform span:nth-child(2){ height:80%; animation-delay:0.12s; }
        .waveform span:nth-child(3){ height:55%; animation-delay:0.24s; }
        .waveform span:nth-child(4){ height:95%; animation-delay:0.36s; }
        .waveform span:nth-child(5){ height:35%; animation-delay:0.48s; }
        .waveform span:nth-child(6){ height:70%; animation-delay:0.6s; }
        @keyframes wave{ 0%,100%{ transform:scaleY(0.4); } 50%{ transform:scaleY(1); } }

        /* ---------- Hero ---------- */
        .hero{ text-align:center; padding:2.2rem 1rem 0.4rem; animation:fadeUp 0.7s var(--ease) both; }
        .hero-badge{
            display:inline-flex; align-items:center; gap:0.4rem;
            padding:0.4rem 0.9rem; border-radius:var(--radius-pill);
            background:rgba(29,185,84,0.12); border:1px solid rgba(29,185,84,0.32);
            color:var(--green-bright); font-size:0.78rem; font-weight:700;
            letter-spacing:0.02em; margin-bottom:1.1rem;
        }
        .hero-title{
            font-size:clamp(2.4rem, 5.2vw, 4.1rem);
            font-weight:800; line-height:1.06; margin:0 0 0.75rem;
            color:var(--text-1);
        }
        .hero-title .grad{
            background:linear-gradient(120deg, var(--green-bright), #6EE7B7 45%, #1F6FEB 100%);
            -webkit-background-clip:text; background-clip:text; color:transparent;
        }
        .hero-sub{ font-size:1.1rem; color:var(--text-2); max-width:620px; margin:0 auto 0.35rem; }
        .hero-micro{ font-size:0.85rem; color:var(--text-3); font-style:italic; }

        /* ---------- Search shell ----------
           Scoped to the one real st.container(border=True) that directly
           holds a <textarea> — there is exactly one such container in the
           app (the prompt input), so this cannot leak onto other cards. */
        [data-testid="stVerticalBlockBorderWrapper"]:has(textarea){
            margin:1.9rem auto 0.9rem; max-width:900px;
            background:var(--surface) !important;
            border:1px solid var(--border-strong) !important;
            border-radius:var(--radius-l) !important;
            padding:0.4rem 0.6rem 0.4rem 1.1rem !important;
            transition:box-shadow 0.25s var(--ease), border-color 0.25s var(--ease);
            box-shadow:var(--shadow-card);
        }
        [data-testid="stVerticalBlockBorderWrapper"]:has(textarea:focus){
            border-color:rgba(29,185,84,0.55) !important;
            box-shadow:var(--shadow-glow), var(--shadow-card);
        }
        [data-testid="stVerticalBlockBorderWrapper"]:has(textarea) [data-testid="stHorizontalBlock"]{
            align-items:center; gap:0.6rem;
        }
        [data-testid="stVerticalBlockBorderWrapper"]:has(textarea) textarea{
            background:transparent !important; border:none !important;
            color:var(--text-1) !important; font-size:1.02rem !important;
            min-height:52px !important; padding:0.5rem 0 !important;
            box-shadow:none !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"]:has(textarea) textarea::placeholder{ color:var(--text-3); }

        .ideas-row{ display:flex; align-items:center; justify-content:space-between; max-width:900px; margin:0 auto; padding:0 0.2rem; }
        .ideas-label{ font-size:0.82rem; font-weight:700; color:var(--text-2); text-transform:uppercase; letter-spacing:0.06em; }

        .lang-wrap [data-testid="stSelectbox"] > div > div{
            background:var(--surface); border:1px solid var(--border);
            border-radius:var(--radius-pill); min-height:0;
        }
        .lang-wrap label{ font-size:0.72rem !important; color:var(--text-3) !important; }

        /* ---------- Buttons (global) ---------- */
        .stButton > button, .stLinkButton > a{
            border-radius:var(--radius-pill) !important;
            font-weight:700 !important;
            transition:transform 0.15s var(--ease), box-shadow 0.15s var(--ease), background 0.15s var(--ease) !important;
            border:1px solid var(--border-strong) !important;
        }
        .stButton > button:hover, .stLinkButton > a:hover{ transform:translateY(-1px); }
        .stButton > button:active{ transform:translateY(0px) scale(0.98); }

        div[data-testid="stButton"] button[kind="secondary"]{
            background:var(--surface) !important; color:var(--text-1) !important;
        }
        div[data-testid="stButton"] button[kind="secondary"]:hover{
            background:var(--surface-hover) !important; border-color:rgba(29,185,84,0.4) !important;
        }
        div[data-testid="stButton"] button[kind="primary"]{
            background:linear-gradient(135deg, var(--green-bright), var(--green)) !important;
            color:#052312 !important; border:none !important;
        }
        div[data-testid="stButton"] button[kind="primary"]:hover{
            box-shadow:0 10px 24px -6px rgba(29,185,84,0.55) !important;
        }
        .stLinkButton > a{
            background:rgba(29,185,84,0.12) !important; color:var(--green-bright) !important;
            border-color:rgba(29,185,84,0.35) !important; justify-content:center !important;
        }
        .stLinkButton > a:hover{ background:rgba(29,185,84,0.2) !important; }

        /* ---------- Insight panel ---------- */
        .insight-panel{
            display:flex; align-items:center; gap:1.6rem;
            background:linear-gradient(120deg, rgba(29,185,84,0.09), rgba(139,92,246,0.06));
            border:1px solid rgba(29,185,84,0.22);
            border-radius:var(--radius-l);
            padding:1.5rem 1.8rem;
            margin:1.6rem 0 2rem;
        }
        .insight-icon{
            width:46px; height:46px; border-radius:14px; flex-shrink:0;
            background:rgba(29,185,84,0.16); display:flex; align-items:center; justify-content:center;
            font-size:1.3rem;
        }
        .insight-copy h3{ font-size:1.15rem; margin:0 0 0.35rem; color:var(--text-1); }
        .insight-copy p{ font-size:0.92rem; color:var(--text-2); line-height:1.55; margin:0; }
        .insight-visual{ margin-left:auto; opacity:0.9; flex-shrink:0; }
        @media (max-width:900px){ .insight-visual{ display:none; } }

        /* ---------- Section heading ---------- */
        .section-heading{ display:flex; align-items:baseline; justify-content:space-between; flex-wrap:wrap; gap:0.5rem; margin:0.4rem 0 1.1rem; }
        .section-heading h2{ font-size:1.5rem; margin:0; }
        .section-heading .grad{
            background:linear-gradient(120deg, var(--green-bright), #6EE7B7);
            -webkit-background-clip:text; background-clip:text; color:transparent;
        }
        .section-heading p{ margin:0.25rem 0 0; color:var(--text-2); font-size:0.92rem; width:100%; }

        /* ---------- Generic card ---------- */
        .card{
            border:1px solid var(--border); border-radius:var(--radius-m);
            padding:1.3rem 1.4rem; background:var(--surface);
            box-shadow:var(--shadow-card);
        }
        .card h3{ margin-top:0; font-size:1.1rem; }
        .card p{ color:var(--text-2); font-size:0.94rem; line-height:1.6; }

        /* ---------- Intent profile ---------- */
        .intent-card{
            border:1px solid var(--border); border-radius:var(--radius-m);
            padding:1.05rem 1.1rem; background:var(--surface);
            transition:border-color 0.2s var(--ease), transform 0.2s var(--ease);
            animation:fadeUp 0.5s var(--ease) both;
        }
        .intent-card:hover{ border-color:rgba(29,185,84,0.35); transform:translateY(-2px); }
        .intent-icon{ font-size:1.05rem; margin-bottom:0.5rem; }
        .small-label{ color:var(--text-3); font-size:0.7rem; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:0.3rem; }
        .big-value{ font-size:1.08rem; font-weight:700; color:var(--text-1); }
        .energy-meter{ display:flex; gap:4px; margin-top:0.55rem; }
        .energy-meter span{ height:5px; flex:1; border-radius:3px; background:rgba(255,255,255,0.1); }
        .energy-meter span.filled{ background:linear-gradient(90deg, var(--green), var(--green-bright)); }

        /* ---------- Recommendation cards ----------
           Scoped to the one real st.container(border=True) that directly
           holds our own `.rec-art` marker. Each card gets exactly one such
           container (never nested inside another bordered container), so
           this selector cannot leak onto unrelated sections of the page. */
        [data-testid="stVerticalBlockBorderWrapper"]:has(.rec-art){
            border:1px solid var(--border) !important; border-radius:var(--radius-l) !important;
            background:var(--surface) !important;
            padding:1.2rem 1.2rem 0.9rem !important;
            box-shadow:var(--shadow-card);
            transition:transform 0.22s var(--ease), border-color 0.22s var(--ease), box-shadow 0.22s var(--ease);
            margin-bottom:1.3rem;
            animation:fadeUp 0.55s var(--ease) both;
        }
        [data-testid="stVerticalBlockBorderWrapper"]:has(.rec-art):hover{
            transform:translateY(-4px);
            border-color:rgba(29,185,84,0.4) !important;
            box-shadow:0 26px 55px -20px rgba(0,0,0,0.6), 0 0 0 1px rgba(29,185,84,0.2);
        }
        .rec-top{ display:flex; gap:1rem; align-items:flex-start; margin-bottom:0.85rem; }
        .rec-art-link{ text-decoration:none; flex-shrink:0; }
        .rec-art{
            width:84px; height:84px; border-radius:14px; position:relative;
            display:flex; align-items:center; justify-content:center;
            color:#fff; font-family:'Sora',sans-serif; font-weight:800; font-size:1.3rem;
            overflow:hidden; box-shadow:0 10px 24px -8px rgba(0,0,0,0.55);
        }
        .rec-art-play{
            position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
            background:rgba(0,0,0,0.42); opacity:0; transition:opacity 0.2s var(--ease);
            font-size:1.4rem;
        }
        .rec-art:hover .rec-art-play{ opacity:1; }
        .rec-head-row{ display:flex; justify-content:space-between; gap:0.6rem; align-items:flex-start; }
        .rec-title{ font-size:1.08rem; font-weight:800; color:var(--text-1); line-height:1.3; }
        .rec-artist{ color:var(--text-2); font-size:0.88rem; margin-top:0.1rem; }
        .rec-lang-tag{
            flex-shrink:0; font-size:0.72rem; font-weight:700; color:var(--text-2);
            background:rgba(255,255,255,0.06); border:1px solid var(--border);
            border-radius:var(--radius-pill); padding:0.2rem 0.55rem; white-space:nowrap;
        }
        .rec-desc{ font-size:0.88rem; color:var(--text-2); line-height:1.55; margin:0.2rem 0 0.7rem; }
        .rec-why{
            border-left:2px solid var(--green); padding-left:0.7rem;
            font-size:0.85rem; color:rgba(255,255,255,0.9); line-height:1.55; margin-bottom:0.75rem;
        }
        .rec-why b{ display:block; color:var(--green-bright); font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:0.15rem; }
        .rec-genres{ display:flex; flex-wrap:wrap; gap:0.4rem; margin-bottom:0.9rem; }
        .genre-pill{
            font-size:0.72rem; color:var(--text-2); background:rgba(255,255,255,0.05);
            border:1px solid var(--border); border-radius:var(--radius-pill); padding:0.18rem 0.6rem;
        }
        .rec-feedback-note{ font-size:0.76rem; color:var(--green-bright); margin-top:0.4rem; }

        /* ---------- Thinking / loading state ---------- */
        .thinking-panel{
            max-width:560px; margin:2.4rem auto; text-align:center;
            padding:2rem 1.6rem; border:1px solid var(--border); border-radius:var(--radius-l);
            background:var(--surface); animation:fadeUp 0.4s var(--ease) both;
        }
        .thinking-orb{
            width:54px; height:54px; margin:0 auto 1.1rem; border-radius:50%;
            background:conic-gradient(var(--green-bright), #1F6FEB, #8B5CF6, var(--green-bright));
            animation:spin 1.1s linear infinite;
            -webkit-mask:radial-gradient(farthest-side, transparent calc(100% - 6px), #000 calc(100% - 6px));
                    mask:radial-gradient(farthest-side, transparent calc(100% - 6px), #000 calc(100% - 6px));
        }
        .thinking-text{ font-size:1rem; font-weight:600; color:var(--text-1); margin-bottom:1rem; }
        .thinking-bar{ height:4px; border-radius:3px; background:rgba(255,255,255,0.08); overflow:hidden; }
        .thinking-bar-fill{
            height:100%; border-radius:3px;
            background:linear-gradient(90deg, var(--green), var(--green-bright));
            transition:width 0.6s var(--ease);
        }

        /* ---------- Comparison / steps ---------- */
        .comparison-step{
            padding:0.85rem 1rem; border-radius:var(--radius-m);
            background:var(--surface); border:1px solid var(--border);
            text-align:center; font-weight:700; color:var(--text-1);
            transition:border-color 0.2s var(--ease);
        }
        .comparison-step.positive{ border-color:rgba(29,185,84,0.35); }
        .comparison-arrow{ text-align:center; color:var(--text-3); font-size:0.85rem; margin:0.3rem 0; }

        .step-card{ display:flex; gap:1rem; align-items:flex-start; padding:1.1rem 1.2rem; border:1px solid var(--border); border-radius:var(--radius-m); background:var(--surface); margin-bottom:0.85rem; }
        .step-badge{
            width:34px; height:34px; border-radius:10px; flex-shrink:0;
            background:rgba(29,185,84,0.15); color:var(--green-bright);
            display:flex; align-items:center; justify-content:center; font-weight:800; font-family:'Sora',sans-serif;
        }
        .step-card h3{ margin:0 0 0.25rem; font-size:1.02rem; }
        .step-card p{ margin:0; font-size:0.9rem; color:var(--text-2); line-height:1.55; }

        /* ---------- Animations ---------- */
        @keyframes fadeUp{ from{ opacity:0; transform:translateY(10px);} to{ opacity:1; transform:translateY(0);} }
        @keyframes spin{ to{ transform:rotate(360deg); } }

        @media (max-width:768px){
            .hero{ padding-top:1rem; }
            .insight-panel{ flex-direction:column; align-items:flex-start; text-align:left; }
            .rec-top{ flex-wrap:wrap; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Sidebar / navigation
# ---------------------------------------------------------------------------


def render_sidebar_nav(pages: list[str], key: str = "nav_choice") -> str:
    """Render the branded sidebar navigation and return the selected page."""
    # Derive the "AI" suffix highlight dynamically from APP_NAME so the
    # brand mark never drifts out of sync with discover_ai_config.py.
    if APP_NAME.endswith("AI") and len(APP_NAME) > 2:
        brand_base, brand_suffix = APP_NAME[:-2], APP_NAME[-2:]
    else:
        brand_base, brand_suffix = APP_NAME, ""

    st.sidebar.markdown(
        f"""
        <div class="brand">
            <div class="brand-mark">AI</div>
            <div>
                <div class="brand-name">{html.escape(brand_base)}<span>{html.escape(brand_suffix)}</span></div>
                <div class="brand-sub">Intent-driven discovery</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    labeled_options = [f"{NAV_ICONS.get(page, '•')}  {page}" for page in pages]
    choice = st.sidebar.radio(
        "Navigation",
        labeled_options,
        label_visibility="collapsed",
        key=key,
    )
    selected = pages[labeled_options.index(choice)]

    st.sidebar.markdown(
        """
        <div class="ai-callout">
            <div class="ai-callout-icon">✨</div>
            <div class="ai-callout-title">AI-Powered Discovery</div>
            <div class="ai-callout-text">
                Matched to what you want to hear right now &mdash; not just
                what you've played before.
            </div>
            <div class="waveform">
                <span></span><span></span><span></span><span></span><span></span><span></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return selected


# ---------------------------------------------------------------------------
# Landing / hero
# ---------------------------------------------------------------------------


def hero() -> None:
    """Render the DiscoverAI hero section."""
    st.markdown(
        f"""
        <div class="hero">
            <div class="hero-badge">✨ Intent-Driven Discovery</div>
            <h1 class="hero-title">What do you want<br/>to <span class="grad">listen to</span> right now?</h1>
            <p class="hero-sub">{html.escape(TAGLINE)}</p>
            <p class="hero-micro">Not your history. Not your habits. Just this moment.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_language_selector(current: str, key: str = "language_pref") -> str:
    """Render a compact, optional language-preference selector."""
    st.markdown('<div class="lang-wrap">', unsafe_allow_html=True)
    options = list(LANGUAGES.keys())
    index = options.index(current) if current in options else 0
    choice = st.selectbox(
        "Discover in",
        options,
        index=index,
        format_func=lambda code: f"{LANGUAGES[code]}  {code}",
        key=key,
    )
    st.markdown("</div>", unsafe_allow_html=True)
    return choice


def render_ideas_header(current_language: str) -> str:
    """Render the 'Try these ideas' row with an inline language selector."""
    col_label, col_lang = st.columns([3, 1.3])
    with col_label:
        st.markdown(
            '<div class="ideas-row"><span class="ideas-label">Try these ideas</span></div>',
            unsafe_allow_html=True,
        )
    with col_lang:
        return render_language_selector(current_language)


def format_chip_label(label: str) -> str:
    """Attach an icon to a quick-prompt chip label."""
    icon = CHIP_ICONS.get(label, "🎧")
    return f"{icon}  {label}"


def format_feedback_label(label: str) -> str:
    """Attach an icon to a feedback-tuning chip label."""
    icon = FEEDBACK_ICONS.get(label, "🎚️")
    return f"{icon}  {label}"


def render_insight_panel() -> None:
    """Render the 'why DiscoverAI exists' value-proposition panel."""
    st.markdown(
        """
        <div class="insight-panel">
            <div class="insight-icon">💡</div>
            <div class="insight-copy">
                <h3>Why DiscoverAI?</h3>
                <p>Most recommendation engines look backward, ranking songs you've already
                played. DiscoverAI reads your mood, activity and energy <strong>right now</strong>
                so discovery keeps up with how you actually feel today &mdash; no repeats,
                no autopilot suggestions.</p>
            </div>
            <div class="insight-visual">
                <svg width="120" height="70" viewBox="0 0 120 70" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M2 46C14 20 24 60 36 40C48 20 56 55 68 35C80 15 90 50 102 30" stroke="#1DB954" stroke-width="2" opacity="0.55" stroke-linecap="round"/>
                    <path d="M2 55C16 35 26 62 40 48C54 34 62 58 74 44C86 30 96 52 108 40" stroke="#8B5CF6" stroke-width="2" opacity="0.45" stroke-linecap="round"/>
                    <circle cx="102" cy="30" r="4" fill="#1DB954"/>
                    <circle cx="108" cy="40" r="3" fill="#8B5CF6"/>
                </svg>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_heading(prefix: str, highlight: str, subtitle: str) -> None:
    """Render a two-tone section heading with a supporting subtitle."""
    st.markdown(
        f"""
        <div class="section-heading">
            <h2>{html.escape(prefix)} <span class="grad">{html.escape(highlight)}</span></h2>
            <p>{html.escape(subtitle)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Generic card
# ---------------------------------------------------------------------------


def card(markdown: str) -> None:
    """Render a styled content card."""
    st.markdown(f'<div class="card">{markdown}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Loading state
# ---------------------------------------------------------------------------


def thinking_html(message: str, step: int, total: int) -> str:
    """Return HTML markup for the animated 'thinking' loading state."""
    progress_pct = int((step / max(total, 1)) * 100)
    return f"""
    <div class="thinking-panel">
        <div class="thinking-orb"></div>
        <div class="thinking-text">{html.escape(message)}</div>
        <div class="thinking-bar"><div class="thinking-bar-fill" style="width:{progress_pct}%"></div></div>
    </div>
    """


# ---------------------------------------------------------------------------
# Intent understanding
# ---------------------------------------------------------------------------


def render_intent_profile(profile: IntentProfile) -> None:
    """Render structured intent-understanding cards with an energy meter."""
    fields = [
        ("Activity", profile.activity),
        ("Mood", profile.mood),
        ("Energy", profile.energy),
        ("Discovery Level", profile.discovery_level),
        ("Preferred Genres", ", ".join(profile.preferred_genres)),
    ]
    cols = st.columns(len(fields))
    for position, (col, (label, value)) in enumerate(zip(cols, fields, strict=False)):
        with col:
            meter = ""
            if label == "Energy":
                filled = _ENERGY_LEVELS.get(value, 2)
                bars = "".join(
                    f'<span class="{"filled" if i < filled else ""}"></span>' for i in range(3)
                )
                meter = f'<div class="energy-meter">{bars}</div>'
            st.markdown(
                f"""
                <div class="intent-card" style="animation-delay:{position * 0.06:.2f}s">
                    <div class="intent-icon">{_FIELD_ICONS.get(label, "🔎")}</div>
                    <div class="small-label">{html.escape(label)}</div>
                    <div class="big-value">{html.escape(value)}</div>
                    {meter}
                </div>
                """,
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Recommendation cards
# ---------------------------------------------------------------------------


def render_recommendation_card(
    recommendation: Recommendation,
    index: int,
    language: str,
) -> None:
    """Render one recommendation card with art, explanation and actions.

    Everything — the decorative HTML (art/title/why) and the real Streamlit
    widgets (Open in Spotify, thumbs up/down) — lives inside a single
    `st.container(border=True)`. That's a real, public Streamlit layout
    primitive (not a markup hack), so the card renders as one true bordered
    box regardless of Streamlit version. CSS then re-skins that native
    border into the premium look via a selector scoped to this exact card
    (`:has(.rec-art)`), which cannot leak onto unrelated containers.
    """
    initials = "".join(part[0] for part in recommendation.song_name.split()[:2]).upper()
    gradient = _ART_GRADIENTS[index % len(_ART_GRADIENTS)]
    flag = LANGUAGES.get(language, "🌍")
    lang_display = "Auto · English" if language == "Auto" else language
    genre_pills = "".join(
        f'<span class="genre-pill">{html.escape(genre)}</span>' for genre in recommendation.genres[:3]
    )

    with st.container(border=True):
        st.markdown(
            f"""
            <div class="rec-top">
                <a class="rec-art-link" href="{recommendation.spotify_search_url}" target="_blank" rel="noopener">
                    <div class="rec-art" style="background:{gradient}">
                        {html.escape(initials)}
                        <div class="rec-art-play">▶</div>
                    </div>
                </a>
                <div style="flex:1; min-width:0;">
                    <div class="rec-head-row">
                        <div>
                            <div class="rec-title">{html.escape(recommendation.song_name)}</div>
                            <div class="rec-artist">{html.escape(recommendation.artist)}</div>
                        </div>
                        <div class="rec-lang-tag">{flag} {html.escape(lang_display)}</div>
                    </div>
                    <p class="rec-desc">{html.escape(recommendation.description)}</p>
                </div>
            </div>
            <div class="rec-why"><b>Why this recommendation</b>{html.escape(recommendation.why)}</div>
            <div class="rec-genres">{genre_pills}</div>
            """,
            unsafe_allow_html=True,
        )

        action_cols = st.columns([2.4, 1, 1])
        with action_cols[0]:
            st.link_button("🎧 Open in Spotify", recommendation.spotify_search_url, use_container_width=True)
        with action_cols[1]:
            if st.button("👍", key=f"rec_up_{index}", use_container_width=True):
                st.session_state.card_feedback[index] = "up"
        with action_cols[2]:
            if st.button("👎", key=f"rec_down_{index}", use_container_width=True):
                st.session_state.card_feedback[index] = "down"

        feedback = st.session_state.get("card_feedback", {}).get(index)
        if feedback == "up":
            st.markdown('<div class="rec-feedback-note">✓ Noted &mdash; more like this next time.</div>', unsafe_allow_html=True)
        elif feedback == "down":
            st.markdown('<div class="rec-feedback-note">✓ Noted &mdash; we\'ll steer away from this.</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# About / How it works
# ---------------------------------------------------------------------------


def comparison_column(title: str, steps: list[str], positive: bool = False) -> None:
    """Render a vertical comparison flow (Traditional vs DiscoverAI)."""
    st.markdown(f"<h3>{html.escape(title)}</h3>", unsafe_allow_html=True)
    css_class = "comparison-step positive" if positive else "comparison-step"
    for i, step in enumerate(steps):
        st.markdown(f'<div class="{css_class}">{html.escape(step)}</div>', unsafe_allow_html=True)
        if i != len(steps) - 1:
            st.markdown('<div class="comparison-arrow">↓</div>', unsafe_allow_html=True)


def render_step_card(number: int, title: str, description: str) -> None:
    """Render one numbered step card for the How It Works page."""
    st.markdown(
        f"""
        <div class="step-card">
            <div class="step-badge">{number}</div>
            <div>
                <h3>{html.escape(title)}</h3>
                <p>{html.escape(description)}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
