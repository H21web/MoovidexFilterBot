# --- Add to the top of binged.py (or appropriate module) ---

import os
import json
import time
import math
import string
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple

import requests
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

from utils import temp  # your existing temp store
from info import *      # must provide CHANNELS, TMDB_API_KEY (or from env), etc.

# Ensure HEADERS is valid (your snippet missed a closing brace)
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Referer': 'https://www.binged.com/',
}

BINGED_SEARCH_URL = "https://www.binged.com/wp-json/binged-api/v1/movies"
TMDB_API_KEY = os.getenv("TMDB_API_KEY", None) or (globals().get("TMDB_API_KEY") if "TMDB_API_KEY" in globals() else None)
TMDB_BASE = "https://api.themoviedb.org/3"

# Use the same update channel as your existing post (replace with your channel)
UPDATE_CHANNEL_ID = -1001680629032  # same as your "post to channel" in your code

# Parse CHANNELS (space-separated IDs/usernames)
def parse_channels(value: str) -> List[str]:
    if not value:
        return []
    return [x.strip() for x in value.split() if x.strip()]

WATCH_CHANNELS = parse_channels(globals().get("CHANNELS", ""))

# Persistent store to avoid duplicates across restarts.
# Key = normalized_title_year (e.g., "thalaivaa_2025"), Value = {"source":"binged|tmdb","ts": epoch}
DEDUP_FILE = "posted_movies.json"
if not os.path.exists(DEDUP_FILE):
    with open(DEDUP_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f)

def _load_dedup() -> Dict[str, Any]:
    try:
        with open(DEDUP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_dedup(data: Dict[str, Any]):
    tmp = f"{DEDUP_FILE}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DEDUP_FILE)

def _dedup_key(title: str, year: str) -> str:
    t = (title or "").strip().lower()
    t = "".join(ch for ch in t if ch in string.ascii_lowercase + string.digits + " _-")
    y = (str(year) if year else "").strip()
    return f"{t}_{y}"

# --- Utilities from your original code with improvements ---

def clean_text(text):
    if not isinstance(text, str):
        return ""
    import html as _html
    text = _html.unescape(text)
    replacements = {
        "\u2019": "'", "\u2018": "'",
        "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-",
        "\u2026": "..."
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.strip()

def extract_list(data, key, nested_key=None):
    items = data.get(key)
    if not isinstance(items, list):
        return []
    result = []
    for i in items:
        val = i.get(nested_key) if nested_key and isinstance(i, dict) else i
        val = clean_text(val)
        if val:
            result.append(val)
    return result

# Robust filename parser for titles and year
# example inputs:
#   Thalaivaa.2013.1080p.10bit.BluRay.DDP5.1.x265.HEVC-MRX.mkv -> ("Thalaivaa", 2013)
#   Avatar.The.Way.Of.Water.2025.IMAX.2160p.WEB-DL.mkv -> ("Avatar The Way Of Water", 2025)
#   The.Batman.2025.S01E02.1080p.WEB-DL.mkv -> ("The Batman", 2025) but is_series=True
YEAR_RE = re.compile(r'(?<!\d)(19\d{2}|20\d{2}|21\d{2})(?!\d)')
SXXEYY_RE = re.compile(r'(S\d{1,2}E\d{1,3})', re.IGNORECASE)

VIDEO_TAGS = {
    '1080p','2160p','720p','480p','576p','4k','web-dl','webrip','hdrip','bdrip','bluray','dvdrip',
    'x264','x265','hevc','h264','h265','10bit','8bit','hdr','dolbyvision','dv','ddp5.1','dts','truehd','atmos',
    'remux','imax','cam','hdtc','hdtcam','ts','tc','r6','r5','dvdscr','proper','repack','internal',
    'mkv','mp4','avi'
}

def _tokenize_filename(name: str) -> List[str]:
    # Normalize separators to spaces, keep alnum
    base = re.sub(r'[\._\-]+', ' ', name)
    base = re.sub(r'\s+', ' ', base).strip()
    tokens = base.split(' ')
    return tokens

def parse_title_year_from_filename(filename: str) -> Tuple[str, Optional[int], bool]:
    # Strip extension
    base = filename
    if '.' in base:
        # Remove extension only at the end
        base = re.sub(r'\.[A-Za-z0-9]{1,4}$', '', base)
    # Detect year
    year_match = YEAR_RE.search(base)
    year = int(year_match.group(1)) if year_match else None
    # Detect series marker
    is_series = SXXEYY_RE.search(base) is not None
    # Build title from tokens up to year token
    tokens = _tokenize_filename(base)
    title_tokens = []
    for tok in tokens:
        low = tok.lower()
        if YEAR_RE.fullmatch(tok):
            break
        # Stop at common quality tags after we have some title tokens
        if low in VIDEO_TAGS and title_tokens:
            break
        # skip pure quality tags before title discovered? allow first alpha tokens to accumulate
        if low in VIDEO_TAGS:
            continue
        # keep alnum-ish tokens
        if re.fullmatch(r"[A-Za-z0-9']+", tok):
            title_tokens.append(tok)
        else:
            # keep words with internal apostrophes or mixed case
            cleaned = re.sub(r"[^A-Za-z0-9']+", ' ', tok).strip()
            if cleaned:
                title_tokens.extend([w for w in cleaned.split(' ') if w])
    title = " ".join(title_tokens).strip()
    # Title case thoughtfully
    title = " ".join(w if w.isupper() else w.title() for w in title.split())
    return title, year, is_series

# --- Binged search (refined & robust) ---

def binged_search(query: str, timeout=12) -> List[Dict[str, Any]]:
    """
    Robust Binged search with:
      - cleaned query
      - retries for transient 403/5xx
      - paging support (mode=all handles most)
    Returns list of movie dicts (original API response entries).
    """
    q = query.strip()
    if not q:
        return []
    params = {"mode": "all", "search": q}
    attempts = 0
    backoff = 1.2
    while attempts < 3:
        attempts += 1
        try:
            resp = requests.get(BINGED_SEARCH_URL, headers=HEADERS, params=params, timeout=timeout)
            if resp.status_code == 403:
                # Adjust headers on retry to avoid caching blocks
                time.sleep(backoff)
                continue
            resp.raise_for_status()
            data = resp.json()
            results = data.get("data", []) if isinstance(data, dict) else []
            if isinstance(results, list):
                return results
            # sometimes returns dict with 'results'
            if isinstance(results, dict):
                inner = results.get("results", [])
                if isinstance(inner, list):
                    return inner
            return []
        except requests.RequestException:
            time.sleep(backoff)
            backoff *= 1.6
    return []

def refine_binged_pick(results: List[Dict[str, Any]], wanted_title: str, wanted_year: Optional[int]) -> Optional[Dict[str, Any]]:
    """
    Score and pick best match: prioritize exact year==wanted_year (if provided), then fuzzy title containment.
    """
    if not results:
        return None
    title_l = (wanted_title or "").strip().lower()
    best = None
    best_score = -1
    for r in results:
        r_title = clean_text(r.get("title") or "")
        r_title_l = r_title.lower()
        r_year = r.get("theatrical-year")
        # sometimes year is str/int or missing
        try:
            r_year_i = int(r_year) if r_year is not None else None
        except:
            r_year_i = None
        score = 0
        # title exact-ish
        if r_title_l == title_l:
            score += 50
        elif title_l and (title_l in r_title_l or r_title_l in title_l):
            score += 35
        # year match
        if wanted_year and r_year_i == wanted_year:
            score += 40
        # prefer movies over series if type provided
        r_type = (r.get("type") or "").lower()
        if r_type == "movie":
            score += 5
        # add minor bonus for popularity if available
        pop = r.get("popularity") or 0
        try:
            score += min(5, int(pop))
        except:
            pass
        if score > best_score:
            best_score = score
            best = r
    return best

# --- TMDB fallback ---

def tmdb_search_movie(title: str, year: Optional[int]) -> Optional[Dict[str, Any]]:
    if not TMDB_API_KEY:
        return None
    params = {"api_key": TMDB_API_KEY, "query": title, "include_adult": "true"}
    if year:
        params["year"] = year
    try:
        r = requests.get(f"{TMDB_BASE}/search/movie", params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        results = data.get("results") or []
        if not results:
            return None
        # pick best by year match then popularity
        best = None
        best_score = -1
        for it in results:
            score = 0
            r_year = None
            rel = it.get("release_date") or ""
            if rel and len(rel) >= 4:
                try:
                    r_year = int(rel[:4])
                except:
                    r_year = None
            if year and r_year == year:
                score += 50
            score += int((it.get("popularity") or 0))
            if score > best_score:
                best_score = score
                best = it
        return best
    except requests.RequestException:
        return None

def tmdb_movie_details(movie_id: int) -> Optional[Dict[str, Any]]:
    if not TMDB_API_KEY:
        return None
    params = {"api_key": TMDB_API_KEY, "append_to_response": "release_dates"}
    try:
        r = requests.get(f"{TMDB_BASE}/movie/{movie_id}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None

# --- Build message (reuse your function but make it resilient) ---

def build_binged_message(title, year, movie_type, lang, genres, platform, style, safe_title, bot_username):
    # safeguard style range
    if style not in (1,2,3,4,5):
        style = 1
    lang_tag = ", ".join(f"#{l.strip().title()}" for l in lang) if isinstance(lang, list) else f"#{str(lang).strip().title()}" if lang else "N/A"
    genre_str = ", ".join(genres) or "N/A"
    movie_url = f"https://t.me/{bot_username}?start=Search_{safe_title}"
    if style == 1:
        return (
            f"✅ **{title}** · ({year}) · `{movie_type}`\n\n"
            f"🉑 {lang_tag}\n"
            f"🎭 {genre_str} · 📺 {platform}\n\n"
            f"**@MooviDex**"
        )
    elif style == 2:
        return (
            f"🎬 **[{title}]({movie_url})**\n"
            f"`───────────────`\n"
            f"📆 {year} · `{movie_type}`\n\n"
            f"🗣️ Language: {lang_tag}\n"
            f"🎭 Genre: {genre_str}\n"
            f"📺 Platform: {platform}\n\n"
            f"📡 **@MooviDex**"
        )
    elif style == 3:
        return (
            f"✅ **[{title}]({movie_url})**\n"
            f"`({year} · {movie_type})`\n\n"
            f"{lang_tag} 🎭 {genre_str} · 📺 {platform}\n\n"
            f"**@MooviDex**"
        )
    elif style == 4:
        return (
            f"🎬 **[{title}]({movie_url})**\n"
            f"`({year} · {movie_type})`\n\n"
            f"🉑 Language: {lang_tag}\n"
            f"🎭 Genres: {genre_str}\n"
            f"📺 Streaming On: {platform}\n\n"
            f"📝 *A compelling drama series.*\n\n"
            f"📢 Powered by **@MooviDex**"
        )
    elif style == 5:
        return (
            f"✨ **[{title}]({movie_url})**\n"
            f"`({year} · {movie_type})`\n\n"
            f"{lang_tag} 🎭 {genre_str}\n"
            f"📺 {platform}\n\n"
            f"🔥 Only on **@MooviDex**"
        )
    # fallback
    return (
        f"✅ **[{title}]({movie_url})** · `({year}) · {movie_type}`\n\n"
        f"🉑 {lang_tag}\n"
        f"🎭 {genre_str} · 📺 {platform}\n"
        f"**@MooviDex**"
    )

def _safe_title_slug(title: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]', '_', title or "").strip('_') or "Search"

# --- Core: process a file message, fetch info, dedupe, and post ---

async def process_new_file_message(client: Client, message: Message):
    # Only consider documents/videos with filenames
    filename = None
    if message.document and message.document.file_name:
        filename = message.document.file_name
    elif message.video and message.video.file_name:
        filename = message.video.file_name
    elif message.audio and message.audio.file_name:
        filename = message.audio.file_name
    if not filename:
        return

    title, year, is_series = parse_title_year_from_filename(filename)

    # Only process movies from 2025
    if year != 2025:
        return

    # If series-like file, skip unless you want to extend to series logic
    # Requirement says: only search and update for movie from 2025 year
    # So skip if it looks like series
    if is_series:
        return

    # Title must be non-empty
    if not title:
        return

    # Deduplicate
    key = _dedup_key(title, str(year))
    dedup = _load_dedup()
    if key in dedup:
        return  # already posted

    # 1) Try Binged first
    results = binged_search(title)
    picked = refine_binged_pick(results, wanted_title=title, wanted_year=year)
    use_tmdb = False
    source_tag = "binged"

    if not picked:
        # 2) Fallback TMDB
        use_tmdb = True
        source_tag = "tmdb"

    # Build post data from Binged or TMDB
    if not use_tmdb:
        # Extract fields from Binged object
        b = picked
        movie_title = clean_text(b.get("title") or title)
        movie_year = b.get("theatrical-year") or year
        movie_type = clean_text(b.get("type") or "Movie")
        genres = extract_list(b, "genres")
        langs = extract_list(b, "languages") or ["Unknown"]
        platforms = extract_list(b, "platforms", "name")
        platform_str = platforms[0] if platforms else "N/A"
    else:
        # TMDB path
        tmdb_hit = tmdb_search_movie(title, year)
        if not tmdb_hit:
            return  # As a last resort, skip posting if nothing found
        details = tmdb_movie_details(tmdb_hit.get("id"))
        # Map TMDB to our fields
        movie_title = clean_text(details.get("title") or tmdb_hit.get("title") or title)
        rel = details.get("release_date") or tmdb_hit.get("release_date") or ""
        movie_year = rel[:4] if rel else year
        movie_type = "Movie"
        # genres
        tmdb_genres = details.get("genres") or []
        genres = [clean_text(g.get("name")) for g in tmdb_genres if g.get("name")]
        # languages - use spoken_languages or original_language
        langs_data = details.get("spoken_languages") or []
        langs = [clean_text(x.get("english_name") or x.get("name") or "") for x in langs_data if (x.get("english_name") or x.get("name"))]
        if not langs:
            ol = details.get("original_language") or tmdb_hit.get("original_language")
            langs = [ol.upper()] if ol else ["Unknown"]
        # platform unknown from TMDB
        platform_str = "N/A"

    # Compose message with your existing style setting per admin (fallback to style 1)
    # Since this is auto, no direct admin context; pick a default style, e.g., 1 or use a global
    style = 1
    safe_title = _safe_title_slug(movie_title)
    bot_username = temp.U_NAME  # you already use this

    msg = build_binged_message(
        movie_title,
        movie_year,
        movie_type,
        langs if langs else ["Unknown"],
        genres or [],
        platform_str,
        style,
        safe_title,
        bot_username
    )

    # Post to update channel (same behavior as your "post to channel")
    try:
        await client.send_message(
            chat_id=UPDATE_CHANNEL_ID,
            text=msg,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Click to Search", url=f"https://t.me/{bot_username}?start=Search_{safe_title}")]
            ]),
            disable_web_page_preview=True
        )
        # Save dedupe
        dedup[key] = {"source": source_tag, "ts": int(time.time())}
        _save_dedup(dedup)
    except Exception as e:
        # Optionally log error
        logging.exception(f"Failed to post update: {e}")

# --- Listener for DB Channels: auto-trigger on new media ---

def _channel_filter():
    # Build a dynamic filter for multiple channels
    ids = []
    usernames = []
    for ch in WATCH_CHANNELS:
        if not ch:
            continue
        try:
            if str(ch).startswith("-100") or str(ch).isdigit():
                ids.append(int(ch))
            else:
                usernames.append(ch)
        except:
            usernames.append(ch)
    # Allow both IDs and usernames; we'll check at runtime
    def _pred(_, __, msg: Message):
        chat = msg.chat
        if not chat:
            return False
        cid = chat.id
        uname = (chat.username or "").lower()
        if cid in ids:
            return True
        if uname and uname in set(u.lower() for u in usernames):
            return True
        return False
    return filters.create(_pred)

MEDIA_FILTER = (filters.document | filters.video | filters.audio)

@Client.on_message(MEDIA_FILTER & _channel_filter())
async def auto_update_on_new_file(client, message: Message):
    # Fire-and-forget worker
    asyncio.create_task(process_new_file_message(client, message))

# --- Optional: Admin command to clear or query dedupe ---

@Client.on_message(filters.command("posted_info") & filters.user(ADMIN_IDS))
async def cmd_posted_info(client, message):
    data = _load_dedup()
    await message.reply_text(f"Posted entries: {len(data)}")

@Client.on_message(filters.command("clear_posted") & filters.user(ADMIN_IDS))
async def cmd_clear_posted(client, message):
    _save_dedup({})
    await message.reply_text("Cleared posted dedupe store.")
