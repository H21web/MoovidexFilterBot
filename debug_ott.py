
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

async def fetch_url(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, timeout=10) as response:
                if response.status == 200:
                    return await response.json()
    except Exception as e:
        print(f"Request Error: {e}")
    return None

async def main():
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://api2.ottplay.com/api/v4.7/web/new-release?limit=5&from_date={today}&to_date={today}&content_type=all&language=&provider="
    print(f"Fetching: {url}")
    data = await fetch_url(url)
    
    if data and 'result' in data:
        for movie in data['result']:
            print(f"\nTitle: {movie.get('name')}")
            providers = movie.get('where_to_watch', [])
            for p in providers:
                print(json.dumps(p, indent=2))
    else:
        print("No data found")

if __name__ == "__main__":
    asyncio.run(main())
