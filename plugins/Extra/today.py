import requests
import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import temp
from info import *

# List of Admin IDs
ADMIN_IDS = [1011394081, 7191327005]  # Replace with actual admin user IDs

# Function to fetch today's movies
def fetch_today_movies():
    url = "https://www.binged.com/wp-json/binged-api/v1/movies?mode=streaming-today"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36',
        'Referer': 'https://www.binged.com/'
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        try:
            data = response.json()
            return data.get('data', [])  # Extract the 'data' array
        except ValueError:
            return None
    return None

# Function to format the movie title for the search URL
def format_title_for_url(title):
    title = re.sub(r'[^a-zA-Z0-9\s]', '_', title)  # Replace non-alphanumeric characters with '_'
    title = title.replace(' ', '_')  # Replace spaces with '_'
    return title

# /today command - show movie buttons
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
            callback_data = f"movie_detail_{title}"
            buttons.append([InlineKeyboardButton(title, callback_data=callback_data)])

        # Add close button at the end
        buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
        reply_markup = InlineKeyboardMarkup(buttons)

        await message.reply_text("🎬 **Today's Streaming Movies:**", reply_markup=reply_markup)
    else:
        await message.reply_text("⚠️ Failed to fetch today's movies or no movies found. Please try again later.")

# When a movie title button is clicked
@Client.on_callback_query(filters.regex(r"movie_detail_"))
async def show_movie_detail(client, callback_query):
    movie_title = callback_query.data.split("movie_detail_")[1]
    movies_data = fetch_today_movies()

    if movies_data and isinstance(movies_data, list):
        for movie in movies_data:
            if movie.get('title') == movie_title:
                title = movie.get('title', 'No title available')
                language = ', '.join(movie.get('languages', ['No language specified']))
                platform = ', '.join(p.get('name', 'No platform') for p in movie.get('platforms', []))
                movie_type = movie.get('type', 'No type specified')
                genres = ', '.join(movie.get('genres', ['No Data']))
                year = movie.get('theatrical-year', 'N/A')

                movie_details = (
                    f"✅ **{title}** · ({year})\n"
                    f"🎭 {genres} · 🎥 {movie_type} · 🉑 {language}\n"
                    f"📺 {platform}"
                )

                formatted_title = format_title_for_url(title)

                buttons = [
                    [InlineKeyboardButton("🔍 Click to Search", url=f"https://t.me/{temp.U_NAME}?start=Search_{formatted_title}")]
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

# Post to channel if admin clicks the button
@Client.on_callback_query(filters.regex(r"post_movie_"))
async def post_movie_to_channel(client, callback_query):
    movie_title = callback_query.data.split("post_movie_")[1]
    movies_data = fetch_today_movies()

    if movies_data and isinstance(movies_data, list):
        for movie in movies_data:
            if movie.get('title') == movie_title:
                title = movie.get('title', 'No title available')
                language = ', '.join(movie.get('languages', ['No language specified']))
                platform = ', '.join(p.get('name', 'No platform specified') for p in movie.get('platforms', []))
                movie_type = movie.get('type', 'No type specified')
                genres = ', '.join(movie.get('genres', ['No Data']))
                year = movie.get('theatrical-year', 'N/A')

                movie_details = (
                    f"✅ **{title}** · ({year})\n"
                    f"🎥 {movie_type}\n"
                    f"🎭 {genres} · 🉑 {language}\n"
                    f"📺 {platform}\n"
                    f"**@MooviDex**"
                )

                formatted_title = format_title_for_url(title)

                search_button = InlineKeyboardButton("🔍 Click To Search", url=f"https://t.me/{temp.U_NAME}?start=Search_{formatted_title}")
                reply_markup = InlineKeyboardMarkup([[search_button]])

                try:
                    channel_id = "-1001680629032"  # Replace with your channel ID
                    await client.send_message(chat_id=channel_id, text=movie_details, reply_markup=reply_markup)
                    await callback_query.answer("✅ Movie details posted to the channel.")
                except Exception as e:
                    await callback_query.answer(f"⚠️ Error posting movie to channel: {str(e)}")
                break
    else:
        await callback_query.answer("⚠️ Failed to fetch movie details. Please try again later.")

# Close button handler
@Client.on_callback_query(filters.regex(r"close_message"))
async def close_message_callback(client, callback_query):
    try:
        await callback_query.message.delete()
    except Exception:
        await callback_query.answer("⚠️ Unable to delete the message.")
