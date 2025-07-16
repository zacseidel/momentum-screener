# src/run_report.py
# Orchestrates the momentum screener workflow and e‑mails SPY *and* MDY reports

import os
from dotenv import load_dotenv

from src.prices import (
    download_all_required_price_data,
    get_target_dates,
)
from src.ranking import (
    get_price_snapshots,
    compute_returns_and_ranks,
    store_top10_picks,         # SPY
    store_top10_mdy_picks,     # MDY
)
from src.report import cache_company_data
from src.emailer import (
    format_dual_html_email,
    send_email_via_sendgrid,
)

load_dotenv()


def main() -> None:
    print("🚀  Starting Momentum Screener Pipeline (SPY + MDY)")

    # ------------------------------------------------------------------
    # 1.  Pull / cache fresh price & index‑membership data
    # ------------------------------------------------------------------
    download_all_required_price_data()

    # ------------------------------------------------------------------
    # 2.  Resolve date anchors for momentum calculations
    # ------------------------------------------------------------------
    target_dates = get_target_dates()
    print("📅  Target dates:", target_dates)

    # ------------------------------------------------------------------
    # 3.  Build SPY snapshots → ranks → top‑10
    # ------------------------------------------------------------------
    spy_prices, resolved_spy = get_price_snapshots(target_dates)
    spy_ranks = compute_returns_and_ranks(spy_prices, resolved_spy)
    top10_spy = store_top10_picks(spy_ranks)

    if top10_spy.empty:
        print("⚠️  No SPY top‑10 this week — aborting run.")
        return

    # ------------------------------------------------------------------
    # 4.  Build MDY snapshots → ranks → top‑10
    # ------------------------------------------------------------------
    mdy_prices, resolved_mdy = get_price_snapshots(
        target_dates, index_type="sp400"
    )
    mdy_ranks = compute_returns_and_ranks(mdy_prices, resolved_mdy)
    top10_mdy = store_top10_mdy_picks(mdy_ranks)

    if top10_mdy.empty:
        print("⚠️  No MDY top‑10 this week — aborting run.")
        return

    # ------------------------------------------------------------------
    # 5.  Cache metadata + news for *all* tickers we’ll display
    # ------------------------------------------------------------------
    cache_company_data(
        top10_spy["ticker"].tolist() + top10_mdy["ticker"].tolist()
    )

    # ------------------------------------------------------------------
    # 6.  Render HTML (dual index: SPY + MDY)
    # ------------------------------------------------------------------
    html = format_dual_html_email(top10_spy, top10_mdy)

    # ------------------------------------------------------------------
    # 7.  Send the e‑mail
    # ------------------------------------------------------------------
    send_email_via_sendgrid(
        subject="📈 Weekly Momentum Screener Results – SPY & MDY",
        html=html,
        to=os.getenv("TO_EMAIL"),
        from_email=os.getenv("FROM_EMAIL"),
    )

    print("✅  Report sent successfully.")


if __name__ == "__main__":
    main()
