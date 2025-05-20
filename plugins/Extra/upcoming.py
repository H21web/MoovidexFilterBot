import requests
from pyrogram import Client, filters


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
        all_movies_details = "🎬 **Upcoming Movies:**\n\n"
        for movie in movies_data:
            title = movie.get('title', 'No title available')
            streaming_date = movie.get('streaming-date', 'No streaming date available')
            language = ', '.join(movie.get('languages', ['No language specified']))
            platform = ', '.join(platform.get('name', 'No platform specified') for platform in movie.get('platforms', []))
            movie_type = movie.get('type', 'No type specified')  # Add movie type
            
            # Append each movie's details to the message
            movie_details = (
                f"📅 **Title:** {title}\n"
                f"🎥 **Type:** {movie_type}\n"
                f"🗓️ **Streaming Date:** {streaming_date}\n"
                f"🌐 **Language:** {language}\n"
                f"📺 **Platform:** {platform}\n"
                f"--------------------\n"
            )
            all_movies_details += movie_details
        
        await message.reply_text(all_movies_details)
    else:
        await message.reply_text("⚠️ Failed to fetch upcoming movies or no movies found. Please try again later.")
        
