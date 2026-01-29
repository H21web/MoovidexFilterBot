import re
import asyncio
import aiohttp
import traceback
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import temp
from info import *
from plugins.Extra.binged import HEADERS, ADMIN_IDS, clean_text, get_tmdb_details, search_tmdb_advanced, format_search_title, update_channel_post
from database.users_chats_db import db
from TechVJ.bot import TechVJBot
from plugins.Extra.image_gen import generate_status_image
from database.ia_filterdb import get_search_results

# Configuration
UPDATE_CHANNEL_ID = -1001680629032

# Cache to store movies that we are watching for (from Ottplay API)
# Key: movie_id (string), Value: movie_data (dict)
WANTED_MOVIES = {}

# --- HELPER FUNCTIONS ---

def parse_safe_title(safe_title):
    """Convert safe_title back to Title and Year component."""
    try:
        parts = safe_title.split('_')
        year = None
        if parts and parts[-1].isdigit() and len(parts[-1]) == 4:
            year = parts[-1]
            title = " ".join(parts[:-1])
        else:
            title = " ".join(parts)
        return title, year
    except:
        return safe_title, None

def is_smart_match(title, year, file_name):
    """
    Intelligent matching of Movie Title/Year against Filename.
    """
    if not title or not file_name:
        return False

    def clean(s):
        s = str(s).lower()
        s = re.sub(r'[._\-\[\]\(\)\{\}]', ' ', s) # Replace separators
        s = re.sub(r'\s+', ' ', s) # Collapse spaces
        return s.strip()

    t_clean = clean(title)
    f_clean = clean(file_name)

    # 1. Year Check
    # If target year exists, file MUST likely contain it (or +/- 1 year)
    # If file has NO year, we allow it (soft recall).
    if year and str(year).isdigit():
        target_year = int(year)
        # Find all 4-digit years in filename
        years_in_file = [int(y) for y in re.findall(r'\b(19\d{2}|20\d{2})\b', f_clean)]
        
        if years_in_file:
            # If file has years, one of them must match target (+/- 1)
            match = any(abs(y - target_year) <= 1 for y in years_in_file)
            if not match:
                return False

    # 2. Ordered Token Match
    # "Mission Impossible Dead Reckoning" should match "Mission.Impossible..Dead.Reckoning"
    # But "Dead Reckoning" should NOT match "Mission Impossible"
    stopwords = {'the', 'a', 'an', 'of', 'and', 'in', 'on', 'at', 'is', 'for'}
    tokens = [t for t in t_clean.split() if t not in stopwords]
    
    if not tokens: tokens = t_clean.split()

    # Create regex: token1 .* token2 .* token3
    # \b ensures boundary matching to avoid partial words (e.g. "Age" matching "Agent")
    pattern = r'.*'.join([re.escape(t) for t in tokens])
    
    if re.search(pattern, f_clean):
        return True
    
    return False

async def fetch_ottplay_releases(days=5):
    """Fetch releases from Ottplay for +/- days."""
    try:
        today = datetime.now()
        f_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
        t_date = (today + timedelta(days=days)).strftime("%Y-%m-%d")
        
        url = f"https://api2.ottplay.com/api/v4.7/web/new-release?limit=50&from_date={f_date}&to_date={t_date}&content_type=all&language=&provider="
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, timeout=20) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('result') or data.get('data') or []
    except Exception as e:
        print(f"Ottplay Fetch Error: {e}")
    return []

async def construct_movie_data_from_tmdb(title, year):
    """Create a unified movie structure from TMDB only (for Alert matches)."""
    tmdb_hits = await search_tmdb_advanced(title, year=year, media_type="movie")
    if not tmdb_hits:
        tmdb_hits = await search_tmdb_advanced(title, year=year, media_type="tv")
    
    if not tmdb_hits: return None
    
    return {
        "_id": f"tmdb_{tmdb_hits[0]['id']}",
        "name": tmdb_hits[0].get("title") or tmdb_hits[0].get("name"),
        "release_year": year,
        "content_type": "movie" if tmdb_hits[0].get("media_type") == "movie" else "show",
        "primary_language": {"logo_text": "Unknown"},
        "genres": [],
        "where_to_watch": [],
        "certifications": [],
        "posters": [],
        "ottplay_rating": 0,
        "is_tmdb_fallback": True,
        "tmdb_id": tmdb_hits[0]['id']
    }

# --- PROCESSOR ---

async def process_and_post_movie(movie, check_db=True):
    """
    Main Logic: Validate File Exists -> Build Message -> Post -> Notify.
    """
    try:
        title = clean_text(movie.get("name", ""))
        year = str(movie.get("release_year") or "")
        movie_id = str(movie.get("_id"))
        
        if not title: return False
        
        # 1. Deduplication (DB Check)
        if check_db:
             if await db.is_movie_posted(movie_id):
                 # Cleanup cache
                 WANTED_MOVIES.pop(movie_id, None)
                 return True # Already handled

        # 2. File Availability Check
        # Search by Title + Year first
        files, _, total = await get_search_results(UPDATE_CHANNEL_ID, f"{title} {year}", max_results=20)
        
        # Fallback to Title only if Year search failed
        if total == 0:
             files, _, total = await get_search_results(UPDATE_CHANNEL_ID, title, max_results=20)

        # Iterate findings to verify strict match
        found_file = False
        if total > 0:
            for f in files:
                fname = getattr(f, "file_name", "") or getattr(f, "name", "")
                if is_smart_match(title, year, fname):
                    found_file = True
                    break
        
        if not found_file:
            # File not yet available
            return False

        print(f"✅ Auto-Post Triggered: {title} ({year})")

        # 3. Data Enhancement (TMDB)
        content_type = movie.get("content_type", "movie")
        media_type = "movie" if "movie" in str(content_type).lower() else "tv"
        type_str = "Movie" if media_type == "movie" else "Series"
        
        # TMDB
        tmdb_data = None
        tmdb_id = movie.get("tmdb_id")
        
        if not tmdb_id:
             adv = await search_tmdb_advanced(title, year=year, media_type=media_type)
             if adv: tmdb_id = adv[0].get("id")
             
        if tmdb_id:
             tmdb_data = await get_tmdb_details(tmdb_id, media_type)

        # 4. Field Mapping (Safe Getters)
        rating = "N/A"
        plot = "No description available."
        genre_str = "N/A"
        cast_str = "N/A"
        trailer_url = None
        
        tmdb_backdrop = None
        tmdb_poster = None

        if tmdb_data:
            rating = tmdb_data.get("rating", "N/A")
            plot = tmdb_data.get("plot", plot)
            if tmdb_data.get("genres"): genre_str = ", ".join(tmdb_data.get("genres"))
            if tmdb_data.get("cast"): cast_str = ", ".join(tmdb_data.get("cast")[:5])
            if tmdb_data.get("videos") and tmdb_data["videos"][0].get("url"):
                trailer_url = f"https://www.youtube.com/watch?v={tmdb_data['videos'][0]['url']}"
            if tmdb_data.get("image"): tmdb_backdrop = tmdb_data.get("image")
            
            # Extract poster path
            orig = tmdb_data.get("original_data", {})
            if orig.get("poster_path"):
                 tmdb_poster = f"https://image.tmdb.org/t/p/original{orig.get('poster_path')}"

        # Ottplay Data
        lang = movie.get("primary_language", {}).get("logo_text", "Unknown")
        lang_tag = f"#{lang.replace(' ', '')}"
        
        # Providers
        prov_links = []
        for p in movie.get("where_to_watch", []):
             p_name = p.get("provider", {}).get("name")
             if p_name: prov_links.append(p_name)
        provider_str = ", ".join(prov_links[:3]) if prov_links else "N/A"
        
        r_date = "N/A"
        if movie.get("release_date"):
             try: r_date = datetime.fromisoformat(movie.get("release_date").replace("Z","")).strftime("%d-%m-%Y")
             except: r_date = movie.get("release_date")

        # Images
        ott_posters = movie.get("posters", [])
        ott_poster = ott_posters[0] if ott_posters else None
        
        backdrop_url = tmdb_backdrop if tmdb_backdrop else ott_poster
        poster_url = ott_poster if ott_poster else tmdb_poster # Prioritize OTT poster for Poster slot if available? Usually TMDB is better.
        if tmdb_poster: poster_url = tmdb_poster

        # 5. Message Construction
        msg = f"✅ **{title}** · {year} · `{type_str}`\n\n"
        msg += f"**>🉑 {lang_tag}\n"
        msg += f">🎭 {genre_str} · 📺 {provider_str}\n"
        msg += f">®️ N/A · ⭐ {rating}\n"
        msg += f">📅 {r_date}\n"
        msg += f">👥 {cast_str}\n"
        msg += f">\n"
        msg += f">__Plot:__\n"
        msg += f">{plot}**\n"
        msg += f" **@MooviDex** "

        # 6. Image Gen
        final_image = None
        if backdrop_url and poster_url:
             try:
                 final_image = await generate_status_image(
                     backdrop_url, poster_url, [],
                     title, year, rating, genre_str, plot
                 )
             except: pass

        # 7. Post to Channel
        buttons = []
        safe_title = format_search_title(title, year)
        
        if media_type == "movie":
             buttons.append([InlineKeyboardButton(f"🔍 Search: {title}", url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}")])
             
        row = []
        if trailer_url: row.append(InlineKeyboardButton("🎬 Trailer", url=trailer_url))
        if tmdb_id: row.append(InlineKeyboardButton("More like this", url=f"https://t.me/{temp.U_NAME}?start=more_like_{tmdb_id}_{media_type}"))
        if row: buttons.append(row)
        
        posted_message = None
        try:
            if final_image:
                 final_image.seek(0)
                 posted_message = await TechVJBot.send_photo(
                     UPDATE_CHANNEL_ID, photo=final_image, caption=msg, 
                     reply_markup=InlineKeyboardMarkup(buttons)
                 )
            elif backdrop_url:
                 posted_message = await TechVJBot.send_photo(
                     UPDATE_CHANNEL_ID, photo=backdrop_url, caption=msg,
                     reply_markup=InlineKeyboardMarkup(buttons)
                 )
            else:
                 posted_message = await TechVJBot.send_message(
                     UPDATE_CHANNEL_ID, text=msg, 
                     reply_markup=InlineKeyboardMarkup(buttons),
                     disable_web_page_preview=True
                 )
                 
            # 8. Notifications
            if posted_message:
                await db.add_posted_movie(movie_id)
                WANTED_MOVIES.pop(movie_id, None)
                
                # Check DB Alerts
                alerts = await db.get_movie_alerts(safe_title)
                if alerts:
                     for uid in alerts:
                         try:
                             if posted_message.photo:
                                  await TechVJBot.send_photo(uid, posted_message.photo.file_id, caption=msg, reply_markup=InlineKeyboardMarkup(buttons))
                             else:
                                  await TechVJBot.send_message(uid, text=msg, reply_markup=InlineKeyboardMarkup(buttons))
                         except: pass
                     await db.delete_movie_alerts(safe_title)
            
            return True

        except Exception as e:
            print(f"Posting Error: {e}")
            return False

    except Exception as e:
        traceback.print_exc()
        return False

# --- HOOKS ---

async def check_and_post_if_needed(file_name):
    """Triggered by ia_filterdb when a New File is added."""
    
    # 1. Check Cache (WANTED)
    # Convert dict values to list to avoid runtime error if dict changes size
    cached_movies = list(WANTED_MOVIES.values())
    
    for movie in cached_movies:
        title = clean_text(movie.get("name", ""))
        year = movie.get("release_year")
        
        if is_smart_match(title, year, file_name):
            # Move off thread
            asyncio.create_task(process_and_post_movie(movie))
            # optimization: continue? maybe multiple matches? usually one.
            pass

    # 2. Check Alerts (DB)
    # This covers movies that might NOT be in Ottplay recent list but users want.
    try:
        all_alerts = await db.get_all_alerts() # returns [{'movie_id': 'Title_Year', 'user_ids': []}]
        
        for alert in all_alerts:
            safe = alert.get("movie_id")
            if not safe: continue
            
            t, y = parse_safe_title(safe)
            if is_smart_match(t, y, file_name):
                # We have a filename match for an Alert!
                # We don't have movie data, so fetch from TMDB
                movie_data = await construct_movie_data_from_tmdb(t, y)
                if movie_data:
                     # Check if already posted to avoid spam
                     if not await db.is_movie_posted(movie_data["_id"]):
                         asyncio.create_task(process_and_post_movie(movie_data))
    except Exception as e:
        print(f"Audit Hook Error: {e}")

async def check_releases_loop():
    """Background loop to fetch new releases from Ottplay."""
    print("Initializing Auto-Update Loop...")
    
    while True:
        try:
            # Sync Wanted List
            movies = await fetch_ottplay_releases(days=5)
            for m in movies:
                mid = str(m.get("_id"))
                if not await db.is_movie_posted(mid):
                    WANTED_MOVIES[mid] = m
                    # Try post immediately if file exists
                    await process_and_post_movie(m, check_db=True)
            
            # Wait 1 hour
            await asyncio.sleep(3600)
            
        except Exception as e:
            print(f"Loop Error: {e}")
            await asyncio.sleep(60)
