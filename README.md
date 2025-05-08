# momentumscreen
An automated weekly report on top momentum stocks


What this does (momentum screener)
Key dependencies and how to install
How to set up secrets
GitHub Actions schedule
Folder structure
Example output (screenshot of HTML email)
Expansion ideas (Russell 2000, valuation factors, etc.)





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
