import asyncio
import aiohttp
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
import io
# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("binged-bot")


# Binged Search Logic
async def fetch_page(session, page):
    url = f"https://www.binged.com/wp-json/binged-api/v1/movies?mode=all&page={page}"
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                json_data = await response.json()
                return {"page": page, "data": json_data.get("data", [])}
    except Exception as e:
        logger.warning(f"Error fetching page {page}: {e}")
    return {"page": page, "data": []}


async def get_binged_movie_id(title, max_pages=50):
    title = title.strip().lower()
    log_buffer = io.StringIO()
    log_buffer.write(f"Searching Binged for '{title}' (max {max_pages} pages)...\n")

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_page(session, page) for page in range(1, max_pages + 1)]
        results = await asyncio.gather(*tasks)

        # Exact match
        for result in results:
            for movie in result["data"]:
                movie_title = movie.get("post_title", "").strip().lower()
                if movie_title == title:
                    log_buffer.write(f"✅ Exact match: {movie_title} (Page {result['page']})\n")
                    return movie["ID"], movie.get("post_title"), log_buffer

        # Partial match
        for result in results:
            for movie in result["data"]:
                movie_title = movie.get("post_title", "").strip().lower()
                if title in movie_title:
                    log_buffer.write(f"🔍 Partial match: {movie_title} (Page {result['page']})\n")
                    return movie["ID"], movie.get("post_title"), log_buffer

    log_buffer.write("❌ No match found.\n")
    return None, None, log_buffer
    
@Client.on_message(filters.command("binged") & filters.private)
async def binged_command(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❌ Please provide a search query.\n\nExample:\n`/binged pushpa`", quote=True)
        return

    query = " ".join(message.command[1:])
    await message.reply_text(f"🔍 Searching Binged for: **{query}**", quote=True)

    try:
        movie_id, movie_title = await get_binged_movie_id(query)
        if movie_id:
            await message.reply_text(f"✅ **Found:** `{movie_title}`\n🎬 **ID:** `{movie_id}`", quote=True)
        else:
            await message.reply_text("❌ Movie not found on Binged.", quote=True)
    except Exception as e:
        logger.error(f"Error during /binged search: {e}")
        await message.reply_text("⚠️ An error occurred during search. Please try again later.", quote=True)
