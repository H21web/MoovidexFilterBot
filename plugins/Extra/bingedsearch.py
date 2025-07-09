import asyncio
import aiohttp
import logging
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("binged-search")


async def fetch_page(session, page):
    url = f"https://www.binged.com/wp-json/binged-api/v1/movies?mode=all&page={page}"
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                json_data = await response.json()
                logger.debug(f"Fetched page {page} successfully.")
                return {"page": page, "data": json_data.get("data", [])}
            else:
                logger.warning(f"Failed to fetch page {page}: {response.status}")
    except Exception as e:
        logger.warning(f"Error fetching page {page}: {e}")
    return {"page": page, "data": []}


async def get_binged_movie_id(title, max_pages=50):
    start_time = time.time()
    title = title.strip().lower()
    logger.info(f"Searching for title: '{title}' in {max_pages} pages")

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_page(session, page) for page in range(1, max_pages + 1)]
        results = await asyncio.gather(*tasks)

        logger.info("Checking for exact match...")
        for result in results:
            for movie in result["data"]:
                movie_title = movie.get("post_title", "").strip().lower()
                if movie_title == title:
                    logger.info(f"✅ Exact match found on page {result['page']}: {movie_title}")
                    logger.info(f"⏱️ Total time: {time.time() - start_time:.2f}s")
                    return movie["ID"]

        logger.info("No exact match. Checking for partial match...")
        for result in results:
            for movie in result["data"]:
                movie_title = movie.get("post_title", "").strip().lower()
                if title in movie_title:
                    logger.info(f"🔍 Partial match found on page {result['page']}: {movie_title}")
                    logger.info(f"⏱️ Total time: {time.time() - start_time:.2f}s")
                    return movie["ID"]

    logger.info("❌ No match found.")
    logger.info(f"⏱️ Total time: {time.time() - start_time:.2f}s")
    return None
