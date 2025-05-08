# init_db.py
# This script initializes the SQLite database with all required tables

import sqlite3
import os

# Resolve project root regardless of whether run as script or from notebook
if "__file__" in globals():
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
else:
    BASE_DIR = os.path.abspath(os.path.join(os.getcwd(), ".."))

DB_PATH = os.path.join(BASE_DIR, "data", "market_data.sqlite")

schema = """
-- Table: index_constituents
CREATE TABLE IF NOT EXISTS index_constituents (
    ticker TEXT NOT NULL,
    company TEXT,
    index_type TEXT CHECK(index_type IN ('sp500','sp400')),
    gics_sector TEXT,
    gics_sub_industry TEXT,
    headquarters TEXT,
    date_first_added TEXT,
    founded TEXT,
    date_added DATE NOT NULL DEFAULT (DATE('now')),
    PRIMARY KEY (ticker, index_type, date_added)
);

-- Table: index_allocations
CREATE TABLE IF NOT EXISTS index_allocations (
    ticker TEXT NOT NULL,
    company TEXT,
    index_type TEXT CHECK(index_type IN ('sp500','sp400')),
    date DATE NOT NULL,
    weight REAL,
    PRIMARY KEY (ticker, index_type, date)
);

-- Table: daily_prices (adjusted close only)
CREATE TABLE IF NOT EXISTS daily_prices (
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    close REAL NOT NULL,
    PRIMARY KEY (ticker, date)
);

-- Table: top10_picks
CREATE TABLE IF NOT EXISTS top10_picks (
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    current_return REAL,
    rank_change REAL,
    PRIMARY KEY (ticker, date)
);

-- Table: company_info
CREATE TABLE IF NOT EXISTS company_info (
    ticker TEXT PRIMARY KEY,
    name TEXT,
    description TEXT,
    last_updated DATE
);

-- Table: company_news
CREATE TABLE IF NOT EXISTS company_news (
    ticker TEXT,
    date DATE,
    title TEXT,
    summary TEXT,
    url TEXT,
    PRIMARY KEY (ticker, date, title)
);
"""

def initialize_database(path=DB_PATH):
    print(f"DB path: {path}")
    print(f"Will create directory: {os.path.dirname(path)}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(schema)
    conn.commit()
    conn.close()
    print(f"Database initialized at {path}")

if __name__ == "__main__":
    initialize_database()
