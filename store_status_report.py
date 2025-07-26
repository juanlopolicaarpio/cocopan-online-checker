#!/usr/bin/env python3
import os, json, requests, smtplib, argparse
from bs4 import BeautifulSoup
from datetime import datetime
from email.mime.text import MIMEText
from email.header import Header
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from requests.exceptions import HTTPError

# ─── Load ENV & Config ────────────────────────────────────────────────────────
load_dotenv()
TO_ADDRESS   = os.environ['TO_ADDRESS']
FROM_ADDRESS = os.environ['SMTP_USER']
SMTP_CONFIG  = {
    'host': os.getenv('SMTP_HOST', 'smtp.gmail.com'),
    'port': int(os.getenv('SMTP_PORT', 587)),
    'user': os.environ['SMTP_USER'],
    'pass': os.environ['SMTP_PASS'],
}
# branch_urls.json must contain {"urls": [ "...", "..." ]}
BRANCH_FILE = os.path.join(os.path.dirname(__file__), 'branch_urls.json')
with open(BRANCH_FILE) as f:
    STORE_URLS = json.load(f)['urls']

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/115.0.0.0 Safari/537.36'
    )
}

# ─── Status Check ──────────────────────────────────────────────────────────────
def check_store_online(url):
    if 'foodpanda.ph' in url:
        # use Playwright for FP
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page    = browser.new_page()
            page.goto(url, timeout=60000)
            # give it a moment to render dynamic overlays
            page.wait_for_timeout(3000)
            # detect a “closed” overlay
            if ( page.query_selector("text=Temporarily unavailable") or
                 page.query_selector("text=Closed for now")       or
                 page.query_selector("text=Out of delivery area") ):
                browser.close()
                return False
            browser.close()
            return True

    # else: GrabFood
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
    except Exception:
        return False

    soup = BeautifulSoup(r.text, 'html.parser')
    closed = soup.find(
        lambda tag: tag.name in ['div','span','p']
                    and tag.get_text(strip=True).lower() == 'closed'
    )
    return not bool(closed)

# ─── Reporting ────────────────────────────────────────────────────────────────
def build_report(results):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    online  = [(n,u) for n,u,o in results if o]
    offline = [(n,u) for n,u,o in results if not o]

    lines = [
        f"🏷️  CocoPan Store Status Report — {now}",
        f"Total stores checked: {len(results)}",
        f"✅ Online:  {len(online)}",
        f"❌ Offline: {len(offline)}",
        "",
        "🟢 Online branches:",
    ]
    for name, url in online:
        lines.append(f"- [{name}]({url})")

    lines += ["", "🔴 Offline branches:"]
    for name, url in offline:
        lines.append(f"- [{name}]({url})")

    return "\n".join(lines)

def send_email(subject, body):
    msg = MIMEText(body, _charset='utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From']    = FROM_ADDRESS
    msg['To']      = TO_ADDRESS
    with smtplib.SMTP(SMTP_CONFIG['host'], SMTP_CONFIG['port']) as s:
        s.starttls()
        s.login(SMTP_CONFIG['user'], SMTP_CONFIG['pass'])
        s.send_message(msg)

# ─── Main ────────────────────────────────────────────────────────────────────
def main(dry_run=False):
    results = []
    for url in STORE_URLS:
        # extract a human name from <h1> or fallback to URL slug
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            txt = BeautifulSoup(r.text,'html.parser')\
                    .select_one('h1')\
                    .get_text(strip=True)
            name = txt if txt and txt.lower()!='403 error' else None
        except:
            name = None
        if not name:
            slug = url.rstrip('/').split('/')[-1]
            name = slug.replace('-', ' ').title()

        online = check_store_online(url)
        results.append((name, url, online))

    report = build_report(results)
    if dry_run:
        print(report)
    else:
        send_email("CocoPan Store Status Report", report)
        print(f"✅ Report emailed to {TO_ADDRESS}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Print the report instead of sending")
    args = p.parse_args()
    main(dry_run=args.dry_run)
