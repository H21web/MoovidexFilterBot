# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import logging, asyncio, os, re, random, pytz, aiohttp, string
from info import *

from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram import enums
from urllib.parse import quote_plus
from pyrogram.errors import *
from typing import Union, Tuple, Optional
from Script import script
from datetime import datetime, date
from typing import List
from database.users_chats_db import db
from database.join_reqs import JoinReqs
from bs4 import BeautifulSoup
from shortzy import Shortzy

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
join_db = JoinReqs
BTN_URL_REGEX = re.compile(r"(\[([^\[]+?)\]\((buttonurl|buttonalert):(?:/{0,2})(.+?)(:same)?\))")

#imdb = Cinemagoer() 
TOKENS = {}
VERIFIED = {}
BANNED = {}
SECOND_SHORTENER = {}
SMART_OPEN = '“'
SMART_CLOSE = '”'
START_CHAR = ('\'', '"', SMART_OPEN)
IMDB_CACHE = {}
IMDB_CACHE_MAX = 500  # bound the process-local cache; oldest entries evicted


def _imdb_cache_set(key, value):
    if key not in IMDB_CACHE and len(IMDB_CACHE) >= IMDB_CACHE_MAX:
        IMDB_CACHE.pop(next(iter(IMDB_CACHE)))
    IMDB_CACHE[key] = value


_http_session = None


async def _get_http_session():
    """Shared aiohttp session for IMDb lookups (created lazily, reused)."""
    global _http_session
    if _http_session is None or _http_session.closed:
        timeout = aiohttp.ClientTimeout(total=4)
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
        _http_session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
        )
    return _http_session


async def close_http_session():
    """Close the shared HTTP session; called on bot shutdown."""
    global _http_session
    if _http_session is not None and not _http_session.closed:
        await _http_session.close()
        _http_session = None

# temp db for banned 
class temp(object):
    BANNED_USERS = []
    BANNED_CHATS = []
    ME = None
    BOT = None
    try:
        CURRENT = int(os.environ.get("SKIP", 2))
    except (TypeError, ValueError):
        CURRENT = 2
    CANCEL = False
    MELCOW = {}
    U_NAME = None
    B_NAME = None
    GETALL = {}
    SHORT = {}
    SETTINGS = {}
    IMDB_CAP = {}
    FILTERED = {}
    BACK_CB = {}


async def pub_is_subscribed(bot, query, channel):
    btn = []
    for channel_id in channel:
        chat = await bot.get_chat(int(channel_id))
        try:
            await bot.get_chat_member(channel_id, query.from_user.id)
        except UserNotParticipant:
            btn.append(
                [InlineKeyboardButton(f'Join {chat.title}', url=chat.invite_link)]
            )
        except Exception as e:
            logger.exception("pub_is_subscribed failed for channel %s", channel_id)
    return btn

async def is_subscribed(bot, query):
    if REQUEST_TO_JOIN_MODE == True and join_db().isActive():
        try:
            user = await join_db().get_user(query.from_user.id)
            if user and user["user_id"] == query.from_user.id:
                return True
            else:
                try:
                    user_data = await bot.get_chat_member(AUTH_CHANNEL, query.from_user.id)
                except UserNotParticipant:
                    pass
                except Exception as e:
                    logger.exception(e)
                else:
                    if user_data.status != enums.ChatMemberStatus.BANNED:
                        return True
        except Exception as e:
            logger.exception(e)
            return False
    else:
        try:
            user = await bot.get_chat_member(AUTH_CHANNEL, query.from_user.id)
        except UserNotParticipant:
            pass
        except Exception as e:
            logger.exception(e)
        else:
            if user.status != enums.ChatMemberStatus.BANNED:
                return True
        return False



def format_runtime(runtime_str=None, seconds=None):
    """Format runtime from ISO string or seconds."""
    try:
        if runtime_str and isinstance(runtime_str, str):
            m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", runtime_str.strip())
            if m:
                h = int(m.group(1)) if m.group(1) else 0
                m_ = int(m.group(2)) if m.group(2) else 0
                if h or m_:
                    return f"{h}hr {m_}min"
        
        if seconds and isinstance(seconds, (int, float)):
            total_seconds = int(seconds)
            h, remainder = divmod(total_seconds, 3600)
            m_ = remainder // 60
            if h or m_:
                return f"{h}hr {m_}min"
    except Exception:
        pass
    return None

async def lookup_imdb_id(title):
    """Lookup IMDb ID with proper URL encoding for special characters."""
    if not title or not isinstance(title, str):
        return None
    
    title = title.lower().strip()
    if not title:
        return None
    
    # Check cache first
    if title in IMDB_CACHE:
        return IMDB_CACHE[title]

    # Proper URL encoding for special characters
    encoded_title = quote_plus(title)
    api_url = f"https://imdblinkz.s1mallufiles.workers.dev/?q={encoded_title}"

    try:
        session = await _get_http_session()
        async with session.get(api_url) as response:
            if response.status != 200:
                return None

            data = await response.json()

            if not isinstance(data, dict):
                return None

            results = data.get("results", [])
            if not isinstance(results, list):
                return None

            # Try to find exact match first, then partial match
            for result in results:
                if isinstance(result, dict) and result.get("type") == "title":
                    result_title = result.get("title", "").lower()
                    imdb_id = result.get("id")

                    if imdb_id and isinstance(imdb_id, str):
                        # Cache and return first valid result
                        _imdb_cache_set(title, imdb_id)
                        return imdb_id

    except asyncio.TimeoutError:
        logger.warning(f"Timeout looking up: {title}")
    except Exception as e:
        logger.warning(f"Lookup failed for {title}: {str(e)[:100]}")

    return None

async def fetch_json(imdb_id):
    """Fetch movie data with connection pooling."""
    if not imdb_id or not isinstance(imdb_id, str):
        return None
    
    url = f"https://imdb.iamidiotareyoutoo.com/search?tt={imdb_id}"

    try:
        session = await _get_http_session()
        async with session.get(url) as response:
            if response.status != 200:
                return None

            data = await response.json()
            return data if isinstance(data, dict) else None

    except asyncio.TimeoutError:
        logger.warning(f"Timeout fetching: {imdb_id}")
    except Exception as e:
        logger.warning(f"Fetch failed for {imdb_id}: {str(e)[:100]}")

    return None

def safe_get(data, *keys, default=None):
    """Safely navigate nested dictionaries."""
    try:
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            elif isinstance(current, list) and isinstance(key, int) and 0 <= key < len(current):
                current = current[key]
            else:
                return default
        return current if current is not None else default
    except (KeyError, IndexError, TypeError):
        return default

def extract_names(data, key="name"):
    """Extract names from list with better error handling."""
    if not isinstance(data, list):
        return []
    
    names = []
    for item in data:
        try:
            if isinstance(item, dict):
                name = item.get(key)
                if name and isinstance(name, str) and name.strip():
                    names.append(name.strip())
        except Exception:
            continue
    return names

def extract_character_info(cast_data):
    """Extract cast with character information."""
    if not isinstance(cast_data, list):
        return []
    
    cast_info = []
    for actor in cast_data:
        try:
            if isinstance(actor, dict):
                actor_name = actor.get("name", "").strip()
                if actor_name:
                    # Try to get character name
                    character = None
                    if "character" in actor:
                        char_data = actor["character"]
                        if isinstance(char_data, str):
                            character = char_data.strip()
                        elif isinstance(char_data, dict):
                            character = char_data.get("name", "").strip()
                    
                    # Format: "Actor Name (as Character)" or just "Actor Name"
                    if character:
                        cast_info.append(f"{actor_name} (as {character})")
                    else:
                        cast_info.append(actor_name)
        except Exception:
            continue
    
    return cast_info

async def _get_poster_internal(query, bulk=False, id=False, file=None):
    """Internal function for get_poster without timeout wrapper."""
    if not query or not isinstance(query, str):
        return None
    
    try:
        # Get IMDb ID
        imdb_id = query.strip() if id else await lookup_imdb_id(query)
        if not imdb_id:
            return None

        # Fetch movie data
        data = await fetch_json(imdb_id)
        if not data or not data.get("ok"):
            return None

        # Extract data safely
        short = safe_get(data, "short", default={})
        main = safe_get(data, "main", default={})
        
        if not short and not main:
            return None

        # Basic info
        title = safe_get(short, "name")
        if not title:
            return None

        # Rating info
        rating_info = safe_get(short, "aggregateRating", default={})
        votes = safe_get(rating_info, "ratingCount")
        rating_val = safe_get(rating_info, "ratingValue")
        rating = f"{rating_val}/10" if rating_val is not None else None

        # Release info
        release = safe_get(main, "releaseDate", default={})
        release_year = safe_get(main, "releaseYear", "year") or safe_get(release, "year")
        
        release_date = None
        try:
            y, m, d = safe_get(release, "year"), safe_get(release, "month"), safe_get(release, "day")
            if all(isinstance(x, int) for x in [y, m, d]):
                release_date = f"{d:02d}-{m:02d}-{y}"
        except Exception:
            pass

        # Runtime
        duration_iso = safe_get(short, "duration")
        runtime_sec = safe_get(main, "runtime", "seconds")
        runtime = format_runtime(duration_iso, runtime_sec)

        # Extract cast with character information
        cast_data = safe_get(short, "actor", default=[])
        cast_with_chars = extract_character_info(cast_data)
        
        # Fallback to simple names if character extraction fails
        if not cast_with_chars:
            cast_with_chars = extract_names(cast_data)

        # Other lists
        akas = []
        aka_edges = safe_get(main, "akas", "edges", default=[])
        for aka in aka_edges:
            aka_text = safe_get(aka, "text") or safe_get(aka, "title")
            if aka_text and isinstance(aka_text, str):
                akas.append(aka_text.strip())

        countries = []
        country_data = safe_get(main, "countriesDetails", "countries", default=[])
        for country in country_data:
            country_text = safe_get(country, "text")
            if country_text and isinstance(country_text, str):
                countries.append(country_text.strip())

        # Certificates
        certificates = []
        cert = safe_get(main, "certificate")
        if cert and isinstance(cert, str):
            certificates = [cert.strip()]

        # Languages
        languages = []
        lang_data = safe_get(main, "spokenLanguages", "spokenLanguages", default=[])
        for lang in lang_data:
            lang_text = safe_get(lang, "text")
            if lang_text and isinstance(lang_text, str):
                languages.append(lang_text.strip())

        # Crew
        directors = extract_names(safe_get(short, "director", default=[]))
        writers = extract_names(safe_get(main, "writer", default=[]))
        producers = extract_names(safe_get(main, "producer", default=[]))
        composers = extract_names(safe_get(main, "composer", default=[]))
        cinematogs = extract_names(safe_get(main, "cinematographer", default=[]))
        music_team = extract_names(safe_get(main, "musicDepartment", default=[]))
        distributors = extract_names(safe_get(main, "distributors", default=[]))

        # Build result
        movie = {
            'title': title,
            'votes': votes,
            "aka": list_to_str(akas),
            "seasons": safe_get(main, "series", "numberOfSeasons"),
            "box_office": safe_get(main, "lifetimeGross"),
            'localized_title': safe_get(short, "alternateNames", 0) if isinstance(safe_get(short, "alternateNames"), list) else None,
            'kind': safe_get(short, "@type", default="").capitalize(),
            "imdb_id": imdb_id,
            "cast": list_to_str(cast_with_chars),
            "runtime": runtime,
            "countries": list_to_str(countries),
            "certificates": list_to_str(certificates),
            "languages": list_to_str(languages),
            "director": list_to_str(directors),
            "writer": list_to_str(writers),
            "producer": list_to_str(producers),
            "composer": list_to_str(composers),
            "cinematographer": list_to_str(cinematogs),
            "music_team": list_to_str(music_team),
            "distributors": list_to_str(distributors),
            'release_date': release_date,
            'year': release_year,
            'genres': list_to_str(safe_get(short, "genre")),
            'poster': safe_get(short, "image"),
            'plot': safe_get(short, "description"),
            'rating': rating,
            'url': safe_get(short, "url") or f'https://www.imdb.com/title/{imdb_id}'
        }

        return movie

    except Exception as e:
        logger.error(f"Error in _get_poster_internal for '{query}': {str(e)[:100]}")
        return None

async def get_poster(query, bulk=False, id=False, file=None):
    """Get movie details with 6-second max load time and better character handling."""
    try:
        # Use asyncio.wait_for for timeout (compatible with all Python versions)
        result = await asyncio.wait_for(_get_poster_internal(query, bulk, id, file), timeout=6.0)
        return result
    except asyncio.TimeoutError:
        logger.warning(f"Overall timeout for query: {query}")
        return None
    except Exception as e:
        logger.error(f"Error in get_poster for '{query}': {str(e)[:100]}")
        return None

# Maximum FloodWait sleeps before giving up on one recipient (iterative retry;
# the old code recursed with no bound and could hit RecursionError).
_MAX_FLOOD_RETRIES = 5


async def _sleep_floodwait(e, attempt, target):
    if attempt >= _MAX_FLOOD_RETRIES:
        logging.warning("Giving up on broadcast to %s after %s FloodWaits", target, attempt)
        return False
    await asyncio.sleep(e.value)
    return True


async def broadcast_messages(user_id, message):
    attempt = 0
    while True:
        try:
            await message.copy(chat_id=user_id)
            return True, "Success"
        except FloodWait as e:
            attempt += 1
            if not await _sleep_floodwait(e, attempt, user_id):
                return False, "Error"
        except InputUserDeactivated:
            await db.delete_user(int(user_id))
            logging.info(f"{user_id}-Removed from Database, since deleted account.")
            return False, "Deleted"
        except UserIsBlocked:
            await db.delete_user(int(user_id))
            logging.info(f"{user_id} -Blocked the bot.")
            return False, "Blocked"
        except PeerIdInvalid:
            await db.delete_user(int(user_id))
            logging.info(f"{user_id} - PeerIdInvalid")
            return False, "Error"
        except Exception:
            logging.exception("broadcast_messages failed for %s", user_id)
            return False, "Error"

async def broadcast_messages_group(chat_id, message):
    attempt = 0
    while True:
        try:
            kd = await message.copy(chat_id=chat_id)
            try:
                await kd.pin()
            except Exception as e:
                logger.debug("Could not pin broadcast in %s: %s", chat_id, e)
            return True, "Success"
        except FloodWait as e:
            attempt += 1
            if not await _sleep_floodwait(e, attempt, chat_id):
                return False, "Error"
        except Exception:
            logging.exception("broadcast_messages_group failed for %s", chat_id)
            return False, "Error"
    

async def search_gagala(text):
    # Blocking requests.get() in async code stalled the whole event loop;
    # use the shared aiohttp session instead.
    text = quote_plus(text)
    url = f'https://imdb.iamidiotareyoutoo.com/search?q={text}'

    session = await _get_http_session()
    async with session.get(url) as response:
        response.raise_for_status()
        data = await response.json()

    # Extract title and year from the response and assign to the 'titles' variable
    titles = [f"{item['#TITLE']} ({item['#YEAR']})" for item in data.get("description", [])]

    return titles
    
async def get_settings(group_id):
    settings = await db.get_settings(group_id)
    return settings
    
async def save_group_settings(group_id, key, value):
    current = await get_settings(group_id)
    current.update({key: value})
    await db.update_settings(group_id, current)
    
def get_size(size):
    if size is None:
        return ""
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units):
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])

def split_list(l, n):
    for i in range(0, len(l), n):
        yield l[i:i + n]  

def get_file_id(msg: Message):
    if msg.media:
        for message_type in (
            "photo",
            "animation",
            "audio",
            "document",
            "video",
            "video_note",
            "voice",
            "sticker"
        ):
            obj = getattr(msg, message_type)
            if obj:
                setattr(obj, "message_type", message_type)
                return obj

def extract_user(message: Message) -> Tuple[int, Optional[str]]:
    user_id = None
    user_first_name = None
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_first_name = message.reply_to_message.from_user.first_name

    elif len(message.command) > 1:
        if (
            len(message.entities) > 1 and
            message.entities[1].type == enums.MessageEntityType.TEXT_MENTION
        ):
           
            required_entity = message.entities[1]
            user_id = required_entity.user.id
            user_first_name = required_entity.user.first_name
        else:
            user_id = message.command[1]
            # don't want to make a request -_-
            user_first_name = user_id
        try:
            user_id = int(user_id)
        except ValueError:
            pass
    else:
        user_id = message.from_user.id
        user_first_name = message.from_user.first_name
    return (user_id, user_first_name)

def list_to_str(k):
    """Format an IMDb list field for display. Empty -> "N/A" (as deployed);
    plain strings are returned as-is instead of being split into characters;
    lists are comma-joined with no trailing comma, honoring MAX_LIST_ELM."""
    if not k:
        return "N/A"
    if isinstance(k, str):
        return k.strip() or "N/A"
    items = [str(elem).strip() for elem in k if str(elem).strip()]
    if not items:
        return "N/A"
    if MAX_LIST_ELM:
        try:
            items = items[:int(MAX_LIST_ELM)]
        except (TypeError, ValueError):
            pass
    return ", ".join(items)

def last_online(from_user):
    time = ""
    if from_user.is_bot:
        time += "🤖 Bot :("
    elif from_user.status == enums.UserStatus.RECENTLY:
        time += "Recently"
    elif from_user.status == enums.UserStatus.LAST_WEEK:
        time += "Within the last week"
    elif from_user.status == enums.UserStatus.LAST_MONTH:
        time += "Within the last month"
    elif from_user.status == enums.UserStatus.LONG_AGO:
        time += "A long time ago :("
    elif from_user.status == enums.UserStatus.ONLINE:
        time += "Currently Online"
    elif from_user.status == enums.UserStatus.OFFLINE:
        time += from_user.last_online_date.strftime("%a, %d %b %Y, %H:%M:%S")
    return time

def split_quotes(text: str) -> List:
    if not any(text.startswith(char) for char in START_CHAR):
        return text.split(None, 1)
    counter = 1  # ignore first char -> is some kind of quote
    while counter < len(text):
        if text[counter] == "\\":
            counter += 1
        elif text[counter] == text[0] or (text[0] == SMART_OPEN and text[counter] == SMART_CLOSE):
            break
        counter += 1
    else:
        return text.split(None, 1)

    # 1 to avoid starting quote, and counter is exclusive so avoids ending
    key = remove_escapes(text[1:counter].strip())
    # index will be in range, or `else` would have been executed and returned
    rest = text[counter + 1:].strip()
    if not key:
        key = text[0] + text[0]
    return list(filter(None, [key, rest]))

def _button_parser(text, keyword, alert_prefix):
    if "buttonalert" in text:
        text = (text.replace("\n", "\\n").replace("\t", "\\t"))
    buttons = []
    note_data = ""
    prev = 0
    i = 0
    alerts = []
    for match in BTN_URL_REGEX.finditer(text):
        # Check if btnurl is escaped
        n_escapes = 0
        to_check = match.start(1) - 1
        while to_check > 0 and text[to_check] == "\\":
            n_escapes += 1
            to_check -= 1

        # if even, not escaped -> create button
        if n_escapes % 2 == 0:
            note_data += text[prev:match.start(1)]
            prev = match.end(1)
            if match.group(3) == "buttonalert":
                # create a thruple with button label, url, and newline status
                if bool(match.group(5)) and buttons:
                    buttons[-1].append(InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"{alert_prefix}:{i}:{keyword}"
                    ))
                else:
                    buttons.append([InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"{alert_prefix}:{i}:{keyword}"
                    )])
                i += 1
                alerts.append(match.group(4))
            elif bool(match.group(5)) and buttons:
                buttons[-1].append(InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(4).replace(" ", "")
                ))
            else:
                buttons.append([InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(4).replace(" ", "")
                )])

        else:
            note_data += text[prev:to_check]
            prev = match.start(1) - 1
    else:
        note_data += text[prev:]

    return note_data, buttons, alerts


def parser(text, keyword):
    """Parse filter text buttons; alert buttons use the "alertmessage" prefix."""
    return _button_parser(text, keyword, "alertmessage")


def gfilterparser(text, keyword):
    """Parse global-filter text buttons; alert buttons use the "gfilteralert" prefix."""
    return _button_parser(text, keyword, "gfilteralert")


def remove_escapes(text: str) -> str:
    res = ""
    is_escaped = False
    for counter in range(len(text)):
        if is_escaped:
            res += text[counter]
            is_escaped = False
        elif text[counter] == "\\":
            is_escaped = True
        else:
            res += text[counter]
    return res

def humanbytes(size):
    if not size:
        return ""
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'



async def _shorten_link(link, url, api):
    """Shorten one link via the shareus easy API or any shortzy-compatible site.

    A fresh session is used per call because shorteners are called rarely
    (per file/link), unlike the hot IMDb lookup path.
    """
    if url == "api.shareus.io":
        api_url = f'https://{url}/easy_api'
        params = {"key": api, "link": link}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, params=params, raise_for_status=True) as response:
                    return await response.text()
        except Exception as e:
            logger.error(e)
            return link
    shortzy = Shortzy(api_key=api, base_site=url)
    return await shortzy.convert(link)


async def get_clone_shortlink(link, url, api):
    return await _shorten_link(link, url, api)
                           
async def get_shortlink(chat_id, link):
    settings = await get_settings(chat_id) #fetching settings for group
    if 'shortlink' in settings.keys():
        URL = settings['shortlink']
        API = settings['shortlink_api']
    else:
        URL = SHORTLINK_URL
        API = SHORTLINK_API
    if URL.startswith("shorturllink") or URL.startswith("terabox.in") or URL.startswith("urlshorten.in"):
        URL = SHORTLINK_URL
        API = SHORTLINK_API
    return await _shorten_link(link, URL, API)

async def get_tutorial(chat_id):
    settings = await get_settings(chat_id) #fetching settings for group
    return settings['tutorial']
        
async def get_verify_shorted_link(link, url, api):
    return await _shorten_link(link, url, api)

async def check_token(bot, userid, token):
    user = await bot.get_users(userid)
    if not await db.is_user_exist(user.id):
        await db.add_user(user.id, user.first_name)
        await bot.send_message(LOG_CHANNEL, script.LOG_TEXT_P.format(user.id, user.mention))
    if user.id in TOKENS.keys():
        TKN = TOKENS[user.id]
        if token in TKN.keys():
            is_used = TKN[token]
            if is_used == True:
                return False
            else:
                return True
    else:
        return False

async def get_token(bot, userid, link):
    user = await bot.get_users(userid)
    if not await db.is_user_exist(user.id):
        await db.add_user(user.id, user.first_name)
        await bot.send_message(LOG_CHANNEL, script.LOG_TEXT_P.format(user.id, user.mention))
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=7))
    TOKENS[user.id] = {token: False}
    link = f"{link}verify-{user.id}-{token}"
    shortened_verify_url = await get_verify_shorted_link(link, VERIFY_SHORTLINK_URL, VERIFY_SHORTLINK_API)
    if VERIFY_SECOND_SHORTNER == True:
        snd_link = await get_verify_shorted_link(shortened_verify_url, VERIFY_SND_SHORTLINK_URL, VERIFY_SND_SHORTLINK_API)
        return str(snd_link)
    else:
        return str(shortened_verify_url)

async def verify_user(bot, userid, token):
    user = await bot.get_users(userid)
    if not await db.is_user_exist(user.id):
        await db.add_user(user.id, user.first_name)
        await bot.send_message(LOG_CHANNEL, script.LOG_TEXT_P.format(user.id, user.mention))
    TOKENS[user.id] = {token: True}
    tz = pytz.timezone('Asia/Kolkata')
    today = date.today()
    VERIFIED[user.id] = str(today)

async def check_verification(bot, userid):
    user = await bot.get_users(userid)
    if not await db.is_user_exist(user.id):
        await db.add_user(user.id, user.first_name)
        await bot.send_message(LOG_CHANNEL, script.LOG_TEXT_P.format(user.id, user.mention))
    today = date.today()
    if user.id in VERIFIED.keys():
        EXP = VERIFIED[user.id]
        try:
            years, month, day = EXP.split('-')
            comp = date(int(years), int(month), int(day))
        except (ValueError, TypeError, AttributeError):
            logger.warning("Dropping malformed verification date for user %s: %r", user.id, EXP)
            VERIFIED.pop(user.id, None)
            return False
        if comp < today:
            return False
        else:
            return True
    else:
        return False
    
async def _send_with_floodwait(send_coro_factory, max_retries=5):
    """Await ``send_coro_factory()`` (a zero-arg callable returning a coroutine),
    sleeping through FloodWait instead of aborting the whole batch."""
    for attempt in range(max_retries + 1):
        try:
            return await send_coro_factory()
        except FloodWait as e:
            if attempt >= max_retries:
                raise
            await asyncio.sleep(e.value)


async def send_all(bot, userid, files, ident, chat_id, user_name, query):
    settings = await get_settings(chat_id)
    if 'is_shortlink' in settings.keys():
        ENABLE_SHORTLINK = settings['is_shortlink']
    else:
        await save_group_settings(chat_id, 'is_shortlink', False)
        ENABLE_SHORTLINK = False
    # Premium users always get the files directly; shortlinks are only for
    # non-premium users when both the group setting and global mode are on.
    # (Previously premium users received nothing at all in shortlink mode.)
    has_premium = await db.has_premium_access(userid)
    use_shortlink = bool(ENABLE_SHORTLINK and SHORTLINK_MODE and not has_premium)
    try:
        for file in files:
            title = file["file_name"]
            size = get_size(file["file_size"])
            if use_shortlink:
                short_url = await get_shortlink(chat_id, f"https://telegram.me/{temp.U_NAME}?start=files_{file['file_id']}")
                text = (f"<b>Hᴇʏ ᴛʜᴇʀᴇ {user_name} 👋🏽 \n\n✅ Sᴇᴄᴜʀᴇ ʟɪɴᴋ ᴛᴏ ʏᴏᴜʀ ғɪʟᴇ ʜᴀs sᴜᴄᴄᴇssғᴜʟʟʏ ʙᴇᴇɴ ɢᴇɴᴇʀᴀᴛᴇᴅ ᴘʟᴇᴀsᴇ ᴄʟɪᴄᴋ ᴅᴏᴡɴʟᴏᴀᴅ ʙᴜᴛᴛᴏɴ\n\n🗃️ Fɪʟᴇ Nᴀᴍᴇ : {title}\n🔖 Fɪʟᴇ Sɪᴢᴇ : {size}</b>")
                markup = InlineKeyboardMarkup([[InlineKeyboardButton("📤 Dᴏᴡɴʟᴏᴀᴅ 📥", url=short_url)]])
                await _send_with_floodwait(lambda: bot.send_message(chat_id=userid, text=text, reply_markup=markup))
                continue
            f_caption = file["caption"]
            if CUSTOM_FILE_CAPTION:
                try:
                    f_caption = CUSTOM_FILE_CAPTION.format(
                        file_name='' if title is None else title,
                        file_size='' if size is None else size,
                        file_caption='' if f_caption is None else f_caption
                    )
                except Exception:
                    logger.exception("CUSTOM_FILE_CAPTION format failed")
                    # fall through with the raw caption
            if f_caption is None:
                f_caption = f"{title}"
            markup = InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton('Sᴜᴘᴘᴏʀᴛ Gʀᴏᴜᴘ', url=GRP_LNK),
                    InlineKeyboardButton('Uᴘᴅᴀᴛᴇs Cʜᴀɴɴᴇʟ', url=CHNL_LNK)
                ],[
                    InlineKeyboardButton("Bᴏᴛ Oᴡɴᴇʀ", url=OWNER_LNK)
                ]]
            )
            await _send_with_floodwait(lambda: bot.send_cached_media(
                chat_id=userid,
                file_id=file["file_id"],
                caption=f_caption,
                protect_content=True if ident == "filep" else False,
                reply_markup=markup
            ))
    except UserIsBlocked:
        await query.answer('Uɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ ᴍᴀʜɴ !', show_alert=True)
    except PeerIdInvalid:
        await query.answer('Hᴇʏ, Sᴛᴀʀᴛ Bᴏᴛ Fɪʀsᴛ Aɴᴅ Cʟɪᴄᴋ Sᴇɴᴅ Aʟʟ', show_alert=True)
    except Exception:
        logger.exception("send_all failed for user %s", userid)
        await query.answer('Hᴇʏ, Sᴛᴀʀᴛ Bᴏᴛ Fɪʀsᴛ Aɴᴅ Cʟɪᴄᴋ Sᴇɴᴅ Aʟʟ', show_alert=True)


async def get_cap(settings, remaining_seconds, files, query, total_results, search):
    if settings["imdb"]:
        IMDB_CAP = temp.IMDB_CAP.get(query.from_user.id)
        if IMDB_CAP:
            cap = IMDB_CAP
            for file in files:
                cap += f"<b>📁 <a href='https://telegram.me/{temp.U_NAME}?start=files_{file['file_id']}'>[{get_size(file['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file['file_name'].split()))}\n\n</a></b>"

        else:
            imdb = await get_poster(search, file=(files[0])["file_name"]) if settings["imdb"] else None
            if imdb:
                TEMPLATE = script.IMDB_TEMPLATE_TXT
                cap = TEMPLATE.format(
                    qurey=search,
                    title=imdb['title'],
                    votes=imdb['votes'],
                    aka=imdb["aka"],
                    seasons=imdb["seasons"],
                    box_office=imdb['box_office'],
                    localized_title=imdb['localized_title'],
                    kind=imdb['kind'],
                    imdb_id=imdb["imdb_id"],
                    cast=imdb["cast"],
                    runtime=imdb["runtime"],
                    countries=imdb["countries"],
                    certificates=imdb["certificates"],
                    languages=imdb["languages"],
                    director=imdb["director"],
                    writer=imdb["writer"],
                    producer=imdb["producer"],
                    composer=imdb["composer"],
                    cinematographer=imdb["cinematographer"],
                    music_team=imdb["music_team"],
                    distributors=imdb["distributors"],
                    release_date=imdb['release_date'],
                    year=imdb['year'],
                    genres=imdb['genres'],
                    poster=imdb['poster'],
                    plot=imdb['plot'],
                    rating=imdb['rating'],
                    url=imdb['url'],
                    # `message` kept for custom templates that still use
                    # {message.from_user.mention}; the default template uses {query...}.
                    message=query,
                    **locals()
                )
              #  cap+="<b>\n\n<u>🍿 Your Movie Files 👇</u></b>\n\n"
                for file in files:
                    cap += f"<b>📁 <a href='https://telegram.me/{temp.U_NAME}?start=files_{file['file_id']}'>[{get_size(file['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file['file_name'].split()))}\n\n</a></b>"

            else:
                cap = f"<b>𝖱𝖾𝗌𝗎𝗅𝗍  𝖥𝗈𝗎𝗇𝖽 𝖥𝗈𝗋 {search}\n\n🧑‍💻 𝖱𝖾𝗊𝗎𝖾𝗌𝗍𝖾𝖽 𝖡𝗒  : {query.from_user.mention}\n⏰ 𝖱𝖾𝗌𝗎𝗅𝗍 𝖲𝗁𝗈𝗐𝗇 𝗂𝗇 : {remaining_seconds} 𝗌𝖾𝖼𝗈𝗇𝖽𝗌\n\n<blockquote>⚠️ ᴀꜰᴛᴇʀ 5 ᴍɪɴᴜᴛᴇꜱ ᴛʜɪꜱ ᴍᴇꜱꜱᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴅᴇʟᴇᴛᴇᴅ 🗑️</blockquote>\n\n</b>"
                #cap+="<b><u>🍿 Your Movie Files 👇</u></b>\n\n"
                for file in files:
                    cap += f"<b>📁 <a href='https://telegram.me/{temp.U_NAME}?start=files_{file['file_id']}'>[{get_size(file['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file['file_name'].split()))}\n\n</a></b>"
    else:
        cap = f"<b>𝖱𝖾𝗌𝗎𝗅𝗍  𝖥𝗈𝗎𝗇𝖽 𝖥𝗈𝗋 {search}\n\n🧑‍💻 𝖱𝖾𝗊𝗎𝖾𝗌𝗍𝖾𝖽 𝖡𝗒  : {query.from_user.mention}\n⏰ 𝖱𝖾𝗌𝗎𝗅𝗍 𝖲𝗁𝗈𝗐𝗇 𝗂𝗇 : {remaining_seconds} 𝗌𝖾𝖼𝗈𝗇𝖽𝗌\n\n<blockquote>⚠️ ᴀꜰᴛᴇʀ 5 ᴍɪɴᴜᴛᴇꜱ ᴛʜɪꜱ ᴍᴇꜱꜱᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴅᴇʟᴇᴛᴇᴅ 🗑️</blockquote>\n\n</b>"
       # cap+="<b><u>🍿 Your Movie Files 👇</u></b>\n\n"
        for file in files:
            cap += f"<b>📁 <a href='https://telegram.me/{temp.U_NAME}?start=files_{file['file_id']}'>[{get_size(file['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), file['file_name'].split()))}\n\n</a></b>"
    return cap


    
def get_wish():
    tz = pytz.timezone('Asia/Kolkata')
    hour = datetime.now(tz).hour
    if hour < 12:
        status = "Good Morning 🌞"
    elif hour < 18:
        status = "Good Afternoon 🌗"
    else:
        status = "Good Evening 🌘"
    return status

def get_seconds(time_string):
    def extract_value_and_unit(ts):
        value = ""
        unit = ""
        index = 0
        while index < len(ts) and ts[index].isdigit():
            value += ts[index]
            index += 1
        unit = ts[index:]
        if value:
            value = int(value)
        return value, unit
    value, unit = extract_value_and_unit(time_string)
    if unit in ['s', 'sec', 'secs', 'second', 'seconds']:
        return value
    elif unit in ['min', 'mins', 'minute', 'minutes']:
        return value * 60
    elif unit in ['hour', 'hours', 'hr', 'hrs']:
        return value * 3600
    elif unit in ['day', 'days']:
        return value * 86400
    elif unit in ['month', 'months']:
        return value * 86400 * 30
    elif unit in ['year', 'years']:
        return value * 86400 * 365
    else:
        return 0
        
async def is_check_admin(bot, chat_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except (UserNotParticipant, PeerIdInvalid, ChannelPrivate) as e:
        logger.debug("is_check_admin: %s not admin-ish in %s (%s)", user_id, chat_id, e)
        return False
    except Exception:
        logger.exception("is_check_admin failed for user %s in chat %s", user_id, chat_id)
        return False
    return member.status in (enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER)



