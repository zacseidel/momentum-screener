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

# --- Format HTML using Jinja2 ---

def format_html_email(top10_df, report_date=None):
    if report_date is None:
        report_date = datetime.today()
    elif isinstance(report_date, str):
        report_date = pd.to_datetime(report_date)
    elif isinstance(report_date, datetime):
        report_date = pd.Timestamp(report_date)

    formatted_date = report_date.strftime("%B %d, %Y")
    current_date_str = report_date.date().isoformat()

    tickers = [t.strip().upper() for t in top10_df["ticker"].tolist()]
    current_tickers = set(tickers)

    # --- Fetch from DB ---
    with sqlite3.connect(DB_PATH) as conn:
        # 1. Resolve most recent prior report date
        prior_date_row = pd.read_sql(
            "SELECT DISTINCT date FROM top10_picks WHERE date < ? ORDER BY date DESC LIMIT 1",
            conn,
            params=[current_date_str]
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
        voo_dates = {
            "current": current_date_str,
            "one_year_ago": (report_date - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
        }

        voo = pd.read_sql(
            "SELECT date, close FROM daily_prices WHERE ticker = 'VOO' AND date IN (?, ?)",
            conn,
            params=[voo_dates["current"], voo_dates["one_year_ago"]]
        ).set_index("date")["close"]
        voo.index = voo.index.astype(str)

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
        price_rows = pd.read_sql(
            f"SELECT ticker, date, close FROM daily_prices WHERE date = ? AND ticker IN ({','.join(['?']*len(all_compare))})",
            conn, params=[current_date_str] + all_compare
        )
        prices = price_rows.set_index("ticker")["close"].to_dict()

    # --- Compute VOO benchmark ---
    if all(date in voo for date in voo_dates.values()):
        voo_now = voo[voo_dates["current"]]
        voo_then = voo[voo_dates["one_year_ago"]]
        voo_return = (voo_now / voo_then - 1) if voo_then > 0 else None
        voo_line = f"<p><strong>Benchmark (VOO):</strong> ${voo_now:.2f} (+{voo_return:.1%} last 12M)</p>"
    else:
        voo_line = "<p><strong>Benchmark (VOO):</strong> Not available</p>"

    # --- Merge everything ---
    meta_dict = meta.set_index("ticker").to_dict("index")
    news_grouped = news.groupby("ticker")

    enriched = []
    for _, row in top10_df.iterrows():
        ticker = row["ticker"].strip().upper()
        company = meta_dict.get(ticker, {})
        headlines = news_grouped.get_group(ticker).to_dict("records") if ticker in news_grouped.groups else []

        enriched.append({
            "ticker": ticker,
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
            summary_lines.append(f"<b>{text}</b>")
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
        <title> Momentum Screener – {{ formatted_date }}</title>
    </head>
    <body>
        <h2>📈 Momentum Screener – {{ formatted_date }}</h2>
        {{ summary_html | safe }}

        {% for stock in enriched %}
            <div style="margin-bottom: 30px; padding: 10px; border-bottom: 1px solid #ccc;">
                <h3>{{ stock.ticker }} - {{ stock.name }}</h3>
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

    return template.render(
        enriched=enriched,
        formatted_date=formatted_date,
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
