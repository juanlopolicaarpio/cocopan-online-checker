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

def fetch_foodpanda_widget(lat, lon):
    params = {
        "searchTerm": "cocopan",
        "limit":      100,
        "offset":     0,
        "latitude":   lat,
        "longitude":  lon,
    }
    try:
        r = requests.get(
            "https://www.foodpanda.ph/widget/v2/restaurants",
            params=params, headers=HEADERS, timeout=10
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return set()
    urls = set()
    for item in data.get("items", []):
        href = item.get("url")
        if href:
            full = href if href.startswith("http") else urljoin("https://www.foodpanda.ph", href)
            urls.add(full)
    return urls

def main():
    all_urls = set()
    # Philippines approx lat: 5°N to 19°N, lon: 115°E to 127°E
    latitudes  = [i for i in range(5, 20)]   # 5,6,...19
    longitudes = [i for i in range(115, 128)] # 115,116,...127

    for lat in latitudes:
        for lon in longitudes:
            # Query both APIs at each grid point
            gf = fetch_grabfood_api(lat, lon)
            fp = fetch_foodpanda_widget(lat, lon)
            all_urls.update(gf)
            all_urls.update(fp)
            # be polite
            sleep(0.5)

    result = {"urls": sorted(all_urls)}
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
