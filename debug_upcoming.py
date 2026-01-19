import aiohttp
import asyncio
import json

async def fetch_debug():
    url = "https://api2.ottplay.com/api/v4.5/web/ranking?module_name=hot_new&platform=web&section=widget_coming_soon_to_you&page=1&pin_it=true&template_name=upcoming_content"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                print(f"Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    # Print top level keys
                    print(f"Keys: {data.keys()}")
                    
                    if 'data' in data:
                        print("Found 'data' key.")
                        print(json.dumps(data['data'], indent=2)[:500]) # Print first 500 chars of data
                    elif 'result' in data:
                        print("Found 'result' key.")
                    else:
                        print("Neither data nor result found.")
                        print(json.dumps(data, indent=2)[:500])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(fetch_debug())
