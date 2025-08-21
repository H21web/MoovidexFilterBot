# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import logging, asyncio, os, re, random, pytz, aiohttp, requests, string, json, http.client
from info import *

from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram import enums
from urllib.parse import quote_plus
from pyrogram.errors import *
from typing import  Any, Dict, List, Optional, Union
from Script import script
from datetime import datetime, date
from typing import List
from database.users_chats_db import db
from database.join_reqs import JoinReqs
from bs4 import BeautifulSoup
from shortzy import Shortzy
from urllib.parse import quote   


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

# temp db for banned 
class temp(object):
    BANNED_USERS = []
    BANNED_CHATS = []
    ME = None
    BOT = None
    CURRENT=int(os.environ.get("SKIP", 2))
    CANCEL = False
    MELCOW = {}
    U_NAME = None
    B_NAME = None
    GETALL = {}
    SHORT = {}
    SETTINGS = {}
    IMDB_CAP = {}


async def pub_is_subscribed(bot, query, channel):
    btn = []
    for id in channel:
        chat = await bot.get_chat(int(id))
        try:
            await bot.get_chat_member(id, query.from_user.id)
        except UserNotParticipant:
            btn.append(
                [InlineKeyboardButton(f'Join {chat.title}', url=chat.invite_link)]
            )
        except Exception as e:
            pass
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


import re




# Assumed helpers/flags from your environment
# Provide implementations if not present in your project:
try:
    from utils import list_to_str, LONG_IMDB_DESCRIPTION
except Exception:
    def list_to_str(x):
        if not x:
            return ""
        if isinstance(x, str):
            return x
        if isinstance(x, (list, tuple, set)):
            return ", ".join([str(i) for i in x if i is not None])
        return str(x)
    LONG_IMDB_DESCRIPTION = False

imdb_client = IMDB()


def _normalize_year(y: Optional[Union[str, int]]) -> Optional[str]:
    if not y:
        return None
    s = str(y)
    m = re.search(r'([12]\d{3})', s)
    return m.group(1) if m else None


def _extract_kind_from_type(t: Optional[str]) -> str:
    if not t:
        return "movie"
    t = t.lower()
    # PyMovieDb returns "Movie", "TVSeries", etc.
    if "tv" in t or "series" in t:
        return "tv series"
    if "movie" in t or t in ("film", "feature"):
        return "movie"
    return "movie"


def _year_matches(item: Dict[str, Any], target_year: Optional[str]) -> bool:
    if not target_year:
        return True
    # Search-level items may not always have a year; try within the datePublished
    y = _normalize_year(item.get("year") or item.get("datePublished") or item.get("released"))
    return str(y) == str(target_year)


def _join_people(items: Optional[List[Dict[str, Any]]]) -> str:
    if not items:
        return ""
    names = []
    for it in items:
        if isinstance(it, dict):
            n = it.get("name")
            if n:
                names.append(n)
    return list_to_str(names)


def _norm_list(val: Any) -> str:
    if not val:
        return ""
    if isinstance(val, (list, tuple, set)):
        return list_to_str([str(v) for v in val if v is not None])
    return str(val)


def _pick_plot(movie: Dict[str, Any]) -> str:
    # Short vs long description
    short_plot = movie.get("description") or movie.get("plot") or movie.get("plotSummary") or movie.get("overview")
    long_plot = movie.get("plot_outline") or movie.get("summary")
    selected = long_plot if LONG_IMDB_DESCRIPTION and long_plot else short_plot or long_plot or ""
    if selected and len(selected) > 800:
        selected = selected[:800] + "..."
    return selected or ""


def _safe_get_rating(movie: Dict[str, Any]) -> Optional[str]:
    rating = None
    if isinstance(movie.get("rating"), dict):
        rating = movie["rating"].get("ratingValue")
    rating = rating or movie.get("imdb_rating") or movie.get("aggregateRating") or movie.get("ratingValue")
    if rating is None:
        return None
    return str(rating)


def _extract_candidates_from_search(res: Any) -> List[Dict[str, Any]]:
    # PyMovieDb IMDB.get_by_name returns a rich dict for a single title when tv/movie flags narrow the query.
    # For broader queries it may return a list or dict with partial fields. Normalize to list of dicts.
    if isinstance(res, list):
        return res
    if isinstance(res, dict):
        # If it already looks like a single title (has "type" and "name"), treat it as sole candidate
        if any(k in res for k in ("type", "name", "url", "poster", "description")):
            return [res]
        # If there is a nested container, attempt to extract
        for k in ("titles", "results", "items", "data"):
            v = res.get(k)
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                # If dict contains a list under known keys
                for kk in ("titles", "results", "items"):
                    vv = v.get(kk)
                    if isinstance(vv, list):
                        return vv
    return []


async def get_poster(query, bulk=False, id=False, file=None):
    if not id:
        q = (query.strip()).lower()
        title = q
        # trailing year in query, e.g., "reacher 2022"
        year_match = re.findall(r'[1-2]\d{3}$', q, re.IGNORECASE)
        if year_match:
            year = list_to_str(year_match[:1])
            title = (q.replace(year, "")).strip()
        elif file is not None:
            year_match = re.findall(r'[1-2]\d{3}', str(file), re.IGNORECASE)
            year = list_to_str(year_match[:1]) if year_match else None
        else:
            year = None

        # Heuristic: default to tv=True if title suggests a series-like query; else try movie then tv
        # Since your example shows tv=True for Reacher, we’ll try tv=True first, then fallback.
        candidates: List[Dict[str, Any]] = []

        try:
            res = imdb_client.get_by_name(title, tv=True)
            candidates = _extract_candidates_from_search(res)
        except Exception:
            candidates = []

        if not candidates:
            try:
                res = imdb_client.get_by_name(title, tv=False)
                candidates = _extract_candidates_from_search(res)
            except Exception:
                candidates = []

        if not candidates:
            return None

        # Filter by year if provided
        filtered = [c for c in candidates if _year_matches(c, year)] or candidates

        # Filter by kind to movie/tv series
        filtered_kind = []
        for c in filtered:
            kind = _extract_kind_from_type(c.get("type"))
            if kind in ("movie", "tv series"):
                filtered_kind.append(c)
        if not filtered_kind:
            filtered_kind = filtered

        if bulk:
            out = []
            for c in filtered_kind:
                url = c.get("url") or ""
                imdb_id = None
                # Extract tt id from URL if present
                m = re.search(r'/title/(tt\d+)/', url) or re.search(r'(tt\d+)', url)
                if m:
                    imdb_id = m.group(1)
                out.append({
                    'imdb_id': imdb_id,
                    'title': c.get('name') or c.get('title'),
                    'year': _normalize_year(c.get('datePublished') or c.get('year')),
                    'kind': _extract_kind_from_type(c.get('type')),
                })
            return out

        top = filtered_kind[0]
        url = top.get("url") or ""
        imdb_id = None
        m = re.search(r'/title/(tt\d+)/', url) or re.search(r'(tt\d+)', url)
        if m:
            imdb_id = m.group(1)
        if not imdb_id:
            # As a fallback, some responses might include "id"
            maybe_id = top.get("id")
            if maybe_id and str(maybe_id).startswith("tt"):
                imdb_id = str(maybe_id)
        if not imdb_id:
            return None
    else:
        imdb_id = str(query)
        if not imdb_id.startswith("tt"):
            imdb_id = f"tt{imdb_id}"

    # Fetch full details using ID
    try:
        movie = imdb_client.get_by_id(imdb_id)
    except Exception:
        movie = None
    if not movie:
        return None

    # Title, kind, year/date
    title = movie.get("name") or movie.get("title")
    kind = _extract_kind_from_type(movie.get("type"))

    original_air_date = movie.get("datePublished") or movie.get("released")
    year_val = _normalize_year(original_air_date or movie.get("year"))

    # Plot
    plot = _pick_plot(movie)

    # Poster
    poster = movie.get("poster") or (movie.get("image", {}).get("url") if isinstance(movie.get("image"), dict) else None)

    # Ratings and votes
    rating = _safe_get_rating(movie)
    votes = None
    # ratingCount presence in nested rating dict
    if isinstance(movie.get("rating"), dict):
        votes = movie["rating"].get("ratingCount")
    votes = votes or movie.get("imdb_votes") or movie.get("ratingCount")

    # Cast and creators/directors/writers where available
    cast = movie.get("actor") or movie.get("actors") or []
    directors = movie.get("director") or []
    writers = movie.get("writer") or movie.get("writers") or []
    creators = movie.get("creator") or []

    # Producer/composer/cinematographer/music dept may not be present in PyMovieDb responses
    producers = movie.get("producer") or []
    composers = movie.get("composer") or movie.get("music") or []
    cinematographers = movie.get("cinematographer") or []
    music_dept = movie.get("music_department") or []

    # Countries/languages/genres/certificates/runtimes
    countries = movie.get("countryOfOrigin") or movie.get("countries") or []
    languages = movie.get("inLanguage") or movie.get("languages") or []
    genres = movie.get("genre") or movie.get("genres") or []
    certificates = movie.get("contentRating") or movie.get("certificates") or []
    runtime = movie.get("duration") or movie.get("runtime")  # duration might be ISO 8601 or minutes

    # Try to normalize runtime to minutes string if ISO 8601 like PT50M
    def _normalize_runtime(rt):
        if not rt:
            return ""
        if isinstance(rt, (int, float)):
            return str(int(rt))
        s = str(rt)
        # Parse simple ISO-8601 durations like PT50M, PT2H10M
        m_min = re.search(r'PT(?:(\d+)H)?(?:(\d+)M)?', s, re.IGNORECASE)
        if m_min:
            hours = int(m_min.group(1)) if m_min.group(1) else 0
            mins = int(m_min.group(2)) if m_min.group(2) else 0
            total = hours * 60 + mins if (hours or mins) else None
            if total is not None:
                return str(total)
        # Fallback: return as-is
        return s

    runtime_str = _normalize_runtime(runtime)
    seasons = movie.get("numberOfSeasons") or movie.get("totalSeasons") or movie.get("seasons")

    # Box office is typically not provided by PyMovieDb; keep structure if any hints exist
    box_office = None
    if any(movie.get(k) for k in ("budget", "gross", "openingWeekend")):
        box_office = {
            "budget": movie.get("budget"),
            "gross": movie.get("gross"),
            "opening_weekend": movie.get("openingWeekend"),
        }

    # AKAs / localized
    akas = movie.get("alsoKnownAs") or movie.get("aka") or []
    localized_title = movie.get("alternateName") if isinstance(movie.get("alternateName"), str) else None

    # Distributors rarely present
    distributors = movie.get("distributors") or []

    result = {
        'title': title,
        'votes': votes,
        "aka": _norm_list(akas),
        "seasons": seasons,
        "box_office": box_office,
        'localized_title': localized_title,
        'kind': kind,
        "imdb_id": imdb_id,
        "cast": _join_people(cast),
        "runtime": runtime_str,
        "countries": _norm_list(countries),
        "certificates": _norm_list(certificates),
        "languages": _norm_list(languages),
        "director": _join_people(directors),
        "writer": _join_people(writers if writers else creators),  # fall back to creators as writers if writers missing
        "producer": _join_people(producers),
        "composer": _join_people(composers),
        "cinematographer": _join_people(cinematographers),
        "music_team": _join_people(music_dept),
        "distributors": _norm_list(distributors if isinstance(distributors, list) else [distributors] if distributors else []),
        'release_date': original_air_date or (year_val or "N/A"),
        'year': year_val,
        'genres': _norm_list(genres),
        'poster': poster,
        'plot': plot,
        'rating': rating,
        'url': f'https://www.imdb.com/title/{imdb_id}/'
    }
    return result



async def broadcast_messages(user_id, message):
    try:
        await message.copy(chat_id=user_id)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.x)
        return await broadcast_messages(user_id, message)
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
    except Exception as e:
        return False, "Error"

async def broadcast_messages_group(chat_id, message):
    try:
        kd = await message.copy(chat_id=chat_id)
        try:
            await kd.pin()
        except:
            pass
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.x)
        return await broadcast_messages_group(chat_id, message)
    except Exception as e:
        return False, "Error"
    

async def search_gagala(text):
    usr_agent = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/61.0.3163.100 Safari/537.36'
    }
    text = text.replace(" ", '+')
    url = f'https://imdb.iamidiotareyoutoo.com/search?q={text}'
    
    response = requests.get(url, headers=usr_agent)
    response.raise_for_status()
    data = response.json()

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

def extract_user(message: Message) -> Union[int, str]:
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
    if not k:
        return "N/A"
    elif len(k) == 1:
        return str(k[0])
    elif MAX_LIST_ELM:
        k = k[:int(MAX_LIST_ELM)]
        return ' '.join(f'{elem}, ' for elem in k)
    else:
        return ' '.join(f'{elem}, ' for elem in k)

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

def gfilterparser(text, keyword):
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
                        callback_data=f"gfilteralert:{i}:{keyword}"
                    ))
                else:
                    buttons.append([InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"gfilteralert:{i}:{keyword}"
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

    try:
        return note_data, buttons, alerts
    except:
        return note_data, buttons, None

def parser(text, keyword):
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
                        callback_data=f"alertmessage:{i}:{keyword}"
                    ))
                else:
                    buttons.append([InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"alertmessage:{i}:{keyword}"
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

    try:
        return note_data, buttons, alerts
    except:
        return note_data, buttons, None

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



async def get_clone_shortlink(link, url, api):
    shortzy = Shortzy(api_key=api, base_site=url)
    link = await shortzy.convert(link)
    return link
                           
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
    if URL == "api.shareus.io":
        url = f'https://{URL}/easy_api'
        params = {
            "key": API,
            "link": link,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, raise_for_status=True, ssl=False) as response:
                    data = await response.text()
                    return data
        except Exception as e:
            logger.error(e)
            return link
    else:
        shortzy = Shortzy(api_key=API, base_site=URL)
        link = await shortzy.convert(link)
        return link
    
async def get_tutorial(chat_id):
    settings = await get_settings(chat_id) #fetching settings for group
    return settings['tutorial']
        
async def get_verify_shorted_link(link, url, api):
    API = api
    URL = url
    if URL == "api.shareus.io":
        url = f'https://{URL}/easy_api'
        params = {
            "key": API,
            "link": link,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, raise_for_status=True, ssl=False) as response:
                    data = await response.text()
                    return data
        except Exception as e:
            logger.error(e)
            return link
    else:
        shortzy = Shortzy(api_key=API, base_site=URL)
        link = await shortzy.convert(link)
        return link
        
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
    tz = pytz.timezone('Asia/Kolkata')
    today = date.today()
    if user.id in VERIFIED.keys():
        EXP = VERIFIED[user.id]
        years, month, day = EXP.split('-')
        comp = date(int(years), int(month), int(day))
        if comp<today:
            return False
        else:
            return True
    else:
        return False  
    
async def send_all(bot, userid, files, ident, chat_id, user_name, query):
    settings = await get_settings(chat_id)
    if 'is_shortlink' in settings.keys():
        ENABLE_SHORTLINK = settings['is_shortlink']
    else:
        await save_group_settings(message.chat.id, 'is_shortlink', False)
        ENABLE_SHORTLINK = False
    try:
        if ENABLE_SHORTLINK:
            for file in files:
                title = file["file_name"]
                size = get_size(file["file_size"])
                if not await db.has_premium_access(userid) and SHORTLINK_MODE == True:
                    await bot.send_message(chat_id=userid, text=f"<b>Hᴇʏ ᴛʜᴇʀᴇ {user_name} 👋🏽 \n\n✅ Sᴇᴄᴜʀᴇ ʟɪɴᴋ ᴛᴏ ʏᴏᴜʀ ғɪʟᴇ ʜᴀs sᴜᴄᴄᴇssғᴜʟʟʏ ʙᴇᴇɴ ɢᴇɴᴇʀᴀᴛᴇᴅ ᴘʟᴇᴀsᴇ ᴄʟɪᴄᴋ ᴅᴏᴡɴʟᴏᴀᴅ ʙᴜᴛᴛᴏɴ\n\n🗃️ Fɪʟᴇ Nᴀᴍᴇ : {title}\n🔖 Fɪʟᴇ Sɪᴢᴇ : {size}</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📤 Dᴏᴡɴʟᴏᴀᴅ 📥", url=await get_shortlink(chat_id, f"https://telegram.me/{temp.U_NAME}?start=files_{file['file_id']}"))]]))
        else:
            for file in files:
                f_caption = file["caption"]
                title = file["file_name"]
                size = get_size(file["file_size"])
                if CUSTOM_FILE_CAPTION:
                    try:
                        f_caption = CUSTOM_FILE_CAPTION.format(
                            file_name='' if title is None else title,
                            file_size='' if size is None else size,
                            file_caption='' if f_caption is None else f_caption
                        )
                    except Exception as e:
                        print(e)
                        f_caption = f_caption
                if f_caption is None:
                    f_caption = f"{title}"
                await bot.send_cached_media(
                    chat_id=userid,
                    file_id=file["file_id"],
                    caption=f_caption,
                    protect_content=True if ident == "filep" else False,
                    reply_markup=InlineKeyboardMarkup(
                        [[
                            InlineKeyboardButton('Sᴜᴘᴘᴏʀᴛ Gʀᴏᴜᴘ', url=GRP_LNK),
                            InlineKeyboardButton('Uᴘᴅᴀᴛᴇs Cʜᴀɴɴᴇʟ', url=CHNL_LNK)
                        ],[
                            InlineKeyboardButton("Bᴏᴛ Oᴡɴᴇʀ", url=OWNER_LNK)
                        ]]
                    )
                )
    except UserIsBlocked:
        await query.answer('Uɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ ᴍᴀʜɴ !', show_alert=True)
    except PeerIdInvalid:
        await query.answer('Hᴇʏ, Sᴛᴀʀᴛ Bᴏᴛ Fɪʀsᴛ Aɴᴅ Cʟɪᴄᴋ Sᴇɴᴅ Aʟʟ', show_alert=True)
    except Exception as e:
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
    tz = pytz.timezone('Asia/Colombo')
    time = datetime.now(tz)
    now = time.strftime("%H")
    if now < "12":
        status = "Good Morning 🌞"
    elif now < "18":
        status = "Good Afternoon 🌗"
    else:
        status = "Good Evening 🌘"
    return status

async def get_seconds(time_string):
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
    if unit == 's':
        return value
    elif unit == 'min':
        return value * 60
    elif unit == 'hour':
        return value * 3600
    elif unit == 'day':
        return value * 86400
    elif unit == 'month':
        return value * 86400 * 30
    elif unit == 'year':
        return value * 86400 * 365
    else:
        return 0
        
async def is_check_admin(bot, chat_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
    except:
        return False



