"""Streamlit dashboard for the Spotify AI Review Intelligence Platform.

The dashboard is fully data-driven. It reads only:
- data/master_reviews_ai.csv
- output/summary.json

All source, theme, sentiment, pain-point, and feature-request values are detected
from the dataset at runtime so future sources and categories work without code
changes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "master_reviews_ai.csv"
SUMMARY_PATH = BASE_DIR / "output" / "summary.json"

REQUIRED_COLUMNS = {
    "review",
    "source",
    "sentiment",
    "theme",
    "pain_point",
    "feature_request",
    "confidence_score",
}
OPTIONAL_COLUMNS = {"rating", "date", "url", "user_goal"}
TABLE_COLUMNS = [
    "review",
    "source",
    "theme",
    "sentiment",
    "pain_point",
    "feature_request",
    "confidence_score",
]

SPOTIFY_GREEN = "#1DB954"
SPOTIFY_DARK = "#121212"
PLOTLY_TEMPLATE = "plotly_dark"
MAX_TABLE_ROWS = 1000


st.set_page_config(
    page_title="Spotify AI Review Intelligence",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_css() -> None:
    """Apply a modern Spotify-inspired style that works in dark and light mode."""
    st.markdown(
        """
        <style>
        :root {
            --spotify-green: #1DB954;
            --soft-border: rgba(148, 163, 184, 0.22);
        }
        .block-container {
            padding-top: 1.4rem;
            padding-bottom: 2rem;
        }
        h1, h2, h3 {
            letter-spacing: 0;
        }
        div[data-testid="stMetric"] {
            border: 1px solid var(--soft-border);
            border-radius: 8px;
            padding: 1rem;
            background: linear-gradient(135deg, rgba(29,185,84,0.12), rgba(255,255,255,0.03));
        }
        .section-card {
            border: 1px solid var(--soft-border);
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
            background: rgba(255,255,255,0.025);
        }
        .opportunity-card {
            border-left: 4px solid var(--spotify-green);
            border-radius: 8px;
            padding: 1rem 1.1rem;
            margin-bottom: 1rem;
            border-top: 1px solid var(--soft-border);
            border-right: 1px solid var(--soft-border);
            border-bottom: 1px solid var(--soft-border);
            background: rgba(29,185,84,0.06);
        }
        .muted {
            opacity: 0.72;
            font-size: 0.92rem;
        }
        .quote {
            font-style: italic;
            opacity: 0.9;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def clean_text(value: object) -> str:
    """Normalize missing values and whitespace for display and filtering."""
    if pd.isna(value):
        return ""
    return " ".join(str(value).replace("\n", " ").split()).strip()


def dynamic_values(dataframe: pd.DataFrame, column: str) -> list[str]:
    """Return sorted non-empty values detected from a dataset column."""
    if column not in dataframe.columns:
        return []
    values = dataframe[column].map(clean_text)
    return sorted(value for value in values.unique().tolist() if value)


def count_unique_non_empty(dataframe: pd.DataFrame, column: str) -> int:
    """Count unique non-empty values in a column."""
    return len(dynamic_values(dataframe, column))


def value_counts_frame(dataframe: pd.DataFrame, column: str, limit: int | None = None) -> pd.DataFrame:
    """Build a reusable value-counts DataFrame for charts."""
    if column not in dataframe.columns or dataframe.empty:
        return pd.DataFrame(columns=[column, "count"])
    counts = dataframe[column].map(clean_text)
    counts = counts[counts != ""].value_counts().reset_index()
    counts.columns = [column, "count"]
    if limit:
        counts = counts.head(limit)
    return counts


def parse_dates(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Parse date column when present, preserving rows with invalid dates."""
    dataframe = dataframe.copy()
    if "date" not in dataframe.columns:
        dataframe["parsed_date"] = pd.NaT
        return dataframe
    dataframe["parsed_date"] = pd.to_datetime(dataframe["date"], errors="coerce", utc=True)
    return dataframe


@st.cache_data(show_spinner="Loading AI review intelligence data...")
def load_data() -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load the enriched review dataset and summary JSON."""
    if not DATA_PATH.exists():
        st.error(f"Missing required dataset: {DATA_PATH}")
        st.stop()
    if not SUMMARY_PATH.exists():
        st.error(f"Missing required summary file: {SUMMARY_PATH}")
        st.stop()

    dataframe = pd.read_csv(DATA_PATH)
    missing_columns = REQUIRED_COLUMNS - set(dataframe.columns)
    if missing_columns:
        st.error(f"Dataset is missing required columns: {', '.join(sorted(missing_columns))}")
        st.stop()

    for column in REQUIRED_COLUMNS | OPTIONAL_COLUMNS:
        if column not in dataframe.columns:
            dataframe[column] = ""

    text_columns = [
        "review",
        "source",
        "sentiment",
        "theme",
        "pain_point",
        "feature_request",
        "user_goal",
        "date",
        "url",
    ]
    for column in text_columns:
        dataframe[column] = dataframe[column].map(clean_text)

    dataframe["confidence_score"] = pd.to_numeric(
        dataframe["confidence_score"],
        errors="coerce",
    ).fillna(0.0).clip(0, 1)
    dataframe = parse_dates(dataframe)

    with SUMMARY_PATH.open("r", encoding="utf-8") as file:
        summary = json.load(file)

    return dataframe, summary


def apply_filters(
    dataframe: pd.DataFrame,
    sources: list[str] | None = None,
    themes: list[str] | None = None,
    sentiments: list[str] | None = None,
    date_range: tuple[pd.Timestamp, pd.Timestamp] | None = None,
    search_query: str = "",
) -> pd.DataFrame:
    """Apply dynamic filters to the review dataset."""
    filtered = dataframe.copy()

    if sources:
        filtered = filtered[filtered["source"].isin(sources)]
    if themes:
        filtered = filtered[filtered["theme"].isin(themes)]
    if sentiments:
        filtered = filtered[filtered["sentiment"].isin(sentiments)]
    if date_range and filtered["parsed_date"].notna().any():
        start_date, end_date = date_range
        start_ts = pd.Timestamp(start_date, tz="UTC")
        end_ts = pd.Timestamp(end_date, tz="UTC") + pd.Timedelta(days=1)
        filtered = filtered[
            filtered["parsed_date"].isna()
            | ((filtered["parsed_date"] >= start_ts) & (filtered["parsed_date"] < end_ts))
        ]
    if search_query:
        query = search_query.strip()
        searchable_columns = ["review", "pain_point", "feature_request", "theme", "source"]
        mask = pd.Series(False, index=filtered.index)
        for column in searchable_columns:
            mask = mask | filtered[column].str.contains(query, case=False, na=False, regex=False)
        filtered = filtered[mask]

    return filtered


def plot_bar(
    dataframe: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    orientation: str = "v",
) -> go.Figure:
    """Create a consistent Plotly bar chart."""
    if dataframe.empty:
        return empty_figure(title)
    figure = px.bar(
        dataframe,
        x=x,
        y=y,
        title=title,
        orientation=orientation,
        color=y if orientation == "h" else x,
        template=PLOTLY_TEMPLATE,
        color_discrete_sequence=px.colors.qualitative.Set3,
    )
    figure.update_layout(showlegend=False, margin=dict(l=20, r=20, t=55, b=20))
    return figure


def empty_figure(title: str) -> go.Figure:
    """Return an empty chart with a helpful message."""
    figure = go.Figure()
    figure.update_layout(
        title=title,
        template=PLOTLY_TEMPLATE,
        annotations=[
            dict(
                text="No data available",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=16),
            )
        ],
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return figure


def render_header() -> None:
    """Render the dashboard title and short product context."""
    st.title("Spotify AI Review Intelligence Platform")
    st.caption(
        "A dynamic product intelligence dashboard powered by enriched review data. "
        "Sources, themes, sentiments, pain points, and feature requests are detected automatically."
    )


def render_kpi_cards(dataframe: pd.DataFrame) -> None:
    """Render top-level KPI cards."""
    average_confidence = dataframe["confidence_score"].mean() if not dataframe.empty else 0
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Reviews", f"{len(dataframe):,}")
    col2.metric("Sources", count_unique_non_empty(dataframe, "source"))
    col3.metric("Themes", count_unique_non_empty(dataframe, "theme"))
    col4.metric("Pain Points", count_unique_non_empty(dataframe, "pain_point"))
    col5.metric("Feature Requests", count_unique_non_empty(dataframe, "feature_request"))
    st.progress(float(average_confidence), text=f"Average AI confidence: {average_confidence:.0%}")


def build_ai_insight_summary(dataframe: pd.DataFrame, summary: dict[str, Any]) -> str:
    """Build a data-driven executive insight paragraph."""
    if dataframe.empty:
        return "No review records are available for analysis."

    top_theme = dataframe["theme"].map(clean_text).value_counts().idxmax()
    top_sentiment = dataframe["sentiment"].map(clean_text).value_counts().idxmax()
    top_feature = dataframe["feature_request"].map(clean_text).value_counts().idxmax()
    total_reviews = summary.get("total_reviews", len(dataframe))

    return (
        f"The dataset contains {int(total_reviews):,} enriched reviews across "
        f"{count_unique_non_empty(dataframe, 'source')} detected source(s). The most common "
        f"sentiment is **{top_sentiment}**, the leading theme is **{top_theme}**, and the "
        f"most frequent product request is **{top_feature}**. Use the drill-down pages to "
        "inspect supporting reviews and identify product opportunities."
    )


def render_executive_summary(dataframe: pd.DataFrame, summary: dict[str, Any]) -> None:
    """Render the Executive Summary page."""
    render_kpi_cards(dataframe)
    st.subheader("AI Insight Summary")
    st.markdown(build_ai_insight_summary(dataframe, summary))

    col1, col2 = st.columns(2)
    with col1:
        sentiment_counts = value_counts_frame(dataframe, "sentiment")
        st.plotly_chart(
            plot_bar(sentiment_counts, "sentiment", "count", "Sentiment Overview"),
            use_container_width=True,
        )
    with col2:
        theme_counts = value_counts_frame(dataframe, "theme", limit=12)
        st.plotly_chart(
            plot_bar(theme_counts, "theme", "count", "Top Themes"),
            use_container_width=True,
        )


def render_sentiment_analysis(dataframe: pd.DataFrame) -> None:
    """Render the Sentiment Analysis page."""
    sentiment_counts = value_counts_frame(dataframe, "sentiment")

    col1, col2 = st.columns(2)
    with col1:
        pie = px.pie(
            sentiment_counts,
            names="sentiment",
            values="count",
            title="Sentiment Share",
            hole=0.45,
            template=PLOTLY_TEMPLATE,
            color_discrete_sequence=px.colors.qualitative.Set3,
        )
        st.plotly_chart(pie, use_container_width=True)
    with col2:
        st.plotly_chart(
            plot_bar(sentiment_counts, "sentiment", "count", "Sentiment Volume"),
            use_container_width=True,
        )

    by_source = dataframe.groupby(["source", "sentiment"], dropna=False).size().reset_index(name="count")
    stacked = px.bar(
        by_source,
        x="source",
        y="count",
        color="sentiment",
        title="Sentiment by Source",
        template=PLOTLY_TEMPLATE,
        color_discrete_sequence=px.colors.qualitative.Set3,
    )
    stacked.update_layout(margin=dict(l=20, r=20, t=55, b=20))
    st.plotly_chart(stacked, use_container_width=True)

    dated = dataframe[dataframe["parsed_date"].notna()].copy()
    if not dated.empty:
        dated["period"] = dated["parsed_date"].dt.to_period("M").astype(str)
        trend = dated.groupby(["period", "sentiment"]).size().reset_index(name="count")
        line = px.line(
            trend,
            x="period",
            y="count",
            color="sentiment",
            markers=True,
            title="Sentiment Trend",
            template=PLOTLY_TEMPLATE,
            color_discrete_sequence=px.colors.qualitative.Set3,
        )
        st.plotly_chart(line, use_container_width=True)
    else:
        st.info("Sentiment trend is unavailable because no valid dates were found.")


def render_theme_analysis(dataframe: pd.DataFrame) -> None:
    """Render the Theme Analysis page."""
    theme_counts = value_counts_frame(dataframe, "theme", limit=25)
    st.plotly_chart(
        plot_bar(theme_counts.sort_values("count"), "count", "theme", "Theme Frequency", orientation="h"),
        use_container_width=True,
    )

    by_source = dataframe.groupby(["source", "theme"], dropna=False).size().reset_index(name="count")
    heatmap = px.density_heatmap(
        by_source,
        x="source",
        y="theme",
        z="count",
        title="Theme by Source",
        template=PLOTLY_TEMPLATE,
        color_continuous_scale=["#121212", SPOTIFY_GREEN],
    )
    st.plotly_chart(heatmap, use_container_width=True)

    selected_theme = st.selectbox("Theme Drill-down", dynamic_values(dataframe, "theme"))
    theme_data = dataframe[dataframe["theme"] == selected_theme] if selected_theme else dataframe.head(0)

    col1, col2 = st.columns(2)
    col1.metric("Reviews in Theme", f"{len(theme_data):,}")
    col2.metric("Average Confidence", f"{theme_data['confidence_score'].mean():.0%}" if not theme_data.empty else "0%")

    st.subheader("Top Example Reviews")
    examples = theme_data.sort_values("confidence_score", ascending=False).head(10)
    st.dataframe(examples[TABLE_COLUMNS], use_container_width=True, hide_index=True)


def render_pain_points(dataframe: pd.DataFrame) -> None:
    """Render the Pain Points page."""
    selected_themes = st.multiselect("Filter by Theme", dynamic_values(dataframe, "theme"))
    filtered = dataframe[dataframe["theme"].isin(selected_themes)] if selected_themes else dataframe

    pain_counts = value_counts_frame(filtered, "pain_point", limit=30)
    st.plotly_chart(
        plot_bar(
            pain_counts.sort_values("count"),
            "count",
            "pain_point",
            "Most Common Pain Points",
            orientation="h",
        ),
        use_container_width=True,
    )

    search = st.text_input("Search pain points or reviews")
    table = apply_filters(filtered, search_query=search)
    st.dataframe(
        table[["pain_point", "theme", "source", "review", "confidence_score"]].head(MAX_TABLE_ROWS),
        use_container_width=True,
        hide_index=True,
    )
    if len(table) > MAX_TABLE_ROWS:
        st.caption(f"Showing first {MAX_TABLE_ROWS:,} of {len(table):,} matching rows.")


def render_feature_requests(dataframe: pd.DataFrame) -> None:
    """Render the Feature Requests page."""
    feature_counts = value_counts_frame(dataframe, "feature_request", limit=30)
    st.plotly_chart(
        plot_bar(
            feature_counts.sort_values("count"),
            "count",
            "feature_request",
            "Most Requested Features",
            orientation="h",
        ),
        use_container_width=True,
    )

    selected_feature = st.selectbox("Inspect Feature Request", dynamic_values(dataframe, "feature_request"))
    if selected_feature:
        examples = dataframe[dataframe["feature_request"] == selected_feature]
        st.metric("Supporting Reviews", f"{len(examples):,}")
        st.dataframe(
            examples[["review", "source", "theme", "sentiment", "pain_point", "confidence_score"]]
            .sort_values("confidence_score", ascending=False)
            .head(MAX_TABLE_ROWS),
            use_container_width=True,
            hide_index=True,
        )


def render_review_explorer(dataframe: pd.DataFrame) -> None:
    """Render the Review Explorer page with dynamic filters."""
    col1, col2, col3 = st.columns(3)
    sources = col1.multiselect("Source", dynamic_values(dataframe, "source"))
    themes = col2.multiselect("Theme", dynamic_values(dataframe, "theme"))
    sentiments = col3.multiselect("Sentiment", dynamic_values(dataframe, "sentiment"))

    date_range = None
    dated = dataframe[dataframe["parsed_date"].notna()]
    if not dated.empty:
        min_date = dated["parsed_date"].min().date()
        max_date = dated["parsed_date"].max().date()
        date_range = st.date_input("Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
        if not isinstance(date_range, tuple) or len(date_range) != 2:
            date_range = None

    search_query = st.text_input("Search reviews, pain points, features, themes, or sources")
    filtered = apply_filters(dataframe, sources, themes, sentiments, date_range, search_query)

    st.metric("Matching Reviews", f"{len(filtered):,}")
    st.dataframe(
        filtered[TABLE_COLUMNS].head(MAX_TABLE_ROWS),
        use_container_width=True,
        hide_index=True,
    )
    if len(filtered) > MAX_TABLE_ROWS:
        st.caption(f"Showing first {MAX_TABLE_ROWS:,} of {len(filtered):,} matching rows.")


def business_impact_label(support_count: int, total_reviews: int, average_confidence: float) -> str:
    """Create a data-driven business-impact label for an opportunity."""
    share = support_count / total_reviews if total_reviews else 0
    if share >= 0.1 and average_confidence >= 0.65:
        return "High impact: frequent, high-confidence customer signal."
    if share >= 0.04:
        return "Medium impact: meaningful recurring customer signal."
    return "Emerging impact: smaller signal worth monitoring."


def representative_quote(group: pd.DataFrame) -> str:
    """Select a concise representative quote from a group of reviews."""
    candidates = group.copy()
    candidates["review_length"] = candidates["review"].str.len()
    candidates = candidates.sort_values(["confidence_score", "review_length"], ascending=[False, True])
    quote = clean_text(candidates.iloc[0]["review"]) if not candidates.empty else ""
    return quote[:420] + ("..." if len(quote) > 420 else "")


def render_opportunity_cards(dataframe: pd.DataFrame) -> None:
    """Render automatically generated AI product opportunity cards."""
    if dataframe.empty:
        st.info("No records available for opportunity generation.")
        return

    grouped = (
        dataframe.groupby(["feature_request", "pain_point"], dropna=False)
        .agg(
            supporting_reviews=("review", "size"),
            average_confidence=("confidence_score", "mean"),
        )
        .reset_index()
        .sort_values(["supporting_reviews", "average_confidence"], ascending=False)
        .head(12)
    )

    total_reviews = len(dataframe)
    for _, row in grouped.iterrows():
        feature_request = clean_text(row["feature_request"]) or "Product improvement"
        pain_point = clean_text(row["pain_point"]) or "Unspecified customer pain point"
        support_count = int(row["supporting_reviews"])
        average_confidence = float(row["average_confidence"])
        group = dataframe[
            (dataframe["feature_request"] == row["feature_request"])
            & (dataframe["pain_point"] == row["pain_point"])
        ]

        st.markdown(
            f"""
            <div class="opportunity-card">
                <h3>{feature_request}</h3>
                <p><strong>Problem:</strong> {pain_point}</p>
                <p><strong>Evidence:</strong> {support_count:,} supporting review(s)</p>
                <p><strong>Suggested AI Feature:</strong> {feature_request}</p>
                <p><strong>Potential Business Impact:</strong> {business_impact_label(support_count, total_reviews, average_confidence)}</p>
                <p class="quote"><strong>Representative User Quote:</strong> "{representative_quote(group)}"</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_sidebar_navigation() -> str:
    """Render sidebar navigation and return the selected page."""
    st.sidebar.title("Navigation")
    pages = [
        "Executive Summary",
        "Sentiment Analysis",
        "Theme Analysis",
        "Pain Points",
        "Feature Requests",
        "Review Explorer",
        "AI Product Opportunities",
    ]
    return st.sidebar.radio("Page", pages)


def main() -> None:
    """Run the Streamlit dashboard."""
    inject_css()
    dataframe, summary = load_data()
    page = render_sidebar_navigation()

    render_header()

    with st.spinner("Preparing dashboard..."):
        if page == "Executive Summary":
            render_executive_summary(dataframe, summary)
        elif page == "Sentiment Analysis":
            render_sentiment_analysis(dataframe)
        elif page == "Theme Analysis":
            render_theme_analysis(dataframe)
        elif page == "Pain Points":
            render_pain_points(dataframe)
        elif page == "Feature Requests":
            render_feature_requests(dataframe)
        elif page == "Review Explorer":
            render_review_explorer(dataframe)
        elif page == "AI Product Opportunities":
            render_opportunity_cards(dataframe)


if __name__ == "__main__":
    main()
