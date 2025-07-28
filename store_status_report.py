#!/usr/bin/env python3
import os, json, requests, smtplib, argparse, socket
from bs4 import BeautifulSoup
from datetime import datetime
from email.mime.text import MIMEText
from email.header import Header
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from requests.exceptions import HTTPError
import time

# ─── Load ENV & Config ────────────────────────────────────────────────────────
load_dotenv()

# In GitHub Actions, environment variables are available directly
# Don't try to "clean" them if they contain the actual values
def get_env_var(var_name, default=None):
    value = os.environ.get(var_name, default)
    if value and value != default:
        # Only clean if it looks like it needs cleaning (has quotes, etc.)
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]  # Remove quotes
        if value.startswith("'") and value.endswith("'"):
            return value[1:-1]  # Remove quotes
        return value.strip()  # Just strip whitespace
    return default

def get_int_env_var(var_name, default):
    value = get_env_var(var_name, str(default))
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

# Get configuration directly from environment
TO_ADDRESS   = get_env_var('TO_ADDRESS')
FROM_ADDRESS = get_env_var('SMTP_USER') 
SMTP_CONFIG  = {
    'host': get_env_var('SMTP_HOST', 'smtp.gmail.com'),
    'port': get_int_env_var('SMTP_PORT', 587),
    'user': get_env_var('SMTP_USER'),
    'pass': get_env_var('SMTP_PASS'),
}

# Debug output - mask sensitive info for logs but verify we have values
print("=== CONFIGURATION DEBUG ===")
print(f"TO_ADDRESS exists: {bool(TO_ADDRESS)}")
print(f"SMTP_HOST exists: {bool(SMTP_CONFIG['host'])}")
print(f"SMTP_PORT: {SMTP_CONFIG['port']}")
print(f"SMTP_USER exists: {bool(SMTP_CONFIG['user'])}")
print(f"SMTP_PASS exists: {bool(SMTP_CONFIG['pass'])}")

if SMTP_CONFIG['pass']:
    print(f"SMTP_PASS length: {len(SMTP_CONFIG['pass'])}")
    # Show first/last char to verify it's not literally "***" 
    if len(SMTP_CONFIG['pass']) > 6:
        print(f"SMTP_PASS sample: '{SMTP_CONFIG['pass'][0]}...{SMTP_CONFIG['pass'][-1]}'")

print("==============================\n")

# Check if we have all required config
missing = []
if not TO_ADDRESS: missing.append('TO_ADDRESS')
if not SMTP_CONFIG['host']: missing.append('SMTP_HOST')  
if not SMTP_CONFIG['user']: missing.append('SMTP_USER')
if not SMTP_CONFIG['pass']: missing.append('SMTP_PASS')

if missing:
    print(f"❌ Missing required environment variables: {missing}")
    print("Check your GitHub Secrets configuration!")
    exit(1)

# Load store URLs
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
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=60000)
                page.wait_for_timeout(3000)
                
                # Check for closed indicators
                closed_indicators = [
                    "text=Temporarily unavailable",
                    "text=Closed for now", 
                    "text=Out of delivery area",
                    "text=Restaurant is closed",
                    ".closed-banner",
                    "[data-testid='closed-banner']"
                ]
                
                for indicator in closed_indicators:
                    if page.query_selector(indicator):
                        browser.close()
                        return False
                        
                browser.close()
                return True
        except Exception as e:
            print(f"  ⚠️  Playwright error: {e}")
            return False
    else:
        # GrabFood
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Check for various closed indicators
            closed_indicators = [
                lambda tag: tag.name in ['div','span','p'] and 'closed' in tag.get_text(strip=True).lower(),
                lambda tag: tag.get('class') and any('closed' in str(c).lower() for c in tag.get('class')),
                lambda tag: 'temporarily unavailable' in tag.get_text(strip=True).lower(),
                lambda tag: 'not available' in tag.get_text(strip=True).lower()
            ]
            
            for indicator in closed_indicators:
                if soup.find(indicator):
                    return False
                    
            return True
        except Exception as e:
            print(f"  ⚠️  Request error: {e}")  
            return False

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

def test_smtp_connection():
    """Test SMTP connection"""
    try:
        print(f"🔍 Testing SMTP connection...")
        with smtplib.SMTP(SMTP_CONFIG['host'], SMTP_CONFIG['port']) as s:
            print("✅ Connected to SMTP server")
            s.starttls()
            print("✅ TLS enabled")
            s.login(SMTP_CONFIG['user'], SMTP_CONFIG['pass'])
            print("✅ Authentication successful")
            return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentication failed: {e}")
        print("🔧 Check your Gmail App Password!")
        return False
    except Exception as e:
        print(f"❌ SMTP connection failed: {e}")
        return False

def send_email(subject, body):
    """Send email"""
    try:
        msg = MIMEText(body, _charset='utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = FROM_ADDRESS
        msg['To'] = TO_ADDRESS
        
        with smtplib.SMTP(SMTP_CONFIG['host'], SMTP_CONFIG['port']) as s:
            s.starttls()
            s.login(SMTP_CONFIG['user'], SMTP_CONFIG['pass'])
            s.send_message(msg)
            print(f"✅ Email sent to {TO_ADDRESS}")
            return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        raise

# ─── Main ────────────────────────────────────────────────────────────────────
def main(dry_run=False):
    print(f"🏪 Starting CocoPan store status check...")
    print(f"📋 Checking {len(STORE_URLS)} stores...\n")
    
    results = []
    for i, url in enumerate(STORE_URLS, 1):
        print(f"🔍 Checking store {i}/{len(STORE_URLS)}: {url}")
        
        # Get store name
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            h1_tag = BeautifulSoup(r.text,'html.parser').select_one('h1')
            name = h1_tag.get_text(strip=True) if h1_tag else None
            if not name or name.lower() == '403 error':
                name = None
        except Exception:
            name = None
            
        if not name:
            slug = url.rstrip('/').split('/')[-1] 
            name = slug.replace('-', ' ').title()

        online = check_store_online(url)
        status = "🟢 ONLINE" if online else "🔴 OFFLINE"
        print(f"  📊 {name}: {status}")
        results.append((name, url, online))

    # Generate report
    report = build_report(results)
    print("\n" + "="*60)
    print("📋 FINAL REPORT:")
    print("="*60)
    print(report)
    print("="*60)
    
    if dry_run:
        print("\n🧪 DRY RUN - Report generated but not emailed")
    else:
        print(f"\n📤 Sending email...")
        send_email("🏪 CocoPan Store Status Report", report)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Print the report instead of sending")
    p.add_argument("--test-config", action="store_true", 
                   help="Test configuration only")
    args = p.parse_args()
    
    if args.test_config:
        print("🔧 Testing configuration...")
        if test_smtp_connection():
            print("✅ Configuration test passed!")
        else:
            print("❌ Configuration test failed!")
            exit(1)  
    else:
        main(dry_run=args.dry_run)