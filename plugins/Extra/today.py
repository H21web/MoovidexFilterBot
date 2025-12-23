import re
import html
import asyncio
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import temp
from info import *
from plugins.Extra.binged import HEADERS, DETAIL_URL, ADMIN_IDS, clean_text, build_released_message, build_upcoming_message, get_similar_movies, format_search_title, find_tmdb_id, get_tmdb_details, search_tmdb_advanced
from database.ia_filterdb import get_search_results
from database.users_chats_db import db
from TechVJ.bot import TechVJBot

# Configuration
UPDATE_CHANNEL_ID = -1001680629032  # Update Channel ID

async def fetch_url(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, timeout=10) as response:
                if response.status == 200:
                    return await response.json()
    except Exception as e:
        print(f"Request Error: {e}")
    return None

# Function to fetch movies
async def fetch_movies(mode="streaming-today"):
    url = f"https://www.binged.com/wp-json/binged-api/v1/movies?mode={mode}"
    data = await fetch_url(url)
    if data:
        return data.get('data', [])
    return None

# Background Loop for Auto-Updates
async def check_releases_loop():
    print("Auto-Update Loop Started")
    # Wait for bot to be ready
    await asyncio.sleep(10) 
    
    
    while True:
        try:
            # Fetch from both categories to catch all available movies
            week_movies = await fetch_movies("streaming-week") or []
            soon_movies = await fetch_movies("streaming-soon") or []
            
            # Combine and remove duplicates based on ID
            all_movies = {str(m.get('id')): m for m in (week_movies + soon_movies)}.values()
            
            if all_movies:
                for movie in all_movies:
                    try:
                        movie_id = str(movie.get("id"))
                        
                        title = clean_text(movie.get("title", ""))
                        if not title:
                            continue
                            
                        year = movie.get("release_year") or movie.get("year") or movie.get("theatrical-year")
                        
                        # Check if movie exists in our database
                        search_query = f"{title} {year}" if year else title
                        _, _, total_results = await get_search_results(0, search_query)
                        
                        if total_results > 0:
                            # --- RELEASED ---
                            is_posted = await db.is_movie_posted(movie_id)
                            if is_posted:
                                continue

                            print(f"Found match for {title} in DB! Posting as Released...")
                            
                            # Fetch full details
                            movie_data = await fetch_url(f"{DETAIL_URL}/{movie_id}")
                            if not movie_data:
                                continue
                                
                            # Build Message
                            msg, image = build_released_message(movie_data, temp.U_NAME, source='binged')
                            
                            # --- TMDB INTEGRATION START ---
                            imdb_id = movie_data.get("imdb_id")
                            tmdb_image = None
                            
                            if imdb_id:
                                try:
                                    tmdb_results = find_tmdb_id(imdb_id)
                                    if tmdb_results:
                                        tmdb_id = tmdb_results[0].get("id")
                                        tmdb_details = get_tmdb_details(tmdb_id, "movie")
                                        if tmdb_details and tmdb_details.get("image"):
                                            tmdb_image = tmdb_details.get("image")
                                except Exception as e:
                                    print(f"TMDB Fetch Error in Loop: {e}")
                            
                            # Fallback: Search by Title if no IMDB ID or no image found
                            if not tmdb_image:
                                title_search = clean_text(movie.get("title", ""))
                                year_search = movie.get("release_year") or movie.get("year")
                                
                                # Determine media type (today is usually streaming movies/series)
                                media_type_hint = "movie"
                                # Basic check for series pattern
                                if "season" in title_search.lower() or re.search(r'S\d+', title_search, re.IGNORECASE):
                                     media_type_hint = "tv"

                                if title_search:
                                    print(f"Searching TMDB Advanced (Loop): {title_search} ({year_search})")
                                    # Use specific year search
                                    tmdb_results = search_tmdb_advanced(title_search, year=year_search, media_type=media_type_hint)
                                    
                                    if tmdb_results:
                                        tmdb_id = tmdb_results[0].get("id")
                                        tmdb_details = get_tmdb_details(tmdb_id, "movie") # get_tmdb_details handles generic types well
                                        
                                        if tmdb_details and tmdb_details.get("image"):
                                            tmdb_image = tmdb_details.get("image")
                                            print(f"Found TMDB Image via Advanced Search (Loop): {tmdb_image}")

                            # Use TMDB image if available, otherwise fallback to Binged image
                            final_image = tmdb_image if tmdb_image else image
                            # --- TMDB INTEGRATION END ---
                            
                            safe_title = format_search_title(title, year)
                                                        
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
                                safe_similar = format_search_title(similar_title, None)
                                row2.append(InlineKeyboardButton(
                                    "🔄 More like this", 
                                    url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_similar}"
                                ))
                                
                            if row2:
                                buttons.append(row2)
                            
                            # Send to Channel
                            try:
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
                            except Exception as e:
                                print(f"Error sending to channel: {e}")
                            
                            # --- NOTIFICATION SYSTEM ---
                            try:
                                alert_users = await db.get_movie_alerts(movie_id)
                                if alert_users:
                                    notify_msg = f"🎬 **{title} ({year})** has been released and is now available!"
                                    btn = [[InlineKeyboardButton("🔍 Get Movie", url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}")]]
                                    
                                    for user_id in alert_users:
                                        try:
                                            await TechVJBot.send_message(
                                                chat_id=user_id,
                                                text=notify_msg,
                                                reply_markup=InlineKeyboardMarkup(btn)
                                            )
                                            await asyncio.sleep(0.5) # Floodwait prevention
                                        except Exception as u_e:
                                            print(f"Failed to notify user {user_id}: {u_e}")
                                            
                                    await db.delete_movie_alerts(movie_id)
                            except Exception as e:
                                print(f"Error in notification system: {e}")
                            # ---------------------------
                                
                            # Mark as posted in DB
                            await db.add_posted_movie(movie_id)

                        # Avoid spamming
                        await asyncio.sleep(5)
                            

                    except Exception as e:
                        print(f"Error processing movie {movie.get('title')}: {e}")
            
        except Exception as e:
            print(f"Error in check_releases_loop: {e}")
            
        # Check every 1 hour
        await asyncio.sleep(3600)

# /today command - show movie buttons
@Client.on_message(filters.command("today"))
async def send_movie_buttons(client, message):
    movies_data = await fetch_movies("streaming-today")

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
    movie_data = await fetch_url(f"{DETAIL_URL}/{movie_id}")
    
    if not movie_data or "ID" not in movie_data:
        return await cq.answer("Movie data not found.", show_alert=True)
    
    # Store full movie data in temp.BINGED_RESULTS (Reusing binged.py storage)
    temp.BINGED_RESULTS[user_id] = temp.BINGED_RESULTS.get(user_id, {})
    temp.BINGED_RESULTS[user_id][movie_id] = movie_data
    
    # Force status to released since it is "today streaming"
    temp.MOVIE_STATUS[movie_id] = "released"

    title = clean_text(movie_data.get("post_title", "Unknown"))
    year = movie_data.get("release_year", "N/A")
    safe_title = format_search_title(title, year)
    
    # Build message using shared function
    msg, image = build_released_message(movie_data, temp.U_NAME, source='binged')

    # --- TMDB INTEGRATION START ---
    imdb_id = movie_data.get("imdb_id")
    tmdb_image = None
    
    if imdb_id:
        try:
            tmdb_results = find_tmdb_id(imdb_id)
            if tmdb_results:
                tmdb_id = tmdb_results[0].get("id")
                tmdb_details = get_tmdb_details(tmdb_id, "movie")
                if tmdb_details and tmdb_details.get("image"):
                    tmdb_image = tmdb_details.get("image")
        except Exception as e:
            print(f"TMDB Fetch Error in Detail: {e}")
            
    # Fallback: Search by Title if no IMDB ID or no image found
    if not tmdb_image:
        title_search = clean_text(movie_data.get("post_title", ""))
        year_search = movie_data.get("release_year")
        
        # Determine media type from categories
        media_type_hint = "movie"
        if "categories" in movie_data:
             cats = str(movie_data["categories"]).lower()
             if "tv" in cats or "series" in cats or "show" in cats:
                 media_type_hint = "tv"
        
        # Also check title pattern
        if re.search(r'S\d+', title_search, re.IGNORECASE):
             media_type_hint = "tv"

        if title_search:
            print(f"Searching TMDB Advanced (Detail): {title_search} ({year_search})")
            
            # Use specific year search
            tmdb_results = search_tmdb_advanced(title_search, year=year_search, media_type=media_type_hint)
            
            if tmdb_results:
                tmdb_id = tmdb_results[0].get("id")
                tmdb_details = get_tmdb_details(tmdb_id, "movie")
                
                if tmdb_details and tmdb_details.get("image"):
                    tmdb_image = tmdb_details.get("image")
                    print(f"Found TMDB Image via Advanced Search (Detail): {tmdb_image}")

    # Use TMDB image if available, otherwise fallback to Binged image
    final_image = tmdb_image if tmdb_image else image
    movie_data["image"] = final_image # Sync for consistency
    # --- TMDB INTEGRATION END ---
    
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
        safe_similar = format_search_title(similar_title, None)
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
            reply_markup=InlineKeyboardMarkup(buttons),
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
