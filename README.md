# Spotify Review Intelligence Engine

Spotify Review Intelligence Engine downloads recent Android app reviews for
Spotify, collects public Reddit discussion pages, and prepares CSV datasets for
analysis.

## Project Structure

```text
spotify-review-engine/
|-- scraper.py
|-- clean_reviews.py
|-- reddit_scraper.py
|-- spotify_community_scraper.py
|-- merge_reviews.py
|-- base_scraper.py
|-- requirements.txt
|-- README.md
|-- data/
`-- output/
```

## Setup

Install the required Python packages:

```bash
pip install -r requirements.txt
```

## Download Google Play Reviews

Run the scraper from the project directory:

```bash
python scraper.py
```

The scraper downloads the latest 500 English United States reviews for the
Spotify Android app (`com.spotify.music`) and writes them to:

```text
data/spotify_reviews.csv
```

The CSV contains:

- Review text
- Rating
- Review date
- Thumbs up count
- App version

If downloading reviews fails, the script prints the exact exception type and
message, followed by likely causes such as network issues, Google Play
availability, package lookup problems, or an unexpected Google Play response.

## Clean Google Play Reviews

After downloading reviews, run:

```bash
python clean_reviews.py
```

The cleaner removes duplicate rows, removes rows with empty review text, strips
leading and trailing whitespace from reviews, and writes the result to:

```text
data/spotify_reviews_cleaned.csv
```

## Download Reddit Discussions

Run the no-auth public Reddit scraper:

```bash
python reddit_scraper.py
```

The Reddit scraper searches publicly available Reddit pages for:

- Spotify recommendations
- Discover Weekly
- Music discovery
- Repetitive recommendations
- Daily Mix

It extracts title, body, URL, and date when available. It tries direct public
Reddit search first, then falls back to public HTML search if direct scraping is
blocked. It removes duplicate URLs and writes:

```text
data/reddit_reviews.csv
```

No Reddit API credentials are required.

## Download Spotify Community Discussions

Run the official Spotify Community scraper:

```bash
python spotify_community_scraper.py
```

The scraper targets only `https://community.spotify.com/` and searches for
discussion pages about Discover Weekly, music discovery, recommendations, Daily
Mix, recommendation algorithms, playlists, new music, and recommended songs. It
extracts discussion title, body, board/category, author, date, and URL, then
removes duplicate URLs and writes:

```text
data/spotify_community_reviews.csv
```

The scraper does not use Spotify Community's blocked search endpoint. It uses
public search results restricted to the official Spotify Community domain, then
visits each discovered Community discussion page to extract the data.

## Merge Review Sources

After the source CSV files exist, create the master dataset:

```bash
python merge_reviews.py
```

The merger standardizes Play Store, Reddit, and Spotify Community records to:

- Review
- Source
- Rating
- Date
- URL

It removes duplicate review text and writes:

```text
data/master_reviews.csv
```

## Output

The `data/` directory stores raw and cleaned CSV files. The `output/` directory
is included for future analysis artifacts, reports, and visualizations.
