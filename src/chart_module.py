"""chart_module.py — helper to build a 1‑year candlestick + volume chart
with a normalised S&P 500 comparison line, using Polygon.io daily
aggregates.

Usage
-----
from chart_module import plot_stock_chart

axs = plot_stock_chart("AVGO", "output/avgo.png")

Embed the saved PNG in your HTML email.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Tuple

import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf  # candlestick helper
import requests
import matplotlib.pyplot as plt


POLYGON_KEY = os.getenv("POLYGON_API_KEY")
BASE_URL = "https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}"

_FETCH_CACHE: dict[tuple[str, str, str], pd.DataFrame] = {}

# -----------------------------------------------------------------------------
# helpers
# -----------------------------------------------------------------------------
from collections import deque
import time, threading, requests

# --- global rate limiter ----------------------------------------------------
_MAX_CALLS = 5           # Polygon Basic
_WINDOW    = 60          # seconds
_CALL_LOG  = deque()     # timestamps of recent calls
_LOCK      = threading.Lock()
_SESSION   = requests.Session()  # TCP reuse speeds things up

def _rate_limited_get(url: str, *, params: dict, timeout: int = 20) -> requests.Response:
    """Perform a GET while blocking if we’re at the 5-calls/min cap."""
    while True:
        with _LOCK:
            now = time.time()
            # drop anything older than 60 s
            while _CALL_LOG and now - _CALL_LOG[0] >= _WINDOW:
                _CALL_LOG.popleft()

            if len(_CALL_LOG) < _MAX_CALLS:
                _CALL_LOG.append(now)
                break          # OK to fire next request

        # Not safe yet – calculate required back-off
        sleep_for = _WINDOW - (now - _CALL_LOG[0]) + 0.1
        time.sleep(sleep_for)

    r = _SESSION.get(url, params=params, timeout=timeout)

    # handle 429 "Too Many Requests" just in case
    if r.status_code == 429:
        retry_after = int(r.headers.get("Retry-After", "15"))
        time.sleep(retry_after)
        return _rate_limited_get(url, params=params, timeout=timeout)

    r.raise_for_status()
    return r




def _fetch_1d_agg(ticker: str, start_dt: datetime, end_dt: datetime, *, sleep_s: float = 13.0) -> pd.DataFrame:
    """Fetch daily OHLCV aggregate bars from Polygon and return a DataFrame.


    Raises RuntimeError if no data comes back (e.g. bad ticker).
    """
    key = (ticker, start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"))
    if key in _FETCH_CACHE:
        return _FETCH_CACHE[key]

    url = BASE_URL.format(ticker=ticker, start=key[1], end=key[2])

    params = {"adjusted": "true", "sort": "asc", "apiKey": POLYGON_KEY}
    r = _rate_limited_get(url, params=params, timeout=20)
    r.raise_for_status()
    js = r.json()
    if not js.get("results"):
        raise RuntimeError(f"Polygon returned no data for {ticker}: {js}")

    df = pd.DataFrame(js["results"])
    
    dt_idx = (
        pd.to_datetime(df["t"], unit="ms", utc=True)
        .dt.tz_convert(None)
    )
    df.index = pd.DatetimeIndex(dt_idx, name = "Date")
    df.sort_index(inplace=True)

    df.rename(
        columns={"o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"},
        inplace=True,
    )

    df = df[["Open", "High", "Low", "Close", "Volume"]]
    _FETCH_CACHE[key] = df
    time.sleep(sleep_s)  # respect Polygon's free-tier rate limits
    return df


def _normalise_series(s: pd.Series) -> pd.Series:
    """Scale a price series to start at 100 so it can be plotted on % basis."""
    return s / s.iloc[0] * 100.0

# -----------------------------------------------------------------------------
# public API
# -----------------------------------------------------------------------------

def plot_stock_chart(
    ticker: str,
    save_path: str | None = None,
    index_ticker: str = "VOO",
    sleep_s: float = 13.0,
) -> Tuple[plt.Figure, Tuple[plt.Axes, plt.Axes]]:
    """Create a candlestick/volume chart for *ticker* for the trailing year.

    A grey normalised line of *index_ticker* (default SPY) is overlaid to
    compare performance.

    Parameters
    ----------
    ticker : str
        Equity ticker symbol, e.g. "AVGO".
    save_path : str | None
        If provided, the figure is saved as PNG at this path.
    index_ticker : str
        Comparison index/ETF (daily OHLCV must be available on Polygon).
    sleep_s : float
        Seconds to `time.sleep()` after *each* Polygon API call to respect
        their free‑tier burst limit (5 req/min, 2 req/sec).

    Returns
    -------
    fig : matplotlib.figure.Figure
    (ax_candle, ax_vol) : tuple of Axes
    """

    if POLYGON_KEY is None:
        raise RuntimeError("POLYGON_API_KEY environment variable not set.")

    utc_today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start_dt = utc_today - timedelta(days=200)

    # --- fetch main ticker ---------------------------------------------------
    df = _fetch_1d_agg(ticker, start_dt, utc_today, sleep_s=sleep_s)

    # --- fetch comparison index ---------------------------------------------
    


    # --- build mplfinance candlestick chart ---------------------------------
    mpf_style = mpf.make_mpf_style(base_mpf_style="yahoo", rc={"axes.grid": False})

    # we will use mplfinance to draw candlesticks + volume, then add comp line
    # --- build mplfinance candlestick chart ------------------------------------
    WIDTH_INCHES  = 12          # wider → wider candles
    HEIGHT_INCHES = 6
    MPF_KWARGS = dict(
        type      = "candle",
        volume    = True,
        mav       = (10, 50),       # simple moving averages (optional)
        style     = mpf.make_mpf_style(
                    base_mpf_style="yahoo",
                    rc={"axes.grid": False}),
        figsize   = (WIDTH_INCHES, HEIGHT_INCHES),
        figratio  = (16, 9),            # keeps the mplfinance title spacing happy
        tight_layout = True,            # let mplfinance call tight_layout itself
        returnfig   = True,
        title       = f"{ticker} vs {index_ticker} – last 200 days",
    )

    #fig, axes = mpf.plot(df, **MPF_KWARGS)
    #ax_candle, ax_vol = axes[0], axes[2]

    # --- overlay normalised index close line -----------------------------------
    # scale the line so it starts at the SAME PRICE as the first candle
    #idx_line = _normalise_series(idx["Close"]) * df["Close"].iloc[0] / 100

    # --- overlay bold, dotted comparison line -----------------------------------
    # 1. pick an anchor ~180 trading days back (or first bar if the series is shorter)
    #anchor_idx = min(150, len(df) - 1)
    #print(anchor_idx)
    #anchor_price = df["Close"].iloc[anchor_idx]
    #print(anchor_price)

    # 2. normalise SPY so it starts at the anchor price
    #spy_norm = idx["Close"] / idx["Close"].iloc[anchor_idx] * anchor_price

    #print(spy_norm.head())

    # 3. draw the line: bold, dotted, high z-order, distinctive colour
    #ax_candle.plot(
    #    spy_norm.index,
    #    spy_norm.values,
    #    linestyle="--",
    #    linewidth=2.5,
    #    color="#ff7f0e",           # matplotlib’s default orange
    #    label=f"{index_ticker} (norm.)",
    #    zorder=20,
    #)

    #ax_candle.legend(loc="upper left", fontsize="x-small")
    idx = _fetch_1d_agg(index_ticker, start_dt, utc_today, sleep_s=sleep_s)

    # --- rescale comparison close so it starts at same price as *df*
    common = df.index.intersection(idx.index)
    if common.empty:
        raise RuntimeError(
            f"No overlapping dates between {ticker} and {index_ticker} price series."
        )
    start = common[50]
    scale = df.loc[start, "Close"] / idx.loc[start, "Close"]
    comp_close = idx["Close"] * scale


    comp_ap = mpf.make_addplot(
        comp_close,
        panel=0,            # same panel as candles
        color="#ff7f0e",
        linestyle="--",
        width=1.0,
        label=f"{index_ticker} (norm.)",
    )

    fig, axes = mpf.plot(df, addplot=comp_ap, **MPF_KWARGS)
    ax_candle, ax_vol = axes[0], axes[2]

    # show legend after addplot is drawn
    ax_candle.legend(loc="upper left", fontsize="x-small")

    # rotate x-tick labels for clarity
    for label in ax_candle.get_xticklabels():
        label.set_rotation(45)
        label.set_ha("right")

    # mplfinance already called tight_layout(), so no extra call here
    if save_path:
        fig.savefig(save_path, dpi=150)
    return fig, (ax_candle, ax_vol)


