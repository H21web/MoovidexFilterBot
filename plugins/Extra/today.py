import requests
import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import temp
from info import *
# List of Admin IDs
ADMIN_IDS = ADMINS  # Replace with actual admin user IDs

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

# Command handler for /today
@Client.on_message(filters.command("today"))
async def send_today_movies(client, message):
    movies_data = fetch_today_movies()
    
    if movies_data and isinstance(movies_data, list):
        if not movies_data:
            await message.reply_text("🚫 No movies streaming today.")
            return

        for movie in movies_data:
            title = movie.get('title', 'No title available')
            streaming_date = movie.get('streaming-date', 'No streaming date available')
            language = ', '.join(movie.get('languages', ['No language specified']))
            platform = ', '.join(platform.get('name', 'No platform specified') for platform in movie.get('platforms', []))
            movie_type = movie.get('type', 'No type specified')  # Add movie type
            genres = ', '.join(movie.get('genres', ['No Data']))
            year = movie.get('theatrical-year', 'N/A')
            # Build the movie's details message
            movie_details = (
                f"✅ **{title}** · ({year})\n"
              #  f"🗓️ **sᴛʀᴇᴀᴍɪɴɢ ᴅᴀᴛᴇ:** {streaming_date}\n"
                f"🎭 {genres} · 🎥 {movie_type} · 🉑 {language}\n"
                f"📺 {platform}\n"
            )

            # Format title for search URL
            formatted_title = format_title_for_url(title)

            # Create buttons
            search_button = InlineKeyboardButton("🔍 Click to Search", url=f"https://t.me/{temp.U_NAME}?start=Search_{formatted_title}")

            buttons = [[search_button]]
            
            # Check if the user is an admin
            if message.from_user.id in ADMIN_IDS:
                post_button = InlineKeyboardButton("📣 Post to Channel", callback_data=f"post_movie_{title}")
                buttons.append([post_button])

            reply_markup = InlineKeyboardMarkup(buttons)

            # Send movie details with buttons
            await message.reply_text(movie_details, reply_markup=reply_markup)
    else:
        await message.reply_text("⚠️ Failed to fetch today's movies or no movies found. Please try again later.")

# Callback query handler for posting movie to channel
@Client.on_callback_query(filters.regex(r"post_movie_"))
async def post_movie_to_channel(client, callback_query):
    # Get the movie title from the callback data
    movie_title = callback_query.data.split("post_movie_")[1]
    
    # Find the movie data in the fetched list
    movies_data = fetch_today_movies()
    
    if movies_data and isinstance(movies_data, list):
        for movie in movies_data:
            if movie.get('title') == movie_title:
                title = movie.get('title', 'No title available')
                streaming_date = movie.get('streaming-date', 'No streaming date available')
                language = ', '.join(movie.get('languages', ['No language specified']))
                platform = ', '.join(platform.get('name', 'No platform specified') for platform in movie.get('platforms', []))
                movie_type = movie.get('type', 'No type specified')  # Add movie type
                genres = ', '.join(movie.get('genres', ['No Data']))
                year = movie.get('theatrical-year', 'N/A')
                # Build the movie's details message for the channel
                movie_details = (
                    f"✅ **{title}** · ({year})\n"
                    f"🎥 {movie_type}\n"
                  #  f"🗓️ **sᴛʀᴇᴀᴍɪɴɢ ᴅᴀᴛᴇ:** {streaming_date}\n"
                    f"🎭 {genres} · 🉑 {language}\n"
                    f"📺 {platform}\n"
                    f"**@MooviDex**"
                )
                # Format title for search URL
                formatted_title = format_title_for_url(title)

                # Create a search button
                search_button = InlineKeyboardButton("🔍 Click To Search", url=f"https://t.me/{temp.U_NAME}?start=Search_{formatted_title}")

                reply_markup = InlineKeyboardMarkup([[search_button]])

                try:
                    # Send the movie details to the specific channel
                    channel_id = "-1001680629032"  # Replace with your channel's ID or username
                    await client.send_message(chat_id=channel_id, text=movie_details, reply_markup=reply_markup)
                    # Notify the admin that the movie was posted
                    await callback_query.answer("✅ Movie details posted to the channel.")
                except Exception as e:
                    await callback_query.answer(f"⚠️ Error posting movie to channel: {str(e)}")
                break
    else:
        await callback_query.answer("⚠️ Failed to fetch movie details. Please try again later.")
        
        
