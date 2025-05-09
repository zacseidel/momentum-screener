# prices.py
# This script fetches and caches daily adjusted close prices from Polygon grouped endpoint

import os
import requests
import sqlite3
import pandas as pd
from datetime import date
from dotenv import load_dotenv

load_dotenv()

# Environment & DB path setup
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "data", "market_data.sqlite")

# --- Date logic ---
def get_target_dates(today=None):
    today = pd.Timestamp(today or date.today())
    yesterday = today - pd.Timedelta(days=1)
    one_year = yesterday - pd.DateOffset(years=1)
    one_month = yesterday - pd.DateOffset(months=1)
    one_year_plus_month = one_month - pd.DateOffset(years=1)

    return {
        "yesterday": yesterday.strftime("%Y-%m-%d"),
        "one_year_ago": one_year.strftime("%Y-%m-%d"),
        "one_month_ago": one_month.strftime("%Y-%m-%d"),
        "one_year_plus_month_ago": one_year_plus_month.strftime("%Y-%m-%d")
    }

# --- Download + Store Prices ---
def fetch_and_store_grouped_prices(date_str, db_path=DB_PATH):
    original_date = pd.to_datetime(date_str)
    max_attempts = 7
    attempt = 0

    while attempt < max_attempts:
        check_date_str = original_date.strftime("%Y-%m-%d")

        with sqlite3.connect(db_path) as conn:
            existing = pd.read_sql("SELECT DISTINCT date FROM daily_prices WHERE date = ?", conn, params=[check_date_str])
            if not existing.empty:
                print(f"Skipping {check_date_str} — already in DB")
                return

        print(f"Fetching grouped prices for {check_date_str}...")
        url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{check_date_str}"
        params = {"adjusted": "true", "apiKey": POLYGON_API_KEY}
        r = requests.get(url, params=params)
        r.raise_for_status()
        data = r.json().get("results", [])

        if data:
            rows = [(item["T"], check_date_str, item["c"]) for item in data if "c" in item]
            with sqlite3.connect(db_path) as conn:
                conn.executemany(
                    "INSERT OR IGNORE INTO daily_prices (ticker, date, close) VALUES (?, ?, ?)", rows
                )
            print(f"Stored {len(rows)} rows for {check_date_str}")
            return
        else:
            print(f"No data for {check_date_str} — trying previous weekday...")
            from pandas.tseries.offsets import BDay
            original_date -= BDay(1)
            attempt += 1

    print(f"❌ Failed to fetch data for any trading day near {date_str} after {max_attempts} attempts.")
    with sqlite3.connect(db_path) as conn:
        existing = pd.read_sql("SELECT DISTINCT date FROM daily_prices WHERE date = ?", conn, params=[date_str])
        if not existing.empty:
            print(f"Skipping {date_str} — already in DB")
            return

    print(f"Fetching grouped prices for {date_str}...")
    url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{date_str}"
    params = {"adjusted": "true", "apiKey": POLYGON_API_KEY}
    r = requests.get(url, params=params)
    r.raise_for_status()
    data = r.json().get("results", [])

    rows = [(item["T"], date_str, item["c"]) for item in data if "c" in item]

    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO daily_prices (ticker, date, close) VALUES (?, ?, ?)", rows
        )
    print(f"Stored {len(rows)} rows for {date_str}")

# --- Runner ---
def download_all_required_price_data(db_path=DB_PATH):
    dates = get_target_dates()
    for label, date_str in dates.items():
        fetch_and_store_grouped_prices(date_str, db_path)

if __name__ == "__main__":
    download_all_required_price_data()
