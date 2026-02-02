import re
import html
import asyncio
import aiohttp
import traceback
from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import temp
from info import *
from plugins.Extra.binged import HEADERS, ADMIN_IDS, clean_text, get_tmdb_details, search_tmdb_advanced, format_search_title
from database.users_chats_db import db
from TechVJ.bot import TechVJBot
from plugins.Extra.image_gen import generate_status_image
from database.ia_filterdb import get_search_results

# --- CONFIGURATION & GLOBAL STATE ---
UPDATE_CHANNEL_ID = -1001680629032  # Update Channel ID
PROCESSING_MOVIES = set()           # Cache to prevent race conditions

# --- API FETCHERS ---

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
    url = f"https://api2.ottplay.com/api/v4.7/web/new-release?limit=20&from_date={from_date}&to_date={to_date}&content_type=all&language=&provider="
    data = await fetch_url(url)
    if data:
        return data.get('result', [])
    return []

# --- MATCHING LOGIC ---

def is_smart_match(title, year, file_name):
    """
    Revised Matching Logic: 
    1. Check presence of Title in File Name.
    2. If Year is present in API data AND File Name, it MUST match.
    3. If Year is in API but NOT in File Name, we allow Title-only match (Looser).
    """
    if not title or not file_name: return False
    
    # 1. Cleaning
    def clean(s):
        s = str(s).lower()
        s = re.sub(r'[._\-\[\]\(\)\{\}]', ' ', s) # delimiters to space
        s = re.sub(r'\s+', ' ', s) # collapse spaces
        return s.strip()

    title_clean = clean(title)
    file_clean = clean(file_name)
    
    # 2. Extract Years from File
    file_years = re.findall(r'\b(19\d{2}|20\d{2})\b', file_clean)
    
    # 3. Year Verification
    header_match = False
    
    if year and str(year).isdigit():
        target_year = int(year)
        if file_years:
            # File HAS years. One of them MUST match target (tolerance +/- 1)
            for fy in file_years:
                if abs(int(fy) - target_year) <= 1:
                    header_match = True
                    break
            # If file has years but NO match -> Fail
            if not header_match: return False
        else:
            # File has NO years -> Loose Match Allowed (Proceed to Title Check)
            pass 
    
    # 4. Title Verification (Token Order)
    stopwords = {'the', 'a', 'an', 'of', 'and', 'in', 'on', 'at', 'to', 'is', 'a', 'part', 'vol', 'season', 's'}
    title_words = [w for w in title_clean.split() if w not in stopwords]
    
    if not title_words: title_words = title_clean.split()
    
    # Regex: word1 + anything + word2 ...
    pattern = r'.*'.join([re.escape(w) for w in title_words])
    
    if re.search(pattern, file_clean):
        return True
        
    return False

# --- POSTING LOGIC ---

async def process_and_post_movie(movie, file_name_found=None):
    """
    Generate post and send to channel.
    """
    try:
        movie_id = str(movie.get("_id") or movie.get("id"))
        
        # 0. Check Processing Lock (Thread-Safeish for Asyncio tasks)
        if movie_id in PROCESSING_MOVIES:
            return False

        # 1. Check DB First
        if await db.is_movie_posted(movie_id):
            return False

        # 2. Acquire Lock
        PROCESSING_MOVIES.add(movie_id)
        
        # 3. Double Check DB (in case of race condition during await above)
        is_posted = await db.is_movie_posted(movie_id)
        if is_posted:
             PROCESSING_MOVIES.remove(movie_id)
             return False

        title = clean_text(movie.get("name", ""))
        year = movie.get("release_year")
        
        print(f"✅ Preparing Post for: {title} ({year})")
        
        # --- Gather Details ---
        content_type = movie.get("content_type", "movie")
        media_type = "movie" if content_type == "movie" else "tv"
        type_str = "Movie" if media_type == "movie" else "Series"
        
        # Formatting Helpers
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
            if logo: provider_logos.append(logo)
            
            p_link = p.get("movie_url") or p.get("show_url")
            # Minimal link logic
            if not p_link and p_name and p.get("partner_title_id"):
                 ptid = p.get("partner_title_id")
                 if "netflix" in p_name.lower(): p_link = f"https://www.netflix.com/title/{ptid}"
                 elif "zee5" in p_name.lower(): p_link = f"https://www.zee5.com/global/content/{ptid}"
            
            if p_link and not p_link.startswith("http"):
                 p_link = f"https://{p_link}" if p_link.startswith("www") else None

            if p_link: platform_links.append(f"[{p_name}]({p_link})")
            elif p_name: platform_links.append(p_name)

        provider_str = ", ".join(platform_links[:3]) if platform_links else "N/A"
        
        # Date
        api_date = movie.get("release_date")
        if api_date:
            try: r_date = datetime.fromisoformat(api_date.replace("Z", "+00:00")).strftime("%d-%m-%Y")
            except: r_date = api_date
        else: r_date = "N/A"

        certs = [c.get("certification") for c in movie.get("certifications", [])]
        cert_str = "/".join(certs) if certs else "N/A"

        posters = movie.get("posters", [])
        ottplay_poster = posters[0] if posters else None
        
        # TMDB Integration
        tmdb_backdrop, tmdb_poster, tmdb_rating, tmdb_plot, tmdb_id = None, None, None, None, None
        cast_str = "N/A"
        trailer_url = None
        
        tmdb_results = await search_tmdb_advanced(title, year=year, media_type=media_type)
        if tmdb_results:
            tmdb_id = tmdb_results[0].get("id")
            tmdb_details = await get_tmdb_details(tmdb_id, media_type)
            if tmdb_details:
                 if tmdb_details.get("image"): tmdb_backdrop = tmdb_details.get("image")
                 t_orig = tmdb_details.get("original_data", {})
                 if t_orig.get("poster_path"): tmdb_poster = f"https://image.tmdb.org/t/p/original{t_orig.get('poster_path')}"
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
        
        # Message Construction
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
            final_image_io = await generate_status_image(
                backdrop_url, poster_url, provider_logos,
                title, year, rating, genre_str, plot
            )

        # Buttons
        buttons = []
        if media_type != "tv":
            buttons.append([InlineKeyboardButton(f"🔍 Search: {title}", url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}")])
            
        row = []
        if trailer_url: row.append(InlineKeyboardButton("🎬 Trailer", url=trailer_url))
        if tmdb_id: row.append(InlineKeyboardButton("More like this", url=f"https://t.me/{temp.U_NAME}?start=more_like_{tmdb_id}_{media_type}"))
        if row: buttons.append(row)

        # Send
        posted_msg = None
        if final_image_io:
            final_image_io.seek(0)
            posted_msg = await TechVJBot.send_photo(UPDATE_CHANNEL_ID, final_image_io, caption=msg, reply_markup=InlineKeyboardMarkup(buttons))
        elif backdrop_url:
            posted_msg = await TechVJBot.send_photo(UPDATE_CHANNEL_ID, backdrop_url, caption=msg, reply_markup=InlineKeyboardMarkup(buttons))
        else:
            posted_msg = await TechVJBot.send_message(UPDATE_CHANNEL_ID, msg, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
            
        # Notify Users
        alert_users = await db.get_movie_alerts(safe_title)
        if alert_users:
            for uid in alert_users:
                try:
                    if posted_msg.photo:
                         await TechVJBot.send_photo(uid, posted_msg.photo.file_id, caption=msg, reply_markup=InlineKeyboardMarkup(buttons))
                    else:
                         await TechVJBot.send_message(uid, msg, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
                except: pass
            await db.delete_movie_alerts(safe_title)
            
        # Mark Posted
        await db.add_posted_movie(movie_id)
        
        # Remove from Processing Lock after DB update is secure
        if movie_id in PROCESSING_MOVIES:
             PROCESSING_MOVIES.remove(movie_id)
             
        return True

    except Exception as e:
        print(f"Post Error: {e}")
        # Release lock on error to allow retry later
        movie_id = str(movie.get("_id") or movie.get("id"))
        if movie_id in PROCESSING_MOVIES:
             PROCESSING_MOVIES.remove(movie_id)
             
        traceback.print_exc()
        return False

# --- CORE LOGIC ---

async def refresh_new_releases():
    """
    1. Fetch today's releases from API.
    2. Store in DB (NEW_UPDATE).
    3. Prune old releases (FIFO).
    """
    try:
        today = datetime.now()
        # Fetching for today + next 2 days to cover recent release timezones
        from_date = today.strftime("%Y-%m-%d")
        to_date = (today + timedelta(days=2)).strftime("%Y-%m-%d")
        
        print(f"🔄 Refreshing Releases: {from_date}")
        releases = await fetch_ottplay_releases(from_date, to_date)
        
        users_added = 0
        for movie in releases:
            await db.add_new_release(movie)
            users_added += 1
            
        # Keep list fresh (limit to 100 items)
        await db.delete_old_releases(limit=100)
        
        print(f"✅ Refreshed: Added/Updated {users_added} releases.")
        
    except Exception as e:
        print(f"Refresh Error: {e}")

async def check_and_post_if_needed(file_name):
    """
    Called when a new file is saved.
    1. Load NEW_UPDATE from DB.
    2. Check Match.
    3. Post if Match.
    """
    try:
        # Get active watch list
        new_updates = await db.get_all_new_releases()
        if not new_updates: return

        matched_movie = None
        
        for movie in new_updates:
            title = movie.get("name")
            year = movie.get("release_year")
            
            if is_smart_match(title, year, file_name):
                matched_movie = movie
                break
        
        if matched_movie:
             print(f"⚡ Match Found: {file_name} -> {matched_movie.get('name')}")
             await process_and_post_movie(matched_movie, file_name_found=file_name)

    except Exception as e:
        print(f"Check File Error: {e}")


# --- LOOPS & COMMANDS ---

async def check_releases_loop():
    print("🚀 Started Daily Release Watcher")
    while True:
        await refresh_new_releases()
        await asyncio.sleep(3600 * 6) # Refresh every 6 hours

# /today Command (Admin)
@Client.on_message(filters.command("today") & filters.user(ADMIN_IDS))
async def manual_refresh_and_list(client, message):
    m = await message.reply("🔄 Refreshing database...")
    await refresh_new_releases()
    
    # Show what's in DB
    new_updates = await db.get_all_new_releases()
    if not new_updates:
        return await m.edit("Database is empty.")
        
    txt = f"**📂 Current Watch List ({len(new_updates)}):**\n\n"
    for mv in new_updates[:20]: # Show top 20
         txt += f"- {mv.get('name')} ({mv.get('release_year')})\n"
         
    await m.edit(txt)

# Helper for processing data (used by other plugins if needed)
async def process_movie_data(movie, user_id):
    # Backward compatibility stub if other plugins import this
    return {}
