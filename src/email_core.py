"""email_core.py

Single, flexible HTML renderer for momentum‑screener e‑mails.

This *core* module is **index‑agnostic**: you feed it any mapping of
``{"Section Name": top10_dataframe}`` plus a list of pre‑rendered
company deep‑dives (one HTML snippet per ticker) and it returns a
complete HTML document.

Wrappers (``emailer.py``, ``email_with_sp400.py``) delegate here so we
maintain backward compatibility while supporting an arbitrary number of
universes (S&P 500, S&P 400, watchlists, etc.).
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Mapping, Sequence, Optional

import pandas as pd
from jinja2 import Template

__all__ = ["format_html_email_multi"]

# ---------------------------------------------------------------------------
# 🔖  Built‑in fallback Jinja2 template
# ---------------------------------------------------------------------------
_TEMPLATE = """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
  <title>Momentum Report – {{ report_date }}</title>
  <style>
    body{font-family:Arial,sans-serif;margin:0 auto;max-width:800px;padding:1rem;color:#222}
    h1{font-size:1.4rem;margin-top:0}
    h2{font-size:1.1rem;margin:1.6rem 0 0.6rem}
    table{border-collapse:collapse;width:100%}
    th,td{border:1px solid #ddd;padding:6px;text-align:right}
    th{background:#f4f4f4;text-align:center}
    tr:nth-child(even){background:#fafafa}
  </style>
</head>
<body>
  <h1>📈 Weekly Momentum Report – {{ report_date }}</h1>

  {# ---- Summary tables ---- #}
  {% for section, table_html in summary_tables.items() %}
    <h2>{{ section }} Top 10</h2>
    {{ table_html | safe }}
  {% endfor %}

  {# ---- Deep‑dive cards ---- #}
  {% if deep_dives %}
    <h2>Company Deep‑Dives</h2>
    {% for card in deep_dives %}
      {{ card | safe }}
    {% endfor %}
  {% endif %}

  <p style=\"font-size:0.9em;color:#666;margin-top:2rem\">Generated automatically by the Momentum Screener.</p>
</body>
</html>"""

# ---------------------------------------------------------------------------
# 🖨  Helpers
# ---------------------------------------------------------------------------

def _df_to_html(df: pd.DataFrame) -> str:
    """Return *df* as a compact, index‑less HTML table."""
    return df.to_html(index=False, classes="dataframe", border=0, escape=False,
                      justify="center", float_format="{:.2f}".format)


# ---------------------------------------------------------------------------
# ✨  Public API
# ---------------------------------------------------------------------------

def format_html_email_multi(
    summary_tables: Mapping[str, pd.DataFrame],
    deep_dives: Sequence[str] | None,
    *,
    report_date: date | datetime,
    template_path: Optional[str | Path] = None,
) -> str:
    """Render a momentum e‑mail that may cover **multiple universes**.

    Parameters
    ----------
    summary_tables
        Mapping from *section heading* (e.g. "S&P 500") to a Top‑10
        ``DataFrame``.
    deep_dives
        List of already‑rendered HTML snippets – one per ticker – in the
        order you want them to appear.  Pass ``None`` or an empty list
        to omit the deep‑dive section entirely.
    report_date
        The date shown in the e‑mail header; will be formatted as
        YYYY‑MM‑DD.
    template_path
        Optional path to a custom Jinja2 template with placeholders:
        ``summary_tables`` (mapping), ``deep_dives`` (list) and
        ``report_date``.  Falls back to a built‑in template when the file
        cannot be opened.
    """
    # Pre‑render all DataFrames so they don’t go through Jinja loop
    rendered_tables = {
        heading: _df_to_html(df) for heading, df in summary_tables.items()
    }

    # Load template source (external or fallback)
    if template_path is not None:
        try:
            template_src = Path(template_path).read_text(encoding="utf-8")
        except FileNotFoundError:
            template_src = _TEMPLATE
    else:
        template_src = _TEMPLATE

    tmpl = Template(template_src)
    html = tmpl.render(
        report_date=pd.Timestamp(report_date).strftime("%Y‑%m‑%d"),
        summary_tables=rendered_tables,
        deep_dives=list(deep_dives or []),
    )
    return html
