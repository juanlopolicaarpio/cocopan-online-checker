import requests
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError

def check_store_online(url):
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
    except HTTPError:
        # If we get 403, 404, etc., treat as offline
        return False
    except Exception:
        # On network issues/timeouts, also treat as offline
        return False

    soup = BeautifulSoup(resp.text, 'html.parser')
    # Adjust this selector if your storefront uses a different class
    banner = soup.select_one('.status-banner')
    if banner and 'closed' in banner.get_text(strip=True).lower():
        return False
    return True

if __name__ == '__main__':
    test_urls = [
        'https://food.grab.com/ph/en/restaurant/cocopan-recto-delivery/2-C6TAT22GNVN2AA',
        'https://food.grab.com/ph/en/restaurant/cocopan-maypajo-delivery/2-C6XKTFWELJ51R6'
    ]
    for u in test_urls:
        status = 'ONLINE' if check_store_online(u) else 'OFFLINE'
        print(f"{u} -> {status}")
