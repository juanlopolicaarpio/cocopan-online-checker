#!/usr/bin/env python3
import requests
import json
from urllib.parse import urljoin
from time import sleep

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/115.0.0.0 Safari/537.36'
    )
}

def fetch_grabfood_api(lat, lon):
    params = {
        "matchTerm": "cocopan",
        "latitude":  lat,
        "longitude": lon,
        "start":     0,
        "limit":     100
    }
    try:
        r = requests.get(
            "https://food.grab.com/grabfood/consumer/restaurants",
            params=params, headers=HEADERS, timeout=10
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return set()

    urls = set()
    for r in data.get("restaurants", []):
        slug = r.get("slug") or r.get("restaurant_slug")
        uuid = r.get("uuid") or r.get("restaurant_uuid")
        if slug and uuid:
            path = f"/ph/en/restaurant/{slug}/{uuid}"
            urls.add(urljoin("https://food.grab.com", path))
    return urls

def main():
    all_urls = set()
    # Sweep Philippines: lat 5–19, lon 115–127 at 1° increments
    for lat in range(5, 20):
        for lon in range(115, 128):
            found = fetch_grabfood_api(lat, lon)
            all_urls.update(found)
            sleep(0.2)
    print(json.dumps({"urls": sorted(all_urls)}, indent=2))

if __name__ == "__main__":
    main()
