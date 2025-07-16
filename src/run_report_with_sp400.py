"""run_report_with_sp400.py

Calculate weekly momentum for **both** the S&P 500 *and* the S&P 400
universes and e‑mail a combined HTML report.

This file is a lightly‑modified copy of the original *run_report.py*.
The new logic lives in :pyfunc:`main` – the helper functions are left
untouched so that the code stays familiar.

Changes
-------
* Call `ranking.get_price_snapshots(..., index_type='sp400')`
  in addition to the existing S&P 500 call.
* Pass the two DataFrames to
  :pyfunc:`emailer_with_sp400.format_html_email_dual`.
"""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import pandas as pd

import ranking
from email_with_sp400 import format_html_email_dual, send_email_via_sendgrid

_LOGGER = logging.getLogger(__name__)
_DEFAULT_TEMPLATE = Path(__file__).with_name("email_template_dual.html")


def compute_top10(index_type: str) -> pd.DataFrame:
    """Compute momentum table for *index_type* (sp500 / sp400)."""

    snapshots = ranking.get_price_snapshots(index_type=index_type)
    returns = ranking.compute_returns(snapshots)
    ranks = ranking.compute_ranks(returns)
    top10 = ranking.prepare_top10_table(ranks, index_type=index_type)
    return top10


def main(
    *,
    sendgrid_api_key: str,
    email_to: str,
    email_from: str = "momentum‑bot@example.com",
    dry_run: bool = False,
) -> None:
    """Entry‑point used by the **weekly cron‑job**."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    _LOGGER.info("Computing S&P 500 momentum …")
    top10_sp500 = compute_top10("sp500")

    _LOGGER.info("Computing S&P 400 momentum …")
    top10_sp400 = compute_top10("sp400")

    html_body = format_html_email_dual(top10_sp500, top10_sp400, report_date=date.today())

    if dry_run:
        Path("momentum_report_preview.html").write_text(html_body, encoding="utf‑8")
        _LOGGER.info("Preview written to momentum_report_preview.html")
    else:
        _LOGGER.info("Sending e‑mail via SendGrid → %s", email_to)
        send_email_via_sendgrid(
            subject="📈 Weekly Momentum Report – SP500 & SP400",
            html_body=html_body,
            to=[email_to],
            from_email=email_from,
            api_key=sendgrid_api_key,
        )


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sendgrid-api-key", required=True)
    parser.add_argument("--email-to", required=True)
    parser.add_argument("--email-from", default="momentum‑bot@example.com")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(
        sendgrid_api_key=args.sendgrid_api_key,
        email_to=args.email_to,
        email_from=args.email_from,
        dry_run=args.dry_run,
    )
