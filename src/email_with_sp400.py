"""email_with_sp400.py

Second version of emailer.py that can render an HTML momentum e‑mail
containing **two** separate sections:

1. S&P 500 universe (unchanged from original behaviour)
2. S&P 400 universe (new)

The public interface is identical to the original module but with an
extra argument for the SP400 DataFrame.

Usage
-----
>>> html = format_html_email_dual(top10_sp500_df, top10_sp400_df,
...                               report_date=date.today())
>>> send_email_via_sendgrid("Weekly Momentum – dual", html,
...                         to=['user@example.com'], from_email='bot@example.com')
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import jinja2
import pandas as pd

# ----------------------------------------------------------------------
# HTML TEMPLATE
# ----------------------------------------------------------------------

_TEMPLATE = jinja2.Template(
    Path(__file__).with_name("email_template_dual.html").read_text(), autoescape=True
)

# ----------------------------------------------------------------------
# Formatting helpers
# ----------------------------------------------------------------------


def _render_section(title: str, summary_html: str, detail_html_list: list[str]) -> str:
    """Render a single index section.

    Parameters
    ----------
    title:
        Heading shown above the section.
    summary_html:
        Prepared <p> block from `ranking.build_summary_html`.
    detail_html_list:
        List with one HTML block per ticker.
    """
    return f"""
        <h2>{title}</h2>
        {summary_html}
        {''.join(detail_html_list)}
    """


# ----------------------------------------------------------------------
# Public helpers
# ----------------------------------------------------------------------


def format_html_email_dual(
    top10_sp500: pd.DataFrame,
    top10_sp400: pd.DataFrame,
    *,
    report_date: Optional[date] = None,
) -> str:
    """Return a ready‑to‑send HTML string with *two* momentum sections.

    The function simply renders the two blocks sequentially so that
    subscribers can see the 500‑ and 400‑universes side‑by‑side.
    """

    # ── Build *summary* html blocks (function imported from `ranking`) ──
    from ranking import build_summary_html, build_detail_sections, BENCHMARK

    summary_500 = build_summary_html(top10_sp500, benchmark_ticker=BENCHMARK["sp500"])
    summary_400 = build_summary_html(top10_sp400, benchmark_ticker=BENCHMARK["sp400"])

    # ── Build per‑stock *detail* html blocks ──
    details_500 = build_detail_sections(top10_sp500)
    details_400 = build_detail_sections(top10_sp400)

    section_500 = _render_section("S&P 500 Universe", summary_500, details_500)
    section_400 = _render_section("S&P 400 Universe", summary_400, details_400)

    html = _TEMPLATE.render(
        today=report_date or date.today(),
        sections=section_500 + section_400,
    )
    return html


# ----------------------------------------------------------------------
# Re‑export original helpers so downstream code keeps working
# ----------------------------------------------------------------------
from emailer import send_email_via_sendgrid  # noqa: E402  pylint: disable=wrong-import-position
