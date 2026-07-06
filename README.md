# DiscoverAI – AI-Powered Music Discovery Intelligence for Spotify

DiscoverAI is an AI-powered product research and recommendation system built to understand why Spotify users struggle with music discovery. The project combines large-scale AI review analysis with user research to identify the root cause of repetitive listening and demonstrates an AI-native MVP that recommends music based on user intent rather than listening history.

---

## 🚀 Live Applications

### 🎵 DiscoverAI MVP
https://discoverai-mvp.streamlit.app/

### 📊 DiscoverAI Insights Dashboard
https://discoverai-dashboard.streamlit.app/

### 💻 GitHub Repository
https://github.com/Prince12849/Spotify-review-intelligence-engine

---

## 📌 Problem Statement

Spotify aims to increase meaningful music discovery while reducing repetitive listening behaviour. Despite having one of the world's most sophisticated recommendation systems, users continue listening to familiar artists, repeat playlists, and previously discovered tracks.

This project investigates why discovery breaks before proposing an AI-native solution.

---

## 💡 Solution Overview

### DiscoverAI Insights

An AI-powered review intelligence engine that collects user feedback from multiple public sources, extracts themes and sentiment, and identifies recurring pain points through an interactive dashboard.

**Sources:**
- Google Play Store
- Apple App Store
- Reddit
- Spotify Community
- YouTube

**Dataset:** 1,393 public reviews across 5 sources.

---

### DiscoverAI

DiscoverAI is an AI-native music discovery assistant that recommends songs based on:

- Mood
- Activity
- Preferred Language
- Energy Level
- Listening Intent

Unlike traditional recommendation systems that rely primarily on listening history, DiscoverAI focuses on understanding **why** a user wants music in the current moment.

---

## 🤖 AI Workflow

Google Play Reviews
↓
Apple App Store Reviews
↓
Reddit Discussions
↓
Spotify Community
↓
YouTube Comments
↓
Merge Reviews
↓
AI Review Engine
↓
Interactive Dashboard
↓
User Research
↓
DiscoverAI MVP

---

## ✨ Features

- Multi-source review collection
- AI sentiment analysis
- Theme detection
- Pain point extraction
- Interactive analytics dashboard
- AI-native recommendation engine
- Explainable recommendations
- Multilingual recommendations
- Live deployment

---

## 🛠 Tech Stack

- Python
- Streamlit
- Pandas
- Plotly
- OpenAI API (Rule-based fallback)
- Google Play Scraper
- PRAW (Reddit API)
- BeautifulSoup
- Requests

---

## 📂 Project Structure

```
spotify-review-engine/
│
├── dashboard.py
├── discover_ai.py
├── ai_review_engine.py
├── merge_reviews.py
├── data/
├── output/
├── requirements.txt
└── README.md
```

---

## ▶️ Run Locally

```bash
pip install -r requirements.txt

python merge_reviews.py

python ai_review_engine.py

streamlit run dashboard.py

streamlit run discover_ai.py
```

---

## 🔮 Future Improvements

- Spotify API integration
- LLM-powered recommendation reasoning
- Real-time personalization
- RAG-powered music exploration
- Continuous learning from user feedback

---

## 📄 Project Deliverables

- ✅ AI Review Discovery Engine
- ✅ AI Insights Dashboard
- ✅ User Research
- ✅ Root Cause Analysis
- ✅ AI-native MVP
- ✅ Live Deployment
