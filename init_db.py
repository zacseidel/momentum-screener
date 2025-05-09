# init_db.py
# Creates and initializes the SQLite database schema

import os
import sqlite3

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_PATH, "market_data.sqlite")

os.makedirs(DATA_PATH, exist_ok=True)

def initialize_database():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Constituents table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS index_constituents (
            ticker TEXT NOT NULL,
            company TEXT,
            index_type TEXT NOT NULL,
            gics_sector TEXT,
            gics_sub_industry TEXT,
            headquarters TEXT,
            date_first_added TEXT,
            founded TEXT,
            date_added TEXT NOT NULL,
            PRIMARY KEY (ticker, index_type, date_added)
        )
        """)

        # ETF allocation table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS index_allocations (
            ticker TEXT NOT NULL,
            company TEXT,
            index_type TEXT NOT NULL,
            date DATE NOT NULL,
            weight REAL,
            PRIMARY KEY (ticker, index_type, date)
        )
        """)

        # Price history table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_prices (
            ticker TEXT NOT NULL,
            date DATE NOT NULL,
            close REAL,
            PRIMARY KEY (ticker, date)
        )
        """)

        # Top 10 picks table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS top10_picks (
            ticker TEXT NOT NULL,
            date DATE NOT NULL,
            current_return TEXT,
            last_month_return TEXT,
            current_rank REAL,
            last_month_rank REAL,
            rank_change REAL,
            PRIMARY KEY (ticker, date)
        )
        """)

        conn.commit()
        print("✅ Database initialized at:", DB_PATH)

if __name__ == "__main__":
    initialize_database()
