# ranking.py
# This module computes 1-year momentum returns and ranks for SP500 stocks, stores top 10 picks

import sqlite3
import pandas as pd
from datetime import date
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "data", "market_data.sqlite")

# --- Fetch prices ---
from pandas.tseries.offsets import BDay

def get_price_snapshots(target_dates, index_type="sp500", db_path=DB_PATH):
    with sqlite3.connect(db_path) as conn:
        tickers = pd.read_sql("SELECT DISTINCT ticker FROM index_constituents WHERE index_type = ?", conn, params=[index_type])
        tickers = tickers["ticker"].tolist()

            # Backtrack dates to the most recent available in DB
    def backtrack_to_available(conn, date_str):
        d = pd.to_datetime(date_str)
        for _ in range(7):
            test_date = d.strftime("%Y-%m-%d")
            q = conn.execute("SELECT 1 FROM daily_prices WHERE date = ? LIMIT 1", (test_date,)).fetchone()
            if q:
                return test_date
            d -= BDay(1)
        raise ValueError(f"No price data found near {date_str}")

    with sqlite3.connect(db_path) as conn:
        tickers = pd.read_sql("SELECT DISTINCT ticker FROM index_constituents WHERE index_type = ?", conn, params=[index_type])
        tickers = tickers["ticker"].tolist()

        resolved_dates = {label: backtrack_to_available(conn, ds) for label, ds in target_dates.items()}
        prices = pd.read_sql(
            "SELECT * FROM daily_prices WHERE date IN (?, ?, ?, ?)",
            conn,
            params=[
                resolved_dates["yesterday"],
                resolved_dates["one_year_ago"],
                resolved_dates["one_month_ago"],
                resolved_dates["one_year_plus_month_ago"]
            ]
        )

    df = prices.pivot(index="ticker", columns="date", values="close")
    df = df.reindex(index=tickers)
    df.columns.name = None
    return df, resolved_dates

    df = prices.pivot(index="ticker", columns="date", values="close")
    df = df.reindex(index=tickers)
    df.columns.name = None
    return df

# --- Compute returns and ranks ---
def compute_returns_and_ranks(df, target_dates):
    c_now = df[target_dates["yesterday"]]
    c_1y = df[target_dates["one_year_ago"]]
    c_1mo = df[target_dates["one_month_ago"]]
    c_1y_1mo = df[target_dates["one_year_plus_month_ago"]]

    current_return = (c_now - c_1y) / c_1y
    previous_return = (c_1mo - c_1y_1mo) / c_1y_1mo

    current_rank = current_return.rank(ascending=False, method="min")
    previous_rank = previous_return.rank(ascending=False, method="min")
    rank_change = previous_rank - current_rank

    result = pd.DataFrame({
        "current_return": current_return,
        "last_month_return": previous_return,
        "current_rank": current_rank,
        "last_month_rank": previous_rank,
        "rank_change": rank_change
    })

    result = result.dropna()

    # Filter: only include stocks whose rank is improving or steady
    result = result[result["current_rank"] <= result["last_month_rank"]]

    # Sort by highest current return
    result = result.sort_values("current_return", ascending=False)

    # Format returns for display
    result["current_return"] = result["current_return"].map(lambda x: f"{x * 100:.1f}%")
    result["last_month_return"] = result["last_month_return"].map(lambda x: f"{x * 100:.1f}%")

    return result



# --- Store top 10 in database ---

def store_top10_picks(result, run_date=None, db_path=DB_PATH):
    if result.empty:
        print("⚠️ No results available to store. Skipping top 10 storage.")
        return pd.DataFrame()

    top10 = result[result["rank_change"] >= 0].copy().head(10)

    if run_date is None:
        run_date = pd.Timestamp.today().date().isoformat()
    elif isinstance(run_date, pd.Timestamp):
        run_date = run_date.date().isoformat()
    elif isinstance(run_date, datetime):
        run_date = run_date.date().isoformat()

    top10["date"] = run_date
    top10 = top10.reset_index().rename(columns={"ticker": "ticker"})

    with sqlite3.connect(db_path) as conn:
        top10.to_sql("top10_picks", conn, if_exists="replace", index=False)
        print(f"✅ Stored top 10 picks for {run_date}")

    return top10


if __name__ == "__main__":
    from prices import get_target_dates
    dates = get_target_dates()
    prices_df, resolved_dates = get_price_snapshots(dates)
    result = compute_returns_and_ranks(prices_df, resolved_dates)
    store_top10_picks(result)
