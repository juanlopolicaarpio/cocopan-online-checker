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

# Strip quotes and whitespace from environment variables
def clean_env_var(var_name, default=None):
    value = os.getenv(var_name, default)
    if value and value not in ['***', '', 'None', 'null']:
        # Strip all types of whitespace including newlines, tabs, etc.
        cleaned = value.strip().strip('"').strip("'").strip()
        return cleaned
    return default

def get_int_env_var(var_name, default):
    value = clean_env_var(var_name, str(default))
    try:
        return int(value)
    except (ValueError, TypeError):
        print(f"Warning: Could not convert {var_name}='{value}' to int, using default {default}")
        return default

# Check if required environment variables are available
required_vars = ['TO_ADDRESS', 'SMTP_USER', 'SMTP_PASS', 'SMTP_HOST']
missing_vars = []
for var in required_vars:
    if not os.getenv(var) or os.getenv(var) in ['***', '', 'None', 'null']:
        missing_vars.append(var)

if missing_vars:
    print(f"Error: Missing required environment variables: {missing_vars}")
    print("Please check your GitHub Secrets configuration.")
    exit(1)

TO_ADDRESS   = clean_env_var('TO_ADDRESS')
FROM_ADDRESS = clean_env_var('SMTP_USER')
SMTP_CONFIG  = {
    'host': clean_env_var('SMTP_HOST', 'smtp.gmail.com'),
    'port': get_int_env_var('SMTP_PORT', 587),
    'user': clean_env_var('SMTP_USER'),
    'pass': clean_env_var('SMTP_PASS'),
}

# Debug print SMTP config (without password)
print(f"SMTP Config - Host: '{SMTP_CONFIG['host']}', Port: {SMTP_CONFIG['port']}, User: '{SMTP_CONFIG['user']}'")

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
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page    = browser.new_page()
                page.goto(url, timeout=60000)
                # give it a moment to render dynamic overlays
                page.wait_for_timeout(3000)
                # detect a "closed" overlay
                if ( page.query_selector("text=Temporarily unavailable") or
                     page.query_selector("text=Closed for now")       or
                     page.query_selector("text=Out of delivery area") ):
                    browser.close()
                    return False
                browser.close()
                return True
        except Exception as e:
            print(f"Playwright error for {url}: {e}")
            return False

    # else: GrabFood
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"Request error for {url}: {e}")
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

def test_smtp_connection():
    """Test SMTP connection with better error handling"""
    try:
        print(f"Testing DNS resolution for {SMTP_CONFIG['host']}...")
        socket.gethostbyname(SMTP_CONFIG['host'])
        print(f"✓ DNS resolution successful for {SMTP_CONFIG['host']}")
        
        print(f"Testing SMTP connection to {SMTP_CONFIG['host']}:{SMTP_CONFIG['port']}...")
        with smtplib.SMTP(SMTP_CONFIG['host'], SMTP_CONFIG['port']) as s:
            print("✓ SMTP server connection established")
            s.starttls()
            print("✓ TLS encryption enabled")
            s.login(SMTP_CONFIG['user'], SMTP_CONFIG['pass'])
            print("✓ SMTP authentication successful")
            return True
    except socket.gaierror as e:
        print(f"✗ DNS resolution failed: {e}")
        return False
    except smtplib.SMTPAuthenticationError as e:
        print(f"✗ SMTP Authentication failed: {e}")
        print("This usually means:")
        print("  1. Incorrect username or password")
        print("  2. For Gmail: You need to use an 'App Password' instead of your regular password")
        print("  3. For Gmail: 2-Factor Authentication must be enabled to create App Passwords")
        print("  4. The app password may have expired and needs to be regenerated")
        print("  5. COMMON ISSUE: Extra whitespace (newlines/spaces) in the password")
        print("  6. Check https://support.google.com/mail/?p=BadCredentials for more info")
        print("\n🔧 TO FIX: Go to GitHub Secrets, clear SMTP_PASS completely, and paste ONLY the 16-character app password")
        return False
    except smtplib.SMTPException as e:
        print(f"✗ SMTP error: {e}")
        return False
    except Exception as e:
        print(f"✗ Connection error: {e}")
        return False

def send_email(subject, body, max_retries=3):
    """Send email with retry mechanism"""
    for attempt in range(max_retries):
        try:
            print(f"Email attempt {attempt + 1}/{max_retries}")
            
            # Test connection first
            if not test_smtp_connection():
                if attempt < max_retries - 1:
                    print(f"Retrying in 10 seconds...")
                    time.sleep(10)
                    continue
                else:
                    raise Exception("SMTP connection failed after all retries")
            
            msg = MIMEText(body, _charset='utf-8')
            msg['Subject'] = Header(subject, 'utf-8')
            msg['From']    = FROM_ADDRESS
            msg['To']      = TO_ADDRESS
            
            with smtplib.SMTP(SMTP_CONFIG['host'], SMTP_CONFIG['port']) as s:
                s.starttls()
                s.login(SMTP_CONFIG['user'], SMTP_CONFIG['pass'])
                s.send_message(msg)
                print(f"✅ Email sent successfully to {TO_ADDRESS}")
                return True
                
        except Exception as e:
            print(f"✗ Email attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in 10 seconds...")
                time.sleep(10)
            else:
                print(f"✗ All email attempts failed")
                raise

# ─── Main ────────────────────────────────────────────────────────────────────
def main(dry_run=False):
    print(f"Starting CocoPan store status check...")
    print(f"Checking {len(STORE_URLS)} stores...")
    
    results = []
    for i, url in enumerate(STORE_URLS, 1):
        print(f"Checking store {i}/{len(STORE_URLS)}: {url}")
        
        # extract a human name from <h1> or fallback to URL slug
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            h1_tag = BeautifulSoup(r.text,'html.parser').select_one('h1')
            txt = h1_tag.get_text(strip=True) if h1_tag else None
            name = txt if txt and txt.lower()!='403 error' else None
        except Exception as e:
            print(f"  Error getting store name: {e}")
            name = None
            
        if not name:
            slug = url.rstrip('/').split('/')[-1]
            name = slug.replace('-', ' ').title()

        online = check_store_online(url)
        status = "ONLINE" if online else "OFFLINE"
        print(f"  {name}: {status}")
        results.append((name, url, online))

    report = build_report(results)
    print("\n" + "="*50)
    print("REPORT GENERATED:")
    print("="*50)
    print(report)
    print("="*50)
    
    if dry_run:
        print("\n🔍 DRY RUN - Report would be emailed but not actually sent")
    else:
        print(f"\n📧 Sending email to {TO_ADDRESS}...")
        try:
            send_email("CocoPan Store Status Report", report)
        except Exception as e:
            print(f"✗ Failed to send email: {e}")
            print("📄 Report content saved for debugging:")
            print(report)
            raise

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Print the report instead of sending")
    p.add_argument("--test-config", action="store_true",
                   help="Test configuration and SMTP connection only")
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