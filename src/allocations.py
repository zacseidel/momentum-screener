# allocations.py
# This script provides functions to download and store SPDR index allocations (SPY/SP500, MDY/SP400)

import requests
import pandas as pd
import sqlite3
from datetime import date
import os

# Resolve project root
if "__file__" in globals():
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
else:
    BASE_DIR = os.path.abspath(os.path.join(os.getcwd(), ".."))

DB_PATH = os.path.join(BASE_DIR, "data", "market_data.sqlite")

SPY_URL = "https://www.ssga.com/us/en/individual/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx"
MDY_URL = "https://www.ssga.com/us/en/individual/library-content/products/fund-data/etfs/us/holdings-daily-us-en-mdy.xlsx"

def download_spdr_holdings(url, filename):
    """Download SPDR ETF allocation XLSX file from State Street."""
    r = requests.get(url)
    r.raise_for_status()
    with open(filename, 'wb') as f:
        f.write(r.content)
    print(f"Saved file: {filename}")

def parse_and_store_allocation(xlsx_path, index_type, db_path=DB_PATH):
    print(f"Attempting to connect to database at: {db_path}")
    """Parse downloaded XLSX file and insert allocation info into SQLite."""
    df = pd.read_excel(xlsx_path, skiprows=4)
    print(f"Columns in {xlsx_path}: {df.columns.tolist()}")

    df = df.rename(columns={
        "Ticker": "ticker",
        "Name": "company",
        "Weight": "weight"
    }).dropna(subset=["ticker"])

    required_columns = {"ticker", "company", "weight"}
    missing = required_columns - set(df.columns)
    if missing:
        raise KeyError(f"Missing expected columns: {missing}")

    df["index_type"] = index_type
    df["date"] = date.today().isoformat()
    df = df[["ticker", "company", "index_type", "date", "weight"]]

    with sqlite3.connect(db_path) as conn:
        df.to_sql("index_allocations", conn, if_exists="append", index=False)
    print(f"Stored {len(df)} rows for {index_type}")

def update_index_allocations():
    """High-level wrapper to fetch and store both SPY and MDY allocations."""
    download_spdr_holdings(SPY_URL, "spy_holdings.xlsx")
    parse_and_store_allocation("spy_holdings.xlsx", "sp500")

    download_spdr_holdings(MDY_URL, "mdy_holdings.xlsx")
    parse_and_store_allocation("mdy_holdings.xlsx", "sp400")

if __name__ == "__main__":
    update_index_allocations()
