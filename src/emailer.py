# emailer.py
# Functions to format and send the HTML email report

import os
import pandas as pd
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from jinja2 import Template
from dotenv import load_dotenv
import sqlite3

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "data", "market_data.sqlite")

# --- Format HTML using Jinja2 ---
def format_html_email(top10_df):
    tickers = top10_df["ticker"].tolist()
    with sqlite3.connect(DB_PATH) as conn:
        meta = pd.read_sql(
            "SELECT ticker, name, description FROM company_metadata WHERE ticker IN ({seq})".format(
                seq=','.join(['?']*len(tickers))
            ), conn, params=tickers
        )
        news = pd.read_sql(
            "SELECT ticker, headline, url, published_utc FROM company_news WHERE ticker IN ({seq}) ORDER BY published_utc DESC".format(
                seq=','.join(['?']*len(tickers))
            ), conn, params=tickers
        )

    meta_dict = meta.set_index("ticker").to_dict("index")
    news_grouped = news.groupby("ticker")

    # Merge everything
    enriched = []
    for _, row in top10_df.iterrows():
        ticker = row["ticker"]
        company = meta_dict.get(ticker, {})
        headlines = news_grouped.get_group(ticker).to_dict("records") if ticker in news_grouped.groups else []

        enriched.append({
            "ticker": ticker,
            "current_return": row["current_return"],
            "last_month_return": row["last_month_return"],
            "rank_change": row["rank_change"],
            "name": company.get("name", ""),
            "description": company.get("description", ""),
            "headlines": headlines[:5]  # top 5
        })

    # HTML template
    template = Template("""
    <html>
    <body>
        <h2>📈 Weekly Momentum Screener - Top 10 Stocks</h2>
        {% for stock in enriched %}
            <div style="margin-bottom: 30px; padding: 10px; border-bottom: 1px solid #ccc;">
                <h3>{{ stock.ticker }} - {{ stock.name }}</h3>
                <p><strong>Current 12M Return:</strong> {{ stock.current_return }} | <strong>12M Return, as of Last Month:</strong> {{ stock.last_month_return }} | <strong>Rank Change:</strong> {{ stock.rank_change }}</p>
                <p>{{ stock.description }}</p>
                <ul>
                    {% for item in stock.headlines %}
                        <li><a href="{{ item.url }}" target="_blank">{{ item.headline }}</a> <em>({{ item.published_utc[:10] }})</em></li>
                    {% endfor %}
                </ul>
            </div>
        {% endfor %}
    </body>
    </html>
    """)

    return template.render(enriched=enriched)

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
