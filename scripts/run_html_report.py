import os
from datetime import datetime, timedelta
import pandas as pd
from dotenv import load_dotenv

from src.prices import get_target_dates, download_all_required_price_data
from src.ranking import get_price_snapshots, compute_returns_and_ranks, store_top10_picks
from src.report import cache_company_data
from src.emailer import format_html_email
from src.prices import fetch_and_store_spx_price  # <-- NEW

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_DIR = os.path.join(BASE_DIR, "site", "reports")


def get_current_friday():
    today = datetime.today()
    offset = (today.weekday() - 4) % 7  # 4 = Friday
    friday = today if today.weekday() == 4 else today - timedelta(days=offset)
    return friday.strftime("%Y-%m-%d")


def generate_html_report(friday_str):
    print(f"📊 Running Momentum Screener to generate HTML report for {friday_str}")
    anchor = pd.Timestamp(friday_str)

    # Step 1: Download and cache price data (stocks + SPX)
    download_all_required_price_data(today=anchor)
    
    target_dates = get_target_dates(today=anchor)
    for label, date_str in target_dates.items():
        fetch_and_store_spx_price(date_str)  # <-- NEW: add SPX for all relevant dates

    # Step 2: Compute rankings
    df, resolved = get_price_snapshots(target_dates)
    ranks = compute_returns_and_ranks(df, resolved)
    top10 = store_top10_picks(ranks, run_date=anchor)

    if top10.empty:
        print("⚠️ No top 10 results to include in report.")
        return None

    # Step 3: Cache metadata and news
    tickers = top10["ticker"].tolist()
    cache_company_data(tickers)

    # Step 4: Generate HTML with correct report date
    return format_html_email(top10, report_date=anchor)


def run():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    friday_str = get_current_friday()
    output_path = os.path.join(OUTPUT_DIR, f"momentum_{friday_str}.html")

    html_content = generate_html_report(friday_str)
    if not html_content:
        print("❌ No HTML content generated. Exiting.")
        return

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ Report written to {output_path}")


if __name__ == "__main__":
    run()
