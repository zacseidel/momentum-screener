# emailer.py
# Functions to format and send the HTML email report

import os, numbers
import pandas as pd
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from jinja2 import Template
from dotenv import load_dotenv
import sqlite3
from datetime import datetime

from chart_module import plot_stock_chart
import base64, io
import matplotlib
matplotlib.use("Agg")  # Use non-interactive backend for saving charts
import matplotlib.pyplot as plt



load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "data", "market_data.sqlite")
# optional – keep charts together
CHART_DIR = os.path.join(BASE_DIR, "assets", "charts")
os.makedirs(CHART_DIR, exist_ok=True)
# -- Backtracking date function -- 
from pandas.tseries.offsets import BDay


def as_float(x):
    """
    Convert '484.1%' -> 4.841, '0.27' -> 0.27, return None on failure/NaN.
    """
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    if isinstance(x, str):
        x = x.strip()
        had_percent = x.endswith("%")
        if had_percent:
            x = x.rstrip("%").strip()
        try:
            num = float(x)
            return num / 100 if had_percent else num
        except ValueError:
            return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None




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

def get_price_backtracked(conn, ticker, anchor_date, max_days=7):
    """Float closing price on last trading day ≤ anchor_date, or None."""
    ds = backtrack_to_available_date(conn, ticker, anchor_date, max_days)
    if ds:
        row = conn.execute(
            "SELECT close FROM daily_prices WHERE ticker=? AND date=?",
            (ticker, ds)
        ).fetchone()
        try:
            return float(row[0]) if row else None    # ← cast right here
        except (TypeError, ValueError):
            return None
    return None

# --- Format HTML using Jinja2 ---
def is_real(x):
    return isinstance(x, numbers.Real) and not pd.isna(x)


def format_html_email(top10_df, report_date=None):
        # light vs. dark variants
    POS_L, NEG_L = "#006400", "#c42020"     # light green / red
    POS_D, NEG_D = "#006400", "#7d0d0d"     # darker green / red

    def style_return(val, darker=False):
        """
        Return a coloured <span> with sign and 1-dec %.
        If darker=True the dark palette is used.
        """
        val = as_float(val)
        if val is None:
            return "-"

        sign   = "+" if val >= 0 else "−"
        colour = (
            POS_D if (val >= 0 and darker) else
            NEG_D if (val < 0  and darker) else
            POS_L if val >= 0 else
            NEG_L
        )
        return f'<span style="color:{colour};">{sign}{abs(val):.1%}</span>'

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
    print(top10_df[["ticker","current_return","last_week_return"]].head())
    print([as_float(x) for x in top10_df["last_week_return"].head()])

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
            ),
            "one_week_ago": backtrack_to_available_date(
                conn, "VOO",
                (price_date - pd.DateOffset(weeks=1)).strftime("%Y-%m-%d")
            ),
        }
        print("📅 Resolved VOO dates:", voo_dates)


        voo = pd.read_sql(
            "SELECT date, close FROM daily_prices WHERE ticker = 'VOO' AND date IN (?, ?, ?)",
            conn,
            params=[voo_dates["current"], voo_dates["one_year_ago"], voo_dates["one_week_ago"]]
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
        # extra dates for dropped-ticker return calc
        price_curr = {
            tk: get_price_backtracked(conn, tk, current_price_date_str, max_days=7)
                for tk in all_compare
            }

        # --------------------------------------------------------------------
        one_week_anchor = (price_date - pd.DateOffset(weeks=1)).strftime("%Y-%m-%d")
        one_year_anchor = (report_date - pd.DateOffset(years=1)).strftime("%Y-%m-%d")

        price_wk = {tk: get_price_backtracked(conn, tk, one_week_anchor) for tk in all_compare}
        price_yr = {tk: get_price_backtracked(conn, tk, one_year_anchor) for tk in all_compare}

        prices_raw = price_rows.set_index(price_rows["ticker"].str.upper())["close"].to_dict()
        prices = {k: float(v) for k, v in prices_raw.items()}
# -------------------------------------------------------------------

        print("🔎 Available price tickers:", list(prices.keys()))
        print("🔎 Tickers in report:", tickers)

    # --- Compute VOO benchmark ---
    if all(date in voo for date in voo_dates.values()):
        voo_now = voo[voo_dates["current"]]
        voo_then = voo[voo_dates["one_year_ago"]]
        voo_week_ago = voo[voo_dates["one_week_ago"]]
        voo_ret_12m = (voo_now / voo_then - 1) if voo_then > 0 else None
        voo_ret_1w = (voo_now / voo_week_ago - 1) if is_real(voo_week_ago) else None
        voo_price_fmt = f"${voo_now:.2f}" if is_real(voo_now) else "—"        
        voo_12m_span  = style_return(voo_ret_12m)        # light palette
        voo_1w_span   = style_return(voo_ret_1w)         # light palette

        voo_line = f"<p><strong>Benchmark (VOO):</strong> {voo_price_fmt} ({voo_12m_span} last 12M, {voo_1w_span} last week)</p>"
    else:
        voo_line = "<p><strong>Benchmark (VOO):</strong> Not available</p>"

    # --- Merge everything ---
    meta_dict = meta.set_index("ticker").to_dict("index")
    news_grouped = news.groupby("ticker")

    enriched = []
    print("🔎 Prices dict keys:", list(prices.keys())[:10])



    for _, row in top10_df.iterrows():
        ticker = row["ticker"].strip().upper()

        # BEFORE you append to `enriched`  (just after headlines = …)

        # ------------------------------------------------------------
        # build / embed price chart
  # -----------------------------------------------------------------
        #  generate chart  →  base-64  (fail-safe)
        try:
            fig, _ = plot_stock_chart(ticker, save_path=None)
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
            plt.close(fig)                         # free memory
            buf.seek(0)
            chart_b64 = base64.b64encode(buf.read()).decode()
            chart_uri = f"data:image/png;base64,{chart_b64}"
        except Exception as err:
            print(f"⚠️  chart for {ticker} skipped: {err}")
            chart_uri = ""                         # empty → no <img>
# -----------------------------------------------------------------

        # ------------------------------------------------------------
        
        # darker flag in loops       
        
        last_week_val = as_float(row["last_week_return"])
        
        darker = (
            as_float(voo_ret_1w) is not None and
            last_week_val is not None and
            abs(last_week_val) > abs(voo_ret_1w)
        )
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
            "last_week_span": style_return(last_week_val, darker=darker),
            "chart_uri": chart_uri,
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

    for ticker in tickers:                      # keep original order
        row         = top10_df.loc[top10_df["ticker"].str.upper() == ticker].iloc[0]
        ret12_num   = as_float(row["current_return"])
        retwk_num   = as_float(row["last_week_return"])
        price_val   = prices.get(ticker, "—")

        # price formatting ------------------------------------------------------
        if is_real(price_val):
            price_fmt = f"${price_val:.2f}"
        else:
            price_fmt = f"${price_val}"

        # darker?  |stock_1w| > |VOO_1w|  (only if both numeric) ---------------
        darker = (
            as_float(voo_ret_1w) is not None and
            retwk_num is not None and
            retwk_num > voo_ret_1w
        )

        # build coloured spans --------------------------------------------------
        retwk_span = style_return(retwk_num, darker=darker)
        ret12_span = style_return(ret12_num)          # 12-month always light

        text = f"{ticker} – {price_fmt} ({ret12_span} last 12M, {retwk_span} last week)"

        if ticker in added:
            summary_lines.append(f"<i><span style=\"color:#0000FF\">{text}</span></i>")
        elif ticker in continuing:
            summary_lines.append(text)

    for ticker in sorted(dropped):
        price_now = price_curr.get(ticker)
        price_wk0 = as_float(price_wk.get(ticker))
        price_yr0 = as_float(price_yr.get(ticker))

        price_fmt = f"${price_now:.2f}" if is_real(price_now) else f"${price_now}"
        retwk_num = (price_now / price_wk0 - 1) if is_real(price_wk0) else None
        ret12_num = (price_now / price_yr0 - 1) if is_real(price_yr0) else None

        retwk_span = style_return(retwk_num)     # dropped stocks: always light colours
        ret12_span = style_return(ret12_num)

        text = f"{ticker} – {price_fmt} ({ret12_span} last 12 M, {retwk_span} last week)"
        summary_lines.append(f"<span style=\"color:#808080\">{text}</span>")



    summary_html = voo_line + "<h3>Summary of Changes</h3><p>" + "<br>".join(summary_lines) + "</p><p>New stocks in <i><span style=\"color:#0000FF\">blue italic</span></i>, dropped stocks in <span style=\"color:#808080\">gray</span></p>"

    # --- HTML Template ---
    template = Template("""
    <html>
    <head>
        <meta charset="utf-8">
        <title> Momentum Report – {{ formatted_date }}</title>
    </head>
    <body>
        <h2>📈 Momentum Report – {{ formatted_date }}</h2>
        {{ summary_html | safe }}

        {% for stock in enriched %}
            
            <div style="margin-bottom:30px; padding:10px; border-bottom:1px solid #ccc;">
                <h3>{{ stock.ticker }} - {{ stock.name }} – ${{ stock.price }}</h3>
                {% if stock.chart_uri %}
                <img src="{{ stock.chart_uri }}" alt="Price chart for {{ stock.ticker }}" style="max-width: 100%; height: auto; margin-bottom: 10px;">        
                {% endif %}
                <p><strong>Current 12M Return:</strong> {{ stock.current_return }}
                   | <strong>12M Return, as of Last Month:</strong> {{ stock.last_month_return }}
                   | <strong>Rank Change:</strong> {{ stock.rank_change }}</p>
                   | <strong>Last Week Return:</strong> {{ stock.last_week_span | safe }}
                </p>
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
