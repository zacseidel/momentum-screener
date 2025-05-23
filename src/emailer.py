# emailer.py
# Functions to format and send the HTML email report

import os
import pandas as pd
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from jinja2 import Template
from dotenv import load_dotenv
import sqlite3
from datetime import datetime

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "data", "market_data.sqlite")

# -- Backtracking date function -- 
from pandas.tseries.offsets import BDay

def backtrack_to_available_date(conn, ticker, date_str, max_days=7):
    """Backtrack from date_str to find most recent trading day with data."""
    d = pd.to_datetime(date_str)
    for _ in range(max_days):
        ds = d.strftime("%Y-%m-%d")
        exists = conn.execute(
            "SELECT 1 FROM daily_prices WHERE ticker = ? AND date = ?",
            (ticker, ds)
        ).fetchone()
        if exists:
            return ds
        d -= BDay(1)
    return None




# --- Format HTML using Jinja2 ---

def format_html_email(top10_df, report_date=None):
    if report_date is None:
        report_date = datetime.today() - pd.DateOffset(days=1)
    elif isinstance(report_date, str):
        report_date = pd.to_datetime(report_date) 
        price_date = pd.to_datetime(report_date)- pd.DateOffset(days=1)
    elif isinstance(report_date, datetime):
        report_date = pd.Timestamp(report_date) 
        price_date = pd.to_datetime(report_date)- pd.DateOffset(days=1)

    formatted_report_date = report_date.strftime("%B %d, %Y")
    current_report_date_str = report_date.date().isoformat()

    formatted_price_date = price_date.strftime("%B %d, %Y")
    current_price_date_str = price_date.date().isoformat()

    tickers = [t.strip().upper() for t in top10_df["ticker"].tolist()]
    current_tickers = set(tickers)


    # --- Fetch from DB ---
    with sqlite3.connect(DB_PATH) as conn:
        # 1. Resolve most recent prior report date
        prior_date_row = pd.read_sql(
            "SELECT DISTINCT date FROM top10_picks WHERE date < ? ORDER BY date DESC LIMIT 1",
            conn,
            params=[current_report_date_str]
        )

        if not prior_date_row.empty:
            prior_date_str = prior_date_row["date"].iloc[0]
            prev = pd.read_sql(
                "SELECT DISTINCT ticker FROM top10_picks WHERE date = ?",
                conn,
                params=[prior_date_str]
            )
            prev_tickers = set(prev["ticker"].str.strip().str.upper())
        else:
            prior_date_str = None
            prev_tickers = set()

        # 2. Fetch VOO prices

        # Backtrack VOO dates to available trading days
        voo_dates = {
            "current": backtrack_to_available_date(conn, "VOO", current_report_date_str),
            "one_year_ago": backtrack_to_available_date(
                conn, "VOO", (report_date - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
            )
        }
        print("📅 Resolved VOO dates:", voo_dates)


        voo = pd.read_sql(
            "SELECT date, close FROM daily_prices WHERE ticker = 'VOO' AND date IN (?, ?)",
            conn,
            params=[voo_dates["current"], voo_dates["one_year_ago"]]
        ).set_index("date")["close"]
        voo.index = voo.index.astype(str)
        print("📈 Retrieved VOO prices:", voo.to_dict())


        # 3. Fetch metadata + news
        meta = pd.read_sql(
            f"SELECT ticker, name, description FROM company_metadata WHERE ticker IN ({','.join(['?']*len(tickers))})",
            conn, params=tickers
        )
        news = pd.read_sql(
            f"SELECT ticker, headline, url, published_utc FROM company_news WHERE ticker IN ({','.join(['?']*len(tickers))}) ORDER BY published_utc DESC",
            conn, params=tickers
        )

        # 4. Fetch prices for summary
        all_compare = list(current_tickers.union(prev_tickers))
        print("🔎 All compare tickers:", all_compare)

        price_rows = pd.read_sql(
            f"SELECT ticker, date, close FROM daily_prices WHERE date = ? AND ticker IN ({','.join(['?']*len(all_compare))})",
            conn, params=[current_price_date_str] + all_compare
        )
        prices = price_rows.set_index(price_rows["ticker"].str.upper())["close"].to_dict()
        print("🔎 Available price tickers:", list(prices.keys()))
        print("🔎 Tickers in report:", tickers)

    # --- Compute VOO benchmark ---
    if all(date in voo for date in voo_dates.values()):
        voo_now = voo[voo_dates["current"]]
        voo_then = voo[voo_dates["one_year_ago"]]
        voo_return = (voo_now / voo_then - 1) if voo_then > 0 else None
        voo_price_fmt = f"${voo_now:.2f}" if isinstance(voo_now, (float, int)) else "—"
        voo_ret_fmt = f"+{voo_return:.1%} last 12M" if isinstance(voo_return, (float, int)) else "— last 12M"
        voo_line = f"<p><strong>Benchmark (VOO):</strong> {voo_price_fmt} ({voo_ret_fmt})</p>"
    else:
        voo_line = "<p><strong>Benchmark (VOO):</strong> Not available</p>"

    # --- Merge everything ---
    meta_dict = meta.set_index("ticker").to_dict("index")
    news_grouped = news.groupby("ticker")

    enriched = []
    print("🔎 Prices dict keys:", list(prices.keys())[:10])



    for _, row in top10_df.iterrows():
        ticker = row["ticker"].strip().upper()
        price_val = prices.get(ticker)
        try:
            price_fmt = f"{float(price_val):.2f}"
        except:
            price_fmt = "—"

        company = meta_dict.get(ticker, {})
        headlines = news_grouped.get_group(ticker).to_dict("records") if ticker in news_grouped.groups else []

        enriched.append({
            "ticker": ticker,
            "price": price_fmt,
            "current_return": row["current_return"],
            "last_month_return": row["last_month_return"],
            "rank_change": row["rank_change"],
            "name": company.get("name", ""),
            "description": company.get("description", ""),
            "headlines": headlines[:5]
        })

    # --- Build Summary ---
    added = current_tickers - prev_tickers
    dropped = prev_tickers - current_tickers
    continuing = current_tickers & prev_tickers

    summary_lines = []
    for ticker in tickers:  # maintain order
        ret_val = top10_df.loc[top10_df["ticker"].str.upper() == ticker, "current_return"].values[0]
        price_val = prices.get(ticker, "—")

        try:
            price_fmt = f"${float(price_val):.2f}"
        except:
            price_fmt = f"${price_val}"

        try:
            ret_fmt = f"+{float(ret_val):.1%} last 12M"
        except:
            ret_fmt = f"{ret_val} last 12M"

        text = f"{ticker} – {price_fmt} ({ret_fmt})"
        if ticker in added:
            summary_lines.append(f"<i>{text}</i>")
        elif ticker in continuing:
            summary_lines.append(text)

    for ticker in sorted(dropped):
        price_val = prices.get(ticker, "—")
        try:
            price_fmt = f"${float(price_val):.2f}"
        except:
            price_fmt = f"${price_val}"
        text = f"{ticker} – {price_fmt} (— last 12M)"
        summary_lines.append(f"<s>{text}</s>")

    summary_html = voo_line + "<h3>Summary of Changes</h3><p>" + "<br>".join(summary_lines) + "</p>"

    # --- HTML Template ---
    template = Template("""
    <html>
    <head>
        <meta charset="utf-8">
        <title> Momentum Report – {{ formatted_report_date }}</title>
    </head>
    <body>
        <h2>📈 Momentum Report – {{ formatted_report_date }}</h2>
        {{ summary_html | safe }}

        {% for stock in enriched %}
            <div style="margin-bottom: 30px; padding: 10px; border-bottom: 1px solid #ccc;">
                <h3>{{ stock.ticker }} - {{ stock.name }} – ${{ stock.price }}</h3>
                <p><strong>Current 12M Return:</strong> {{ stock.current_return }}
                   | <strong>12M Return, as of Last Month:</strong> {{ stock.last_month_return }}
                   | <strong>Rank Change:</strong> {{ stock.rank_change }}</p>
                <p>{{ stock.description }}</p>
                <ul>
                    {% for item in stock.headlines %}
                        <li><a href="{{ item.url }}" target="_blank">{{ item.headline }}</a>
                            <em>({{ item.published_utc[:10] }})</em></li>
                    {% endfor %}
                </ul>
            </div>
        {% endfor %}
    </body>
    </html>
    """)

    print("✅ Summary HTML block:\n", summary_html[:500])

    print("🧪 DEBUG: Jinja context types and sample values:")

    # Print summary preview
    print("  summary_html:", type(summary_html), summary_html[:200])

    # Print formatted date
    print("  formatted_date:", type(formatted_report_date), formatted_report_date)

    # Print VOO price values if available
    if 'voo_now' in locals():
        print("  voo_now:", type(voo_now), voo_now)
    if 'voo_return' in locals():
        print("  voo_return:", type(voo_return), voo_return)

    # Print enriched list summary
    print("  enriched (length):", len(enriched))
    if enriched:
        first = enriched[0]
        print("    First stock:")
        print("      ticker:", type(first.get("ticker")), first.get("ticker"))
        print("      price:", type(first.get("price")), first.get("price"))
        print("      current_return:", type(first.get("current_return")), first.get("current_return"))
        print("      last_month_return:", type(first.get("last_month_return")), first.get("last_month_return"))
        print("      rank_change:", type(first.get("rank_change")), first.get("rank_change"))



    return template.render(
        enriched=enriched,
        formatted_date=formatted_report_date,
        summary_html=summary_html
    )




# --- Send email using SendGrid ---
def send_email_via_sendgrid(subject, html, to, from_email):
    sg = SendGridAPIClient(api_key=os.getenv("SENDGRID_TOKEN"))
    message = Mail(
        from_email=from_email,
        to_emails=to,
        subject=subject,
        html_content=html
    )
    response = sg.send(message)
    print(f"✉️ Email sent. Status code: {response.status_code}")
