import re
import html
import asyncio
import aiohttp
from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import temp
from info import *
from plugins.Extra.binged import HEADERS, ADMIN_IDS, clean_text, find_tmdb_id, get_tmdb_details, search_tmdb_advanced, format_search_title
from database.users_chats_db import db
from TechVJ.bot import TechVJBot
from plugins.Extra.image_gen import generate_status_image
from database.ia_filterdb import get_search_results

# Configuration
UPDATE_CHANNEL_ID = -1001680629032  # Update Channel ID

# Global Cache for Wanted Movies (Movies released but not yet posted)
# Format: {movie_id: movie_data}
WANTED_MOVIES = {}

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

def is_smart_match(title, year, file_name):
    """
    Enhanced Smart Match for Movie/Series Updates
    """
    if not title or not file_name:
        return False
        
    # 1. Normalize Names (Lower, remove specific noise)
    def clean(s):
        s = str(s).lower()
        # Replace delimiters with space
        s = re.sub(r'[._\-\[\]\(\)\{\}]', ' ', s) 
        # Collapse spaces
        s = re.sub(r'\s+', ' ', s) 
        return s.strip()

    title_clean = clean(title)
    file_clean = clean(file_name)
    
    # 2. Year Validation Logic
    # Extract all 4-digit years from filename (1900-2099)
    file_years = re.findall(r'\b(19\d{2}|20\d{2})\b', file_clean)
    
    if year:
        year_str = str(year)
        if file_years:
            # If filename has years, one of them MUST match the API year
            if year_str not in file_years:
                return False
        else:
            # If filename has NO years, we allow match ONLY if:
            # It looks like a Series (S01E01, etc)
            # Regex covers: s01e01, s01, e01, season 1, episode 1
            is_series_file = re.search(r'(s\d+e\d+|s\d+|e\d+|season\s*\d+|episode\s*\d+)', file_clean)
            if not is_series_file:
                 # If valid movie year is known but missing from file -> Strict Reject to avoid false positives
                 return False

    # 3. Flexible Title Matching (Token Order)
    stopwords = {'the', 'a', 'an', 'of', 'and', 'in', 'on', 'at', 'to', 'is', 'are', 'am'}
    title_words = [w for w in title_clean.split() if w not in stopwords]
    
    if not title_words: 
        title_words = title_clean.split()
        
    # Construct Regex: word1 + anything + word2 + anything ...
    # This allows "Mission Impossible" to match "Mission.Impossible"
    pattern = r'.*'.join([re.escape(w) for w in title_words])
    
    if re.search(pattern, file_clean):
        return True
        
    return False

async def process_and_post_movie(movie, check_db=True):
    """
    Process a single movie: Check if file exists (strict), generate post, send.
    Returns True if posted, False otherwise.
    """
    try:
        movie_id = str(movie.get("_id"))
        title = clean_text(movie.get("name", ""))
        if not title:
            return False
            
        year = movie.get("release_year")
        
        # Double check DB if requested
        if check_db:
             if await db.is_movie_posted(movie_id):
                 # Remove from wanted if already posted
                 if movie_id in WANTED_MOVIES:
                     del WANTED_MOVIES[movie_id]
                 return True

        # Check File Availability with STRICT MATCH
        # Strategy 1: Search with Year (Precision)
        search_query = f"{title} {year}"
        files, _, total_files = await get_search_results(UPDATE_CHANNEL_ID, search_query, max_results=20)
        
        # Strategy 2: Fallback to Title Only if not found (Recall)
        # Many series files might just be "Series Name S01" without year
        if total_files == 0:
            print(f"DEBUG: No files found for '{search_query}', retrying with '{title}'")
            files, _, total_files = await get_search_results(UPDATE_CHANNEL_ID, title, max_results=20)
        
        found_file = False
        if total_files > 0:
            for file in files:
                # Use file_name if available, else name
                fname = getattr(file, "file_name", None) or getattr(file, "name", "")
                if is_smart_match(title, year, fname):
                    found_file = True
                    break
        
        if not found_file:
            print(f"Skipping {title} ({year}) - No exact matching file found.")
            return False

        print(f"✅ Found release with available file into DB: {title} ({year})")
        
        # --- Gather Details ---
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
            if p_name: 
                # dedupe logic could be here but kept simple
                pass
            logo = prov.get("logo_url") or prov.get("icon_url")
            if logo:
                provider_logos.append(logo)
            
            p_link = p.get("movie_url") or p.get("show_url")
            
            # Try to construct direct link if missing
            if not p_link and p_name and p.get("partner_title_id"):
                ptid = p.get("partner_title_id")
                if "netflix" in p_name.lower():
                    p_link = f"https://www.netflix.com/title/{ptid}"
                elif "zee5" in p_name.lower():
                    # Zee5 structure varies (movies vs tvshows), default to generic or check type
                    # Using clean ID logic might be needed, but simple append often works for deep links
                    p_link = f"https://www.zee5.com/global/content/{ptid}"
                elif "sonyliv" in p_name.lower():
                    p_link = f"https://www.sonyliv.com/shows/{ptid}"
            
            if p_link:
                if p_link.startswith("http"):
                    pass
                elif p_link.startswith("www."):
                    p_link = f"https://{p_link}"
                else:
                    # If it's still a relative path without http, it's likely an Ottplay internal path.
                    # User requested direct links ONLY. So we skip Ottplay links entirely.
                    p_link = None
            
            if p_link:
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
        
        # TMDB Integration
        tmdb_backdrop = None
        tmdb_poster = None
        tmdb_rating = None
        tmdb_plot = None
        tmdb_id = None
        cast_str = "N/A"
        trailer_url = None
        
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

                videos = tmdb_details.get("videos", [])
                if videos:
                     video_url = videos[0].get("url")
                     if video_url:
                         trailer_url = f"https://www.youtube.com/watch?v={video_url}"

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
            print(f"Generating image for {title}...")
            final_image_io = await generate_status_image(
                backdrop_url, poster_url, provider_logos,
                title, year, rating, genre_str, plot
            )

        buttons = []
        if media_type != "tv":
            buttons.append([
                InlineKeyboardButton(
                    f"🔍 Search: {title}", 
                    url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}"
                )
            ])
            
        row = []
        if trailer_url:
            row.append(InlineKeyboardButton("🎬 Trailer", url=trailer_url))
        if tmdb_id:
            row.append(InlineKeyboardButton("More like this", url=f"https://t.me/{temp.U_NAME}?start=more_like_{tmdb_id}_{media_type}"))
        if row:
            buttons.append(row)

        try:
            posted_msg = None
            if final_image_io:
                # Reset stream position just in case, though send_photo usually handles it if it's not closed
                final_image_io.seek(0)
                posted_msg = await TechVJBot.send_photo(
                    chat_id=UPDATE_CHANNEL_ID,
                    photo=final_image_io,
                    caption=msg,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            elif backdrop_url:
                posted_msg = await TechVJBot.send_photo(
                    chat_id=UPDATE_CHANNEL_ID,
                    photo=backdrop_url,
                    caption=msg,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            else:
                posted_msg = await TechVJBot.send_message(
                    chat_id=UPDATE_CHANNEL_ID,
                    text=msg,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    disable_web_page_preview=True
                )
            
            # --- NOTIFICATION SYSTEM ---
            # Check if any users are waiting for this movie
            alert_users = await db.get_movie_alerts(safe_title)
            if alert_users:
                print(f"🔔 Notifying {len(alert_users)} users about {title}")
                for uid in alert_users:
                    try:
                        # Send the same poster and message to the user
                        if posted_msg.photo:
                             await TechVJBot.send_photo(
                                 chat_id=uid, 
                                 photo=posted_msg.photo.file_id, 
                                 caption=msg, 
                                 reply_markup=InlineKeyboardMarkup(buttons)
                             )
                        else:
                             await TechVJBot.send_message(
                                 chat_id=uid, 
                                 text=msg, 
                                 reply_markup=InlineKeyboardMarkup(buttons),
                                 disable_web_page_preview=True
                             )
                    except Exception as e:
                        print(f"Failed to notify user {uid}: {e}")
                
                # Clear alerts for this movie
                await db.delete_movie_alerts(safe_title)
             # ---------------------------
                
            # Mark as posted
            await db.add_posted_movie(movie_id)
            if movie_id in WANTED_MOVIES:
                del WANTED_MOVIES[movie_id]
            
            return True
            
        except Exception as e:
            print(f"Error sending to channel: {e}")
            return False

    except Exception as e:
        print(f"Error processing movie {movie.get('name')}: {e}")
        return False

# Hook for Database Insert (Instant Update)
async def check_and_post_if_needed(file_name):
    """
    Called by database/ia_filterdb.py immediately after a file is saved.
    Checks if the saved file matches any 'Wanted Movie' and triggers a post.
    """
    if not WANTED_MOVIES:
        return

    try:
        # Use a copy of values safely
        wanted_list = list(WANTED_MOVIES.values())
        
        for movie in wanted_list:
            movie_id = str(movie.get("_id"))
            title = clean_text(movie.get("name", ""))
            
            # Strict match check
            year = movie.get("release_year")
            if is_smart_match(title, year, file_name):
                # Double check to prevent race conditions
                if await db.is_movie_posted(movie_id):
                    if movie_id in WANTED_MOVIES:
                        del WANTED_MOVIES[movie_id]
                    continue
                
                print(f"⚡ Instant Hook Match: {file_name} for {title}")
                
                # Check DB for file presence (since it was JUST saved, it should be there)
                # But we pass check_db=True to process_and_post_movie safely or custom logic
                # Actually process_and_post_movie does: 
                # 1. db.is_movie_posted? (We checked above)
                # 2. get_search_results (searches DB). 
                # Since we just saved it, search should find it.
                
                success = await process_and_post_movie(movie)
                if success:
                    # Remove from wanted list to prevent future matching
                    if movie_id in WANTED_MOVIES:
                        del WANTED_MOVIES[movie_id]
                break 
                
    except Exception as e:
        print(f"Error in check_and_post_if_needed: {e}")

# Background Loop for Auto-Updates
async def check_releases_loop():
    print("Auto-Update Loop Started (Ottplay v2)")
    await asyncio.sleep(10) 
    
    while True:
        try:
            today = datetime.now()
            from_date = (today - timedelta(days=5)).strftime("%Y-%m-%d")
            to_date = (today + timedelta(days=5)).strftime("%Y-%m-%d")
            
            print(f"Fetching Ottplay releases from {from_date} to {to_date}")
            movies = await fetch_ottplay_releases(from_date, to_date)
            
            if movies:
                for movie in movies:
                    movie_id = str(movie.get("_id"))
                    
                    # If already posted, skip and remove from wanted
                    if await db.is_movie_posted(movie_id):
                        if movie_id in WANTED_MOVIES:
                            del WANTED_MOVIES[movie_id]
                        continue
                        
                    # Add to Wanted List (optional now, since we don't have a listener)
                    WANTED_MOVIES[movie_id] = movie
                    
                    # Use existing Logic: Search DB ("check channels") for this movie
                    # process_and_post_movie searches via get_search_results (db search)
                    # If found in DB (which reflects channel state), it posts.
                    # If not found, it returns False (do nothing).
                    await process_and_post_movie(movie, check_db=False)
                    
                    # Floodwait prevention
                    await asyncio.sleep(2)
            
        except Exception as e:
            print(f"Error in check_releases_loop: {e}")
            
        await asyncio.sleep(3600) # Check every hour


# Start Handler for More Like This (Deep Link)
@Client.on_message(filters.command("start") & filters.regex(r"more_like_(\d+)_(.+)"))
async def start_more_like(client, message):
    if len(message.command) > 1:
        data = message.command[1] # e.g. more_like_123_movie
        parts = data.split("_")
        # parts: ['more', 'like', 'id', 'type']? Start param is one string "more_like_id_type"
        # regex will match the whole line properly if we are careful.
        # Actually easiest is to just parse the parameter manually.
        pass
    else: return
    
    try:
        _, _, tmdb_id, media_type =  message.command[1].split("_")
    except:
        return

    details = get_tmdb_details(tmdb_id, media_type)
    if not details:
        return await message.reply_text("Error fetching details")
        
    similar = details.get("similar", [])
    if not similar:
        return await message.reply_text("No similar content found.")
        
    buttons = []
    for sim in similar[:6]:
        title = sim.get("title") or sim.get("name")
        safe_title = format_search_title(title, None)
        buttons.append([InlineKeyboardButton(f"🔍 {title}", url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}")])
        
    # No close button needed in PM really, but sure.
    
    await message.reply_text(f"**More like: {details['title']}**", reply_markup=InlineKeyboardMarkup(buttons))


# Original Callback (Optional, keeping for legacy or direct PM clicks if any)
@Client.on_callback_query(filters.regex(r"^more_like_(\d+)_(.+)$"))
async def more_like_callback(client, cq):
    # Just redirect to the URL behavior if possible, or execute same logic
    # But user wants "open in bot pm". 
    # If this callback is clicked in a channel (rare if we change button), we can't redirect easily without answer(url=...) which is not supported by all clients identically for deep linking to self.
    # It's better to just change the logic to rely on the URL button.
    
    # If we keep this, and user clicks in PM, it just works.
    # If in channel, we try to send PM.
    try:
        await client.send_message(
            chat_id=cq.from_user.id,
            text=f"Click here to see similar movies:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("View Similar", url=f"https://t.me/{temp.U_NAME}?start={cq.data}")]])
        )
        await cq.answer("Check your PM!", show_alert=True)
    except:
        await cq.answer("Please start the bot in PM first!", show_alert=True)

# /today command
@Client.on_message(filters.command("today"))
async def send_movie_buttons(client, message):
    today = datetime.now().strftime("%Y-%m-%d")
    movies_data = await fetch_ottplay_releases(today, today)

    if not movies_data:
        await message.reply_text("🚫 No new releases found today.")
        return

    buttons = []
    for movie in movies_data[:10]: 
        title = clean_text(movie.get('name', 'No title'))
        movie_id = str(movie.get("_id"))
        callback_data = f"ottplay_detail_{movie_id}"
        buttons.append([InlineKeyboardButton(title, callback_data=callback_data)])

    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
    reply_markup = InlineKeyboardMarkup(buttons)

    await message.reply_text(f"🎬 **Releases for {today}:**", reply_markup=reply_markup)

@Client.on_callback_query(filters.regex(r"^ottplay_detail_(.+)$"))
async def ottplay_detail(client, cq):
    user_id = cq.from_user.id
    movie_id = cq.data.split("_")[-1]
    
    today = datetime.now().strftime("%Y-%m-%d")
    movies = await fetch_ottplay_releases(today, today)
    
    movie = next((m for m in movies if str(m.get("_id")) == movie_id), None)
    if not movie:
         return await cq.answer("Movie details not found.", show_alert=True)

    # Process Data
    data = await process_movie_data(movie, user_id)
    
    msg = f"✅ **{data['title']}** · {data['year']} · `{data['type_str']}`\n\n"
    msg += f"**>🉑 {data['lang_tag']}\n"
    msg += f">🎭 {data['genre_str']} · 📺 {data['provider_str']}\n"
    msg += f">®️ {data['cert_str']} · ⭐ {data['rating']}\n"
    msg += f">📅 {data['r_date']}\n"
    msg += f">👥 {data['cast_str']}\n"
    msg += f">\n"
    msg += f">__Plot:__\n"
    msg += f">{data['plot']}**\n"
    msg += f" **@MooviDex** "
    
    backdrop_url = data['backdrop_url']
    poster_url = data['poster_url']
    
    final_image_io = None
    if backdrop_url and poster_url:
        await cq.answer("Generating image...", cache_time=0)
        try:
             final_image_io = await generate_status_image(
                backdrop_url, poster_url, data['provider_logos'],
                data['title'], data['year'], data['rating'], data['genre_str'], data['plot']
             )
        except: pass
    
    buttons = [[InlineKeyboardButton(f"🔍 Search: {data['title']}", url=f"https://t.me/{temp.U_NAME}?start=Search_{data['safe_title']}")]]
    
    # Admin Buttons
    if user_id in ADMIN_IDS:
         buttons.append([
             InlineKeyboardButton("✏️ Edit & Post", callback_data=f"ottplay_edit_post_{data['movie_id']}"),
             InlineKeyboardButton("📣 Post Default", callback_data=f"ottplay_post_{data['movie_id']}")
         ])
         
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
    
    if final_image_io:
        await cq.message.reply_photo(photo=final_image_io, caption=msg, reply_markup=InlineKeyboardMarkup(buttons))
    elif backdrop_url:
        await cq.message.reply_photo(photo=backdrop_url, caption=msg, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await cq.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
    await cq.answer()

async def process_movie_data(movie, user_id):
    """
    Helper to process movie data and store in temp.OTTPLAY_RESULTS
    """
    title = clean_text(movie.get("name", ""))
    year = movie.get("release_year")
    content_type = movie.get("content_type", "movie")
    media_type = "movie" if content_type == "movie" else "tv"
    type_str = "Movie" if media_type == "movie" else "Series"
    lang = movie.get("primary_language", {}).get("logo_text", "Unknown")
    genres = [g.get("name") for g in movie.get("genres", [])]
    genre_str = ", ".join(genres) if genres else "N/A"
    
    providers_data = movie.get("where_to_watch", [])
    provider_logos = []
    platform_links = []
    
    for p in providers_data:
        prov = p.get("provider", {})
        p_name = prov.get("name")
        logo = prov.get("logo_url") or prov.get("icon_url")
        if logo: provider_logos.append(logo)
        p_link = p.get("movie_url") or p.get("show_url")
        
        if not p_link and p_name and p.get("partner_title_id"):
            ptid = p.get("partner_title_id")
            if "netflix" in p_name.lower():
                p_link = f"https://www.netflix.com/title/{ptid}"
            elif "zee5" in p_name.lower():
                p_link = f"https://www.zee5.com/global/content/{ptid}"
            elif "sonyliv" in p_name.lower():
                p_link = f"https://www.sonyliv.com/shows/{ptid}"

        if p_link:
             if p_link.startswith("http"): pass
             elif p_link.startswith("www."): p_link = f"https://{p_link}"
             else: p_link = None
        
        if p_link: platform_links.append(f"[{p_name}]({p_link})")
        elif p_name: platform_links.append(p_name)
    provider_str = ", ".join(platform_links[:3]) if platform_links else "N/A"
    
    api_date = movie.get("release_date")
    if api_date:
        try: r_date = datetime.fromisoformat(api_date.replace("Z", "+00:00")).strftime("%d-%m-%Y")
        except: r_date = api_date
    else: r_date = "N/A"

    certs = [c.get("certification") for c in movie.get("certifications", [])]
    cert_str = "/".join(certs) if certs else "N/A"
    posters = movie.get("posters", [])
    ottplay_poster = posters[0] if posters else None
    
    tmdb_backdrop, tmdb_poster, tmdb_rating, tmdb_plot, tmdb_id = None, None, None, None, None
    cast_str = "N/A"
    trailer_url = None
    
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
            videos = tmdb_details.get("videos", [])
            if videos and videos[0].get("url"):
                 trailer_url = f"https://www.youtube.com/watch?v={videos[0].get('url')}"

    rating = tmdb_rating if tmdb_rating else (str(movie.get("ottplay_rating")) + "/10" if movie.get("ottplay_rating") else "N/A")
    plot = tmdb_plot if tmdb_plot else "No description available."
    safe_title = format_search_title(title, year)
    lang_tag = f"#{lang.replace(' ', '')}"
    
    # Cache
    movie_id = str(movie.get("_id"))
    if not hasattr(temp, "OTTPLAY_RESULTS"): temp.OTTPLAY_RESULTS = {}
    if user_id not in temp.OTTPLAY_RESULTS: temp.OTTPLAY_RESULTS[user_id] = {}
    
    temp.OTTPLAY_RESULTS[user_id][movie_id] = {
        "title": title, "year": year, "type_str": type_str, "lang_tag": lang_tag,
        "genre_str": genre_str, "provider_str": provider_str, "cert_str": cert_str,
        "rating": rating, "r_date": r_date, "cast_str": cast_str, "plot": plot,
        "backdrop_url": tmdb_backdrop if tmdb_backdrop else ottplay_poster,
        "poster_url": ottplay_poster if ottplay_poster else tmdb_poster,
        "provider_logos": provider_logos,
        "safe_title": safe_title, "movie_id": movie_id,
        "trailer_url": trailer_url, "tmdb_id": tmdb_id
    }
    return temp.OTTPLAY_RESULTS[user_id][movie_id]


@Client.on_callback_query(filters.regex(r"^ottplay_post_(.+)$"))
async def ottplay_post(client, cq):
    movie_id = cq.data.split("_")[-1]
    user_id = cq.from_user.id
    
    if user_id not in ADMIN_IDS:
        return await cq.answer("🚫 Authorized for Admins only!", show_alert=True)
        
    data = temp.OTTPLAY_RESULTS.get(user_id, {}).get(movie_id)
    
    # Try RE-FETCH if expired
    if not data:
         await cq.answer("♻️ Session expired. Refetching data...", cache_time=0)
         today = datetime.now().strftime("%Y-%m-%d")
         # Fetch a broader range just in case
         movies = await fetch_ottplay_releases(today, today)
         movie = next((m for m in movies if str(m.get("_id")) == movie_id), None)
         if movie:
             data = await process_movie_data(movie, user_id)
         else:
             return await cq.answer("❌ Error: Movie data not found.", show_alert=True)
    
    await cq.answer("Posting...", cache_time=0)
    
    # Reconstruct message
    msg = f"✅ **{data['title']}** · {data['year']} · `{data['type_str']}`\n\n"
    msg += f"**>🉑 {data['lang_tag']}\n"
    msg += f">🎭 {data['genre_str']} · 📺 {data['provider_str']}\n"
    msg += f">®️ {data['cert_str']} · ⭐ {data['rating']}\n"
    msg += f">📅 {data['r_date']}\n"
    msg += f">👥 {data['cast_str']}\n"
    msg += f">\n"
    msg += f">__Plot:__\n"
    msg += f">{data['plot']}**\n"
    msg += f" **@MooviDex** "
    
    backdrop_url = data['backdrop_url']
    poster_url = data['poster_url']
    
    final_image_io = None
    if backdrop_url and poster_url:
        try:
             final_image_io = await generate_status_image(
                backdrop_url, poster_url, data['provider_logos'],
                data['title'], data['year'], data['rating'], data['genre_str'], data['plot']
             )
        except Exception as e:
            print(f"Post Image Gen Error: {e}")

    buttons = []
    buttons.append([
        InlineKeyboardButton(
            f"🔍 Search: {data['title']}", 
            url=f"https://t.me/{temp.U_NAME}?start=Search_{data['safe_title']}"
        )
    ])
    
    row = []
    if data['trailer_url']:
        row.append(InlineKeyboardButton("🎬 Trailer", url=data['trailer_url']))
    if data['tmdb_id']:
        media_type = "movie" if data['type_str'] == "Movie" else "tv"
        row.append(InlineKeyboardButton("More like this", url=f"https://t.me/{temp.U_NAME}?start=more_like_{data['tmdb_id']}_{media_type}"))
    if row:
        buttons.append(row)
        
    try:
        if final_image_io:
            final_image_io.seek(0)
            await client.send_photo(
                chat_id=UPDATE_CHANNEL_ID,
                photo=final_image_io,
                caption=msg,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        elif backdrop_url:
            await client.send_photo(
                chat_id=UPDATE_CHANNEL_ID,
                photo=backdrop_url,
                caption=msg,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
             await client.send_message(
                chat_id=UPDATE_CHANNEL_ID,
                text=msg,
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=True
            )
        await cq.answer("✅ Posted successfully!", show_alert=True)
    except Exception as e:
        await cq.answer(f"Error: {e}", show_alert=True)

@Client.on_callback_query(filters.regex(r"^ottplay_edit_post_(.+)$"))
async def ottplay_edit_post(client, cq):
    movie_id = cq.data.split("_")[-1]
    user_id = cq.from_user.id
    
    if user_id not in ADMIN_IDS:
        return await cq.answer("🚫 Authorized for Admins only!", show_alert=True)

    data = temp.OTTPLAY_RESULTS.get(user_id, {}).get(movie_id)
    if not data:
         # Try Re-fetch
         today = datetime.now().strftime("%Y-%m-%d")
         movies = await fetch_ottplay_releases(today, today)
         movie = next((m for m in movies if str(m.get("_id")) == movie_id), None)
         if movie:
             data = await process_movie_data(movie, user_id)
         else:
             return await cq.answer("❌ Error: Movie data not found.", show_alert=True)
        
    temp.EDITING_POST[user_id] = {"movie_id": movie_id, "source": "ottplay"}
    await cq.message.reply_text("✏️ Send the **new search keyword** or **full URL** to use in the search button.", quote=True)
    await cq.answer()

@Client.on_callback_query(filters.regex(r"close_message"))
async def close_message_callback(client, callback_query):
    try: await callback_query.message.delete()
    except Exception: await callback_query.answer("⚠️ Unable to delete the message.")

asyncio.create_task(check_releases_loop())
