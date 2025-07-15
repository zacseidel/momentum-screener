# Momentum Screener Architecture

## Next Steps

## Database Diagram

Tables:
- index_allocations
- daily_prices
- index_constituents
- company_metadata
- company_news
- top10_picks

Table details:
- **index_allocations**: Contains the allocation of stocks in the index for each date.
  - Columns: ticker, company, index_type, date, weight
- **daily_prices**: Contains daily stock prices for each ticker.
  - Columns: date, ticker, close
- **index_constituents**: Contains the list of tickers in the index.
    - Columns: ticker, company, index_type, gics_sector, gics_sub_industry, headquarters, date_added, founded
- **company_metadata**: Contains metadata about companies.
  - Columns: ticker, name, description, updated_at
- **company_news**: Contains news articles related to companies.
- Columns: ticker, published_UTC, headline, URL
- **top10_picks**: Contains the top 10 picks for each date.
  - Columns: ticker, current_return, last_month_return, current_rank, last_month_rank, rank_change, date
## SRC Documents

### Prices.py

Directory-level setup:
- Packages:
- Needs:
  - Polygon API
  - Database path, directory path.


#### get_target_dates(today = None)
 - In: "today" date for report
 - Out: dictionary of formatted dated, consisting of
    - yesterday
    - week_ago_yesterday
    - one_year_ago
    - one_month_ago
    - one_year_plus_month_ago

#### fetch_and_store_grouped_prices(date_str, db_path)
 - In: date_str to fetch, path to database
 - Out: prints "Stored XXXX rows for YYYY date"
 - Notes:
    - checks whether date already exists in daily_prices table--skips if it is (daily prices table consists of all stock prices for a set of dates)
    - downloads daily prices for the date
    - If the date doesn't work, it tries the previous weekday, for up to seven days.
    - Inserts the prices into the database

#### fetch_and_store_spx_price(date_str, db_path, max_attempts=7)
 - In: date_str, db_path
 - Out: Stored SPX price for YYYY date

#### download_all_required_price_date(today = None)
 - In: date_str
 - Out: prices stored in database for all stocks and SPX for all target dates
 - Runs:
    - get_target_dates()
    - For all target dates:
        - fetch_and_store_grouped_prices()
        - fetch_and_store_spx_price()

### Ranking.py

Directory-level setup:
- Packages: datetime, os, pandas, sqlite3
- Needs:
  - Database path, directory path.

#### get_price_snapshots(target_dates, index_type, db_path)
 - In: 
 - Out: 
 - Runs:
    - selects tickers from index_constituents --> Unsure how this is handling multiple
    - finds most recent relevant date in daily_prices table in database
    - 

#### compute_returns_and_ranks(df, target_dates)
 - In: 
 - Out: 
 - Runs:

 #### store_top10_picks(result, run_date = None, db_path)
 - In: 
 - Out: 
 - Runs:


### Report.py

### Allocations.py


### Charts.py


### RunReport.py

## Possible Redundancies & Inconsistencies

We have multiple ways of backtracking from a date to the next available date when the market was open.
- Complex setup in fetch_prices functions
- More contained setup

