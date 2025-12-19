import requests
import re
import html
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import temp
from info import *
from plugins.Extra.binged import HEADERS, DETAIL_URL, ADMIN_IDS, clean_text, build_released_message, get_tmdb_backdrop, get_similar_movies
from database.ia_filterdb import get_search_results
from database.users_chats_db import db
from TechVJ.bot import TechVJBot

# Configuration
UPDATE_CHANNEL_ID = -1001680629032  # Update Channel ID

# Function to fetch today's movies
def fetch_today_movies():
    url = "https://www.binged.com/wp-json/binged-api/v1/movies?mode=streaming-today"
    
    response = requests.get(url, headers=HEADERS)

    if response.status_code == 200:
        try:
            data = response.json()
            return data.get('data', [])  # Extract the 'data' array
        except ValueError:
            return None
    return None

# Function to format the movie title for the search URL
def format_title_for_url(title):
    # Clean the title first
    title = clean_text(title)
    title = re.sub(r'[^a-zA-Z0-9\s]', '_', title)  # Replace non-alphanumeric characters with '_'
    title = title.replace(' ', '_')  # Replace spaces with '_'
    return title

# Background Loop for Auto-Updates
async def check_releases_loop():
    print("Auto-Update Loop Started")
    # Wait for bot to be ready
    await asyncio.sleep(10) 
    
    while True:
        try:
            today_movies = fetch_today_movies()
            if today_movies:
                for movie in today_movies:
                    movie_id = str(movie.get("id"))
                    
                    # Skip if already posted (DB check)
                    if await db.is_movie_posted(movie_id):
                        continue
                        
                    title = clean_text(movie.get("title", ""))
                    if not title:
                        continue
                        
                    # Check if movie exists in our database
                    # get_search_results returns (files, next_offset, total_results)
                    _, _, total_results = await get_search_results(0, title)
                    
                    if total_results > 0:
                        print(f"Found match for {title} in DB! Posting...")
                        
                        # Fetch full details
                        try:
                            resp = requests.get(f"{DETAIL_URL}/{movie_id}", headers=HEADERS, timeout=10)
                            resp.raise_for_status()
                            movie_data = resp.json()
                            
                            # Build Message
                            msg, image = build_released_message(movie_data, temp.U_NAME, source='binged')
                            
                            # Backdrop
                            year = movie_data.get("release_year", "N/A")
                            backdrop_image = get_tmdb_backdrop(title, year)
                            final_image = backdrop_image if backdrop_image else image
                            
                            safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)
                            
                            # Buttons
                            buttons = [[
                                InlineKeyboardButton(
                                    f"🔍 Search: {title}", 
                                    url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}"
                                )
                            ]]
                            
                            row2 = []
                            # Trailer Button
                            videos = movie_data.get("videos", [])
                            if videos and len(videos) > 0:
                                video_url = videos[0].get("url", "")
                                if video_url:
                                    trailer_url = f"https://www.youtube.com/watch?v={video_url}"
                                    row2.append(InlineKeyboardButton("🎬 Trailer", url=trailer_url))
                                    
                            # More Like This Button
                            similar_movies = get_similar_movies(movie_data, count=1)
                            if similar_movies:
                                similar_title = clean_text(similar_movies[0].get("title", ""))
                                safe_similar = re.sub(r'[^a-zA-Z0-9]', '_', similar_title)
                                row2.append(InlineKeyboardButton(
                                    "🔄 More like this", 
                                    url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_similar}"
                                ))
                                
                            if row2:
                                buttons.append(row2)
                            
                            # Send to Channel
                            if final_image:
                                await TechVJBot.send_photo(
                                    chat_id=UPDATE_CHANNEL_ID,
                                    photo=final_image,
                                    caption=msg,
                                    reply_markup=InlineKeyboardMarkup(buttons)
                                )
                            else:
                                await TechVJBot.send_message(
                                    chat_id=UPDATE_CHANNEL_ID,
                                    text=msg,
                                    reply_markup=InlineKeyboardMarkup(buttons),
                                    disable_web_page_preview=True
                                )
                                
                            # Mark as posted in DB
                            await db.add_posted_movie(movie_id)
                            
                            # Avoid spamming
                            await asyncio.sleep(5)
                            
                        except Exception as e:
                            print(f"Error posting {title}: {e}")
            
        except Exception as e:
            print(f"Error in check_releases_loop: {e}")
            
        # Check every 1 hour
        await asyncio.sleep(3600)

# /today command - show movie buttons
@Client.on_message(filters.command("today"))
async def send_movie_buttons(client, message):
    movies_data = fetch_today_movies()

    if movies_data and isinstance(movies_data, list):
        if not movies_data:
            await message.reply_text("🚫 No movies streaming today.")
            return

        buttons = []
        for movie in movies_data:  # No reverse here
            title = movie.get('title', 'No title available')
            movie_id = str(movie.get("id"))
            clean_title = clean_text(title)
            # Use same callback pattern but distinct prefix to fetch details
            callback_data = f"today_detail_{movie_id}"
            buttons.append([InlineKeyboardButton(clean_title, callback_data=callback_data)])

        buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
        reply_markup = InlineKeyboardMarkup(buttons)

        await message.reply_text("🎬 **Today's Streaming Movies:**", reply_markup=reply_markup)
    else:
        await message.reply_text("⚠️ Failed to fetch today's movies or no movies found. Please try again later.")


# When a movie title button is clicked
@Client.on_callback_query(filters.regex(r"today_detail_(\d+)"))
async def show_movie_detail(client, cq):
    movie_id = cq.data.split("_")[-1]
    user_id = cq.from_user.id
    import re as regex_module

    # Fetch detailed movie data using Binged API (same as binged.py)
    try:
        resp = requests.get(f"{DETAIL_URL}/{movie_id}", headers=HEADERS, timeout=10)
        resp.raise_for_status()
        movie_data = resp.json()
    except requests.RequestException as e:
        return await cq.answer(f"Failed to fetch movie details: {e}", show_alert=True)
    
    if not movie_data or "ID" not in movie_data:
        return await cq.answer("Movie data not found.", show_alert=True)
    
    # Store full movie data in temp.BINGED_RESULTS (Reusing binged.py storage)
    temp.BINGED_RESULTS[user_id] = temp.BINGED_RESULTS.get(user_id, {})
    temp.BINGED_RESULTS[user_id][movie_id] = movie_data
    
    # Force status to released since it is "today streaming"
    temp.MOVIE_STATUS[movie_id] = "released"

    title = clean_text(movie_data.get("post_title", "Unknown"))
    safe_title = regex_module.sub(r'[^a-zA-Z0-9]', '_', title)
    year = movie_data.get("release_year", "N/A")
    
    # Build message using shared function
    msg, image = build_released_message(movie_data, temp.U_NAME, source='binged')

    # Try to get backdrop from TMDB
    backdrop_image = get_tmdb_backdrop(title, year)
    final_image = backdrop_image if backdrop_image else image
    
    # Build buttons
    buttons = []
    
    # Search Button
    buttons.append([InlineKeyboardButton(
        f"{title} · {year}", 
        url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}"
    )])
    
    row2 = []
    # Trailer Button
    videos = movie_data.get("videos", [])
    if videos and len(videos) > 0:
        video_url = videos[0].get("url", "")
        if video_url:
            trailer_url = f"https://www.youtube.com/watch?v={video_url}"
            row2.append(InlineKeyboardButton("🎬 Trailer", url=trailer_url))
            
    # More Like This Button (New)
    similar_movies = get_similar_movies(movie_data, count=1)
    if similar_movies:
        similar_title = clean_text(similar_movies[0].get("title", ""))
        safe_similar = regex_module.sub(r'[^a-zA-Z0-9]', '_', similar_title)
        row2.append(InlineKeyboardButton(
            "🔄 More like this", 
            url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_similar}"
        ))
        
    if row2:
        buttons.append(row2)

    # Admin buttons (Reusing binged.py callbacks)
    if user_id in ADMIN_IDS:
        buttons.append([
            InlineKeyboardButton("✏️ Edit & Post", callback_data=f"binged_edit_post_{movie_id}"),
            InlineKeyboardButton("📣 Post Default", callback_data=f"binged_post_{movie_id}")
        ])

    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
    reply_markup = InlineKeyboardMarkup(buttons)

    # Send with image
    if final_image:
        await cq.message.reply_photo(
            photo=final_image,
            caption=msg,
            reply_markup=reply_markup
        )
    else:
        await cq.message.reply_text(
            msg,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
    await cq.answer()

# Close button handler
@Client.on_callback_query(filters.regex(r"close_message"))
async def close_message_callback(client, callback_query):
    try:
        await callback_query.message.delete()
    except Exception:
        await callback_query.answer("⚠️ Unable to delete the message.")

# Start the background task
asyncio.create_task(check_releases_loop())
