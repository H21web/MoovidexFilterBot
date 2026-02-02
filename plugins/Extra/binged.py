import aiohttp
import re
import html
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import temp
from info import *
from plugins.Extra.image_gen import generate_status_image

# --- HELPER FUNCTIONS ---

def clean_text(text):
    if not isinstance(text, str):
        return ""
    text = html.unescape(text)
    for orig, sub in [
        ("\u2019", "'"), ("\u2018", "'"),
        ("\u201c", '"'), ("\u201d", '"'),
        ("\u2013", "-"), ("\u2014", "-"),
        ("\u2026", "...")
    ]:
        text = text.replace(orig, sub)
    return text.strip()

def format_search_title(title, year):
    if not title:
        return ""
    
    title = clean_text(title)
        
    def season_repl(match):
        try:
            num = int(match.group(1))
            return f"S{num:02d}"
        except:
            return match.group(0)
            
    title = re.sub(r'(?i)Season\s+(\d+)', season_repl, title)
    safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)
    
    if year and str(year).isdigit():
         safe_title = f"{safe_title}_{year}"
         
    return safe_title

def unix_to_date(unix_ts):
    try:
        if not unix_ts: return "N/A"
        return datetime.fromtimestamp(int(unix_ts)).strftime("%d-%m-%Y")
    except:
        return "N/A"

def get_platform_name(platform_data):
    if not platform_data:
        return "OTT"
    
    ref_url = (platform_data.get("ref_url") or "").lower()
    logo_url = (platform_data.get("logo_url") or "").lower()
    
    if "hotstar" in ref_url or "hotstar" in logo_url: return "Hotstar"
    elif "prime" in ref_url or "prime" in logo_url: return "Prime Video"
    elif "netflix" in ref_url or "netflix" in logo_url: return "Netflix"
    elif "zee5" in ref_url or "zee5" in logo_url: return "Zee5"
    elif "sunnxt" in ref_url or "sunnxt" in logo_url: return "SunNXT"
    elif "sonyliv" in ref_url or "sonyliv" in logo_url: return "SonyLIV"
    elif "jiocinema" in ref_url or "jiocinema" in logo_url: return "JioCinema"
    elif "voot" in ref_url or "voot" in logo_url: return "Voot"
    elif "mxplayer" in ref_url or "mxplayer" in logo_url: return "MX Player"
    elif "aha" in ref_url or "aha" in logo_url: return "Aha"
    elif "apple" in ref_url or "apple" in logo_url: return "Apple TV+"
    elif "hulu" in ref_url or "hulu" in logo_url: return "Hulu"
    elif "hbo" in ref_url or "hbo" in logo_url: return "HBO Max"
    elif "disney" in ref_url or "disney" in logo_url: return "Disney+"
    else: return "OTT"

async def fetch_json(url, params=None, headers=None, timeout=10):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=timeout) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
    except Exception as e:
        print(f"Fetch Error: {e}")
        return None

# --- TMDB API ---

TMDB_API_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_URL = "https://image.tmdb.org/t/p/original"
SEARCH_URL = "https://api2.ottplay.com/api/search-service/v1.1/universal-search"
# DETAIL_URL = "https://www.binged.com/wp-json/binged-api/v1/movie" # Unused?

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/85.0.4183.121 Safari/537.36',
    'Referer': 'https://www.binged.com/'
}

ADMIN_IDS = [1011394081, 7191327005]
UPDATE_CHANNEL_ID = -1001680629032

# Init global vars just in case
if not hasattr(temp, 'BINGED_RESULTS'): temp.BINGED_RESULTS = {}
if not hasattr(temp, 'TMDB_RESULTS'): temp.TMDB_RESULTS = {}
if not hasattr(temp, 'EDITING_POST'): temp.EDITING_POST = {}
if not hasattr(temp, 'MOVIE_STATUS'): temp.MOVIE_STATUS = {}


from database.users_chats_db import db
from database.stats_db import stats_db

# --- API FUNCTIONS ---

async def search_tmdb(query):
    try:
        url = f"{TMDB_API_URL}/search/multi"
        params = {
            "api_key": TMDB_API_KEY,
            "query": query,
            "language": "en-US",
            "page": 1,
            "include_adult": "true"
        }
        data = await fetch_json(url, params=params)
        if not data: return []
        
        results = []
        for item in data.get("results", []):
            if item.get("media_type") not in ["movie", "tv"]:
                continue
            results.append(item)
        return results
    except Exception as e:
        print(f"TMDB Search Error: {e}")
        return []

async def search_tmdb_advanced(query, year=None, media_type="movie"):
    try:
        endpoint = "tv" if media_type == "tv" else "movie"
        url = f"{TMDB_API_URL}/search/{endpoint}"
        
        params = {
            "api_key": TMDB_API_KEY,
            "query": query,
            "language": "en-US",
            "page": 1,
            "include_adult": "true"
        }
        
        if year and str(year).isdigit():
            if media_type == "tv":
                params["first_air_date_year"] = str(year)
            else:
                params["primary_release_year"] = str(year)
                
        data = await fetch_json(url, params=params)
        if not data: return []
        
        results = []
        for item in data.get("results", []):
            item["media_type"] = media_type
            results.append(item)
            
        return results
    except Exception as e:
        print(f"TMDB Advanced Search Error: {e}")
        return await search_tmdb(f"{query} {year}" if year else query)

async def find_tmdb_id(query):
    try:
        if re.match(r'^tt\d+$', query):
            url = f"{TMDB_API_URL}/find/{query}"
            params = {
                "api_key": TMDB_API_KEY,
                "external_source": "imdb_id"
            }
            data = await fetch_json(url, params=params)
            if not data: return []
            
            results = []
            for media_type in ["movie_results", "tv_results"]:
                for item in data.get(media_type, []):
                    item["media_type"] = "movie" if media_type == "movie_results" else "tv"
                    results.append(item)
            return results
        else:
            return await search_tmdb(query)
            
    except Exception as e:
        print(f"TMDB Find Error: {e}")
        return []

async def get_tmdb_details(tmdb_id, media_type="movie"):
    try:
        url = f"{TMDB_API_URL}/{media_type}/{tmdb_id}"
        params = {
            "api_key": TMDB_API_KEY,
            "language": "en-US",
            "append_to_response": "credits,videos,images,recommendations,similar"
        }
        data = await fetch_json(url, params=params)
        if not data: return None
        
        title = data.get("title") or data.get("name") or "Unknown"
        release_date = data.get("release_date") or data.get("first_air_date") or "N/A"
        year = release_date.split("-")[0] if release_date != "N/A" else "N/A"
        
        genres = [g["name"] for g in data.get("genres", [])]
        cast = [c["name"] for c in data.get("credits", {}).get("cast", [])[:5]]
        
        runtime = data.get("runtime") or (data.get("episode_run_time")[0] if data.get("episode_run_time") else None)
        runtime_str = f"{runtime}m" if runtime else "N/A"
        
        rating = f"{round(data.get('vote_average', 0), 1)}/10"
        
        # Images
        poster_path = data.get("poster_path")
        backdrop_path = data.get("backdrop_path")
        
        images = data.get("images", {})
        backdrops = images.get("backdrops", [])
        
        best_backdrop = None
        if backdrops:
            english_backdrops = [b for b in backdrops if b.get("iso_639_1") == "en"]
            english_backdrops.sort(key=lambda x: x.get("vote_count", 0), reverse=True)
            backdrops.sort(key=lambda x: x.get("vote_count", 0), reverse=True)
            none_backdrops = [b for b in backdrops if b.get("iso_639_1") is None]
            none_backdrops.sort(key=lambda x: x.get("vote_count", 0), reverse=True)

            if english_backdrops:
                best_backdrop = english_backdrops[0].get("file_path")
            elif none_backdrops and none_backdrops[0].get("vote_count", 0) > 5:
                 best_backdrop = none_backdrops[0].get("file_path")
            elif backdrops:
                best_backdrop = backdrops[0].get("file_path")
        
        if not best_backdrop: best_backdrop = backdrop_path
            
        image_url = f"{TMDB_IMAGE_URL}{best_backdrop}" if best_backdrop else (f"{TMDB_IMAGE_URL}{poster_path}" if poster_path else "")
        
        similar = []
        recommendations = data.get("recommendations", {}).get("results", []) or data.get("similar", {}).get("results", [])
        for item in recommendations:
            if item.get("backdrop_path") or item.get("poster_path"):
                similar.append({
                    "id": item.get("id"),
                    "title": item.get("title") or item.get("name"),
                    "media_type": media_type
                })
                
        videos = []
        for v in data.get("videos", {}).get("results", []):
            if v.get("site") == "YouTube" and v.get("type") == "Trailer":
                videos.append(v)
                
        return {
            "id": data.get("id"),
            "title": title,
            "year": year,
            "plot": data.get("overview", "No description available."),
            "rating": rating,
            "genres": genres,
            "cast": cast,
            "runtime": runtime_str,
            "image": image_url,
            "type": "Movie" if media_type == "movie" else "Series",
            "release_date": release_date,
            "videos": videos,
            "similar": similar,
            "media_type": media_type,
            "original_data": data 
        }
    except Exception as e:
        print(f"TMDB Details Error: {e}")
        return None

def get_similar_movies(movie_data, count=3):
    similar = movie_data.get("similar", [])
    current_title = clean_text(movie_data.get("post_title", movie_data.get("title", ""))).lower()
    current_id = str(movie_data.get("ID", movie_data.get("id", "")))
    
    unique_similar = []
    seen_titles = set()
    
    for sim in similar:
        sim_title = clean_text(sim.get("title", ""))
        sim_id = str(sim.get("id", ""))
        sim_title_lower = sim_title.lower()
        
        if sim_title_lower == current_title or sim_id == current_id: continue
        if sim_title_lower in seen_titles: continue
        
        seen_titles.add(sim_title_lower)
        unique_similar.append(sim)
        if len(unique_similar) >= count: break
    
    return unique_similar

# --- MESSAGE BUILDERS ---

def build_released_message(movie_data, bot_username, source='binged'):
    # Logic for released movie formatting
    if source == 'imdb':
        title = clean_text(movie_data.get("title", "Unknown"))
        year = movie_data.get("year", "N/A")
        movie_type = movie_data.get("type", "Movie").capitalize()
        lang_tags = "#English"
        genres = movie_data.get("genres", [])
        genre_str = ", ".join(genres) if genres else "N/A"
        platform_str = "N/A"
        runtime = movie_data.get("runtime", "N/A")
        if runtime and runtime != "N/A" and not str(runtime).endswith("m"): runtime = f"{runtime}m"
        rating = movie_data.get("rating", "N/A")
        cast = movie_data.get("cast", [])
        cast_str = ", ".join(cast[:5]) if cast else "N/A"
        plot = clean_text(movie_data.get("description", "No description available."))
        msg = f"✅ **{title}** · {year} · `{movie_type}`\n\n**>🉑 {lang_tags}\n>🎭 {genre_str} · 📺 {platform_str}\n>⏱️ {runtime} · ⭐ {rating}\n>👥 {cast_str}\n>\n>__Plot:__\n>{plot}**\n **@MooviDex** "
        return msg, movie_data.get("image", "")

    else: # binged
        title = clean_text(movie_data.get("post_title", movie_data.get("title", "Unknown")))
        year = movie_data.get("release_year", movie_data.get("year", "N/A"))
        movie_type = movie_data.get("category", movie_data.get("type", "N/A"))
        
        # Langs
        langs = movie_data.get("lang", [])
        if isinstance(langs, list):
             lang_tags = " ".join([f"#{l.strip().replace(' ', '')}" for l in langs]) if langs else "#Unknown"
        else:
             lang_tags = "#Unknown"

        # Genres
        genres = movie_data.get("genre", [])
        genre_str = ", ".join(genres) if genres else "N/A"

        # Platforms
        platform_str = "N/A"
        if movie_data.get("provider_str") and movie_data.get("provider_str") != "N/A":
             platform_str = movie_data.get("provider_str")
        else:
             platforms = movie_data.get("platform_logos", [])
             if platforms:
                for p in platforms:
                     if p and p.get("rent_and_buy") == "0":
                         ref = p.get("ref_url") or ""
                         name = get_platform_name(p)
                         platform_str = f"[{name}]({ref})" if ref else name
                         break

        # Runtime/Censor
        runtime = movie_data.get("run_time", movie_data.get("duration", "N/A"))
        if runtime != "N/A" and not str(runtime).endswith("m"): runtime = f"{runtime}m"
        censor = movie_data.get("censor", "NR")
        release_date = unix_to_date(movie_data.get("release_date"))
        
        # Cast
        actors = movie_data.get("actors", [])
        cast_str = "N/A"
        if actors:
             if isinstance(actors[0], list) and len(actors[0]) > 1:
                  cast_str = ", ".join([a[1] for a in actors[:5]])
             elif isinstance(actors[0], str):
                  cast_str = ", ".join(actors[:5])

        plot = clean_text(movie_data.get("post_content", "No description available."))

        msg = f"✅ **{title}** · {year} · `{movie_type}`\n\n**>🉑 {lang_tags}\n>🎭 {genre_str} · 📺 {platform_str}\n>⏱️ {runtime} · ®️ {censor}\n>📅 {release_date}\n>👥 {cast_str}\n>\n>__Plot:__\n>{plot}**\n **@MooviDex** "
        return msg, movie_data.get("image", "")

def build_upcoming_message(movie_data, bot_username, source='binged'):
    # Simplyfy Upcoming Message Logic
    if source == 'imdb':
        title = clean_text(movie_data.get("title", "Unknown"))
        year = movie_data.get("year", "N/A")
        movie_type = movie_data.get("type", "Movie").capitalize()
        # Fallbacks not really needed since we removed detailed fields
        msg = f"🔜 **{title}** · {year} · `{movie_type}`\n\n**>🉑 English\n>📺 N/A\n>📅 N/A\n\n **@MooviDex** "
        return msg, movie_data.get("image", "")
    else:
        title = clean_text(movie_data.get("post_title", movie_data.get("title", "Unknown")))
        year = movie_data.get("release_year", movie_data.get("year", "N/A"))
        movie_type = movie_data.get("category", movie_data.get("type", "N/A"))
        
        langs = movie_data.get("lang", [])
        lang_str = ", ".join(langs) if langs else "Unknown" # Using comma separation instead of hashtags for simplified look? User used hashtags in upcoming.py... let's stick to user style if possible
        # User in Step 191 used: msg += f"**>🉑 {data['lang_tag']}\n"
        
        lang_tag = f"#{lang_str.split(',')[0].strip()}" if lang_str != "Unknown" else "#Unknown"
        if isinstance(langs, list):
             # Just use first lang if multiple, or all tags
             lang_tag = " ".join([f"#{l.strip().replace(' ', '')}" for l in langs])
        
        release_date = unix_to_date(movie_data.get("release_date"))
        
        platform_str = "N/A"
        if movie_data.get("provider_str") and movie_data.get("provider_str") != "N/A":
             platform_str = movie_data.get("provider_str")
        
        msg = f"🔜 **{title}** · {year} · `{movie_type}`\n\n>🉑 {lang_tag}\n>📺 {platform_str}\n>📅 {release_date}\n **@MooviDex** "
        return msg, movie_data.get("image", "")

# --- HANDLERS ---

@Client.on_message(filters.command("binged"))
async def binged_search(client, message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply_text("🚫 This command is for admins only.")
    
    query = " ".join(message.command[1:]).strip()
    if not query: return await message.reply_text("Usage: /binged <movie name>")
    
    url = f"https://imdb.iamidiotareyoutoo.com/justwatch?q={query}"
    try:
        data = await fetch_json(url, headers={'User-Agent': 'Mozilla/5.0'})
        results = data.get("description", []) if data else []
    except Exception as e:
        return await message.reply_text(f"API Error: {e}")

    if not results: return await message.reply_text("No results found.")

    temp.BINGED_RESULTS[message.from_user.id] = {}
    buttons = []
    for item in results:
        title = clean_text(item.get("title"))
        if not title: continue
        item_id = str(item.get("id"))
        year = item.get("year", "N/A")
        ctype = item.get("type", "MOVIE")
        
        temp.BINGED_RESULTS[message.from_user.id][item_id] = item
        buttons.append([InlineKeyboardButton(f"{title} ({year}) - {ctype}", callback_data=f"binged_detail_{item_id}")])

    buttons.append([InlineKeyboardButton("Close ❌", callback_data="close_message")])
    await message.reply_text(f"JustWatch Search: <b>{query}</b>", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^binged_detail_(.+)$"))
async def binged_detail(client, cq):
    movie_id = cq.data.split("_")[-1]
    user_id = cq.from_user.id
    movie = temp.BINGED_RESULTS.get(user_id, {}).get(movie_id)
    
    if not movie: return await cq.answer("Session expired. Search again.", show_alert=True)
    await cq.answer("Fetching details...")

    # Basic data
    title = clean_text(movie.get("title", ""))
    year = movie.get("year", "N/A")
    media_type = "movie" if movie.get("type") == "MOVIE" else "tv"
    type_str = "Movie" if media_type == "movie" else "Series"

    # Providers
    offers = movie.get("offers", [])
    seen = set()
    links = []
    logos = [] 
    
    for offer in offers:
        name = offer.get("name")
        url = offer.get("url")
        if name and name not in seen:
            seen.add(name)
            links.append(f"[{name}]({url})")
    
    provider_str = ", ".join(links[:3]) if links else "N/A"

    # Images
    jw_backdrop = (movie.get("backdrops") or [None])[0]
    jw_poster = (movie.get("photo_url") or [None])[0]

    # TMDB Enrich
    tmdb_details = None
    tmdb_id = movie.get("tmdbId")
    if tmdb_id:
        tmdb_details = await get_tmdb_details(tmdb_id, media_type)
    else:
        adv = await search_tmdb_advanced(title, year, media_type)
        if adv: tmdb_details = await get_tmdb_details(adv[0].get("id"), media_type)

    final_langs = []
    tmdb_rating = "N/A"
    tmdb_plot = "No description available."
    genres = []
    cast = []
    tmdb_backdrop = None
    
    if tmdb_details:
        tmdb_plot = tmdb_details.get("plot")
        tmdb_rating = tmdb_details.get("rating")
        genres = tmdb_details.get("genres", [])
        cast = tmdb_details.get("cast", [])
        
        # Original Image
        if tmdb_details.get("image"): tmdb_backdrop = tmdb_details.get("image")
        
        # Languages
        orig = tmdb_details.get("original_data", {})
        spoken = orig.get("spoken_languages", [])
        if spoken:
             final_langs = list(set([l.get("english_name") for l in spoken]))[:3]
        else:
             final_langs = [orig.get("original_language", "en")]

    # Update Data
    movie['rating'] = tmdb_rating
    movie['post_content'] = tmdb_plot
    movie['genre'] = genres
    movie['genre_str'] = ", ".join(genres) if genres else "N/A"
    movie['cast'] = cast
    movie['cast_str'] = ", ".join(cast[:5]) if cast else "N/A"
    movie['backdrop_url'] = jw_backdrop
    movie['poster_url'] = jw_poster
    movie['image'] = tmdb_backdrop or jw_backdrop
    movie['provider_logos'] = [] # Pass empty usually unless we scrape logos
    
    # MAPPING FOR POSTING (ENSURE ALL KEYS EXIST)
    movie['post_title'] = title
    movie['release_year'] = year
    movie['category'] = type_str
    movie['run_time'] = tmdb_details.get("runtime") if tmdb_details else "N/A"
    movie['lang'] = final_langs if final_langs else ["Unknown"]
    movie['provider_str'] = provider_str
    movie['actors'] = [[None, c] for c in cast]
    if 'censor' not in movie: movie['censor'] = "NR"
    if 'release_date' not in movie: movie['release_date'] = None
    if 'lang' not in movie: movie['lang'] = []
    
    temp.BINGED_RESULTS[user_id][movie_id] = movie
    
    # Message
    lang_tag = " ".join([f"#{l.replace(' ', '')}" for l in movie['lang']])
    msg = f"✅ **{title}** · {year} · `{type_str}`\n\n**>🉑 {lang_tag}\n>🎭 {movie['genre_str']} · 📺 {provider_str}\n>®️ N/A · ⭐ {tmdb_rating}\n>📅 {year}\n>👥 {movie['cast_str']}\n>\n>__Plot:__\n>{tmdb_plot}**\n **@MooviDex** "

    # Buttons
    safe_title = format_search_title(title, year)
    btn = [[InlineKeyboardButton(f"🔍 Search: {title}", url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}")]]
    btn.append([
        InlineKeyboardButton("✏️ Edit & Post", callback_data=f"binged_edit_post_{movie_id}"),
        InlineKeyboardButton("📣 Post Default", callback_data=f"binged_post_{movie_id}")
    ])
    btn.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
    
    if movie.get('image'):
         await cq.message.reply_photo(movie['image'], caption=msg, reply_markup=InlineKeyboardMarkup(btn))
    else:
         await cq.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
    await cq.answer()

@Client.on_callback_query(filters.regex(r"^binged_status_(released|upcoming)_(.+)$"))
async def binged_status_select(client, cq):
    match = re.match(r"^binged_status_(released|upcoming)_(.+)$", cq.data)
    status, movie_id = match.group(1), match.group(2)
    user_id = cq.from_user.id
    
    movie_data = temp.BINGED_RESULTS.get(user_id, {}).get(movie_id)
    if not movie_data: return await cq.answer("Data lost.", show_alert=True)
    
    temp.MOVIE_STATUS[movie_id] = status
    
    title = clean_text(movie_data.get("post_title", "Unknown"))
    year = movie_data.get("release_year", "N/A")
    safe_title = format_search_title(title, year)
    
    if status == "upcoming":
        msg, image = build_upcoming_message(movie_data, temp.U_NAME, source='binged')
    else:
        msg, image = build_released_message(movie_data, temp.U_NAME, source='binged')
        
    btn = []
    if status == "upcoming":
        videos = movie_data.get("videos", [])
        if videos:
             v_url = videos[0].get("url")
             if v_url: btn.append([InlineKeyboardButton("🎬 Trailer", url=f"https://www.youtube.com/watch?v={v_url}")])
        btn.append([InlineKeyboardButton("🔔 Notify when Released", callback_data=f"notify_release_{movie_id}")])
    else:
        btn.append([InlineKeyboardButton(f"{title} · {year}", url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}")])
        row = []
        videos = movie_data.get("videos", [])
        if videos:
             v_url = videos[0].get("url")
             if v_url: row.append(InlineKeyboardButton("🎬 Trailer", url=f"https://www.youtube.com/watch?v={v_url}"))
        
        sims = get_similar_movies(movie_data, 1)
        if sims:
             st = clean_text(sims[0].get("title"))
             sst = format_search_title(st, None)
             row.append(InlineKeyboardButton("🔄 More like this", url=f"https://t.me/{temp.U_NAME}?start=Search_{sst}"))
        if row: btn.append(row)
        
    if user_id in ADMIN_IDS:
        btn.append([
            InlineKeyboardButton("✏️ Edit & Post", callback_data=f"binged_edit_post_{movie_id}"),
            InlineKeyboardButton("📣 Post Default", callback_data=f"binged_post_{movie_id}")
        ])
    btn.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
    
    if image: await cq.message.reply_photo(image, caption=msg, reply_markup=InlineKeyboardMarkup(btn))
    else: await cq.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
    await cq.answer()

@Client.on_callback_query(filters.regex(r"^binged_post_(.+)$"))
async def binged_post(client, cq):
    if cq.from_user.id not in ADMIN_IDS: return await cq.answer("Unauthorized.", show_alert=True)
    
    movie_id = cq.data.split("_")[-1]
    movie_data = temp.BINGED_RESULTS.get(cq.from_user.id, {}).get(movie_id)
    if not movie_data: return await cq.answer("Data lost.", show_alert=True)
    
    status = temp.MOVIE_STATUS.get(movie_id, "released")
    title = clean_text(movie_data.get("post_title", "Unknown"))
    year = movie_data.get("release_year", "N/A")
    safe_title = format_search_title(title, year)
    
    if status == "upcoming":
        msg, image = build_upcoming_message(movie_data, temp.U_NAME, source='binged')
    else:
        msg, image = build_released_message(movie_data, temp.U_NAME, source='binged')
        
    final_image = image
    if movie_data.get('backdrop_url') and movie_data.get('poster_url'):
         try:
            await cq.answer("Generating image...", cache_time=0)
            is_upcoming = (status == "upcoming")
            r_date = unix_to_date(movie_data.get('release_date')) if is_upcoming else None
            
            final_image = await generate_status_image(
                movie_data['backdrop_url'], 
                movie_data['poster_url'], 
                movie_data.get('provider_logos', []), 
                title, year, 
                movie_data.get('rating', 'N/A'), 
                movie_data.get('genre_str', 'N/A'), 
                movie_data.get('post_content', 'No plot'),
                is_upcoming=is_upcoming,
                release_date=r_date
            )
         except Exception as e:
            print(f"Image Gen Error: {e}")
            
    btn = []
    if status == "upcoming":
        videos = movie_data.get("videos", [])
        if videos and videos[0].get("url"):
            btn.append([InlineKeyboardButton("🎬 Trailer", url=f"https://www.youtube.com/watch?v={videos[0]['url']}")])
        btn.append([InlineKeyboardButton("🔔 Notify when Released", callback_data=f"notify_release_{movie_id}")])
    else:
        btn.append([InlineKeyboardButton(f"{title} · {year}", url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}")])
        row = []
        videos = movie_data.get("videos", [])
        if videos and videos[0].get("url"):
            row.append(InlineKeyboardButton("🎬 Trailer", url=f"https://www.youtube.com/watch?v={videos[0]['url']}"))
        sims = get_similar_movies(movie_data, 1)
        if sims:
             st = clean_text(sims[0].get("title"))
             row.append(InlineKeyboardButton("🔄 More like this", url=f"https://t.me/{temp.U_NAME}?start=Search_{format_search_title(st, None)}"))
        if row: btn.append(row)
        
    try:
        method = client.send_photo if final_image else client.send_message
        kwargs = {'chat_id': UPDATE_CHANNEL_ID, 'caption' if final_image else 'text': msg, 'reply_markup': InlineKeyboardMarkup(btn)}
        if final_image: 
             if hasattr(final_image, 'seek'): final_image.seek(0)
             kwargs['photo'] = final_image
        else: kwargs['disable_web_page_preview'] = True
        
        await method(**kwargs)
        await cq.answer("✅ Posted.")
    except Exception as e:
        await cq.answer(f"Error: {e}", show_alert=True)

@Client.on_callback_query(filters.regex(r"^binged_edit_post_(.+)$"))
async def binged_edit_post_prompt(client, cq):
    movie_id = cq.data.split("_")[-1]
    temp.EDITING_POST[cq.from_user.id] = {"movie_id": movie_id, "source": "binged"}
    await cq.message.reply_text("✏️ Send custom Search keyword or URL.", quote=True)
    await cq.answer()

# Custom Filter to check if user is editing
async def is_editing_filter(_, __, message):
    try:
        return message.from_user.id in temp.EDITING_POST
    except:
        return False

editing_filter = filters.create(is_editing_filter)

@Client.on_message(filters.private & filters.text & filters.user(ADMIN_IDS) & editing_filter)
async def receive_custom_search(client, message):
    user_id = message.from_user.id
    if user_id not in temp.EDITING_POST: return
    
    data = temp.EDITING_POST.pop(user_id)
    movie_id = data["movie_id"]
    source = data["source"] # binged or imdb
    
    movie_data = (temp.BINGED_RESULTS if source == 'binged' else temp.TMDB_RESULTS).get(user_id, {}).get(movie_id)
    if not movie_data: return await message.reply("Session expired.")
    
    status = temp.MOVIE_STATUS.get(movie_id, "released")
    title = clean_text(movie_data.get("post_title", movie_data.get("title", "")))
    year = movie_data.get("release_year", movie_data.get("year", ""))
    
    if status == "upcoming":
        msg, image = build_upcoming_message(movie_data, temp.U_NAME, source=source)
    else:
        msg, image = build_released_message(movie_data, temp.U_NAME, source=source)
    
    final_image = image
    if source == 'binged' and movie_data.get('backdrop_url') and movie_data.get('poster_url'):
         try:
            is_upcoming = (status == "upcoming")
            r_date = unix_to_date(movie_data.get('release_date')) if is_upcoming else None
            final_image = await generate_status_image(
                movie_data['backdrop_url'], movie_data['poster_url'], [],
                title, year, movie_data.get('rating', 'N/A'), 
                movie_data.get('genre_str', 'N/A'), movie_data.get('post_content', ''),
                is_upcoming=is_upcoming, release_date=r_date
            )
         except: pass

    custom_input = message.text.strip()
    btn = []
    
    if status == "upcoming":
        if source == "binged":
             # Only trailer
             videos = movie_data.get("videos", [])
             if videos and videos[0].get("url"):
                 btn.append([InlineKeyboardButton("🎬 Trailer", url=f"https://www.youtube.com/watch?v={videos[0]['url']}")])
    else:
        # Released
        url = custom_input if custom_input.startswith("http") else f"https://t.me/{temp.U_NAME}?start=Search_{re.sub(r'[^a-zA-Z0-9]', '_', custom_input)}"
        btn.append([InlineKeyboardButton(f"{title} · {year}", url=url)])
        
        row = []
        if source == "binged":
             videos = movie_data.get("videos", [])
             if videos and videos[0].get("url"):
                 row.append(InlineKeyboardButton("🎬 Trailer", url=f"https://www.youtube.com/watch?v={videos[0]['url']}"))
             sims = get_similar_movies(movie_data, 1)
             if sims:
                 st = clean_text(sims[0].get("title"))
                 sst = format_search_title(st, None)
                 row.append(InlineKeyboardButton("🔄 More like this", url=f"https://t.me/{temp.U_NAME}?start=Search_{sst}"))
        if row: btn.append(row)

    try:
        method = client.send_photo if final_image else client.send_message
        kwargs = {'chat_id': UPDATE_CHANNEL_ID, 'caption' if final_image else 'text': msg, 'reply_markup': InlineKeyboardMarkup(btn)}
        if final_image: 
             if hasattr(final_image, 'seek'): final_image.seek(0)
             kwargs['photo'] = final_image
        else: kwargs['disable_web_page_preview'] = True
        
        await method(**kwargs)
        await message.reply("✅ Posted with custom button.")
    except Exception as e:
        await message.reply(f"Error: {e}")

@Client.on_callback_query(filters.regex(r"^close_message$"))
async def close_message_callback(client, cq):
    try: await cq.message.delete()
    except: pass

@Client.on_callback_query(filters.regex(r"^notify_release_(.+)$"))
async def notify_release_callback(client, cq):
    movie_id = cq.data.split("_")[-1]
    user_id = cq.from_user.id
    
    await db.add_movie_alert(user_id, movie_id)
    await cq.answer("✅ Notification set!", show_alert=True)
    
# --- IMDB Handlers preserved for compatibility ---

@Client.on_callback_query(filters.regex(r"^imdb_post_(.+)$"))
async def imdb_post(client, cq):
    if cq.from_user.id not in ADMIN_IDS: return await cq.answer("Unauthorized.", show_alert=True)
    tmdb_id = cq.data.replace("imdb_post_", "")
    movie_data = temp.TMDB_RESULTS.get(cq.from_user.id, {}).get(tmdb_id)
    if not movie_data: return await cq.answer("Data lost.", show_alert=True)
    
    status = temp.MOVIE_STATUS.get(tmdb_id, "released")
    title = clean_text(movie_data.get("title", ""))
    year = movie_data.get("year", "")
    safe_title = format_search_title(title, year)
    
    if status == "upcoming":
        msg, image = build_upcoming_message(movie_data, temp.U_NAME, source='imdb')
    else:
        msg, image = build_released_message(movie_data, temp.U_NAME, source='imdb')
        
    btn = []
    if status == "released":
        btn.append([InlineKeyboardButton(f"{title} · {year}", url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}")])
        sims = movie_data.get("similar", [])
        if sims:
             st = clean_text(sims[0].get("title"))
             sst = format_search_title(st, None)
             btn.append([InlineKeyboardButton("🔄 More like this", url=f"https://t.me/{temp.U_NAME}?start=Search_{sst}")])
             
    try:
        await client.send_photo(UPDATE_CHANNEL_ID, photo=image, caption=msg, reply_markup=InlineKeyboardMarkup(btn))
        await cq.answer("✅ Posted.")
    except Exception as e:
        await cq.answer(f"Error: {e}")

@Client.on_callback_query(filters.regex(r"^imdb_edit_post_(.+)$"))
async def imdb_edit_post_prompt(client, cq):
    movie_id = cq.data.replace("imdb_edit_post_", "")
    temp.EDITING_POST[cq.from_user.id] = {"movie_id": movie_id, "source": "imdb"}
    await cq.message.reply_text("✏️ Send custom Search keyword or URL.", quote=True)
    await cq.answer()