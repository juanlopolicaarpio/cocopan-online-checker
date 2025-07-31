#!/usr/bin/env python3
"""
CocoPan Monitoring System - Easy Startup Script
Repository: juanlopolicarpio/cocopan-online-checker
"""
import os
import sys
import subprocess
from datetime import datetime

def print_header():
    print("🥥" * 25)
    print("🏪 CocoPan Store Monitoring System")
    print("🥥" * 25)
    print(f"📅 {datetime.now().strftime('%B %d, %Y • %I:%M %p')}")
    print()

def check_requirements():
    """Quick check if main requirements are available"""
    print("🔍 Checking system requirements...")
    
    required = ['requests', 'streamlit', 'plotly', 'pandas']
    missing = []
    
    for package in required:
        try:
            __import__(package)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} - MISSING")
            missing.append(package)
    
    if missing:
        print(f"\n❌ Missing packages: {', '.join(missing)}")
        print("💡 Run: pip install -r requirements.txt")
        return False
    
    print("✅ Requirements check passed")
    return True

def main():
    print_header()
    
    # Quick requirements check
    if not check_requirements():
        print("\n❌ Please install requirements first")
        sys.exit(1)
    
    # Check what's available
    has_database = os.path.exists('store_status.db')
    
    if has_database:
        print("📊 Found existing database")
        
        # Show quick stats
        try:
            import sqlite3
            conn = sqlite3.connect('store_status.db')
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM stores')
            stores = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM status_checks')
            checks = cursor.fetchone()[0]
            
            cursor.execute('SELECT MAX(checked_at) FROM status_checks')
            last_check = cursor.fetchone()[0]
            
            conn.close()
            
            print(f"  📁 {stores} stores tracked")
            print(f"  📈 {checks:,} total status checks")
            print(f"  ⏰ Last check: {last_check}")
            
        except Exception as e:
            print(f"  ⚠️ Database error: {e}")
    else:
        print("❌ No local database found")
    
    print("\n❓ What would you like to do?")
    print("  1. 🚀 Launch dashboard (view current data)")
    print("  2. 🔄 Sync latest database from GitHub Actions")
    print("  3. 🧪 Test scraper locally (takes 3-5 minutes)")
    
    if has_database:
        print("  4. 📊 Show database statistics")
    
    print("  0. ❌ Exit")
    
    try:
        choice = input("\nEnter your choice (0-4): ").strip()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
    
    if choice == "1":
        print("\n🚀 Launching CocoPan Dashboard...")
        print("💡 Dashboard will open at: http://localhost:8501")
        print("💡 Press Ctrl+C to stop the dashboard")
        print()
        try:
            subprocess.run([sys.executable, '-m', 'streamlit', 'run', 'dashboard.py'])
        except KeyboardInterrupt:
            print("\n👋 Dashboard stopped")
    
    elif choice == "2":
        print("\n🔄 Syncing latest database from GitHub Actions...")
        subprocess.run([sys.executable, 'sync_database.py'])
        
        # Ask if they want to launch dashboard after sync
        if os.path.exists('store_status.db'):
            launch = input("\n❓ Launch dashboard now? (y/n): ").strip().lower()
            if launch == 'y' or launch == 'yes':
                print("\n🚀 Launching dashboard...")
                subprocess.run([sys.executable, '-m', 'streamlit', 'run', 'dashboard.py'])
    
    elif choice == "3":
        print("\n🧪 Testing scraper locally...")
        print("⚠️  This will take 3-5 minutes to check all stores")
        print("💡 Press Ctrl+C to cancel")
        
        confirm = input("Continue? (y/n): ").strip().lower()
        if confirm == 'y' or confirm == 'yes':
            try:
                subprocess.run([sys.executable, 'store_status_report.py'])
                
                # Ask about launching dashboard
                if os.path.exists('store_status.db'):
                    launch = input("\n❓ Launch dashboard to view results? (y/n): ").strip().lower()
                    if launch == 'y' or launch == 'yes':
                        subprocess.run([sys.executable, '-m', 'streamlit', 'run', 'dashboard.py'])
            except KeyboardInterrupt:
                print("\n⚠️ Scraper test cancelled")
    
    elif choice == "4" and has_database:
        print("\n📊 Database Statistics:")
        try:
            import sqlite3
            conn = sqlite3.connect('store_status.db')
            cursor = conn.cursor()
            
            # Store count
            cursor.execute('SELECT COUNT(*) FROM stores')
            stores = cursor.fetchone()[0]
            
            # Platform breakdown
            cursor.execute('SELECT platform, COUNT(*) FROM stores GROUP BY platform')
            platforms = cursor.fetchall()
            
            # Total checks
            cursor.execute('SELECT COUNT(*) FROM status_checks')
            total_checks = cursor.fetchone()[0]
            
            # Checks today
            cursor.execute('SELECT COUNT(*) FROM status_checks WHERE DATE(checked_at) = DATE("now")')
            today_checks = cursor.fetchone()[0]
            
            # Latest summary
            cursor.execute('SELECT * FROM summary_reports ORDER BY report_time DESC LIMIT 1')
            summary = cursor.fetchone()
            
            print(f"📁 Total stores tracked: {stores}")
            for platform, count in platforms:
                print(f"   • {platform.title()}: {count} stores")
            
            print(f"📈 Status checks: {total_checks:,} total, {today_checks} today")
            
            if summary:
                print(f"📋 Latest summary: {summary[2]}/{summary[1]} online ({summary[4]:.1f}%)")
                print(f"⏰ Last updated: {summary[5]}")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ Error reading database: {e}")
    
    elif choice == "0":
        print("\n👋 Goodbye!")
    
    else:
        print("\n❌ Invalid choice")

if __name__ == "__main__":
    main()