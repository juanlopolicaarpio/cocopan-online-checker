#!/usr/bin/env python3
import os, json, requests, sqlite3, argparse
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from requests.exceptions import HTTPError
import time

# ─── Database Setup ────────────────────────────────────────────────────────
DATABASE_FILE = os.path.join(os.path.dirname(__file__), 'store_status.db')

def init_database():
    """Initialize SQLite database with required tables"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # Create stores table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            platform TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create status_checks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS status_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id INTEGER,
            is_online BOOLEAN NOT NULL,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            response_time_ms INTEGER,
            error_message TEXT,
            FOREIGN KEY (store_id) REFERENCES stores (id)
        )
    ''')
    
    # Create summary_reports table for hourly summaries
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS summary_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            total_stores INTEGER NOT NULL,
            online_stores INTEGER NOT NULL,
            offline_stores INTEGER NOT NULL,
            online_percentage REAL NOT NULL,
            report_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully")

def get_or_create_store(cursor, name, url):
    """Get store ID or create new store record"""
    platform = "foodpanda" if "foodpanda.ph" in url else "grabfood"
    
    # Try to find existing store
    cursor.execute("SELECT id FROM stores WHERE url = ?", (url,))
    result = cursor.fetchone()
    
    if result:
        return result[0]
    
    # Create new store
    cursor.execute(
        "INSERT INTO stores (name, url, platform) VALUES (?, ?, ?)",
        (name, url, platform)
    )
    return cursor.lastrowid

def save_status_check(store_id, is_online, response_time_ms=None, error_message=None):
    """Save individual store status check to database"""
    import time
    max_retries = 5
    
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(DATABASE_FILE, timeout=30)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO status_checks (store_id, is_online, response_time_ms, error_message)
                VALUES (?, ?, ?, ?)
            ''', (store_id, is_online, response_time_ms, error_message))
            
            conn.commit()
            conn.close()
            return  # Success!
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                print(f"  ⚠️ Database locked, retrying in {attempt + 1} seconds...")
                time.sleep(attempt + 1)
                continue
            else:
                print(f"  ❌ Database error: {e}")
                if 'conn' in locals():
                    conn.close()
                break

def save_summary_report(total_stores, online_stores, offline_stores):
    """Save hourly summary report"""
    # This function is now handled in main() to avoid multiple connections
    pass

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

# ─── Status Check (ORIGINAL WORKING LOGIC) ──────────────────────────────────────
def check_store_online(url):
    """Check if store is online using ORIGINAL WORKING LOGIC"""
    start_time = time.time()
    
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
                        response_time = int((time.time() - start_time) * 1000)
                        return False, response_time, "Store shows as closed"
                        
                browser.close()
                response_time = int((time.time() - start_time) * 1000)
                return True, response_time, None
                
        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)
            print(f"  ⚠️  Playwright error: {e}")
            return False, response_time, str(e)
    else:
        # GrabFood - ORIGINAL WORKING LOGIC
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
        except HTTPError:
            response_time = int((time.time() - start_time) * 1000)
            return False, response_time, "HTTP error"
        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)
            print(f"  ⚠️  Request error: {e}")
            return False, response_time, str(e)

        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # ORIGINAL DETECTION LOGIC
        banner = soup.select_one('.status-banner')
        if banner and 'closed' in banner.get_text(strip=True).lower():
            response_time = int((time.time() - start_time) * 1000)
            return False, response_time, "Status banner shows closed"
        
        response_time = int((time.time() - start_time) * 1000)
        return True, response_time, None

# ─── Reporting ────────────────────────────────────────────────────────────────
def print_summary_report(results):
    """Print a nice summary to console"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    online  = [r for r in results if r[2]]  # r[2] is is_online
    offline = [r for r in results if not r[2]]

    print("\n" + "="*60)
    print(f"🏷️  CocoPan Store Status Report — {now}")
    print("="*60)
    print(f"📊 Total stores checked: {len(results)}")
    print(f"✅ Online:  {len(online)}")
    print(f"❌ Offline: {len(offline)}")
    print(f"📈 Online Rate: {len(online)/len(results)*100:.1f}%")
    print("="*60)
    
    if offline:
        print("🔴 Offline stores:")
        for name, url, _, _, _ in offline:
            short_name = name.replace('Cocopan ', '').replace('- ', '')
            print(f"  ❌ {short_name}")
    
    if online:
        print(f"🟢 Online stores: {len(online)} (showing first 5)")
        for name, url, _, _, _ in online[:5]:
            short_name = name.replace('Cocopan ', '').replace('- ', '')
            print(f"  ✅ {short_name}")
        if len(online) > 5:
            print(f"  ... and {len(online) - 5} more")

# ─── Main Function ────────────────────────────────────────────────────────────
def main():
    print(f"🏪 Starting CocoPan store status check...")
    print(f"📋 Checking {len(STORE_URLS)} stores...")
    print(f"💾 Saving data to database for dashboard\n")
    
    # Initialize database
    init_database()
    
    # Use single connection for all operations
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE, timeout=30)
        cursor = conn.cursor()
        
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

            # Check store status
            is_online, response_time, error_msg = check_store_online(url)
            status = "🟢 ONLINE" if is_online else "🔴 OFFLINE"
            print(f"  📊 {name}: {status} ({response_time}ms)")
            
            # Store in database using existing connection
            store_id = get_or_create_store(cursor, name, url)
            cursor.execute('''
                INSERT INTO status_checks (store_id, is_online, response_time_ms, error_message)
                VALUES (?, ?, ?, ?)
            ''', (store_id, is_online, response_time, error_msg))
            
            results.append((name, url, is_online, response_time, error_msg))

        # Commit all changes at once
        conn.commit()
        
        # Save summary report
        online_count = sum(1 for _, _, is_online, _, _ in results if is_online)
        offline_count = len(results) - online_count
        
        online_percentage = (online_count / len(results) * 100) if len(results) > 0 else 0
        cursor.execute('''
            INSERT INTO summary_reports (total_stores, online_stores, offline_stores, online_percentage)
            VALUES (?, ?, ?, ?)
        ''', (len(results), online_count, offline_count, online_percentage))
        
        conn.commit()
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

    # Print summary
    print_summary_report(results)
    
    print(f"\n💾 Data saved to database!")
    print(f"📊 Launch dashboard: streamlit run dashboard.py")
    print(f"🌐 View at: http://localhost:8501")

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="CocoPan Store Monitor - Database Only")
    p.add_argument("--init-only", action="store_true", help="Just initialize database")
    args = p.parse_args()
    
    if args.init_only:
        init_database()
        print("✅ Database initialized only")
    else:
        main()