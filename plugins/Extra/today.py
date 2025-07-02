import requests
import re
import html
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import temp
from info import *

# List of Admin IDs
ADMIN_IDS = [1011394081, 7191327005]  # Replace with actual admin user IDs

# Function to decode HTML entities and clean text
def clean_text(text):
    if not text:
        return text
    text = html.unescape(text)
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2013', '-').replace('\u2014', '-')
    text = text.replace('\u2026', '...')
    return text

# Fetch today's movies from Binged
def fetch_today_movies():
    url = "https://www.binged.com/wp-json/binged-api/v1/movies?mode=streaming-today"
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://www.binged.com/'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        try:
            return response.json().get('data', [])
        except ValueError:
            return None
    return None

# Format title and year for URL-safe search slug
def format_title_for_url(title, year=None):
    title = clean_text(title)
    title = re.sub(r'[^a-zA-Z0-9\s]', '_', title)
    title = title.replace(' ', '_')
    if year:
        return f"{title}_{year}"
    return title

# /today command
@Client.on_message(filters.command("today"))
async def send_movie_buttons(client, message):
    movies_data = fetch_today_movies()
    if movies_data and isinstance(movies_data, list):
        if not movies_data:
            await message.reply_text("🚫 No movies streaming today.")
            return

        buttons = []
        for movie in reversed(movies_data):
            title = movie.get('title', 'No title available')
            clean_title = clean_text(title)
            callback_data = f"movie_detail_{title}"
            buttons.append([InlineKeyboardButton(clean_title, callback_data=callback_data)])

        buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_text("🎬 **Today's Streaming Movies:**", reply_markup=reply_markup)
    else:
        await message.reply_text("⚠️ Failed to fetch today's movies.")

# Handle movie detail button
@Client.on_callback_query(filters.regex(r"movie_detail_"))
async def show_movie_detail(client, callback_query):
    movie_title = callback_query.data.split("movie_detail_")[1]
    movies_data = fetch_today_movies()

    if movies_data and isinstance(movies_data, list):
        for movie in movies_data:
            if movie.get('title') == movie_title:
                title = clean_text(movie.get('title', 'No title available'))
                language = ', '.join([clean_text(lang) for lang in movie.get('languages', ['No language'])])
                platform = ', '.join([clean_text(p.get('name', 'No platform')) for p in movie.get('platforms', [])])
                movie_type = clean_text(movie.get('type', 'No type') or '')
                genres = ', '.join([clean_text(genre) for genre in movie.get('genres', ['No Data'])])
                year = movie.get('theatrical-year', 'N/A')

                movie_details = (
                    f"✅ **{title}** · ({year})\n"
                    f"🎭 {genres} · 🎥 {movie_type} · 🉑 {language}\n"
                    f"📺 {platform}"
                )

                formatted_title_with_year = format_title_for_url(title, year)

                buttons = [
                    [InlineKeyboardButton("🔍 Click to Search", url=f"https://t.me/{temp.U_NAME}?start=Search_{formatted_title_with_year}")]
                ]

                if callback_query.from_user.id in ADMIN_IDS:
                    buttons.append([InlineKeyboardButton("📣 Post to Channel", callback_data=f"post_movie_{title}")])

                buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
                reply_markup = InlineKeyboardMarkup(buttons)

                await callback_query.message.reply_text(movie_details, reply_markup=reply_markup)
                await callback_query.answer()
                break
    else:
        await callback_query.answer("⚠️ Could not fetch movie details.")

# Admin posts movie to channel
@Client.on_callback_query(filters.regex(r"post_movie_"))
async def post_movie_to_channel(client, callback_query):
    movie_title = callback_query.data.split("post_movie_")[1]
    movies_data = fetch_today_movies()

    if movies_data and isinstance(movies_data, list):
        for movie in movies_data:
            if movie.get('title') == movie_title:
                title = clean_text(movie.get('title', 'No title available'))
                language = ', '.join([clean_text(lang) for lang in movie.get('languages', ['No language'])])
                platform = ', '.join([clean_text(p.get('name', 'No platform')) for p in movie.get('platforms', [])])
                movie_type = clean_text(movie.get('type', 'No type') or '')
                genres = ', '.join([clean_text(genre) for genre in movie.get('genres', ['No Data'])])
                year = movie.get('theatrical-year', 'N/A')

                movie_details = (
                    f"✅ **{title}** · ({year})\n"
                    f"🎥 {movie_type}\n"
                    f"🎭 {genres} · 🉑 {language}\n"
                    f"📺 {platform}\n"
                    f"**@MooviDex**"
                )

                formatted_title_with_year = format_title_for_url(title, year)
                search_button = InlineKeyboardButton("🔍 Click To Search", url=f"https://t.me/{temp.U_NAME}?start=Search_{formatted_title_with_year}")
                reply_markup = InlineKeyboardMarkup([[search_button]])

                try:
                    channel_id = "-1001680629032"  # Your channel ID
                    await client.send_message(chat_id=channel_id, text=movie_details, reply_markup=reply_markup)
                    await callback_query.answer("✅ Movie details posted to the channel.")
                except Exception as e:
                    await callback_query.answer(f"⚠️ Error posting movie to channel: {str(e)}")
                break
    else:
        await callback_query.answer("⚠️ Failed to fetch movie details. Please try again later.")

# Close button callback
@Client.on_callback_query(filters.regex(r"close_message"))
async def close_message_callback(client, callback_query):
    try:
        await callback_query.message.delete()
    except Exception:
        await callback_query.answer("⚠️ Unable to delete the message.")
