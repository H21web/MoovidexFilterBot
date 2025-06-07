import requests
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Function to fetch upcoming movies
def fetch_upcoming_movies():
    url = "https://www.binged.com/wp-json/binged-api/v1/movies?mode=streaming-soon"
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

# Command handler for /upcoming
@Client.on_message(filters.command("upcoming"))
async def send_upcoming_movies(client, message):
    movies_data = fetch_upcoming_movies()

    if movies_data and isinstance(movies_data, list):
        if not movies_data:
            await message.reply_text("🚫 No upcoming movies found.")
            return

        # Build a single message with all movie details
        all_movies_details = "🎬 <b>Upcoming Movies</b>:\n\n"

        for movie in movies_data:
            title = movie.get('title', 'No title available')
            streaming_date = movie.get('streaming-date', 'No streaming date available')
            language = ', '.join(movie.get('languages', ['No language specified']))
            platform = ', '.join(
                platform.get('name', 'No platform specified') for platform in movie.get('platforms', [])
            )
            movie_type = movie.get('type', 'No type specified')

            movie_details = (
                f"◉ <u>{streaming_date}</u>\n"
                f"<b>{title}</b>  ·  <i>{movie_type}</i>\n"
                f"{platform}  ·  {language}\n\n"
            )
            all_movies_details += movie_details

        # Inline keyboard with a close button
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Close", callback_data="close_message")]]
        )

        await message.reply_text(
            all_movies_details,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

    else:
        await message.reply_text("⚠️ Failed to fetch upcoming movies or no movies found. Please try again later.")

# Callback handler for Close button
@Client.on_callback_query(filters.regex("close_message"))
async def close_message_callback(client, callback_query):
    try:
        await callback_query.message.delete()
    except Exception:
        await callback_query.answer("❌ Unable to delete this message.")
