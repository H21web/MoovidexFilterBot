import re
import html
import asyncio
import aiohttp
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import temp
from info import *
from plugins.Extra.binged import HEADERS, ADMIN_IDS, clean_text, find_tmdb_id, get_tmdb_details, search_tmdb_advanced, format_search_title
from database.users_chats_db import db
from TechVJ.bot import TechVJBot
from plugins.Extra.image_gen import generate_status_image

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

async def fetch_ottplay_releases(from_date, to_date):
    url = f"https://api2.ottplay.com/api/v4.7/web/new-release?limit=10&from_date={from_date}&to_date={to_date}&content_type=all&language=&provider="
    data = await fetch_url(url)
    if data:
        return data.get('result', [])
    return []

# Background Loop for Auto-Updates
async def check_releases_loop():
    print("Auto-Update Loop Started (Ottplay)")
    # Wait for bot to be ready
    await asyncio.sleep(10) 
    
    while True:
        try:
            # Dynamic Dates: Today - 5 to Today + 5
            today = datetime.now()
            from_date = (today - timedelta(days=5)).strftime("%Y-%m-%d")
            to_date = (today + timedelta(days=5)).strftime("%Y-%m-%d")
            
            print(f"Fetching Ottplay releases from {from_date} to {to_date}")
            
            movies = await fetch_ottplay_releases(from_date, to_date)
            
            if movies:
                for movie in movies:
                    try:
                        movie_id = str(movie.get("_id"))
                        title = clean_text(movie.get("name", ""))
                        if not title:
                            continue
                            
                        year = movie.get("release_year")
                        
                        # Check if movie exists in our database (using _id as unique key)
                        is_posted = await db.is_movie_posted(movie_id)
                        if is_posted:
                            continue

                        print(f"Found new release: {title} ({year})")
                        
                        # --- Gather Details ---
                        # Type
                        content_type = movie.get("content_type", "movie")
                        media_type = "movie" if content_type == "movie" else "tv"
                        type_str = "Movie" if media_type == "movie" else "Series"
                        
                        # Language
                        lang = movie.get("primary_language", {}).get("logo_text", "Unknown")
                        
                        # Genres
                        genres = [g.get("name") for g in movie.get("genres", [])]
                        genre_str = ", ".join(genres) if genres else "N/A"
                        
                        # Providers
                        providers_data = movie.get("where_to_watch", [])
                        provider_names = []
                        provider_logos = []
                        platform_links = []
                        
                        for p in providers_data:
                            prov = p.get("provider", {})
                            p_name = prov.get("name")
                            if p_name:
                                provider_names.append(p_name)
                            logo = prov.get("logo_url") or prov.get("icon_url")
                            if logo:
                                provider_logos.append(logo)
                            
                            # Link
                            p_link = p.get("movie_url") or p.get("show_url") or prov.get("seourl")
                            if p_link:
                                if not p_link.startswith("http"):
                                    p_link = f"https://www.ottplay.com/{p_link}"
                                platform_links.append(f"[{p_name}]({p_link})")
                            elif p_name:
                                platform_links.append(p_name)

                        provider_str = ", ".join(platform_links[:3]) if platform_links else "N/A"
                        
                        # Release Date
                        api_date = movie.get("release_date")
                        if api_date:
                            try:
                                r_date = datetime.fromisoformat(api_date.replace("Z", "+00:00")).strftime("%d-%m-%Y")
                            except:
                                r_date = api_date
                        else:
                            r_date = "N/A"

                        # Certifications
                        certs = [c.get("certification") for c in movie.get("certifications", [])]
                        cert_str = "/".join(certs) if certs else "N/A"

                        # Images from Ottplay
                        posters = movie.get("posters", [])
                        ottplay_poster = posters[0] if posters else None
                        
                        # --- TMDB Integration for Backdrop & Extras ---
                        tmdb_backdrop = None
                        tmdb_poster = None
                        tmdb_rating = None
                        tmdb_plot = None
                        cast_str = "N/A"
                        
                        tmdb_results = search_tmdb_advanced(title, year=year, media_type=media_type)
                        if tmdb_results:
                            tmdb_id = tmdb_results[0].get("id")
                            tmdb_details = get_tmdb_details(tmdb_id, media_type)
                            if tmdb_details:
                                # Get better images
                                tmdb_img = tmdb_details.get("image") # usually backdrop
                                if tmdb_img:
                                    tmdb_backdrop = tmdb_img
                                
                                # Poster from TMDB if available (often better quality)
                                # get_tmdb_details returns 'image' which is best_backdrop. 
                                # Access original_data for specific poster
                                t_orig = tmdb_details.get("original_data", {})
                                p_path = t_orig.get("poster_path")
                                if p_path:
                                    tmdb_poster = f"https://image.tmdb.org/t/p/original{p_path}"

                                tmdb_rating = tmdb_details.get("rating")
                                tmdb_plot = tmdb_details.get("plot")
                                cast = tmdb_details.get("cast", [])
                                cast_str = ", ".join(cast[:5]) if cast else "N/A"

                        # Use Ottplay rating/plot if TMDB failed
                        rating = tmdb_rating if tmdb_rating else (str(movie.get("ottplay_rating")) + "/10" if movie.get("ottplay_rating") else "N/A")
                        
                        # Plot: Ottplay doesn't easily give plot in list.
                        plot = tmdb_plot if tmdb_plot else "No description available."
                        
                        # --- Build Message ---
                        # Template:
                        # ✅ **Title** · Year · `Type`
                        #
                        # >**>🉑 #Lang**
                        # >🎭 Genre · 📺 Platform
                        # >⏱️ Runtime · ®️ Censor
                        # >📅 Date
                        # >👥 Cast
                        # >
                        # >__Plot:__
                        # >Plot**
                        #  **@MooviDex** 

                        safe_title = format_search_title(title, year)
                        lang_tag = f"#{lang.replace(' ', '')}"
                        
                        msg = f"✅ **{title}** · {year} · `{type_str}`\n\n"
                        msg += f"**>🉑 {lang_tag}\n"
                        msg += f">🎭 {genre_str} · 📺 {provider_str}\n"
                        msg += f">®️ {cert_str} · ⭐ {rating}\n"
                        msg += f">📅 {r_date}\n"
                        msg += f">👥 {cast_str}\n"
                        msg += f">\n"
                        msg += f">__Plot:__\n"
                        msg += f">{plot}**\n"
                        msg += f" **@MooviDex** "

                        # --- Generate Image ---
                        # Prioritize TMDB backdrop, else use Ottplay poster as background (blurred)?
                        # Prioritize Ottplay poster for foreground, or TMDB. Ottplay posters might be localized.
                        
                        backdrop_url = tmdb_backdrop if tmdb_backdrop else ottplay_poster
                        poster_url = ottplay_poster if ottplay_poster else tmdb_poster
                        
                        # If we have no images, skip image gen
                        final_image_io = None
                        if backdrop_url and poster_url:
                            print(f"Generating image for {title}...")
                            final_image_io = await generate_status_image(backdrop_url, poster_url, provider_logos)

                        # --- Buttons ---
                        buttons = [[
                            InlineKeyboardButton(
                                f"🔍 Search: {title}", 
                                url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}"
                            )
                        ]]
                        
                        # Trailer logic (from TMDB details if available)
                        if tmdb_details:
                             videos = tmdb_details.get("videos", [])
                             if videos:
                                 video_url = videos[0].get("url")
                                 if video_url:
                                     trailer_url = f"https://www.youtube.com/watch?v={video_url}"
                                     buttons.append([InlineKeyboardButton("🎬 Trailer", url=trailer_url)])

                        # Send to Channel
                        try:
                            if final_image_io:
                                await TechVJBot.send_photo(
                                    chat_id=UPDATE_CHANNEL_ID,
                                    photo=final_image_io,
                                    caption=msg,
                                    reply_markup=InlineKeyboardMarkup(buttons)
                                )
                            elif backdrop_url: # Fallback to single image
                                await TechVJBot.send_photo(
                                    chat_id=UPDATE_CHANNEL_ID,
                                    photo=backdrop_url,
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
                                
                            # Mark as posted
                            await db.add_posted_movie(movie_id)
                            
                            # Floodwait
                            await asyncio.sleep(5)
                            
                        except Exception as e:
                            print(f"Error sending to channel: {e}")

                    except Exception as e:
                        print(f"Error processing movie {movie.get('name')}: {e}")
            
        except Exception as e:
            print(f"Error in check_releases_loop: {e}")
            
        # Check every 4 hours (daily update but checking more often is safer for uptime)
        await asyncio.sleep(14400) 

# /today command - mapped to new logic? 
# The user asked to "fetch latest... update daily", implying the loop.
# But I should probably update the /today command to fetch specifically "today's" releases from this API if needed.
# For now, I'll update /today to fetch releases for the *current day* using the same API.

@Client.on_message(filters.command("today"))
async def send_movie_buttons(client, message):
    today = datetime.now().strftime("%Y-%m-%d")
    # Fetch just for today
    movies_data = await fetch_ottplay_releases(today, today)

    if not movies_data:
        await message.reply_text("🚫 No new releases found today.")
        return

    buttons = []
    for movie in movies_data[:10]: # Limit to 10
        title = clean_text(movie.get('name', 'No title'))
        movie_id = str(movie.get("_id"))
        
        # We can use a callback to show details (reuse logic?)
        # Since I changed the ID system (Ottplay IDs vs Binged/TMDB IDs), 
        # I need a callback that processes Ottplay IDs.
        # I'll create a new callback `ottplay_detail_`
        
        callback_data = f"ottplay_detail_{movie_id}"
        buttons.append([InlineKeyboardButton(title, callback_data=callback_data)])

    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
    reply_markup = InlineKeyboardMarkup(buttons)

    await message.reply_text(f"🎬 **Releases for {today}:**", reply_markup=reply_markup)


# Callback for Ottplay details
@Client.on_callback_query(filters.regex(r"^ottplay_detail_(.+)$"))
async def ottplay_detail(client, cq):
    movie_id = cq.data.split("_")[-1]
    
    # We need to fetch details for this specific ID. 
    # Because there isn't a direct "get by ID" readily available in previously assumed contexts,
    # and /today fetched "today", we fetch today's list again to find it.
    today = datetime.now().strftime("%Y-%m-%d")
    movies = await fetch_ottplay_releases(today, today)
    
    movie = next((m for m in movies if str(m.get("_id")) == movie_id), None)
    
    if not movie:
         return await cq.answer("Movie details not found.", show_alert=True)

    # Now build the message and image (Reuse logic from loop essentially)
    
    title = clean_text(movie.get("name", ""))
    year = movie.get("release_year")
    content_type = movie.get("content_type", "movie")
    media_type = "movie" if content_type == "movie" else "tv"
    type_str = "Movie" if media_type == "movie" else "Series"
    lang = movie.get("primary_language", {}).get("logo_text", "Unknown")
    genres = [g.get("name") for g in movie.get("genres", [])]
    genre_str = ", ".join(genres) if genres else "N/A"
    
    # Providers
    providers_data = movie.get("where_to_watch", [])
    provider_logos = []
    platform_links = []
    
    for p in providers_data:
        prov = p.get("provider", {})
        p_name = prov.get("name")
        logo = prov.get("logo_url") or prov.get("icon_url")
        if logo:
            provider_logos.append(logo)
        
        p_link = p.get("movie_url") or p.get("show_url") or prov.get("seourl")
        if p_link:
             if not p_link.startswith("http"):
                 p_link = f"https://www.ottplay.com/{p_link}"
             platform_links.append(f"[{p_name}]({p_link})")
        elif p_name:
             platform_links.append(p_name)
    provider_str = ", ".join(platform_links[:3]) if platform_links else "N/A"
    
    api_date = movie.get("release_date")
    if api_date:
        try:
            r_date = datetime.fromisoformat(api_date.replace("Z", "+00:00")).strftime("%d-%m-%Y")
        except:
            r_date = api_date
    else:
        r_date = "N/A"

    certs = [c.get("certification") for c in movie.get("certifications", [])]
    cert_str = "/".join(certs) if certs else "N/A"
    posters = movie.get("posters", [])
    ottplay_poster = posters[0] if posters else None
    
    # TMDB Helper
    tmdb_backdrop = None
    tmdb_poster = None
    tmdb_rating = None
    tmdb_plot = None
    cast_str = "N/A"
    
    tmdb_results = search_tmdb_advanced(title, year=year, media_type=media_type)
    if tmdb_results:
        tmdb_id = tmdb_results[0].get("id")
        tmdb_details = get_tmdb_details(tmdb_id, media_type)
        if tmdb_details:
            tmdb_img = tmdb_details.get("image")
            if tmdb_img: tmdb_backdrop = tmdb_img
            t_orig = tmdb_details.get("original_data", {})
            p_path = t_orig.get("poster_path")
            if p_path: tmdb_poster = f"https://image.tmdb.org/t/p/original{p_path}"
            tmdb_rating = tmdb_details.get("rating")
            tmdb_plot = tmdb_details.get("plot")
            cast = tmdb_details.get("cast", [])
            cast_str = ", ".join(cast[:5]) if cast else "N/A"
            
    rating = tmdb_rating if tmdb_rating else (str(movie.get("ottplay_rating")) + "/10" if movie.get("ottplay_rating") else "N/A")
    plot = tmdb_plot if tmdb_plot else "No description available."
    safe_title = format_search_title(title, year)
    lang_tag = f"#{lang.replace(' ', '')}"
    
    msg = f"✅ **{title}** · {year} · `{type_str}`\n\n"
    msg += f"**>🉑 {lang_tag}\n"
    msg += f">🎭 {genre_str} · 📺 {provider_str}\n"
    msg += f">®️ {cert_str} · ⭐ {rating}\n"
    msg += f">📅 {r_date}\n"
    msg += f">👥 {cast_str}\n"
    msg += f">\n"
    msg += f">__Plot:__\n"
    msg += f">{plot}**\n"
    msg += f" **@MooviDex** "
    
    backdrop_url = tmdb_backdrop if tmdb_backdrop else ottplay_poster
    poster_url = ottplay_poster if ottplay_poster else tmdb_poster
    
    final_image_io = None
    if backdrop_url and poster_url:
        await cq.answer("Generating image...", cache_time=0)
        final_image_io = await generate_status_image(backdrop_url, poster_url, provider_logos)
    
    buttons = [[InlineKeyboardButton(f"🔍 Search: {title}", url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}")]]
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
    
    if final_image_io:
        await cq.message.reply_photo(photo=final_image_io, caption=msg, reply_markup=InlineKeyboardMarkup(buttons))
    elif backdrop_url:
        await cq.message.reply_photo(photo=backdrop_url, caption=msg, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await cq.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
    
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
