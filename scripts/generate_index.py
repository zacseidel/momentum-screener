# scripts/generate_index.py

import os
import re
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPORT_DIR = os.path.join(BASE_DIR, "site", "reports")
INDEX_PATH = os.path.join(BASE_DIR, "site", "index.html")


def get_sorted_reports():
    pattern = re.compile(r"momentum_(\d{4}-\d{2}-\d{2})\.html")
    files = []
    for fname in os.listdir(REPORT_DIR):
        match = pattern.match(fname)
        if match:
            date_str = match.group(1)
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d")
                files.append((date, fname))
            except ValueError:
                continue
    return sorted(files, reverse=True)


def generate_sidebar_links(sorted_reports):
    links = []
    for date, fname in sorted_reports:
        display = date.strftime("%B %d, %Y")
        links.append(f'<a href="#" onclick="loadReport(\'reports/{fname}\')">{display}</a>')
    return "\n".join(links)


def generate_index_html(sorted_reports):
    latest = sorted_reports[0][1] if sorted_reports else ""
    latest_src = f"reports/{latest}"

    sidebar_links = generate_sidebar_links(sorted_reports)

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Momentum Screener Reports</title>
  <style>
    body {{ display: flex; font-family: sans-serif; margin: 0; }}
    nav {{ width: 240px; background: #f4f4f4; height: 100vh; overflow-y: auto; padding: 1em; box-shadow: 2px 0 5px rgba(0,0,0,0.1); }}
    nav h2 {{ font-size: 16px; margin-top: 1em; }}
    nav a {{ display: block; margin: 0.5em 0; color: #333; text-decoration: none; }}
    nav a:hover {{ text-decoration: underline; }}
    main {{ flex-grow: 1; padding: 1em; }}
    iframe {{ width: 100%; height: 95vh; border: none; }}
  </style>
</head>
<body>
  <nav>
    <h2>🗂️ Weekly Reports</h2>
    {sidebar_links}
    <h2>📘 Documentation</h2>
    <a href="#" onclick="loadReport('docs/index.html')">View Docs</a>
  </nav>
  <main>
    <iframe id="reportFrame" src="{latest_src}"></iframe>
  </main>

  <script>
    function loadReport(path) {{
      document.getElementById('reportFrame').src = path;
    }}
  </script>
</body>
</html>"""
    return html


def main():
    reports = get_sorted_reports()
    if not reports:
        print("⚠️ No reports found. Skipping index generation.")
        return

    html = generate_index_html(reports)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ Sidebar index written to {INDEX_PATH}")


if __name__ == "__main__":
    main()
