import requests
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Define your admin list
ADMINS = [1011394081]  # Replace with real Telegram user IDs

# Search Binged movie and fetch ID
async def get_binged_movie_id(title, max_pages=5):
    base_url = "https://www.binged.com/wp-json/binged-api/v1/movies"
    title = title.lower()
    for page in range(1, max_pages + 1):
        res = requests.get(f"{base_url}?mode=all&page={page}")
        if res.status_code != 200:
            break
        data = res.json().get("data", [])
        for movie in data:
            movie_title = movie.get("post_title", "").lower()
            if title in movie_title:
                return movie["ID"]
    return None

# Format and fetch details from /movie/<id>
def fetch_movie_details(movie_id):
    res = requests.get(f"https://www.binged.com/wp-json/binged-api/v1/movie/{movie_id}")
    if res.status_code != 200:
        return None
    data = res.json()
    
    title = data.get("post_title")
    year = data.get("release_year")
    description = data.get("post_content", "No description available.")
    category = data.get("category")
    genre = ", ".join(data.get("genre", []))
    language = ", ".join(data.get("lang", []))
    imdb_link = f"https://www.imdb.com/title/{data.get('imdb')}"

    platform_data = data.get("platform_logos", [])
    if platform_data:
        platform_url = platform_data[0].get("ref_url")
        platform_name = platform_url.split("/")[2].split(".")[0].capitalize()
    else:
        platform_url = "https://www.binged.com"
        platform_name = "Unknown"

    trailer_url = None
    for vid in data.get("videos", []):
        if vid.get("type") == "Trailer" and vid.get("source") == "Youtube":
            trailer_url = f"https://www.youtube.com/watch?v={vid.get('url')}"
            break

    message = f"<b>{title}</b> ({year})\n"
    message += f"<b>Category:</b> {category}\n"
    message += f"<b>Genre:</b> {genre}\n"
    message += f"<b>Language:</b> {language}\n"
    message += f"<b>Platform:</b> <a href=\"{platform_url}\">{platform_name}</a>\n"
    message += f"<b>IMDb:</b> <a href=\"{imdb_link}\">{imdb_link}</a>\n"
    message += f"\n<details><summary><b>📖 Description</b></summary>\n<blockquote>{description}</blockquote></details>"

    buttons = []
    if trailer_url:
        buttons.append([InlineKeyboardButton("▶️ Watch Trailer", url=trailer_url)])

    return message, buttons

# Pyrogram handler
@Client.on_message(filters.command("bingedsearch") & filters.user(ADMINS))
async def binged_search_handler(client, message):
    if len(message.command) < 2:
        return await message.reply("❌ Usage: /bingedsearch <movie name>")

    query = " ".join(message.command[1:])
    await message.reply("🔍 Searching for movie...")

    movie_id = await get_binged_movie_id(query)
    if not movie_id:
        return await message.reply("❌ Movie not found.")

    details, keyboard = fetch_movie_details(movie_id)
    if not details:
        return await message.reply("❌ Could not fetch movie details.")

    await message.reply(details, reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=False, parse_mode="html")
