import os
import json
import requests
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError
from datetime import datetime
import smtplib
import argparse
from email.mime.text import MIMEText
from email.header import Header

# === CONFIG FROM ENV & JSON ===
BRANCH_FILE = os.path.join(os.path.dirname(__file__), 'branch_urls.json')
with open(BRANCH_FILE) as f:
    STORE_URLS = json.load(f)['urls']

SMTP_CONFIG = {
    'host': os.getenv('SMTP_HOST', 'smtp.gmail.com'),
    'port': int(os.getenv('SMTP_PORT', 587)),
    'user': os.environ['SMTP_USER'],
    'pass': os.environ['SMTP_PASS'],
}

TO_ADDRESS   = os.environ['TO_ADDRESS']
FROM_ADDRESS = SMTP_CONFIG['user']

# === FUNCTIONS ===
def scrape_store(url):
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/115.0.0.0 Safari/537.36'
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except (HTTPError, Exception):
        short = url.rstrip('/').split('/')[-1]
        return short.replace('-', ' ').title(), False

    soup = BeautifulSoup(resp.text, 'html.parser')
    name_elem = soup.select_one('h1')
    name = name_elem.get_text(strip=True) if name_elem else url
    banner = soup.select_one('.status-banner')
    online = not (banner and 'closed' in banner.get_text(strip=True).lower())
    return name, online

def build_report(results):
    now   = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    total = len(results)
    online = [(n,u) for n,u,o in results if o]
    offline= [(n,u) for n,u,o in results if not o]

    lines = [
        f"🏷️  CocoPan Store Status Report — {now}",
        f"Total stores checked: {total}",
        f"✅ Online:  {len(online)}",
        f"❌ Offline: {len(offline)}",
        "",
        "🟢 Online branches:",
    ]
    for name,url in online:
        lines.append(f"- {name} — {url}")

    lines += ["", "🔴 Offline branches:"]
    for name,url in offline:
        lines.append(f"- {name} — {url}")

    return "\n".join(lines)

def send_email(subject, body):
    msg = MIMEText(body, _charset='utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From']    = FROM_ADDRESS
    msg['To']      = TO_ADDRESS

    with smtplib.SMTP(SMTP_CONFIG['host'], SMTP_CONFIG['port']) as server:
        server.starttls()
        server.login(SMTP_CONFIG['user'], SMTP_CONFIG['pass'])
        server.send_message(msg)

# === MAIN ===
def main(dry_run=False):
    results = [(*scrape_store(url), url) for url in STORE_URLS]
    report = build_report(results)

    if dry_run:
        print(report)
    else:
        send_email("CocoPan Store Status Report", report)
        print("✅ Report emailed to", TO_ADDRESS)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Print report instead of sending email")
    args = p.parse_args()
    main(dry_run=args.dry_run)
