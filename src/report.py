# report.py
# Fetches and caches company metadata and news from Polygon

import os
import requests
import sqlite3
import pandas as pd
from datetime import datetime
from time import sleep
from dotenv import load_dotenv

load_dotenv()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "data", "market_data.sqlite")

# --- Create metadata and news tables ---
def ensure_tables_exist():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS company_metadata (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            description TEXT,
            updated_at TEXT
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS company_news (
            ticker TEXT,
            published_utc TEXT,
            headline TEXT,
            url TEXT,
            PRIMARY KEY (ticker, published_utc)
        )
        """)

# --- Fetch company metadata from Polygon ---
def fetch_company_metadata(ticker):
    url = f"https://api.polygon.io/v3/reference/tickers/{ticker.upper()}"
    params = {"apiKey": POLYGON_API_KEY}
    r = requests.get(url, params=params)
    r.raise_for_status()
    data = r.json().get("results", {})
    return {
        "ticker": ticker.upper(),
        "name": data.get("name"),
        "description": data.get("description"),
        "updated_at": datetime.utcnow().isoformat()
    }

# --- Fetch recent company news ---
def fetch_company_news(ticker, limit=5):
    url = f"https://api.polygon.io/v2/reference/news"
    params = {
        "ticker": ticker.upper(),
        "limit": limit,
        "order": "desc",
        "sort": "published_utc",
        "apiKey": POLYGON_API_KEY
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json().get("results", [])

# --- Cache metadata and news for a list of tickers ---
def cache_company_data(tickers):
    ensure_tables_exist()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        for i, ticker in enumerate(tickers):
            print(f"🔍 Fetching info for {ticker} ({i+1}/{len(tickers)})")

            # Check if metadata already cached
            cursor.execute("SELECT updated_at FROM company_metadata WHERE ticker = ?", (ticker,))
            meta_cached = cursor.fetchone()

            # Check if recent news exists (within last 7 days)
            one_week_ago = (datetime.utcnow() - pd.Timedelta(days=7)).isoformat()
            cursor.execute("SELECT COUNT(*) FROM company_news WHERE ticker = ? AND published_utc > ?", (ticker, one_week_ago))
            news_count = cursor.fetchone()[0]

            try:
                # Fetch metadata only if not already cached
                if not meta_cached:
                    meta = fetch_company_metadata(ticker)
                    cursor.execute("""
                        INSERT OR REPLACE INTO company_metadata (ticker, name, description, updated_at)
                        VALUES (:ticker, :name, :description, :updated_at)
                    """, meta)
                    sleep(12)

                # Fetch news only if no recent articles are found
                if news_count == 0:
                    news_items = fetch_company_news(ticker)
                    for item in news_items:
                        cursor.execute("""
                            INSERT OR IGNORE INTO company_news (ticker, published_utc, headline, url)
                            VALUES (?, ?, ?, ?)
                        """, (
                            ticker,
                            item.get("published_utc"),
                            item.get("title"),
                            item.get("article_url")
                        ))
                    sleep(12)
                meta = fetch_company_metadata(ticker)
                cursor.execute("""
                    INSERT OR REPLACE INTO company_metadata (ticker, name, description, updated_at)
                    VALUES (:ticker, :name, :description, :updated_at)
                """, meta)

                news_items = fetch_company_news(ticker)
                for item in news_items:
                    cursor.execute("""
                        INSERT OR IGNORE INTO company_news (ticker, published_utc, headline, url)
                        VALUES (?, ?, ?, ?)
                    """, (
                        ticker,
                        item.get("published_utc"),
                        item.get("title"),
                        item.get("article_url")
                    ))

                conn.commit()
                sleep(12)  # Respect Polygon's 5 req/min limit

            except Exception as e:
                print(f"❌ Error fetching {ticker}: {e}")
                continue

if __name__ == "__main__":
    cache_company_data(["AAPL", "MSFT", "GOOGL"])
