# momentumscreen


----------------
Need to add:
 - Current price
 - Change since last week

 - Last week's picks, this weeks picks

- Notebook to generate the report for a past date
----------------



An automated weekly report on top momentum stocks.

The script downloads the top stocks in the SP500 over the past year, and filters for stocks whose relative performance is better now than one month ago.

- Gets stock symbols for the index from wikipedia
- Obtains relative market cap information from SPDR index funds site
- Pulls stock market data, company information, and recent headlines from polygon.io
- Sends an automated email with Sendgrid's API and Github Actions

```text
momentum-screener/  
│  
├── data/                      # Optional local cache or SQLite DB  
│   └── market_data.sqlite  
│
├── notebooks/                 # For exploratory development  
│   └── setup_notebook.ipynb   # Initial dev + database setup  
│
├── src/                       # Core logic as importable modules  
│   ├── __init__.py  
│   ├── prices.py              # Polygon fetch + price caching  
│   ├── allocations.py         # SPDR XLSX download + parsing  
│   ├── ranking.py             # Return calculation + ranking  
│   ├── report.py              # Metadata, news, HTML rendering  
│   └── emailer.py             # Email sending  
│
├── run_report.py              # Main runner script for GitHub Actions  
├── init_db.py                 # One-time database schema init  
├── requirements.txt  
│  
├── .github/  
│   └── workflows/  
│       └── weekly_momentum.yml  # GitHub Actions workflow  
│  
└── README.md  
```


### Initial Setup Sequence

✅ Clone your GitHub repo  
✅ Run init_db.py or setup_notebook.ipynb to create SQLite schema  
✅ Populate tables:  
- Scrape S&P constituents (sp500, sp400)  
- Download SPY + MDY allocations  
✅ Create a .env file (locally) for local testing:  
- POLYGON_API_KEY=your_key  
- SMTP_PASSWORD=your_password  
- SMTP_USER=your@email.com  
✅ Create GitHub Secrets for:  
- POLYGON_API_KEY  
- SMTP_PASSWORD  
- SMTP_USER  
✅ Test run_report.py locally  
✅ Commit to GitHub + verify weekly GitHub Actions trigger  
📓 Development Notebook (notebooks/setup_notebook.ipynb)  


🧪 Additional Utilities (recommended later)

Backtest notebook — track if top picks outperform SPY
Weight drift analyzer — analyze changes in SPY/MDY allocation over time
News tagger — classify news sentiment or themes for top picks
Debug CLI — run: python run_report.py --today 2025-05-06 for local overrides
📝 README.md Template

Document:

What this does (momentum screener)
Key dependencies and how to install
How to set up secrets
GitHub Actions schedule
Folder structure
Example output (screenshot of HTML email)
Expansion ideas (Russell 2000, valuation factors, etc.)

## Checklist Summary

✅ Setup  
- Clone repo and install Python deps  
- Run init_db.py or setup_notebook.ipynb  
 - Verify SQLite schema and seed with initial data  
 - Add .env or GitHub secrets  
✅ Core Scripts  
 - prices.py: download + cache price data  
 - allocations.py: download SPY/MDY and save to DB  
 - ranking.py: compute returns + rank logic  
 - report.py: fetch metadata, news, format HTML  
 - emailer.py: send via SMTP  
 - run_report.py: orchestrator  
✅ Automation  
 - weekly_momentum.yml for GitHub Actions  
 - Email tested and reliable  
 - Logs/stats optional (next phase)  
