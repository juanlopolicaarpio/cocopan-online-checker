#!/usr/bin/env python3
"""
CocoPan Database Sync - Download latest database from GitHub Actions
Repository: juanlopolicarpio/cocopan-online-checker
"""
import requests
import zipfile
import os
import sys
from datetime import datetime

# Your GitHub Configuration (PRE-CONFIGURED)
GITHUB_USERNAME = "juanlopolicarpio"
GITHUB_REPO = "cocopan-online-checker"
GITHUB_TOKEN = None  # Add personal access token here if repo becomes private

DATABASE_FILE = "store_status.db"
ARTIFACT_NAME = "store-database"

def download_latest_database():
    """Download the latest database from GitHub Actions artifacts"""
    
    # GitHub API URL for artifacts
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO}/actions/artifacts"
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "CocoPan-Database-Sync"
    }
    
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    
    try:
        print("🔍 Searching for latest database from GitHub Actions...")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        artifacts = response.json()["artifacts"]
        
        # Find the latest store-database artifact that hasn't expired
        database_artifacts = [
            artifact for artifact in artifacts 
            if artifact["name"] == ARTIFACT_NAME and not artifact["expired"]
        ]
        
        if not database_artifacts:
            print("❌ No database artifacts found or all have expired")
            print("💡 Make sure GitHub Actions has run at least once")
            print("🔗 Check: https://github.com/juanlopolicarpio/cocopan-online-checker/actions")
            return False
            
        # Get the most recent one
        latest_artifact = max(database_artifacts, key=lambda x: x["created_at"])
        
        print(f"📦 Found database artifact:")
        print(f"   📅 Created: {latest_artifact['created_at']}")
        print(f"   💾 Size: {latest_artifact['size_in_bytes']:,} bytes")
        
        # Download the artifact
        download_url = latest_artifact["archive_download_url"]
        print(f"⬇️  Downloading database...")
        
        download_response = requests.get(download_url, headers=headers, timeout=60)
        download_response.raise_for_status()
        
        # Save and extract the zip file
        zip_filename = f"{ARTIFACT_NAME}.zip"
        with open(zip_filename, "wb") as f:
            f.write(download_response.content)
        
        print(f"📦 Extracting database...")
        with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
            zip_ref.extractall('.')
        
        # Clean up zip file
        os.remove(zip_filename)
        
        if os.path.exists(DATABASE_FILE):
            print(f"✅ Database downloaded successfully: {DATABASE_FILE}")
            
            # Show basic database stats
            try:
                import sqlite3
                conn = sqlite3.connect(DATABASE_FILE)
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM stores")
                store_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM status_checks")
                check_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT MAX(checked_at) FROM status_checks")
                last_check = cursor.fetchone()[0]
                
                # Get recent summary
                cursor.execute("SELECT * FROM summary_reports ORDER BY report_time DESC LIMIT 1")
                summary = cursor.fetchone()
                
                conn.close()
                
                print(f"📊 Database Statistics:")
                print(f"   🏪 {store_count} stores tracked")
                print(f"   📈 {check_count:,} total status checks")
                print(f"   ⏰ Last check: {last_check}")
                
                if summary:
                    print(f"   📋 Latest: {summary[2]}/{summary[1]} online ({summary[4]:.1f}%)")
                
            except Exception as e:
                print(f"   ⚠️ Could not read database stats: {e}")
            
            return True
        else:
            print("❌ Database file not found after extraction")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        print("💡 Check your internet connection")
        return False
    except KeyError as e:
        print(f"❌ GitHub API response error: {e}")
        print("💡 The repository might be private or the API format changed")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    print("🔄 CocoPan Database Sync")
    print("=" * 50)
    print(f"📂 Repository: {GITHUB_USERNAME}/{GITHUB_REPO}")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    success = download_latest_database()
    
    if success:
        print("\n🎉 Database sync completed successfully!")
        print()
        print("💡 Next steps:")
        print("   1. Run: streamlit run dashboard.py")
        print("   2. Open: http://localhost:8501")
        print("   3. View your live CocoPan store dashboard!")
        print()
        print("🔄 To get fresh data later, run this script again")
    else:
        print("\n❌ Database sync failed")
        print()
        print("💡 Troubleshooting:")
        print("   • Make sure GitHub Actions has run at least once")
        print("   • Check: https://github.com/juanlopolicarpio/cocopan-online-checker/actions")
        print("   • Verify your internet connection")
        print("   • If repository is private, add GitHub token to this script")

if __name__ == "__main__":
    main()