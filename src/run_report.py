# run_report.py
# Orchestrates the momentum screener workflow and sends an email with the top 10 picks

import os
from dotenv import load_dotenv
from src.prices import get_target_dates, download_all_required_price_data
from src.ranking import get_price_snapshots, compute_returns_and_ranks, store_top10_picks
from src.report import cache_company_data
from src.emailer import send_email_via_sendgrid

load_dotenv()

def main():
    print("🚀 Starting Momentum Screener Pipeline")

    # Step 1: Download and cache price data
    download_all_required_price_data()

    # Step 2: Compute rankings
    target_dates = get_target_dates()
    df, resolved = get_price_snapshots(target_dates)
    ranks = compute_returns_and_ranks(df, resolved)
    top10 = store_top10_picks(ranks)

    if top10.empty:
        print("⚠️ No top 10 results to report. Exiting.")
        return

    # Step 3: Cache metadata and news
    tickers = top10["ticker"].tolist()
    cache_company_data(tickers)

    # Step 4: Generate HTML email
    from src.emailer import format_html_email  # local import to avoid circular
    html = format_html_email(top10)

    # Step 5: Send email
    send_email_via_sendgrid(
        subject="📈 Weekly Momentum Screener Results",
        html=html,
        to=os.getenv("TO_EMAIL"),
        from_email=os.getenv("FROM_EMAIL")
    )

    print("✅ Report sent successfully.")

if __name__ == "__main__":
    main()
