# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @H21TG

import os, logging, string, asyncio, time, re, ast, random, math, pytz, pyrogram, aiohttp
from difflib import SequenceMatcher
from datetime import datetime, timedelta, date, time
from Script import script
import requests
from info import *
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto, ChatPermissions, WebAppInfo
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserIsBlocked, MessageNotModified, PeerIdInvalid
from pyrogram.errors.exceptions.bad_request_400 import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from utils import get_wish, get_size, is_subscribed, pub_is_subscribed, get_poster, search_gagala, temp, get_settings, save_group_settings, get_shortlink, get_tutorial, send_all, get_cap
from database.users_chats_db import db
from database.stats_db import stats_db
from database.ia_filterdb import col, sec_col, db as vjdb, sec_db, get_file_details, get_search_results, get_bad_files
from database.filters_mdb import del_all, find_filter, get_filters
from database.connections_mdb import mydb, active_connection, all_connections, delete_connection, if_active, make_active, make_inactive
from database.gfilters_mdb import find_gfilter, get_gfilters, del_allg
from urllib.parse import quote_plus
from TechVJ.util.file_properties import get_name, get_hash, get_media_file_size
from database.config_db import mdb


logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)
lock = asyncio.Lock()

BUTTON = {}
BUTTONS = {}
FRESH = {}
BUTTONS0 = {}
BUTTONS1 = {}
BUTTONS2 = {}
SPELL_CHECK = {}
TITLES = {} # [NEW] Store display titles for filtered results

# Language Mapping
LANG_MAP = {
    'hind': 'Hindi', 'hndi': 'Hindi', 'hin': 'Hindi',
    'eng': 'English', 'english': 'English',
    'tam': 'Tamil', 'tamil': 'Tamil',
    'tel': 'Telugu', 'telugu': 'Telugu',
    'mal': 'Malayalam', 'malayalam': 'Malayalam',
    'kan': 'Kannada', 'kannada': 'Kannada',
    'ben': 'Bengali', 'bengali': 'Bengali',
    'kor': 'Korean', 'korean': 'Korean',
    'jap': 'Japanese',
    'dual': 'Dual Audio', 'multi': 'Multi Audio'
}

# Quality Mapping
QUALITY_MAP = ['2160p', '4k', '1080p', '720p', '480p', '360p', 'cam', 'dvd']

# --- Optimization: Global Regex Compilation ---
# 1. Season Pattern: Fixed to avoid "DS4K" (enforce word boundaries)
# Matches: S01, Season 1, Season01, S 1
SEASON_PATTERN = re.compile(r'(?i)\b(?:S|Season)\s?(\d{1,3})\b') 

# 2. Series Keywords
SERIES_KEYWORDS = re.compile(r'(?i)\b(?:ep|episode)\s?\d+')

# 3. Combined Language Regex
# Create a robust pattern from LANG_MAP values + Common Languages
COMMON_LANGS = ["French", "German", "Italian", "Spanish", "Russian", "Japanese", "Chinese", "Korean", "Thai", "Indonesian"]
ALL_LANGS = set(LANG_MAP.values()) | set(COMMON_LANGS)
# Sort by length desc to match longest first (e.g. "Dual Audio" before "Audio")
SORTED_LANG_KEYS = sorted(LANG_MAP.keys(), key=len, reverse=True) 
AL_LANG_PATTERN = '|'.join(map(re.escape, ALL_LANGS))
LANG_KEYS_PATTERN = '|'.join(map(re.escape, SORTED_LANG_KEYS))

# Combine codes and full names: match either a known code OR a full language name
# We separate them to map codes back to full names
LANG_CODE_REGEX = re.compile(rf'(?i)\b({LANG_KEYS_PATTERN})\b')
LANG_NAME_REGEX = re.compile(rf'(?i)\b({AL_LANG_PATTERN})\b')

# 4. Combined Quality Regex
QUALITY_REGEX = re.compile(rf'(?i)\b({"|".join(map(re.escape, QUALITY_MAP))})\b')

@Client.on_message(filters.group & filters.text & filters.incoming)
async def give_filter(client, message):
    user_id = message.from_user.id if message.from_user else 0
    try:
        await mdb.update_top_messages(user_id, message.text)
    except Exception as e:
        logger.error(f"Error updating top messages: {e}")
        
    if message.chat.id != SUPPORT_CHAT_ID:
        settings = await get_settings(message.chat.id)
        chatid = message.chat.id
        if settings['fsub'] != None:
            try:
                btn = await pub_is_subscribed(client, message, settings['fsub'])
                if btn:
                    btn.append([InlineKeyboardButton("Unmute Me 🔕", callback_data=f"unmuteme#{int(user_id)}")])
                    await client.restrict_chat_member(chatid, message.from_user.id, ChatPermissions(can_send_messages=False))
                    await message.reply_photo(photo=random.choice(PICS), caption=f"👋 Hello {message.from_user.mention},\n\nPlease join the channel then click on unmute me button. 😇", reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
                    return
            except Exception as e:
                print(e)
            
        manual = await manual_filters(client, message)
        if manual == False:
            settings = await get_settings(message.chat.id)
            try:
                if settings['auto_ffilter']:
                    # Check for Premium/Referral Access
                    if not await db.has_premium_access(user_id):
                        invite_link = f"https://t.me/{temp.U_NAME}?start=VJ-{user_id}"
                        share_text = f"Hey! Check out this amazing bot for downloading movies and series. Join now using my link: {invite_link}"
                        share_url = f"https://t.me/share/url?url={invite_link}&text={quote_plus(share_text)}"
                        
                        btn = [[
                            InlineKeyboardButton("🚀 Share Referral Link", url=share_url)
                        ]]
                        await message.reply_text(
                            text=(
                                f"<b>⚠️ Access Denied! ⚠️</b>\n\n"
                                f"You need to refer <b>1 friend</b> to get <b>3 months</b> of access.\n\n"
                                f"<b>Your Referral Link:</b>\n<code>{invite_link}</code>\n\n"
                                f"<i>Share this link with your friends. Once 1 friend joins, you will get instant access!</i>"
                            ),
                            reply_markup=InlineKeyboardMarkup(btn),
                            disable_web_page_preview=True
                        )
                        return

                    # Daily Usage Check (Free Tier)
                    daily_usage = await db.get_daily_usage(user_id)
                    if daily_usage < 4:
                        await db.increment_daily_usage(user_id)
                    else:
                        invite_link = f"https://t.me/{temp.U_NAME}?start=VJ-{user_id}"
                        share_text = f"Hey! Check out this amazing bot for downloading movies and series. Join now using my link: {invite_link}"
                        share_url = f"https://t.me/share/url?url={invite_link}&text={quote_plus(share_text)}"
                        
                        btn = [[
                            InlineKeyboardButton("🚀 Share Referral Link", url=share_url)
                        ]]
                        await message.reply_text(
                            text=(
                                f"<b>⚠️ Daily Limit Reached! ⚠️</b>\n\n"
                                f"You have used your <b>4 free searches</b> for today.\n\n"
                                f"To get <b>UNLIMITED ACCESS</b> for <b>3 MONTHS</b>, simply refer <b>1 friend</b>!\n\n"
                                f"<b>Your Referral Link:</b>\n<code>{invite_link}</code>\n\n"
                                f"<i>Share this link with your friends. Once 1 friend joins, you will get instant access!</i>"
                            ),
                            reply_markup=InlineKeyboardMarkup(btn),
                            disable_web_page_preview=True
                        )
                        return

                    ai_search = True
                    reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                    await auto_filter(client, message.text, message, reply_msg, ai_search)
            except KeyError:
                grpid = await active_connection(str(message.from_user.id))
                await save_group_settings(grpid, 'auto_ffilter', True)
                settings = await get_settings(message.chat.id)
                if settings['auto_ffilter']:
                    ai_search = True
                    reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                    await auto_filter(client, message.text, message, reply_msg, ai_search)
    else: #a better logic to avoid repeated lines of code in auto_filter function
        search = message.text
        temp_files, temp_offset, total_results = await get_search_results(chat_id=message.chat.id, query=search.lower(), offset=0, filter=True)
        if total_results == 0:
            return
        else:
            return await message.reply_text(f"<b>Hᴇʏ {message.from_user.mention}, {str(total_results)} ʀᴇsᴜʟᴛs ᴀʀᴇ ғᴏᴜɴᴅ ɪɴ ᴍʏ ᴅᴀᴛᴀʙᴀsᴇ ғᴏʀ ʏᴏᴜʀ ᴏ̨ᴜᴇʀʏ {search}. \n\nTʜɪs ɪs ᴀ sᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ sᴏ ᴛʜᴀᴛ ʏᴏᴜ ᴄᴀɴ'ᴛ ɢᴇᴛ ғɪʟᴇs ғʀᴏᴍ ʜᴇʀᴇ...\n\nJᴏɪɴ ᴀɴᴅ Sᴇᴀʀᴄʜ Hᴇʀᴇ - {GRP_LNK}</b>")

async def boovo(bot, title, message):
    ai_search = True
    data = title
    reply_msg = await bot.send_message(
        message.chat.id,
        f"<b> 🔎Searching {data}</b>",
        reply_to_message_id=message.id
    )
    
    await auto_filter(bot, data, message, reply_msg, ai_search)
    

@Client.on_message(filters.private & filters.text & filters.incoming)
async def pm_text(bot, message):
    await mdb.update_top_messages(message.from_user.id, message.text)
    content = message.text
    user = message.from_user.first_name
    user_id = message.from_user.id

    if content.startswith("/") or content.startswith("#"):
        return

    kd = await global_filters(bot, message)
    if kd is False:
        if PM_SEARCH == True:
            # Check for Premium/Referral Access
            if not await db.has_premium_access(user_id):
                invite_link = f"https://t.me/{temp.U_NAME}?start=VJ-{user_id}"
                share_text = f"Hey! Check out this amazing bot for downloading movies and series. Join now using my link: {invite_link}"
                share_url = f"https://t.me/share/url?url={invite_link}&text={quote_plus(share_text)}"
                
                btn = [[
                    InlineKeyboardButton("🚀 Share Referral Link", url=share_url)
                ]]
                await message.reply_text(
                    text=(
                        f"<b>⚠️ Access Denied! ⚠️</b>\n\n"
                        f"You need to refer <b>1 friend</b> to get <b>3 months</b> of access.\n\n"
                        f"<b>Your Referral Link:</b>\n<code>{invite_link}</code>\n\n"
                        f"<i>Share this link with your friends. Once 1 friend joins, you will get instant access!</i>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn),
                    disable_web_page_preview=True
                )
                return

            # Daily Usage Check (Free Tier)
            daily_usage = await db.get_daily_usage(user_id)
            if daily_usage < 4:
                await db.increment_daily_usage(user_id)
            else:
                invite_link = f"https://t.me/{temp.U_NAME}?start=VJ-{user_id}"
                share_text = f"Hey! Check out this amazing bot for downloading movies and series. Join now using my link: {invite_link}"
                share_url = f"https://t.me/share/url?url={invite_link}&text={quote_plus(share_text)}"
                
                btn = [[
                    InlineKeyboardButton("🚀 Share Referral Link", url=share_url)
                ]]
                await message.reply_text(
                    text=(
                        f"<b>⚠️ Daily Limit Reached! ⚠️</b>\n\n"
                        f"You have used your <b>4 free searches</b> for today.\n\n"
                        f"To get <b>UNLIMITED ACCESS</b> for <b>3 MONTHS</b>, simply refer <b>1 friend</b>!\n\n"
                        f"<b>Your Referral Link:</b>\n<code>{invite_link}</code>\n\n"
                        f"<i>Share this link with your friends. Once 1 friend joins, you will get instant access!</i>"
                    ),
                    reply_markup=InlineKeyboardMarkup(btn),
                    disable_web_page_preview=True
                )
                return

            await stats_db.add_pm_search_log(content, user_id)
            ai_search = True
            reply_msg = await bot.send_message(
                chat_id=message.chat.id,
                text=f"<b>🔎 Searching {content} </b>",
                reply_to_message_id=message.id
            )
            await auto_filter(bot, content, message, reply_msg, ai_search=True)

    # After processing, send the nicely formatted PM search log:
   # await bot.send_message(
    #    chat_id=LOG_CHANNEL,
     #   text=f"<b><u>🔎 BOT SEARCH</u>\n<blockquote>👤 {user} ({user_id})</blockquote>\n\n📜<code> {content}</code></b>"
   # )

async def doo(bot, data, message):
    user = message.from_user.first_name
    user_id = message.from_user.id
    ai_search = True

    # Replace underscores with spaces
    data = data.replace('_', ' ')

    # Send the initial search message
    reply_msg = await bot.send_message(
        message.from_user.id, 
        f"<b>🔎 Searching {data} </b>", 
        reply_to_message_id=message.id
    )
    
    await auto_filter(bot, data, message, reply_msg, ai_search)


def get_size(file_size):
    if file_size < (1024 ** 3):  # Less than 1GB
        size_in_mb = file_size / (1024 ** 2)
        return f"{int(size_in_mb)}MB"
    else:
        size_in_gb = file_size / (1024 ** 3)
        return f"{size_in_gb:.1f}GB"

def extract_shortdetails(filename, file_size, max_length=64):
    # Pre-cleaning
    cleaned = ' '.join(
        filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'),
               filename.split())
    )
    lower = cleaned.lower()

    # Season and episode detection
    se_match = re.search(
        r'(?i)(?:(?:S(?P<season>\d{2}))\s?E(?:P)?(?P<episode>\d{1,2}))|'  # S01E01, S01 EP01, S01EP1
        r'(?:S(?P<season_only>\d{2}))|'                                  # S01
        r'(?:EP(?P<episode_only>\d{1,2}))|'                              # EP1
        r'(?:SEASON[\s._-]?(?P<season_text>\d{1,2}))',                   # Season 1
        lower
    )

    season_episode_str = ''
    season = episode = None
    is_series = False

    if se_match:
        gd = se_match.groupdict()
        is_series = True
        if gd['season'] and gd['episode']:
            season, episode = int(gd['season']), int(gd['episode'])
        elif gd['season_only']:
            season = int(gd['season_only'])
        elif gd['season_text']:
            season = int(gd['season_text'])
        elif gd['episode_only']:
            episode = int(gd['episode_only'])

        if season is not None and episode is not None:
            season_episode_str = f"[S{season:02d}E{episode:02d}]"
        elif season is not None:
            season_episode_str = f"[S{season:02d}]"
        elif episode is not None:
            season_episode_str = f"[E{episode:02d}]"

    # Year detection
    year_match = re.search(r'(19|20)\d{2}', cleaned)
    year = year_match.group() if year_match else ''

    # Quality detection
    quality_tags = ['480p', '720p', '1080p', '2160p', '4K', 'HDRip', 'BluRay', 'WEB-DL', 'WEBRip']
    quality = next((q for q in quality_tags if q.lower() in lower), '')

    # Language detection
    shorthand_lang_map = {
        'hin': 'Hindi',
        'eng': 'English',
        'tam': 'Tamil',
        'tel': 'Telugu',
        'mal': 'Malayalam',
        'kan': 'Kannada',
        'ben': 'Bengali',
        'kor': 'Korean',
        'multi': 'Multi',
        'dual': 'Dual Audio',
    }

    full_lang_set = set([
        'Hindi', 'English', 'Tamil', 'Telugu', 'Malayalam', 'Kannada',
        'Bengali', 'Dual Audio', 'Multi', 'Korean', 'Multi Audio'
    ])

    language = []

    for word in lower.split():
        if word in shorthand_lang_map:
            language.append(shorthand_lang_map[word])
        elif word.capitalize() in full_lang_set:
            language.append(word.capitalize())

    language = ' '.join(sorted(set(language)))

    # Tag extraction
    all_tags_priority = [
        'NF', 'AMZN', 'DSNP', 'HMAX', 'WEBRip', 'WEB-DL', 'BluRay', 'HDRip', 'HDR', 'HQ', 'DVD', 'CAM',
        'HEVC', 'x265', 'x264', '10bit',
        'AAC', 'AC3', 'DDP', 'DD+', '5.1', '7.1', 'Atmos', 'ESubs'
    ]

    found_tags = []
    tag_set = set()
    for tag in all_tags_priority:
        if tag.lower() in lower and tag.upper() not in tag_set:
            tag_set.add(tag.upper())
            found_tags.append(tag)

    # Clean redundant tags
    if 'x265' in found_tags and 'HEVC' in found_tags:
        found_tags.remove('HEVC')
    if ('5.1' in found_tags or '7.1' in found_tags) and ('DDP' in found_tags or 'DD+' in found_tags):
        found_tags = [t for t in found_tags if t not in ('DDP', 'DD+')]

    # Title cleanup
    title_no_ext = re.sub(r'\.(?=[^.]*$)', ' ', cleaned)

    # Remove season/episode patterns from title
    title_cleaned = re.sub(
        r'(S\d{2}\s?E(?:P)?\d{1,2})|'     # S01E01, S01 EP01, S01EP1
        r'(S\d{2})|'                      # S01
        r'(EP\d{1,2})',                   # EP1, EP01
        '',
        title_no_ext,
        flags=re.IGNORECASE
    )

    title_part = re.split(r'(19|20)\d{2}', title_cleaned)[0]
    title = re.sub(r'[\._\-]', ' ', title_part).strip().title()

    # Build title (with year)
    title_year = f"{title} ({year})" if year else title
    if len(title_year) > 30:
        title_year = title_year[:27].rstrip() + "..."

    # Emoji
    emoji = '📺' if is_series else '🎞️'

    # Build parts with a space after the size
    parts = [emoji, f"[{get_size(file_size)}] "]
    if season_episode_str:
        parts.append(season_episode_str)
    parts.append(title_year)
    if language:
        parts.append(language)
    if quality:
        parts.append(quality)

    # Append tags within limit
    current = ' '.join(parts)
    for tag in found_tags:
        test = current + f" {tag}"
        if len(test) > max_length:
            break
        current = test

    return current.strip()
def sort_by_relevance(files, query):
    """
    Sort files by relevance using Similarity Score.
    """
    # Clean query for comparison
    query_norm = re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', query.lower())).strip()
    
    def get_score(f):
        name = f['file_name'].lower().replace('.', ' ').strip()
        
        # 0. Check Year for Tie-Breaking
        year_match = re.search(r'\b(19|20)\d{2}\b', name)
        year = int(year_match.group(0)) if year_match else 0
        
        # 1. Similarity Score
        # Remove Tags for comparison to get "Core Title"
        clean_name = re.sub(r'\b(4k|1080p|720p|480p|cam|rip|web|hdr|x264|x265|hevc|dual|audio|hindi|eng|sub)\b', '', name)
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        
        similarity = SequenceMatcher(None, query_norm, clean_name).ratio()
        
        # Categorize Score
        if similarity > 0.9: 
            score = 3 # Exact-ish
        elif name.startswith(query_norm):
            score = 2.5 # Prefix match high priority
        elif similarity > 0.6:
            score = 2 # Good match
        elif query_norm in name:
            score = 1 # Basic Containment
        else:
            score = 0
            
        return (score, year, f['file_size'])

    return sorted(files, key=get_score, reverse=True)


def analyze_query_results(files):
    """
    Analyzes a list of files to identify unique languages, seasons, and qualities.
    Returns a dict with sets of detected attributes.
    Optimized for speed: Single pass, global regex, limited depth.
    """
    languages = set()
    seasons = set()
    qualities = set()
    is_series = False
    
    # Limit analysis to top 500 files for speed
    # Users usually search for relevance, so top results matter most for filters.
    # We still show ALL files in "Show All Files" option.
    files_to_analyze = files[:500] 

    for file in files_to_analyze:
        name = file['file_name'].lower()
        
        # 1. Check for Series & Extract Season
        s_matches = SEASON_PATTERN.findall(name)
        if s_matches:
            is_series = True
            for match in s_matches:
                # match could be from group 1 or implicit if simple regex
                # regex is (\d{1,3}), findall returns list of str
                try:
                    # In our filtered regex (?i)\b(?:S|Season)\s?(\d{1,3})\b, findall returns only the capturing group
                    seasons.add(f"Season {int(match)}") 
                except: pass

        if not is_series and SERIES_KEYWORDS.search(name):
             is_series = True

        # 2. Extract Languages
        # Match Codes (hind, tam, etc.)
        for code_match in LANG_CODE_REGEX.findall(name):
             languages.add(LANG_MAP[code_match.lower()])
        
        # Match Full Names (French, etc.)
        for name_match in LANG_NAME_REGEX.findall(name):
             # Capitalize properly (e.g. 'french' -> 'French' if in set)
             # simpler: just add title case
             languages.add(name_match.title())
        
        # 3. Extract Qualities
        for q_match in QUALITY_REGEX.findall(name):
             qualities.add(q_match.upper())

    # Sort results
    # Custom sort for seasons (numerical)
    sorted_seasons = sorted(list(seasons), key=lambda x: int(x.split()[-1]) if x.split()[-1].isdigit() else 999)
    
    # Custom sort for qualities
    quality_order = ['2160P', '4K', '1080P', '720P', '480P', '360P', 'DVD', 'CAM']
    sorted_qualities = sorted(list(qualities), key=lambda x: quality_order.index(x) if x in quality_order else 99)

    return {
        'languages': sorted(list(languages)),
        'seasons': sorted_seasons,
        'qualities': sorted_qualities,
        'is_series': is_series
    }

@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    try:
        ident, req, key, offset = query.data.split("_")
    except ValueError:
        try:
            ident, req, key, offset = query.data.split("#")
        except ValueError:
             # Fallback: maybe key has underscores? Try maxsplit?
             # But standardized on # is better.
             # If format is next_REQ_KEY_OFFSET and KEY has _, split("_") yields > 4 parts.
             # We should probably handle that if we can't change the generating source easily.
             # But for now, try/except is safer.
             parts = query.data.split("_")
             if len(parts) > 4: 
                 # Assume first is 'next', second is req, last is offset, middle is key
                 ident = parts[0]
                 req = parts[1]
                 offset = parts[-1]
                 key = "_".join(parts[2:-1])
             else:
                 return await query.answer("Invalid callback data")
    curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
    try:
        offset = int(offset)
    except:
        offset = 0
    search = (
    BUTTONS.get(key)
    or BUTTONS0.get(key)
    or BUTTONS1.get(key)
    or BUTTONS2.get(key)
    or FRESH.get(key)
    )

   # if not search:
      #  await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name),show_alert=True)
       # return

    files, n_offset, total = await get_search_results(query.message.chat.id, search, offset=offset, filter=True)
    try:
        n_offset = int(n_offset)
    except:
        n_offset = 0

    if not files:
        return
    temp.GETALL[key] = files
    temp.SHORT[query.from_user.id] = query.message.chat.id
    total_results_str = str(total)
    settings = await get_settings(query.message.chat.id)
    pre = 'filep' if settings['file_secure'] else 'file'
    if settings['button']:
        btn = [
            [
                InlineKeyboardButton(
                    text=extract_shortdetails(file['file_name'], file['file_size']),
                    callback_data=f"{pre}#{file['file_id']}"
                ),
            ]
            for file in files
        ]

        btn.insert(0, 
            [
                InlineKeyboardButton('🎚 Quality', callback_data=f"qualities#{key}"),
                InlineKeyboardButton('ℹ Info', url='https://t.me/moovidex/11'),
               # InlineKeyboardButton("📺 ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}"),
                InlineKeyboardButton("🗃 Seasons",  callback_data=f"seasons#{key}")
            ]
        )
        btn.insert(0, [
            InlineKeyboardButton(f"🗂 Files: {total_results_str}" , 'total'),
           # InlineKeyboardButton('ℹ Info', url='https://t.me/moovidex/11'),
           # InlineKeyboardButton("🔮 sᴇɴᴅ ᴀʟʟ", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("🎧 Languages", callback_data=f"languages#{key}")
           # InlineKeyboardButton("🗓️ ʏᴇᴀʀs", callback_data=f"years#{key}")
        ])
    else:
        btn = []
        btn.insert(0, 
            [
                InlineKeyboardButton('🎚 Quality', callback_data=f"qualities#{key}"),
                InlineKeyboardButton('ℹ Info', url='https://t.me/moovidex/11'),
              #  InlineKeyboardButton("📺 ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}"),
                InlineKeyboardButton("🗃 Seasons",  callback_data=f"seasons#{key}")
            ]
        )
        btn.insert(0, [
            InlineKeyboardButton(f"🗂 Files: {total_results_str}" , 'total'),
           # InlineKeyboardButton('ℹ Info', url='https://t.me/moovidex/11'),
          #  InlineKeyboardButton("🔮 sᴇɴᴅ ᴀʟʟ", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("🎧 Languages", callback_data=f"languages#{key}")
          #  InlineKeyboardButton("🗓️ ʏᴇᴀʀs", callback_data=f"years#{key}")
        ])
    try:
        if settings['max_btn']:
            if 0 < offset <= 10:
                off_set = 0
            elif offset == 0:
                off_set = None
            else:
                off_set = offset - 10
            if n_offset == 0:
                btn.append(
                    [InlineKeyboardButton("◀ Back", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages")]
                )
            elif off_set is None:
                btn.append([InlineKeyboardButton("📑 Page", callback_data="pages"), InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"), InlineKeyboardButton("Next ▶", callback_data=f"next_{req}_{key}_{n_offset}")])
            else:
                btn.append(
                    [
                        InlineKeyboardButton("◀ Back", callback_data=f"next_{req}_{key}_{off_set}"),
                        InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"),
                        InlineKeyboardButton("Next ▶", callback_data=f"next_{req}_{key}_{n_offset}")
                    ],
                )
        else:
            if 0 < offset <= int(MAX_B_TN):
                off_set = 0
            elif offset == 0:
                off_set = None
            else:
                off_set = offset - int(MAX_B_TN)
            if n_offset == 0:
                btn.append(
                    [InlineKeyboardButton("◀ Back", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"{math.ceil(int(offset)/int(MAX_B_TN))+1} / {math.ceil(total/int(MAX_B_TN))}", callback_data="pages")]
                )
            elif off_set is None:
                btn.append([InlineKeyboardButton("📑 Page", callback_data="pages"), InlineKeyboardButton(f"{math.ceil(int(offset)/int(MAX_B_TN))+1} / {math.ceil(total/int(MAX_B_TN))}", callback_data="pages"), InlineKeyboardButton("Next ▶", callback_data=f"next_{req}_{key}_{n_offset}")])
            else:
                btn.append(
                    [
                        InlineKeyboardButton("◀ Back", callback_data=f"next_{req}_{key}_{off_set}"),
                        InlineKeyboardButton(f"{math.ceil(int(offset)/int(MAX_B_TN))+1} / {math.ceil(total/int(MAX_B_TN))}", callback_data="pages"),
                        InlineKeyboardButton("Next ▶", callback_data=f"next_{req}_{key}_{n_offset}")
                    ],
                )
    except KeyError:
        await save_group_settings(query.message.chat.id, 'max_btn', True)
        if 0 < offset <= 10:
            off_set = 0
        elif offset == 0:
            off_set = None
        else:
            off_set = offset - 10
        if n_offset == 0:
            btn.append(
                [InlineKeyboardButton("◀ Back", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages")]
            )
        elif off_set is None:
            btn.append([InlineKeyboardButton("📑 Page", callback_data="pages"), InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"), InlineKeyboardButton("Next ▶", callback_data=f"next_{req}_{key}_{n_offset}")])
        else:
            btn.append(
                [
                    InlineKeyboardButton("◀ Back", callback_data=f"next_{req}_{key}_{off_set}"),
                    InlineKeyboardButton(f"{math.ceil(int(offset)/10)+1} / {math.ceil(total/10)}", callback_data="pages"),
                    InlineKeyboardButton("Next ▶", callback_data=f"next_{req}_{key}_{n_offset}")
                ],
            )
    if not settings["button"]:
        cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
        remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
        btntext = extract_shortdetails(file['file_name'], file['file_size'])
        cap = await get_cap(settings, remaining_seconds, files, query, total, btntext, search)
        try:
            await query.message.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
        except MessageNotModified:
            pass
    else:
        try:
            await query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(btn)
            )
        except MessageNotModified:
            pass
    await query.answer()



@Client.on_callback_query(filters.regex(r"^spol"))
async def advantage_spoll_choker(bot, query):
    _, user_id, movie_index = query.data.split('#')
    movies = SPELL_CHECK.get(query.message.reply_to_message.id)

    if not movies:
        return await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name), show_alert=True)
    
    if int(user_id) != 0 and query.from_user.id != int(user_id):
        return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
    
    if movie_index == "close_spellcheck":
        return await query.message.delete()
    
    movie = movies[int(movie_index)]
    
    # Logic: Extract Year, Search Title, Sort by Year
    year_match = re.search(r'\s(\d{4})$', movie)
    search_year = year_match.group(1) if year_match else None
    
    # Remove year from search query for broader results
    movie_title = re.sub(r'\s\d{4}$', '', movie)
    # Remove special chars for clean search
    movie_clean = re.sub(r'[^\w\s]', ' ', movie_title)
    movie_clean = re.sub(r"\s+", " ", movie_clean).strip()
    
    await query.answer(script.TOP_ALRT_MSG)
    
    if not await global_filters(bot, query.message, text=movie_clean):
        if not await manual_filters(bot, query.message, text=movie_clean):
            files, offset, total_results = await get_search_results(query.message.chat.id, movie_clean, offset=0, filter=True)
            if files:
                # Custom Sort: 
                # 1. Year Match (Highest Priority)
                # 2. Similarity of Title (Avoid "Reloaded" when searching "Matrix")
                
                def get_ranking_score(f):
                    fname = f['file_name'].lower()
                    
                    # 1. Check Year (Primary)
                    has_year = search_year in fname if search_year else False
                    
                    # 2. Calculate Similarity (Secondary)
                    # Remove year/resolution/quality from filename for cleaner comparison
                    fname_clean = re.sub(r'\b(19|20)\d{2}\b', '', fname) # Remove year
                    fname_clean = re.sub(r'(\.|_|\-)', ' ', fname_clean) # Remove separators
                    fname_clean = re.sub(r'\b(4k|1080p|720p|480p|cam|rip|web|hdr|x264|x265|hevc)\b', '', fname_clean) # Remove qualities
                    fname_clean = re.sub(r'\s+', ' ', fname_clean).strip()
                    
                    # Compare Core Title vs Clean Filename
                    # movie_clean is "the matrix" (no year)
                    similarity = SequenceMatcher(None, movie_clean.lower(), fname_clean).ratio()
                    
                    # Return tuple for sorting: (Has Year? (1/0), Similarity Score)
                    # Python sorts tuples element-by-element. We want Descending order.
                    return (1 if has_year else 0, similarity)

                files.sort(key=get_ranking_score, reverse=True)
                
                ai_search = True
                k = (movie_clean, files, offset, total_results)
                # reply_msg = await query.message.edit_text(f"<b>🔍 Searching {movie_clean} </b>")
                await auto_filter(bot, movie_clean, query, query.message, ai_search, k)
            else:
                reqstr = await bot.get_users(query.from_user.id if query.from_user else 0)

                # API fallback info
                api_answer = ""
                query_param = movie.replace(" ", "%20")
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"https://api.safone.co/asq?query={query_param}%20ott%20released%20date(short)") as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                api_answer = data.get("answer", "")
                except Exception:
                    api_answer = ""  # Fail silently

                encoded_movie = re.sub(r'\W+', '_', movie)
                request_btn = [[
                    InlineKeyboardButton(
                        '💬 Send request',
                        url=f"https://t.me/{temp.U_NAME}?start=Request_{encoded_movie}"
                    )
                ]]

                final_text = script.MVE_NT_FND
                if api_answer:
                    final_text += f"\n\n<blockquote expandable><b>{api_answer}</b></blockquote>\n"
          
                msg = await query.message.edit(
                    final_text,
                    reply_markup=InlineKeyboardMarkup(request_btn),
                    disable_web_page_preview=True
                )
                
                # Fix: use 'bot' instead of undefined 'client'
                await bot.send_message(
                    chat_id=LOG_CHANNEL,
                    text=(script.NORSLTS.format(reqstr.id, reqstr.mention, movie))
                )
                
                await asyncio.sleep(120)
                await msg.delete()

#languages

@Client.on_callback_query(filters.regex(r"^languages#"))
async def languages_cb_handler(client: Client, query: CallbackQuery):
    try:
        if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ Hello {query.from_user.first_name},\n🎬 Only the person who requested this can change languages.",
                show_alert=True,
            )
    except:
        pass

    _, key = query.data.split("#")
    
    if key not in temp.GETALL:
        await query.answer("Search expired.", show_alert=True)
        return
        
    all_files = temp.GETALL[key]
    analysis = analyze_query_results(all_files)
    
    btn = []
    # Dynamic Language Buttons from found files
    for lang in analysis['languages']:
        btn.append([InlineKeyboardButton(f"🗣 {lang}", callback_data=f"smart_lang#{lang}#{key}")])
        
    # Standard "Back" to show all files (effectively "Home" for this search)
    btn.append([InlineKeyboardButton("📂 Show All Files", callback_data=f"smart_default#{key}")])

    await query.message.edit_text(
        f"**Found {len(all_files)} results.**\n\nSELECT LANGUAGE:",
        reply_markup=InlineKeyboardMarkup(btn)
    )

@Client.on_callback_query(filters.regex(r"^fl#"))
async def filter_languages_cb_handler(client: Client, query: CallbackQuery):
    _, lang, key = query.data.split("#")
    curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    search = FRESH.get(key)
    search = search.replace("_", " ")
    baal = lang in search
    if baal:
        search = search.replace(lang, "")
    else:
        search = search
    req = query.from_user.id
    chat_id = query.message.chat.id
    message = query.message
    try:
        if int(req) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ Hello {query.from_user.first_name},\n🎬 Only the person who requested this can change languages.",
                show_alert=True,
            )
    except:
        pass
    if lang != "homepage":
        full_lang = LANG_MAP.get(lang.lower(), lang)
        search = f"{search} {full_lang}" 
    BUTTONS[key] = search

    files, offset, total_results = await get_search_results(chat_id, search, offset=0, filter=True)
    if not files:
        await query.answer("📁 Sorry, no results available right now 🚫", show_alert=1)
        return
    temp.GETALL[key] = files
    total_results_str = len(files)
    settings = await get_settings(message.chat.id)
    pre = 'filep' if settings['file_secure'] else 'file'

    btn = [
        [
            InlineKeyboardButton(f"🗂 Files: {total_results_str}" , 'total'),
            
           # InlineKeyboardButton("🔮 sᴇɴᴅ ᴀʟʟ", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("🎧 Languages", callback_data=f"languages#{key}")
          #  InlineKeyboardButton("🗓️ ʏᴇᴀʀs", callback_data=f"years#{key}")
        ],
        [
            InlineKeyboardButton("🎚 Quality", callback_data=f"qualities#{key}"),
            InlineKeyboardButton('ℹ Info', url='https://t.me/moovidex/11'),
           # InlineKeyboardButton("📺 ᴇᴘɪꜱᴏᴅᴇꜱ", callback_data=f"episodes#{key}"),
            InlineKeyboardButton("🗃 Seasons", callback_data=f"seasons#{key}")
        ]
    ]

    for file in files:
        btn.append([
            InlineKeyboardButton(
                text=extract_shortdetails(file['file_name'], file['file_size']),
                callback_data=f"{pre}#{file['file_id']}"
            )
        ])

    total_pages = math.ceil(total_results / (int(MAX_B_TN) if not settings.get('max_btn') else 10))
    if total_pages > 1:
        btn.append([
            InlineKeyboardButton("📑 Page", callback_data="pages"),
            InlineKeyboardButton(f"1/{total_pages}", callback_data="pages"),
            InlineKeyboardButton("Next ▶", callback_data=f"next_{req}_{key}_{offset}")
        ])
    else:
        btn.append([
            InlineKeyboardButton("⛔ NO MORE PAGES ⛔", callback_data="pages")
        ])

    # Add BACK button only if filtered
    if lang and lang != "homepage":
        btn.append([
            InlineKeyboardButton("◀ Back To Files", callback_data=f"fl#homepage#{key}")
        ])

    # Send caption if button setting is off
    if not settings["button"]:
        cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        time_difference = timedelta(
            hours=cur_time.hour,
            minutes=cur_time.minute,
            seconds=cur_time.second + (cur_time.microsecond / 1000000)
        ) - timedelta(
            hours=curr_time.hour,
            minutes=curr_time.minute,
            seconds=curr_time.second + (curr_time.microsecond / 1000000)
        )
        remaining_seconds = "{:.2f}".format(time_difference.total_seconds())

        cap = await get_cap(settings, remaining_seconds, files, query, total_results, search)
        try:
            await query.message.edit_text(
                text=cap,
                reply_markup=InlineKeyboardMarkup(btn),
                disable_web_page_preview=True
            )
        except MessageNotModified:
            pass
    else:
        try:
            await query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(btn)
            )
        except MessageNotModified:
            pass

    await query.answer()


@Client.on_callback_query(filters.regex(r"^seasons#"))
async def seasons_cb_handler(client: Client, query: CallbackQuery):

    try:
        if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ Hello {query.from_user.first_name},\n🎬 Only the person who requested this can change seasons.",
                show_alert=True,
            )
    except:
        pass
    
    _, key = query.data.split("#")
    # if BUTTONS.get(key+"2")!=None:
    #     search = BUTTONS.get(key+"2")
    # else:
    #     search = BUTTONS.get(key)
    #     BUTTONS[key+"2"] = search
    search = FRESH.get(key)
    BUTTONS[key] = None
    search = search.replace(' ', '_')
    btn = []
    for i in range(0, len(SEASONS)-1, 2):
        btn.append([
            InlineKeyboardButton(
                text=SEASONS[i].title(),
                callback_data=f"fs#{SEASONS[i].lower()}#{key}"
            ),
            InlineKeyboardButton(
                text=SEASONS[i+1].title(),
                callback_data=f"fs#{SEASONS[i+1].lower()}#{key}"
            ),
        ])

    btn.insert(
        0,
        [
            InlineKeyboardButton(
                text="👇 𝖲𝖾𝗅𝖾𝖼𝗍 Season 👇", callback_data="ident"
            )
        ],
    )
    req = query.from_user.id
    offset = 0
    btn.append([InlineKeyboardButton(text="◀ Back To Files", callback_data=f"next_{req}_{key}_{offset}")])

    await query.edit_message_reply_markup(InlineKeyboardMarkup(btn))


@Client.on_callback_query(filters.regex(r"^fs#"))
async def filter_seasons_cb_handler(client: Client, query: CallbackQuery):
    _, seas, key = query.data.split("#")
    curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    search = FRESH.get(key)
    search = search.replace("_", " ")
    sea = ""
    season_search = ["s01","s02", "s03", "s04", "s05", "s06", "s07", "s08", "s09", "s10", "season 01","season 02","season 03","season 04","season 05","season 06","season 07","season 08","season 09","season 10", "season 1","season 2","season 3","season 4","season 5","season 6","season 7","season 8","season 9"]
    for x in range (len(season_search)):
        if season_search[x] in search:
            sea = season_search[x]
            break
    if sea:
        search = search.replace(sea, "")
    else:
        search = search
    
    req = query.from_user.id
    chat_id = query.message.chat.id
    message = query.message
    try:
        if int(req) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ Hello {query.from_user.first_name},\n🎬 Only the person who requested this can change seasons.",
                show_alert=True,
            )
    except:
        pass
    
    searchagn = search
    search1 = search
    search2 = search
    search = f"{search} {seas}"
    BUTTONS0[key] = search
    
    files, _, _ = await get_search_results(chat_id, search, max_results=10)
    files = [file for file in files if re.search(seas, file["file_name"], re.IGNORECASE)]
    
    seas1 = "s01" if seas == "season 1" else "s02" if seas == "season 2" else "s03" if seas == "season 3" else "s04" if seas == "season 4" else "s05" if seas == "season 5" else "s06" if seas == "season 6" else "s07" if seas == "season 7" else "s08" if seas == "season 8" else "s09" if seas == "season 9" else "s10" if seas == "season 10" else ""
    search1 = f"{search1} {seas1}"
    BUTTONS1[key] = search1
    files1, _, _ = await get_search_results(chat_id, search1, max_results=10)
    files1 = [file for file in files1 if re.search(seas1, file["file_name"], re.IGNORECASE)]
    
    if files1:
        files.extend(files1)
    
    seas2 = "season 01" if seas == "season 1" else "season 02" if seas == "season 2" else "season 03" if seas == "season 3" else "season 04" if seas == "season 4" else "season 05" if seas == "season 5" else "season 06" if seas == "season 6" else "season 07" if seas == "season 7" else "season 08" if seas == "season 8" else "season 09" if seas == "season 9" else "s010"
    search2 = f"{search2} {seas2}"
    BUTTONS2[key] = search2
    files2, _, _ = await get_search_results(chat_id, search2, max_results=10)
    files2 = [file for file in files2 if re.search(seas2, file["file_name"], re.IGNORECASE)]

    if files2:
        files.extend(files2)
        
    if not files:
        await query.answer("📁 Sorry, no results available right now 🚫", show_alert=1)
        return
    temp.GETALL[key] = files
    total_results_str = len(files)
    settings = await get_settings(message.chat.id)
    pre = 'filep' if settings['file_secure'] else 'file'
    if settings["button"]:
        btn = [
            [
                InlineKeyboardButton(
                    text=extract_shortdetails(file['file_name'], file['file_size']),
                    callback_data=f"{pre}#{file['file_id']}"
                )
            ]
            for file in files
        ]
        btn.insert(0, 
            [
                InlineKeyboardButton(f'🎚 Quality', callback_data=f"qualities#{key}"),
                InlineKeyboardButton('ℹ Info', url='https://t.me/moovidex/11'),
               # InlineKeyboardButton("📺 ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}"),
                InlineKeyboardButton("🗃 Seasons",  callback_data=f"seasons#{key}")
            ]
        )
        btn.insert(0, [
            InlineKeyboardButton(f"🗂 Files: {total_results_str}" , 'total'),
           # InlineKeyboardButton("🔮 sᴇɴᴅ ᴀʟʟ", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("🎧 Languages", callback_data=f"languages#{key}")
           # InlineKeyboardButton("🗓️ ʏᴇᴀʀs", callback_data=f"years#{key}")
        ])
    else:
        btn = []
        btn.insert(0, 
            [
                InlineKeyboardButton(f'🎚 Quality', callback_data=f"qualities#{key}"),
                InlineKeyboardButton('ℹ Info', url='https://t.me/moovidex/11'),
             #   InlineKeyboardButton("📺 ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}"),
                InlineKeyboardButton("🗃 Seasons",  callback_data=f"seasons#{key}")
            ]
        )
        btn.insert(0, [
            InlineKeyboardButton(f"🗂 Files: {total_results_str}" , 'total'),
            
          #  InlineKeyboardButton("🔮 sᴇɴᴅ ᴀʟʟ", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("🎧 Languages", callback_data=f"languages#{key}")
           # InlineKeyboardButton("🗓️ ʏᴇᴀʀs", callback_data=f"years#{key}")
        ])
    offset = 0

    btn.append([
            InlineKeyboardButton(
                text="◀ Back To Files",
                callback_data=f"next_{req}_{key}_{offset}"
                ),
    ])
    
    if not settings["button"]:
        cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
        remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
        total_results = len(files)
        cap = await get_cap(settings, remaining_seconds, files, query, total_results, search)
        try:
            await query.message.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
        except MessageNotModified:
            pass
    else:
        try:
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
        except MessageNotModified:
            pass
    await query.answer()

@Client.on_callback_query(filters.regex(r"^qualities#"))
async def qualities_cb_handler(client: Client, query: CallbackQuery):

    try:
        if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ Hello {query.from_user.first_name},\n🎬 Only the person who requested this can change quality.",
                show_alert=False,
            )
    except:
        pass
    _, key = query.data.split("#")
    search = FRESH.get(key)
    try:
        search = search.replace(' ', '_')
    except:
        pass
    btn = []
    for i in range(0, len(QUALITIES)-1, 2):
        btn.append([
            InlineKeyboardButton(
                text=QUALITIES[i].title(),
                callback_data=f"fl#{QUALITIES[i].lower()}#{key}"
            ),
            InlineKeyboardButton(
                text=QUALITIES[i+1].title(),
                callback_data=f"fl#{QUALITIES[i+1].lower()}#{key}"
            ),
        ])

    btn.insert(
        0,
        [
            InlineKeyboardButton(
                text="⚙ Select The Quality", callback_data="ident"
            )
        ],
    )
    req = query.from_user.id
    offset = 0
    btn.append([InlineKeyboardButton(text="◀ Back To Files", callback_data=f"fl#homepage#{key}")])

    await query.edit_message_reply_markup(InlineKeyboardMarkup(btn))
    

@Client.on_callback_query(filters.regex(r"^fl#"))
async def filter_qualities_cb_handler(client: Client, query: CallbackQuery):
    _, qual, key = query.data.split("#")
    search = FRESH.get(key)
    try:
        search = search.replace(' ', '_')
    except:
        pass
    baal = qual in search
    if baal:
        search = search.replace(qual, "")
    else:
        search = search
    req = query.from_user.id
    chat_id = query.message.chat.id
    message = query.message
    try:
        if int(req) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ Hello {query.from_user.first_name},\n🎬 Only the person who requested this can change quality.",
                show_alert=False,
            )
    except:
        pass
    searchagain = search
    if lang != "homepage":
        search = f"{search} {qual}" 
    BUTTONS[key] = search

    files, offset, total_results = await get_search_results(chat_id, search, offset=0, filter=True)
    # files = [file for file in files if re.search(lang, file["file_name"], re.IGNORECASE)]
    if not files:
        await query.answer("🚫 𝗡𝗼 𝗙𝗶𝗹𝗲 𝗪𝗲𝗿𝗲 𝗙𝗼𝘂𝗻𝗱 🚫", show_alert=1)
        return
    temp.GETALL[key] = files
    total_results_str = len(files)
    settings = await get_settings(message.chat.id)
    pre = 'filep' if settings['file_secure'] else 'file'
    if settings["button"]:
        btn = [
            [
                InlineKeyboardButton(
                    text=extract_shortdetails(file['file_name'], file['file_size']),
                    callback_data=f"{pre}#{file['file_id']}"
                ),
            ]
            for file in files
        ]
        btn.insert(0, 
            [
                InlineKeyboardButton(f'🎚 Quality', callback_data=f"qualities#{key}"),
                InlineKeyboardButton('ℹ Info', url='https://t.me/moovidex/11'),
               # InlineKeyboardButton("📺 ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}"),
                InlineKeyboardButton("🗃 Seasons",  callback_data=f"seasons#{key}")
            ]
        )
        btn.insert(0, [
            InlineKeyboardButton(f"🗂 Files: {total_results_str}" , 'total'),
           # InlineKeyboardButton("🔮 sᴇɴᴅ ᴀʟʟ", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("🎧 Languages", callback_data=f"languages#{key}")
           # InlineKeyboardButton("🗓️ ʏᴇᴀʀs", callback_data=f"years#{key}")
        ])
    else:
        btn = []
        btn.insert(0, 
            [
                InlineKeyboardButton(f'🎚 Quality', callback_data=f"qualities#{key}"),
                InlineKeyboardButton('ℹ Info', url='https://t.me/moovidex/11'),
              #  InlineKeyboardButton("📺 ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}"),
                InlineKeyboardButton("🗃 Seasons",  callback_data=f"seasons#{key}")
            ]
        )
        btn.insert(0, [
            InlineKeyboardButton(f"🗂 Files: {total_results_str}" , 'total'),
           # InlineKeyboardButton("🔮 sᴇɴᴅ ᴀʟʟ", callback_data=f"sendfiles#{key}"),
            InlineKeyboardButton("🎧 Languages", callback_data=f"languages#{key}")
          #  InlineKeyboardButton("🗓️ ʏᴇᴀʀs", callback_data=f"years#{key}")
        ])

    if offset != "":
        try:
            if settings['max_btn']:
                btn.append(
                    [InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="ɴᴇxᴛ ⇛",callback_data=f"next_{req}_{key}_{offset}")]
                )
    
            else:
                btn.append(
                    [InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/int(MAX_B_TN))}",callback_data="pages"), InlineKeyboardButton(text="ɴᴇxᴛ ⇛",callback_data=f"next_{req}_{key}_{offset}")]
                )
        except KeyError:
            await save_group_settings(query.message.chat.id, 'max_btn', True)
            btn.append(
                [InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages"), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/10)}",callback_data="pages"), InlineKeyboardButton(text="ɴᴇxᴛ ⇛",callback_data=f"next_{req}_{key}_{offset}")]
            )
    else:
        btn.append(
            [InlineKeyboardButton(text="⛔ NO MORE PAGES AVAILABLE ⛔",callback_data="pages")]
        )
    if lang != "homepage":
        req = query.from_user.id
        offset = 0
        btn.append([InlineKeyboardButton(text="◀ Back To Files", callback_data=f"next_{req}_{key}_{offset}")])
    
    if not settings["button"]:
        cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
        remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
        total_results = len(files)
        cap = await get_cap(settings, remaining_seconds, files, query, total_results, search)
        try:
            await query.message.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
        except MessageNotModified:
            pass
    else:
        try:
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
        except MessageNotModified:
            pass

# --- Smart Filter Callbacks (Moved before cb_handler) ---

@Client.on_callback_query(filters.regex(r"^smart_lang"))
async def smart_lang_handler(client, query):
    try:
        if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
             return await query.answer(
                f"⚠️ Hello {query.from_user.first_name},\n🎬 Only the person who requested this can change options.",
                show_alert=True,
            )
    except:
        pass
    _, lang, key = query.data.split("#")
    
    # Retrieve all files for this query
    if key not in temp.GETALL:
        await query.answer("Search expired. Please search again.", show_alert=True)
        return
        
    all_files = temp.GETALL[key]
    
    # Filter by Language
    # Identify valid codes for this language
    valid_codes = [code for code, l in LANG_MAP.items() if l == lang]
    
    filtered_files = []
    for f in all_files:
        name = f['file_name'].lower()
        if any(code in name for code in valid_codes):
            filtered_files.append(f)
            
    # Fallback: strict name check if nothing found via codes (rare)
    if not filtered_files:
        filtered_files = [f for f in all_files if lang.lower() in f['file_name'].lower()]
    
    # Proceed to next check (Series/Season or Quality)
    analysis = analyze_query_results(filtered_files)
    
    if analysis['is_series'] and len(analysis['seasons']) > 0:
        btn = []
        row = []
        for season in analysis['seasons']:
            row.append(InlineKeyboardButton(f"📺 {season}", callback_data=f"smart_season#{season}#{key}#{lang}")) # Pass lang forward
            if len(row) == 3:
                btn.append(row)
                row = []
        if row:
            btn.append(row)
        btn.append([InlineKeyboardButton("Show All Episodes", callback_data=f"smart_default#{key}#{lang}")])
        btn.append([InlineKeyboardButton("⬅ Back to Languages", callback_data=f"languages#{key}")])
        
        await query.message.edit_text(
            f"**Selected Language: {lang}**\nFound {len(analysis['seasons'])} Seasons.\n\nSELECT SEASON:",
            reply_markup=InlineKeyboardMarkup(btn)
        )
    elif len(analysis['qualities']) > 1:
        # Quality check for movies
        btn = []
        row = []
        for qual in analysis['qualities']:
            row.append(InlineKeyboardButton(f"{qual}", callback_data=f"smart_quality#{qual}#{key}#{lang}"))
            if len(row) == 3:
                btn.append(row)
                row = []
        if row:
            btn.append(row)
        btn.append([InlineKeyboardButton("Show All Files", callback_data=f"smart_default#{key}#{lang}")])
        btn.append([InlineKeyboardButton("⬅ Back to Languages", callback_data=f"languages#{key}")])
        
        await query.message.edit_text(
            f"**Selected Language: {lang}**\nFound {len(filtered_files)} Files.\n\nSELECT QUALITY:",
            reply_markup=InlineKeyboardMarkup(btn)
        )
    else:
        # Show results directly
        await show_smart_results(client, query, filtered_files, key, f"Language: {lang}")

@Client.on_callback_query(filters.regex(r"^smart_season"))
async def smart_season_handler(client, query):
    try:
        if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
             return await query.answer(
                f"⚠️ Hello {query.from_user.first_name},\n🎬 Only the person who requested this can change options.",
                show_alert=True,
            )
    except:
        pass
    data_parts = query.data.split("#")
    season_str = data_parts[1] # "Season 1"
    key = data_parts[2]
    lang = data_parts[3] if len(data_parts) > 3 else None
    
    if key not in temp.GETALL:
        await query.answer("Search expired.", show_alert=True)
        return

    all_files = temp.GETALL[key]
    
    # Filter by Lang (if any) AND Season
    filtered_files = all_files
    if lang:
        valid_codes = [code for code, l in LANG_MAP.items() if l == lang]
        temp_files = []
        for f in filtered_files:
            if any(code in f['file_name'].lower() for code in valid_codes):
                temp_files.append(f)
        filtered_files = temp_files if temp_files else [f for f in filtered_files if lang.lower() in f['file_name'].lower()]
        
    season_num = season_str.split()[-1] # "1"
    # Match S1, S01, Season 1, Season 01
    # Use (?:\D|$) to match S01 in S01E01 (non-digit boundary) or end of string
    s_regex = re.compile(rf'(?i)(?:S0?{season_num}|Season\s?0?{season_num})(?:\D|$)')
    
    filtered_files = [f for f in filtered_files if s_regex.search(f['file_name'])]
    
    # Sort by Episode
    def ep_sort(f):
        # Find E01, Episode 1 etc
        match = re.search(r'(?i)(?:E|Episode\s?)(\d{1,3})', f['file_name'])
        if match:
            return int(match.group(1))
        return -1
        
    filtered_files.sort(key=ep_sort, reverse=True)
    
    # Back Callback: If lang was present, go back to Season List for that Lang.
    # If not, go back to Languages (if multilang) or main search?
    # Actually, smart_season_handler is entered from Season List (which is shown by smart_lang_handler or auto_filter).
    # If lang is present, smart_lang_handler showed the season list.
    # If lang is NOT present, auto_filter (or smart_default?) showed the season list.
    
    back_cb = f"smart_lang#{lang}#{key}" if lang else f"languages#{key}"

    await show_smart_results(client, query, filtered_files, key, f"{lang + ' | ' if lang else ''}{season_str}", back_cb=back_cb)

@Client.on_callback_query(filters.regex(r"^smart_quality"))
async def smart_quality_handler(client, query):
    try:
        if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
             return await query.answer(
                f"⚠️ Hello {query.from_user.first_name},\n🎬 Only the person who requested this can change options.",
                show_alert=True,
            )
    except:
        pass
    data_parts = query.data.split("#")
    qual = data_parts[1]
    key = data_parts[2]
    lang = data_parts[3] if len(data_parts) > 3 else None
    
    if key not in temp.GETALL:
        await query.answer("Search expired.", show_alert=True)
        return
        
    all_files = temp.GETALL[key]
    
    filtered_files = all_files
    if lang:
        valid_codes = [code for code, l in LANG_MAP.items() if l == lang]
        temp_files = []
        for f in filtered_files:
            if any(code in f['file_name'].lower() for code in valid_codes):
                temp_files.append(f)
        filtered_files = temp_files if temp_files else [f for f in filtered_files if lang.lower() in f['file_name'].lower()]
        
    filtered_files = [f for f in filtered_files if qual.lower() in f['file_name'].lower()]
    
    back_cb = f"smart_lang#{lang}#{key}" if lang else f"languages#{key}"

    await show_smart_results(client, query, filtered_files, key, f"{lang + ' | ' if lang else ''}{qual}", back_cb=back_cb)

@Client.on_callback_query(filters.regex(r"^smart_default"))
async def smart_default_handler(client, query):
    try:
        if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
             return await query.answer(
                f"⚠️ Hello {query.from_user.first_name},\n🎬 Only the person who requested this can change options.",
                show_alert=True,
            )
    except:
        pass
    data_parts = query.data.split("#")
    key = data_parts[1]
    lang = data_parts[2] if len(data_parts) > 2 else None
    
    if key not in temp.GETALL:
        await query.answer("Search expired.", show_alert=True)
        return
        
    all_files = temp.GETALL[key]
    if lang:
        valid_codes = [code for code, l in LANG_MAP.items() if l == lang]
        temp_files = []
        for f in all_files:
            if any(code in f['file_name'].lower() for code in valid_codes):
                temp_files.append(f)
        all_files = temp_files if temp_files else [f for f in all_files if lang.lower() in f['file_name'].lower()]
        
    back_cb = f"languages#{key}"

    await show_smart_results(client, query, all_files, key, f"{lang if lang else 'All Results'}", back_cb=back_cb)

@Client.on_callback_query(filters.regex(r"^smart_next"))
async def smart_next_page(bot, query):
    try:
        ident, req, key, offset = query.data.split("#")
    except ValueError:
        ident, req, key, offset = query.data.split("_")
    
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
        
    try:
        offset = int(offset)
    except:
        offset = 0
    
    # Use FILTERED if available, else GETALL, else None
    files = temp.FILTERED.get(key, temp.GETALL.get(key))
    
    if not files:
        await query.answer("Search expired. Please search again.", show_alert=True)
        return
        
    # Retrieve title from TITLES dict, fallback to "Results"
    title_extra = TITLES.get(key, "Results")

    await show_smart_results(bot, query, files, key, title_extra, offset=offset)

@Client.on_callback_query(filters.regex(r"^languages"))
async def languages_handler(client, query):
    try:
        key = query.data.split("#")[1]
    except IndexError:
        await query.answer("Invalid request", show_alert=True)
        return
        
    if key not in temp.GETALL:
        await query.answer("Search expired.", show_alert=True)
        return
        
    files = temp.GETALL[key]
    search = FRESH.get(key, "")
    
    # Re-analyze to show the orchestrator view (Language Picker)
    analysis = analyze_query_results(files)
    
    await search_orchestrator(client, query.message, files, key, search, analysis)

async def show_smart_results(client, query_or_msg, files, key, title_extra, offset=0, back_cb=None):
    if isinstance(query_or_msg, CallbackQuery):
        message = query_or_msg.message
        req_user_id = query_or_msg.from_user.id
    else:
        message = query_or_msg
        req_user_id = message.reply_to_message.from_user.id if message.reply_to_message else message.chat.id # Estimate
    
    settings = await get_settings(message.chat.id)
    pre = 'filep' if settings['file_secure'] else 'file'
    
    # Persist Back Callback
    if back_cb:
        temp.BACK_CB[key] = back_cb
    else:
        back_cb = temp.BACK_CB.get(key)
    
    # Slice for display
    total_results = len(files)
    
    # Save the current filtered files for pagination
    temp.FILTERED[key] = files

    if len(files) == 0:
        return await query_or_msg.edit_text(
            f"<b>⚠️ No filtered results found for {title_extra}!</b>", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=back_cb or f"spoll#{key}#{offset}")]])
        )

    # Calculate limits
    limit = int(MAX_B_TN) if not settings.get('max_btn') else 10
    
    # Slice list
    view_files = files[offset:offset+limit]
    
    if settings["button"]:
        btn = [
            [
                InlineKeyboardButton(
                    text=extract_shortdetails(file['file_name'], file['file_size']),
                    callback_data=f"{pre}#{file['file_id']}"
                ),
            ]
            for file in view_files
        ]
    else:
        btn = []
    
    # Update TITLES for context if this function is called directly first time
    if offset == 0:
         TITLES[key] = title_extra
         # Ensure we DO NOT overwrite FRESH[key] here!
    
    req = req_user_id
    
    # Pagination Buttons
    # Previous / Back
    nav_row = []
    if offset >= limit:
         nav_row.append(InlineKeyboardButton("◀ Back", callback_data=f"smart_next#{req}#{key}#{offset-limit}"))
         
    # Page Info
    nav_row.append(InlineKeyboardButton(f"{math.ceil((offset/limit)+1)} / {math.ceil(total_results/limit)}", callback_data="pages"))
    
    # Next
    if total_results > (offset + limit):
         nav_row.append(InlineKeyboardButton("Next ▶", callback_data=f"smart_next#{req}#{key}#{offset+limit}"))
         
    if nav_row:
        btn.append(nav_row)

    if back_cb:
        btn.append([InlineKeyboardButton("⬅ Back to Options", callback_data=back_cb)])

    # App-like Header
    cap = f"⚡️ <b>{title_extra}</b>\n\n📂 <b>Found {total_results} Files</b>"
    
    if settings["button"]:
        try:
            await message.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn))
        except (MessageNotModified, ValueError, BadRequest):
             pass # Ignore if unchanged or bad request
        except Exception as e:
             logger.error(f"Error in show_smart_results: {e}")
    else:
        for file in view_files:
            cap += f"\n📁 [{get_size(file['file_size'])}] {file['file_name']}"
        try:
            await message.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn))
        except (MessageNotModified, ValueError, BadRequest):
             pass
        except Exception as e:
             logger.error(f"Error in show_smart_results: {e}")

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    try:
        link = await client.create_chat_invite_link(int(REQST_CHANNEL))
    except:
        pass
    if query.data == "close_data":
        await query.message.delete()
    elif query.data == "get_trail":
        user_id = query.from_user.id
        free_trial_status = await db.get_free_trial_status(user_id)
        if not free_trial_status:            
            await db.give_free_trail(user_id)
            new_text = "**ʏᴏᴜ ᴄᴀɴ ᴜsᴇ ꜰʀᴇᴇ ᴛʀᴀɪʟ ꜰᴏʀ 5 ᴍɪɴᴜᴛᴇs ꜰʀᴏᴍ ɴᴏᴡ 😀\n\nआप अब से 5 मिनट के लिए निःशुल्क ट्रायल का उपयोग कर सकते हैं 😀**"        
            await query.message.edit_text(text=new_text)
            return
        else:
            new_text= "**🤣 you already used free now no more free trail. please buy subscription here are our 👉 /plans**"
            await query.message.edit_text(text=new_text)
            return
            
            
    elif query.data == "buy_premium":
        btn = [[            
            InlineKeyboardButton("✅sᴇɴᴅ ʏᴏᴜʀ ᴘᴀʏᴍᴇɴᴛ ʀᴇᴄᴇɪᴘᴛ ʜᴇʀᴇ ✅", url = OWNER_LINK)
        ]
            for admin in ADMINS
        ]
        btn.append(
            [InlineKeyboardButton("⚠️ᴄʟᴏsᴇ / ᴅᴇʟᴇᴛᴇ⚠️", callback_data="close_data")]
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.reply_photo(
            photo=PAYMENT_QR,
            caption=PAYMENT_TEXT,
            reply_markup=reply_markup
        )
        return 
    elif query.data == "gfiltersdeleteallconfirm":
        await del_allg(query.message, 'gfilters')
        await query.answer("Done !")
        return
    elif query.data == "gfiltersdeleteallcancel": 
        await query.message.reply_to_message.delete()
        await query.message.delete()
        await query.answer("Process Cancelled !")
        return
    elif query.data == "delallconfirm":
        userid = query.from_user.id
        chat_type = query.message.chat.type

        if chat_type == enums.ChatType.PRIVATE:
            grpid = await active_connection(str(userid))
            if grpid is not None:
                grp_id = grpid
                try:
                    chat = await client.get_chat(grpid)
                    title = chat.title
                except:
                    await query.message.edit_text("Mᴀᴋᴇ sᴜʀᴇ I'm ᴘʀᴇsᴇɴᴛ ɪɴ ʏᴏᴜʀ ɢʀᴏᴜᴘ!!", quote=True)
                    return await query.answer(MSG_ALRT)
            else:
                await query.message.edit_text(
                    "I'ᴍ ɴᴏᴛ ᴄᴏɴɴᴇᴄᴛᴇᴅ ᴛᴏ ᴀɴʏ ɢʀᴏᴜᴘs!\nCʜᴇᴄᴋ /connections ᴏʀ ᴄᴏɴɴᴇᴄᴛ ᴛᴏ ᴀɴʏ ɢʀᴏᴜᴘs",
                    quote=True
                )
                return await query.answer(MSG_ALRT)

        elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            grp_id = query.message.chat.id
            title = query.message.chat.title

        else:
            return await query.answer(MSG_ALRT)

        st = await client.get_chat_member(grp_id, userid)
        if (st.status == enums.ChatMemberStatus.OWNER) or (str(userid) in ADMINS):
            await del_all(query.message, grp_id, title)
        else:
            await query.answer("Yᴏᴜ ɴᴇᴇᴅ ᴛᴏ ʙᴇ Gʀᴏᴜᴘ Oᴡɴᴇʀ ᴏʀ ᴀɴ Aᴜᴛʜ Usᴇʀ ᴛᴏ ᴅᴏ ᴛʜᴀᴛ!", show_alert=True)
    elif query.data == "delallcancel":
        userid = query.from_user.id
        chat_type = query.message.chat.type

        if chat_type == enums.ChatType.PRIVATE:
            await query.message.reply_to_message.delete()
            await query.message.delete()

        elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            grp_id = query.message.chat.id
            st = await client.get_chat_member(grp_id, userid)
            if (st.status == enums.ChatMemberStatus.OWNER) or (str(userid) in ADMINS):
                await query.message.delete()
                try:
                    await query.message.reply_to_message.delete()
                except:
                    pass
            else:
                await query.answer("Tʜᴀᴛ's ɴᴏᴛ ғᴏʀ ʏᴏᴜ!!", show_alert=True)
    elif "groupcb" in query.data:
        await query.answer()

        group_id = query.data.split(":")[1]

        act = query.data.split(":")[2]
        hr = await client.get_chat(int(group_id))
        title = hr.title
        user_id = query.from_user.id

        if act == "":
            stat = "CONNECT"
            cb = "connectcb"
        else:
            stat = "DISCONNECT"
            cb = "disconnect"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{stat}", callback_data=f"{cb}:{group_id}"),
             InlineKeyboardButton("DELETE", callback_data=f"deletecb:{group_id}")],
            [InlineKeyboardButton("BACK", callback_data="backcb")]
        ])

        await query.message.edit_text(
            f"Gʀᴏᴜᴘ Nᴀᴍᴇ : **{title}**\nGʀᴏᴜᴘ ID : `{group_id}`",
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        return await query.answer(MSG_ALRT)
    elif "connectcb" in query.data:
        await query.answer()

        group_id = query.data.split(":")[1]

        hr = await client.get_chat(int(group_id))

        title = hr.title

        user_id = query.from_user.id

        mkact = await make_active(str(user_id), str(group_id))

        if mkact:
            await query.message.edit_text(
                f"Cᴏɴɴᴇᴄᴛᴇᴅ ᴛᴏ **{title}**",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await query.message.edit_text('Sᴏᴍᴇ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ!!', parse_mode=enums.ParseMode.MARKDOWN)
        return await query.answer(MSG_ALRT)
    elif "disconnect" in query.data:
        await query.answer()

        group_id = query.data.split(":")[1]

        hr = await client.get_chat(int(group_id))

        title = hr.title
        user_id = query.from_user.id

        mkinact = await make_inactive(str(user_id))

        if mkinact:
            await query.message.edit_text(
                f"Dɪsᴄᴏɴɴᴇᴄᴛᴇᴅ ғʀᴏᴍ **{title}**",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await query.message.edit_text(
                f"Sᴏᴍᴇ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ!!",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        return await query.answer(MSG_ALRT)
    elif "deletecb" in query.data:
        await query.answer()

        user_id = query.from_user.id
        group_id = query.data.split(":")[1]

        delcon = await delete_connection(str(user_id), str(group_id))

        if delcon:
            await query.message.edit_text(
                "Sᴜᴄᴄᴇssғᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ᴄᴏɴɴᴇᴄᴛɪᴏɴ !"
            )
        else:
            await query.message.edit_text(
                f"Sᴏᴍᴇ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ!!",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        return await query.answer(MSG_ALRT)
    elif query.data == "backcb":
        await query.answer()

        userid = query.from_user.id

        groupids = await all_connections(str(userid))
        if groupids is None:
            await query.message.edit_text(
                "Tʜᴇʀᴇ ᴀʀᴇ ɴᴏ ᴀᴄᴛɪᴠᴇ ᴄᴏɴɴᴇᴄᴛɪᴏɴs!! Cᴏɴɴᴇᴄᴛ ᴛᴏ sᴏᴍᴇ ɢʀᴏᴜᴘs ғɪʀsᴛ.",
            )
            return await query.answer(MSG_ALRT)
        buttons = []
        for groupid in groupids:
            try:
                ttl = await client.get_chat(int(groupid))
                title = ttl.title
                active = await if_active(str(userid), str(groupid))
                act = " - ACTIVE" if active else ""
                if len(languages) > 1:
                    btn = [
                        [
                            InlineKeyboardButton(
                                text=f"🔊 {lang.title()}",
                                callback_data=f"lang#{lang}#{key}"
                            ),
                        ]
                        for lang in languages
                    ]
                buttons.append(
                    [
                        InlineKeyboardButton(
                            text=f"{title}{act}", callback_data=f"groupcb:{groupid}:{act}"
                        )
                    ]
                )
            except:
                pass
        if buttons:
            await query.message.edit_text(
                "Yᴏᴜʀ ᴄᴏɴɴᴇᴄᴛᴇᴅ ɢʀᴏᴜᴘ ᴅᴇᴛᴀɪʟs ;\n\n",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
    elif "gfilteralert" in query.data:
        grp_id = query.message.chat.id
        i = query.data.split(":")[1]
        keyword = query.data.split(":")[2]
        reply_text, btn, alerts, fileid = await find_gfilter('gfilters', keyword)
        if alerts is not None:
            alerts = ast.literal_eval(alerts)
            alert = alerts[int(i)]
            alert = alert.replace("\\n", "\n").replace("\\t", "\t")
            await query.answer(alert, show_alert=True)
    
    elif "alertmessage" in query.data:
        grp_id = query.message.chat.id
        i = query.data.split(":")[1]
        keyword = query.data.split(":")[2]
        reply_text, btn, alerts, fileid = await find_filter(grp_id, keyword)
        if alerts is not None:
            alerts = ast.literal_eval(alerts)
            alert = alerts[int(i)]
            alert = alert.replace("\\n", "\n").replace("\\t", "\t")
            await query.answer(alert, show_alert=True)
        
    if query.data.startswith("file"):
        clicked = query.from_user.id
        try:
            typed = query.message.reply_to_message.from_user.id
        except:
            typed = query.from_user.id
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        if not files_:
            return await query.answer('Nᴏ sᴜᴄʜ ғɪʟᴇ ᴇxɪsᴛ.')
        files = files_
        title = files["file_name"]
        size = get_size(files["file_size"])
        f_caption = files["caption"]
        settings = await get_settings(query.message.chat.id)
        if CUSTOM_FILE_CAPTION:
            try:
                f_caption = CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title,
                                                       file_size='' if size is None else size,
                                                       file_caption='' if f_caption is None else f_caption)
            except Exception as e:
                logger.exception(e)
            f_caption = f_caption
        if f_caption is None:
            f_caption = f"{files['file_name']}"

        try:
            if settings['is_shortlink'] and not await db.has_premium_access(query.from_user.id):
                if clicked == typed:
                    temp.SHORT[clicked] = query.message.chat.id
                    await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=short_{file_id}")
                    return
                else:
                    await query.answer(f"Hᴇʏ {query.from_user.first_name}, Tʜɪs Is Nᴏᴛ Yᴏᴜʀ Mᴏᴠɪᴇ Rᴇǫᴜᴇsᴛ. Rᴇǫᴜᴇsᴛ Yᴏᴜʀ's !", show_alert=True)
            elif settings['is_shortlink'] and await db.has_premium_access(query.from_user.id):
                if clicked == typed:
                    await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start={ident}_{file_id}")
                    return
                else:
                    await query.answer(f"Hᴇʏ {query.from_user.first_name}, Tʜɪs Is Nᴏᴛ Yᴏᴜʀ Mᴏᴠɪᴇ Rᴇǫᴜᴇsᴛ. Rᴇǫᴜᴇsᴛ Yᴏᴜʀ's !", show_alert=True)
                    
            else:
                if clicked == typed:
                    await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start={ident}_{file_id}")
                    return
                else:
                    await query.answer(f"Hᴇʏ {query.from_user.first_name}, Tʜɪs Is Nᴏᴛ Yᴏᴜʀ Mᴏᴠɪᴇ Rᴇǫᴜᴇsᴛ. Rᴇǫᴜᴇsᴛ Yᴏᴜʀ's !", show_alert=True)
        except UserIsBlocked:
            await query.answer('Uɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ ᴍᴀʜɴ !', show_alert=True)
        except PeerIdInvalid:
            await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start={ident}_{file_id}")
        except Exception as e:
            await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start={ident}_{file_id}")
            
    elif query.data.startswith("sendfiles"):
        clicked = query.from_user.id
        ident, key = query.data.split("#")
        settings = await get_settings(query.message.chat.id)
        pre = 'allfilesp' if settings['file_secure'] else 'allfiles'
        try:
            if settings['is_shortlink'] and not await db.has_premium_access(query.from_user.id):
                await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=sendfiles1_{key}")
            elif settings['is_shortlink'] and await db.has_premium_access(query.from_user.id):
                await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start={pre}_{key}")
                return 
            else:
                await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start={pre}_{key}")
                
            
                
        except UserIsBlocked:
            await query.answer('Uɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ ᴍᴀʜɴ !', show_alert=True)
        except PeerIdInvalid:
            await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=sendfiles3_{key}")
        except Exception as e:
            logger.exception(e)
            await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=sendfiles4_{key}")

    elif query.data.startswith("unmuteme"):
        ident, userid = query.data.split("#")
        user_id = query.from_user.id
        settings = await get_settings(int(query.message.chat.id))
        if userid == 0:
            await query.answer("You are anonymous admin !", show_alert=True)
            return
        try:
            btn = await pub_is_subscribed(client, query, settings['fsub'])
            if btn:
                await query.answer("Kindly Join Given Channel Then Click On Unmute Button", show_alert=True)
            else:
                await client.unban_chat_member(query.message.chat.id, user_id)
                await query.answer("Unmuted Successfully !", show_alert=True)
                try:
                    await query.message.delete()
                except:
                    return
        except:
            await query.answer("Not For Your My Dear", show_alert=True)
   
    elif query.data.startswith("del"):
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        if not files_:
            return await query.answer('Nᴏ sᴜᴄʜ ғɪʟᴇ ᴇxɪsᴛ.')
        files = files_
        title = files['file_name']
        size = get_size(files['file_size'])
        f_caption = files['caption']
        settings = await get_settings(query.message.chat.id)
        if CUSTOM_FILE_CAPTION:
            try:
                f_caption = CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title,
                                                       file_size='' if size is None else size,
                                                       file_caption='' if f_caption is None else f_caption)
            except Exception as e:
                logger.exception(e)
            f_caption = f_caption
        if f_caption is None:
            f_caption = f"{files['file_name']}"
        await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=file_{file_id}")
    
    elif query.data.startswith("checksub"):
        if AUTH_CHANNEL and not await is_subscribed(client, query):
            await query.answer("Jᴏɪɴ ᴏᴜʀ Bᴀᴄᴋ-ᴜᴘ ᴄʜᴀɴɴᴇʟ ᴍᴀʜɴ! 😒", show_alert=True)
            return
        ident, kk, file_id = query.data.split("#")
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start={kk}_{file_id}")
    
    elif query.data == "pages":
        await query.answer()
    
    elif query.data.startswith("send_fsall"):
        temp_var, ident, key, offset = query.data.split("#")
        search = BUTTON0.get(key)
     #   if not search:
      #      await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name),show_alert=True)
      #      return
        files, n_offset, total = await get_search_results(query.message.chat.id, search, offset=int(offset), filter=True)
        await send_all(client, query.from_user.id, files, ident, query.message.chat.id, query.from_user.first_name, query)
        search = BUTTONS1.get(key)
        files, n_offset, total = await get_search_results(query.message.chat.id, search, offset=int(offset), filter=True)
        await send_all(client, query.from_user.id, files, ident, query.message.chat.id, query.from_user.first_name, query)
        search = BUTTONS2.get(key)
        files, n_offset, total = await get_search_results(query.message.chat.id, search, offset=int(offset), filter=True)
        await send_all(client, query.from_user.id, files, ident, query.message.chat.id, query.from_user.first_name, query)
        await query.answer(f"Hey {query.from_user.first_name}, All files on this page has been sent successfully to your PM !", show_alert=True)
        
    elif query.data.startswith("send_fall"):
        temp_var, ident, key, offset = query.data.split("#")
        search = FRESH.get(key)
     #   if not search:
       #     await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name),show_alert=True)
      #      return
        files, n_offset, total = await get_search_results(query.message.chat.id, search, offset=int(offset), filter=True)
        await send_all(client, query.from_user.id, files, ident, query.message.chat.id, query.from_user.first_name, query)
        await query.answer(f"Hey {query.from_user.first_name}, All files on this page has been sent successfully to your PM !", show_alert=True)
        
    elif query.data.startswith("killfilesdq"):
        ident, keyword = query.data.split("#")
        #await query.message.edit_text(f"<b>Fetching Files for your query {keyword} on DB... Please wait...</b>")
        files, total = await get_bad_files(keyword)
        await query.message.edit_text("<b>File deletion process will start in 5 seconds !</b>")
        await asyncio.sleep(5)
        deleted = 0
        async with lock:
            try:
                for file in files:
                    file_ids = file["file_id"]
                    file_name = file["file_name"]
                    result = col.delete_one({
                        'file_id': file_ids,
                    })
                    if not result.deleted_count:
                        result = sec_col.delete_one({
                            'file_id': file_ids,
                        })
                    if result.deleted_count:
                        logger.info(f'File Found for your query {keyword}! Successfully deleted {file_name} from database.')
                    deleted += 1
                    if deleted % 50 == 0:
                        await query.message.edit_text(f"<b>Process started for deleting files from DB. Successfully deleted {str(deleted)} files from DB for your query {keyword} !\n\nPlease wait...</b>")
            except Exception as e:
                logger.exception(e)
                await query.message.edit_text(f'Error: {e}')
            else:
                await query.message.edit_text(f"<b>Process Completed for file deletion !\n\nSuccessfully deleted {str(deleted)} files from database for your query {keyword}.</b>")
    
    elif query.data.startswith("opnsetgrp"):
        ident, grp_id = query.data.split("#")
        userid = query.from_user.id if query.from_user else None
        st = await client.get_chat_member(grp_id, userid)
        if (
                st.status != enums.ChatMemberStatus.ADMINISTRATOR
                and st.status != enums.ChatMemberStatus.OWNER
                and str(userid) not in ADMINS
        ):
            await query.answer("Yᴏᴜ Dᴏɴ'ᴛ Hᴀᴠᴇ Tʜᴇ Rɪɢʜᴛs Tᴏ Dᴏ Tʜɪs !", show_alert=True)
            return
        title = query.message.chat.title
        settings = await get_settings(grp_id)
        if settings is not None:
            buttons = [
                [
                    InlineKeyboardButton('Rᴇsᴜʟᴛ Pᴀɢᴇ',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}'),
                    InlineKeyboardButton('Bᴜᴛᴛᴏɴ' if settings["button"] else 'Tᴇxᴛ',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Pʀᴏᴛᴇᴄᴛ Cᴏɴᴛᴇɴᴛ',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Oɴ' if settings["file_secure"] else '❌ Oғғ',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Iᴍᴅʙ', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Oɴ' if settings["imdb"] else '❌ Oғғ',
                                         callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Sᴘᴇʟʟ Cʜᴇᴄᴋ',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Oɴ' if settings["spell_check"] else '❌ Oғғ',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Wᴇʟᴄᴏᴍᴇ Msɢ', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Oɴ' if settings["welcome"] else '❌ Oғғ',
                                         callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Aᴜᴛᴏ-Dᴇʟᴇᴛᴇ',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}'),
                    InlineKeyboardButton('5 Mɪɴs' if settings["auto_delete"] else '❌ Oғғ',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Aᴜᴛᴏ-Fɪʟᴛᴇʀ',
                                         callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Oɴ' if settings["auto_ffilter"] else '❌ Oғғ',
                                         callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Mᴀx Bᴜᴛᴛᴏɴs',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}'),
                    InlineKeyboardButton('10' if settings["max_btn"] else f'{MAX_B_TN}',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('SʜᴏʀᴛLɪɴᴋ',
                                         callback_data=f'setgs#is_shortlink#{settings["is_shortlink"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Oɴ' if settings["is_shortlink"] else '❌ Oғғ',
                                         callback_data=f'setgs#is_shortlink#{settings["is_shortlink"]}#{str(grp_id)}')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.message.edit_text(
                text=f"<b>Cʜᴀɴɢᴇ Yᴏᴜʀ Sᴇᴛᴛɪɴɢs Fᴏʀ {title} As Yᴏᴜʀ Wɪsʜ ⚙</b>",
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.HTML
            )
            await query.message.edit_reply_markup(reply_markup)
        
    elif query.data.startswith("opnsetpm"):
        ident, grp_id = query.data.split("#")
        userid = query.from_user.id if query.from_user else None
        st = await client.get_chat_member(grp_id, userid)
        if (
                st.status != enums.ChatMemberStatus.ADMINISTRATOR
                and st.status != enums.ChatMemberStatus.OWNER
                and str(userid) not in ADMINS
        ):
            await query.answer("Yᴏᴜ Dᴏɴ'ᴛ Hᴀᴠᴇ Tʜᴇ Rɪɢʜᴛs Tᴏ Dᴏ Tʜɪs !", show_alert=True)
            return
        title = query.message.chat.title
        settings = await get_settings(grp_id)
        btn2 = [[
                 InlineKeyboardButton("Cʜᴇᴄᴋ PM", url=f"telegram.me/{temp.U_NAME}")
               ]]
        reply_markup = InlineKeyboardMarkup(btn2)
        await query.message.edit_text(f"<b>Yᴏᴜʀ sᴇᴛᴛɪɴɢs ᴍᴇɴᴜ ғᴏʀ {title} ʜᴀs ʙᴇᴇɴ sᴇɴᴛ ᴛᴏ ʏᴏᴜʀ PM</b>")
        await query.message.edit_reply_markup(reply_markup)
        if settings is not None:
            buttons = [
                [
                    InlineKeyboardButton('Rᴇsᴜʟᴛ Pᴀɢᴇ',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}'),
                    InlineKeyboardButton('Bᴜᴛᴛᴏɴ' if settings["button"] else 'Tᴇxᴛ',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Pʀᴏᴛᴇᴄᴛ Cᴏɴᴛᴇɴᴛ',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Oɴ' if settings["file_secure"] else '❌ Oғғ',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Iᴍᴅʙ', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Oɴ' if settings["imdb"] else '❌ Oғғ',
                                         callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Sᴘᴇʟʟ Cʜᴇᴄᴋ',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Oɴ' if settings["spell_check"] else '❌ Oғғ',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Wᴇʟᴄᴏᴍᴇ Msɢ', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Oɴ' if settings["welcome"] else '❌ Oғғ',
                                         callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Aᴜᴛᴏ-Dᴇʟᴇᴛᴇ',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}'),
                    InlineKeyboardButton('5 Mɪɴs' if settings["auto_delete"] else '❌ Oғғ',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Aᴜᴛᴏ-Fɪʟᴛᴇʀ',
                                         callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Oɴ' if settings["auto_ffilter"] else '❌ Oғғ',
                                         callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Mᴀx Bᴜᴛᴛᴏɴs',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}'),
                    InlineKeyboardButton('10' if settings["max_btn"] else f'{MAX_B_TN}',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('SʜᴏʀᴛLɪɴᴋ',
                                         callback_data=f'setgs#is_shortlink#{settings["is_shortlink"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Oɴ' if settings["is_shortlink"] else '❌ Oғғ',
                                         callback_data=f'setgs#is_shortlink#{settings["is_shortlink"]}#{str(grp_id)}')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            await client.send_message(
                chat_id=userid,
                text=f"<b>Cʜᴀɴɢᴇ Yᴏᴜʀ Sᴇᴛᴛɪɴɢs Fᴏʀ {title} As Yᴏᴜʀ Wɪsʜ ⚙</b>",
                reply_markup=reply_markup,
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.HTML,
                reply_to_message_id=query.message.id
            )

    elif query.data.startswith("show_option"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("Uɴᴀᴠᴀɪʟᴀʙʟᴇ", callback_data=f"unavailable#{from_user}"),
                InlineKeyboardButton("Uᴘʟᴏᴀᴅᴇᴅ", callback_data=f"hfiadded#{from_user}")
             ],[
                InlineKeyboardButton("Aʟʀᴇᴀᴅʏ Aᴠᴀɪʟᴀʙʟᴇ", callback_data=f"already_available#{from_user}")
              ]]
        btn2 = [[
                 InlineKeyboardButton("Vɪᴇᴡ Sᴛᴀᴛᴜs", url=f"{query.message.link}")
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Hᴇʀᴇ ᴀʀᴇ ᴛʜᴇ ᴏᴘᴛɪᴏɴs !")
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢʜᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)
        
    elif query.data.startswith("unavailable"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("⚠️ Uɴᴀᴠᴀɪʟᴀʙʟᴇ ⚠️", callback_data=f"unalert#{from_user}")
              ]]
        btn2 = [[
                 #InlineKeyboardButton('Jᴏɪɴ Cʜᴀɴɴᴇʟ', url=link.invite_link),
                 InlineKeyboardButton("Vɪᴇᴡ Sᴛᴀᴛᴜs", url=f"{query.message.link}")
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b>⛔ {content}</b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Sᴇᴛ ᴛᴏ Uɴᴀᴠᴀɪʟᴀʙʟᴇ !")
            try:
                await client.send_message(chat_id=int(from_user), text=f"<b>Hᴇʏ {user.mention}, Sᴏʀʀʏ Yᴏᴜʀ ʀᴇᴏ̨ᴜᴇsᴛ ɪs ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ. Sᴏ ᴏᴜʀ ᴍᴏᴅᴇʀᴀᴛᴏʀs ᴄᴀɴ'ᴛ ᴜᴘʟᴏᴀᴅ ɪᴛ.</b>", reply_markup=InlineKeyboardMarkup(btn2))
            except UserIsBlocked:
                await client.send_message(chat_id=int(SUPPORT_CHAT_ID), text=f"<b>Hᴇʏ {user.mention}, Sᴏʀʀʏ Yᴏᴜʀ ʀᴇᴏ̨ᴜᴇsᴛ ɪs ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ. Sᴏ ᴏᴜʀ ᴍᴏᴅᴇʀᴀᴛᴏʀs ᴄᴀɴ'ᴛ ᴜᴘʟᴏᴀᴅ ɪᴛ.\n\nNᴏᴛᴇ: Tʜɪs ᴍᴇssᴀɢᴇ ɪs sᴇɴᴛ ᴛᴏ ᴛʜɪs ɢʀᴏᴜᴘ ʙᴇᴄᴀᴜsᴇ ʏᴏᴜ'ᴠᴇ ʙʟᴏᴄᴋᴇᴅ ᴛʜᴇ ʙᴏᴛ. Tᴏ sᴇɴᴅ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴛᴏ ʏᴏᴜʀ PM, Mᴜsᴛ ᴜɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ.</b>", reply_markup=InlineKeyboardMarkup(btn2))
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢʜᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)

    elif query.data.startswith("hfiadded"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("✅ Uᴘʟᴏᴀᴅᴇᴅ ✅", callback_data=f"upalert#{from_user}")
              ]]
        btn2 = [[
                # InlineKeyboardButton('Jᴏɪɴ Cʜᴀɴɴᴇʟ', url=link.invite_link),
                 InlineKeyboardButton("Vɪᴇᴡ Sᴛᴀᴛᴜs", url=f"{query.message.link}")
               ],[
                 InlineKeyboardButton("🔎 ꜱᴇᴀʀᴄʜ ʜᴇʀᴇ", url=f"{GRP_LNK}")
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b> ✅ {content} </b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Sᴇᴛ ᴛᴏ Uᴘʟᴏᴀᴅᴇᴅ !")
            try:
                await client.send_message(chat_id=int(from_user), text=f"<b>Hᴇʏ {user.mention}, Yᴏᴜʀ ʀᴇᴏ̨ᴜᴇsᴛ ʜᴀs ʙᴇᴇɴ ᴜᴘʟᴏᴀᴅᴇᴅ ʙʏ ᴏᴜʀ ᴍᴏᴅᴇʀᴀᴛᴏʀs. Kɪɴᴅʟʏ sᴇᴀʀᴄʜ ɪɴ ᴏᴜʀ Gʀᴏᴜᴘ.</b>", reply_markup=InlineKeyboardMarkup(btn2))
            except UserIsBlocked:
                await client.send_message(chat_id=int(SUPPORT_CHAT_ID), text=f"<b>Hᴇʏ {user.mention}, Yᴏᴜʀ ʀᴇᴏ̨ᴜᴇsᴛ ʜᴀs ʙᴇᴇɴ ᴜᴘʟᴏᴀᴅᴇᴅ ʙʏ ᴏᴜʀ ᴍᴏᴅᴇʀᴀᴛᴏʀs. Kɪɴᴅʟʏ sᴇᴀʀᴄʜ ɪɴ ᴏᴜʀ Gʀᴏᴜᴘ.\n\nNᴏᴛᴇ: Tʜɪs ᴍᴇssᴀɢᴇ ɪs sᴇɴᴛ ᴛᴏ ᴛʜɪs ɢʀᴏᴜᴘ ʙᴇᴄᴀᴜsᴇ ʏᴏᴜ'ᴠᴇ ʙʟᴏᴄᴋᴇᴅ ᴛʜᴇ ʙᴏᴛ. Tᴏ sᴇɴᴅ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴛᴏ ʏᴏᴜʀ PM, Mᴜsᴛ ᴜɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ.</b>", reply_markup=InlineKeyboardMarkup(btn2))
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)

    elif query.data.startswith("already_available"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("🟢 Aʟʀᴇᴀᴅʏ Aᴠᴀɪʟᴀʙʟᴇ 🟢", callback_data=f"alalert#{from_user}")
              ]]
        btn2 = [[
                 #InlineKeyboardButton('Jᴏɪɴ Cʜᴀɴɴᴇʟ', url=link.invite_link),
                 InlineKeyboardButton("Vɪᴇᴡ Sᴛᴀᴛᴜs", url=f"{query.message.link}")
               ],[
                 InlineKeyboardButton("ꜱᴇᴀʀᴄʜ ʜᴇʀᴇ", url=f"{GRP_LNK}")
               ]]
        if query.from_user.id in ADMINS:
            user = await client.get_users(from_user)
            reply_markup = InlineKeyboardMarkup(btn)
            content = query.message.text
            await query.message.edit_text(f"<b>📁 {content}</b>")
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Sᴇᴛ ᴛᴏ Aʟʀᴇᴀᴅʏ Aᴠᴀɪʟᴀʙʟᴇ !")
            try:
                await client.send_message(chat_id=int(from_user), text=f"<b>Hᴇʏ {user.mention}, Yᴏᴜʀ ʀᴇᴏ̨ᴜᴇsᴛ ɪs ᴀʟʀᴇᴀᴅʏ ᴀᴠᴀɪʟᴀʙʟᴇ ᴏɴ ᴏᴜʀ ʙᴏᴛ's ᴅᴀᴛᴀʙᴀsᴇ. Kɪɴᴅʟʏ sᴇᴀʀᴄʜ ɪɴ ᴏᴜʀ Gʀᴏᴜᴘ.</b>", reply_markup=InlineKeyboardMarkup(btn2))
            except UserIsBlocked:
                await client.send_message(chat_id=int(SUPPORT_CHAT_ID), text=f"<b>Hᴇʏ {user.mention}, Yᴏᴜʀ ʀᴇᴏ̨ᴜᴇsᴛ ɪs ᴀʟʀᴇᴀᴅʏ ᴀᴠᴀɪʟᴀʙʟᴇ ᴏɴ ᴏᴜʀ ʙᴏᴛ's ᴅᴀᴛᴀʙᴀsᴇ. Kɪɴᴅʟʏ sᴇᴀʀᴄʜ ɪɴ ᴏᴜʀ Gʀᴏᴜᴘ.\n\nNᴏᴛᴇ: Tʜɪs ᴍᴇssᴀɢᴇ ɪs sᴇɴᴛ ᴛᴏ ᴛʜɪs ɢʀᴏᴜᴘ ʙᴇᴄᴀᴜsᴇ ʏᴏᴜ'ᴠᴇ ʙʟᴏᴄᴋᴇᴅ ᴛʜᴇ ʙᴏᴛ. Tᴏ sᴇɴᴅ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴛᴏ ʏᴏᴜʀ PM, Mᴜsᴛ ᴜɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ.</b>", reply_markup=InlineKeyboardMarkup(btn2))
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)

    elif query.data.startswith("alalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(f"Hᴇʏ {user.first_name}, Yᴏᴜʀ Rᴇᴏ̨ᴜᴇsᴛ ɪs Aʟʀᴇᴀᴅʏ Aᴠᴀɪʟᴀʙʟᴇ !", show_alert=True)
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)

    elif query.data.startswith("upalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(f"Hᴇʏ {user.first_name}, Yᴏᴜʀ Rᴇᴏ̨ᴜᴇsᴛ ɪs Uᴘʟᴏᴀᴅᴇᴅ !", show_alert=True)
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)
        
    elif query.data.startswith("unalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(f"Hᴇʏ {user.first_name}, Yᴏᴜʀ Rᴇᴏ̨ᴜᴇsᴛ ɪs Uɴᴀᴠᴀɪʟᴀʙʟᴇ !", show_alert=True)
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)

    elif query.data.startswith("generate_stream_link"):
        _, file_id = query.data.split(":")
        try:
            log_msg = await client.send_cached_media(chat_id=STREAM_FILES_CHANNEL, file_id=file_id)
            fileName = {quote_plus(get_name(log_msg))}
            stream = f"{URL}watch/{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
            download = f"{URL}watch/{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
            button = [[
                InlineKeyboardButton("📥 Download ", url=download),
                InlineKeyboardButton('📤 Share', url=f'https://t.me/share/url?url={stream}')
            ],[
                InlineKeyboardButton("📱 Open in Telegram", web_app=WebAppInfo(url=stream))
            ]]
            await query.message.edit_reply_markup(InlineKeyboardMarkup(button))
        except Exception as e:
            print(e)
            await query.answer(f"something went wrong\n\n{e}", show_alert=True)
            return
    
    elif query.data == "reqinfo":
        await query.answer(text=script.REQINFO, show_alert=True)

    elif query.data == "select":
        await query.answer(text=script.SELECT, show_alert=True)

    elif query.data == "sinfo":
        await query.answer(text=script.SINFO, show_alert=True)

    elif query.data == "start":
        if PREMIUM_AND_REFERAL_MODE == True:
            buttons = [[
                InlineKeyboardButton('🔗 Add To Your Group', url=f'http://t.me/{temp.U_NAME}?startgroup=true')
            ],[
                InlineKeyboardButton('📈 Top Search', callback_data='mostsearch'),
                InlineKeyboardButton('🎬 New Releases', callback_data='latest')
            ],[
                InlineKeyboardButton('🔎 Search', switch_inline_query_current_chat=''),
                InlineKeyboardButton('🍿 Ott Updates', callback_data='ott_platform')
            ],
             [
                InlineKeyboardButton('⚠ Disclaimer', callback_data='disclaimer')
            ]]
        else:
            buttons = [[
                InlineKeyboardButton('🔗 Add To Your Group', url=f'http://t.me/{temp.U_NAME}?startgroup=true')
            ],[
                InlineKeyboardButton('📈 Top Search', callback_data='mostsearch'),
                InlineKeyboardButton('🎬 New Releases', callback_data='latest')
            ],
                
                
            [
                InlineKeyboardButton('⚠ Disclaimer', callback_data='disclaimer')
            ]]


        reply_markup = InlineKeyboardMarkup(buttons)
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        await query.message.edit_text(
            text=script.START_TXT.format(query.from_user.mention, get_wish()),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        await query.answer(MSG_ALRT)

    elif query.data == "clone":
        user_id = query.from_user.id

        # Check if the user has premium access
        if await db.has_premium_access(user_id):
            buttons = [[
                InlineKeyboardButton('◀ Back', callback_data='start')
            ]]

            await client.edit_message_media(
                chat_id=query.message.chat.id,
                message_id=query.message.id,
                media=InputMediaPhoto(random.choice(PICS))
            )
        
            reply_markup = InlineKeyboardMarkup(buttons)
        
            await query.message.edit_text(
                text=script.CLONE_TXT,
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
            )
        else:
        # If the user doesn't have premium access, show an alert
            await query.answer("🛒 ʙᴜʏ ᴘʀᴇᴍɪᴜᴍ ᴛᴏ ᴜsᴇ ᴛʜɪs ғᴇᴀᴛᴜʀᴇ! 💳", show_alert=True)

    elif query.data == "filters":
        buttons = [[
            InlineKeyboardButton('Mᴀɴᴜᴀʟ FIʟᴛᴇʀ', callback_data='manuelfilter'),
            InlineKeyboardButton('Aᴜᴛᴏ FIʟᴛᴇʀ', callback_data='autofilter')
        ],[
            InlineKeyboardButton('◀ Back', callback_data='help'),
            InlineKeyboardButton('Gʟᴏʙᴀʟ Fɪʟᴛᴇʀs', callback_data='global_filters')
        ]]
        
        reply_markup = InlineKeyboardMarkup(buttons)
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        await query.message.edit_text(
            text=script.ALL_FILTERS.format(query.from_user.mention),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )

    elif query.data == "global_filters":
        buttons = [[
            InlineKeyboardButton('◀ Back', callback_data='filters')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.GFILTER_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    
    elif query.data == "help":
        buttons = [
            [
                InlineKeyboardButton('⚙️ ᴀᴅᴍɪɴ ᴏɴʟʏ 🔧', callback_data='admin'),
            ], 
            [ 
                InlineKeyboardButton('✏️ ʀᴇɴᴀᴍᴇ', callback_data='r_txt'),   
                InlineKeyboardButton('🔗 ғɪʟᴇ ᴛᴏ ʟɪɴᴋ', callback_data='s_txt') 
            ], 
            [ 
                InlineKeyboardButton('🗃️ ꜰɪʟᴇ ꜱᴛᴏʀᴇ', callback_data='store_file'),   
                InlineKeyboardButton('📰 ᴛᴇʟᴇɢʀᴀᴘʜ', callback_data='tele') 
            ], 
            [ 
                InlineKeyboardButton('🖇️ ᴄᴏɴɴᴇᴄᴛɪᴏɴꜱ', callback_data='coct'), 
                InlineKeyboardButton('🛗 ꜰɪʟᴛᴇʀꜱ', callback_data='filters')
            ], 
            [
                InlineKeyboardButton('📥 ʏᴛ ᴅᴏᴡɴʟᴏᴀᴅ', callback_data='ytdl'), 
                InlineKeyboardButton('📮 ꜱʜᴀʀᴇ ᴛᴇxᴛ', callback_data='share')
            ], 
            [
                InlineKeyboardButton('🎵 ꜱᴏɴɢ', callback_data='song'),
                InlineKeyboardButton('💸 ᴇᴀʀɴ ᴍᴏɴᴇʏ', callback_data='shortlink_info')
            ], 
            [
                InlineKeyboardButton('📇 ꜱᴛɪᴄᴋᴇʀ-ɪᴅ', callback_data='sticker'),
                InlineKeyboardButton('📝 ᴊ-ꜱᴏɴ', callback_data='json')
            ], 
            [             
                InlineKeyboardButton('🏠 ʜᴏᴍᴇ 🏠', callback_data='start')
            ]
        ]

        if CLONE_MODE:
            buttons.append([InlineKeyboardButton('🤖 Cʀᴇᴀᴛᴇ Yᴏᴜʀ Oᴡɴ Cʟᴏɴᴇ Bᴏᴛ 🤖', callback_data='clone')])

        reply_markup = InlineKeyboardMarkup(buttons)
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        await query.message.edit_text(
            text=script.HELP_TXT.format(query.from_user.mention),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "about":
        buttons = [[
            InlineKeyboardButton('Sᴜᴘᴘᴏʀᴛ Gʀᴏᴜᴘ', url=GRP_LNK),
            InlineKeyboardButton('Sᴏᴜʀᴄᴇ Cᴏᴅᴇ', url="https://github.com/VJBots/VJ-FILTER-BOT")
        ],[
            InlineKeyboardButton('Hᴏᴍᴇ', callback_data='start'),
            InlineKeyboardButton('Cʟᴏsᴇ', callback_data='close_data')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.ABOUT_TXT.format(temp.U_NAME, temp.B_NAME, OWNER_LNK),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "subscription":
        user_id = query.from_user.id  # Correctly fetching the user ID
        try:
            if await db.has_premium_access(user_id):
                
                
                buttons = [
                    [InlineKeyboardButton('◀ Back', callback_data='start')]
                ]
                reply_markup = InlineKeyboardMarkup(buttons)

            # Edit the media first
                await client.edit_message_media(
                    chat_id=query.message.chat.id, 
                    message_id=query.message.id, 
                    media=InputMediaPhoto(random.choice(PICS))
                )

                # Then edit the text
                await query.message.edit_text(
                    text=f"👑 <b>ʏᴏᴜ ᴀʀᴇ ᴀ ᴘʀᴇᴍɪᴜᴍ sᴜʙsᴄʀɪʙᴇʀ</b> 👑\n\n"
                         f"<b>ᴛᴏ ᴋɴᴏᴡ ʏᴏᴜʀ ᴘʟᴀɴ ᴠᴀʟɪᴅɪᴛʏ : /myplan</b>\n\n",
                    reply_markup=reply_markup,
                    parse_mode=enums.ParseMode.HTML
                )
            else:
                buttons = [
                    [InlineKeyboardButton('🎁 ɪɴᴠɪᴛᴇ & ɢᴇᴛ ᴘʀᴇᴍɪᴜᴍ 🎁', url=f'https://telegram.me/share/url?url=https://telegram.me/{temp.U_NAME}?start=VJ-{user_id}')],
                    [InlineKeyboardButton("💸 ʙᴜʏ ᴘʀᴇᴍɪᴜᴍ", callback_data="buy_premium")],
                    [InlineKeyboardButton('', callback_data='start')]
                ]
                reply_markup = InlineKeyboardMarkup(buttons)

                # Edit the media first
                await client.edit_message_media(
                    chat_id=query.message.chat.id, 
                    message_id=query.message.id, 
                    media=InputMediaPhoto(random.choice(PICS))
                )

            # Then edit the text
                await query.message.edit_text(
                    text=script.SUBSCRIPTION_TXT.format(REFERAL_PREMEIUM_TIME, temp.U_NAME, query.from_user.id, REFERAL_COUNT),
                    reply_markup=reply_markup,
                    parse_mode=enums.ParseMode.HTML
                )
        except Exception as e:
            await query.message.reply_text(f"An error occurred: {str(e)}")
    elif query.data == "manuelfilter":
        buttons = [[
            InlineKeyboardButton('◀ Back', callback_data='filters'),
            InlineKeyboardButton('Bᴜᴛᴛᴏɴs', callback_data='button')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        await query.message.edit_text(
            text=script.MANUELFILTER_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "button":
        buttons = [[
            InlineKeyboardButton('◀ Back', callback_data='manuelfilter')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.BUTTON_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "autofilter":
        buttons = [[
            InlineKeyboardButton('◀ Back', callback_data='filters')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.AUTOFILTER_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "coct":
        buttons = [[
            InlineKeyboardButton('◀ Back', callback_data='help')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.CONNECTION_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "admin":
        if query.from_user.id in ADMINS:
            buttons = [[
                InlineKeyboardButton('⟸ Bᴀᴄᴋ', callback_data='help'),
                InlineKeyboardButton('ᴇxᴛʀᴀ', callback_data='extra')
            ]]
            await client.edit_message_media(
                query.message.chat.id, 
                query.message.id, 
                InputMediaPhoto(random.choice(PICS))
            )
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.message.edit_text(
                text=script.ADMIN_TXT,
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
            )
            #await handle_admin_button(query.data)
        else:
            await query.answer("⚙️ Yᴏᴜ ᴅᴏɴᴛ ʜᴀᴠᴇ ᴀᴄᴄᴇss ᴛᴏ ᴛʜɪs sᴇᴛᴛɪɴɢs!", show_alert=True)
            
    elif query.data == "store_file":
        buttons = [[
            InlineKeyboardButton('◀ Back', callback_data='help')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.FILE_STORE_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "r_txt":
        user_id = query.from_user.id

        # Check if the user has premium access
        if await db.has_premium_access(user_id):
            buttons = [[
                InlineKeyboardButton('◀ Back', callback_data='help')
            ]]
            await client.edit_message_media(
                query.message.chat.id, 
                query.message.id, 
                InputMediaPhoto(random.choice(PICS))
            )
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.message.edit_text(
                text=script.RENAME_TXT,
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
            )
        else:
        # If the user doesn't have premium access, show an alert
            await query.answer("🛒 ʙᴜʏ ᴘʀᴇᴍɪᴜᴍ ᴛᴏ ᴜsᴇ ᴛʜɪs ғᴇᴀᴛᴜʀᴇ! 💳", show_alert=True)
            

    elif query.data == "s_txt":
        user_id = query.from_user.id

        # Check if the user has premium access
        if await db.has_premium_access(user_id):
            buttons = [[
                InlineKeyboardButton('◀ Back', callback_data='help')
            ]]
            await client.edit_message_media(
                query.message.chat.id, 
                query.message.id, 
                InputMediaPhoto(random.choice(PICS))
            )
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.message.edit_text(
                text=script.STREAM_TXT,
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
            )
        else:
        # If the user doesn't have premium access, show an alert
            await query.answer("🛒 ʙᴜʏ ᴘʀᴇᴍɪᴜᴍ ᴛᴏ ᴜsᴇ ᴛʜɪs ғᴇᴀᴛᴜʀᴇ! 💳", show_alert=True)

    elif query.data == "spin":
            user_id = query.from_user.id
            # Check if the user has premium access
            if await db.has_premium_access(user_id):
                buttons = [
                    [InlineKeyboardButton('ᴊᴏɪɴ ᴛᴏ ᴄʜᴀɴɴᴇʟ 🎰', url=f'https://t.me/moovidex')],
                    [InlineKeyboardButton('◀ Back', callback_data='start')]
                ]
                reply_markup = InlineKeyboardMarkup(buttons)
                await query.message.edit_text(
                    text="● ◌ ◌"
                )
                await query.message.edit_text(
                    text="● ● ◌"
                )
                await query.message.edit_text(
                    text="● ● ●"
                )
                reply_markup = InlineKeyboardMarkup(buttons)
                await client.edit_message_media(
                    query.message.chat.id, 
                    query.message.id, 
                    InputMediaPhoto(random.choice(PICS))
                )
                await query.message.edit_text(
                    text=script.ADULT_TXT,
                    reply_markup=reply_markup,
                    parse_mode=enums.ParseMode.HTML
            )
            else:
                # If the user doesn't have premium access, show an alert
                await query.answer("🛒 ʙᴜʏ ᴘʀᴇᴍɪᴜᴍ ᴛᴏ ᴜsᴇ ᴛʜɪs ғᴇᴀᴛᴜʀᴇ! 💳", show_alert=True)




    elif query.data == "stats":
        buttons = [[
            InlineKeyboardButton('⟸ Bᴀᴄᴋ', callback_data='help'),
            InlineKeyboardButton('⟲ Rᴇғʀᴇsʜ', callback_data='rfrsh')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        total_users = await db.total_users_count()
        totl_chats = await db.total_chat_count()
        filesp = col.count_documents({})
        totalsec = sec_col.count_documents({})
        stats = vjdb.command('dbStats')
        used_dbSize = (stats['dataSize']/(1024*1024))+(stats['indexSize']/(1024*1024))
        free_dbSize = 512-used_dbSize
        stats2 = sec_db.command('dbStats')
        used_dbSize2 = (stats2['dataSize']/(1024*1024))+(stats2['indexSize']/(1024*1024))
        free_dbSize2 = 512-used_dbSize2
        stats3 = mydb.command('dbStats')
        used_dbSize3 = (stats3['dataSize']/(1024*1024))+(stats3['indexSize']/(1024*1024))
        free_dbSize3 = 512-used_dbSize3
        await query.message.edit_text(
            text=script.STATUS_TXT.format((int(filesp)+int(totalsec)), total_users, totl_chats, filesp, round(used_dbSize, 2), round(free_dbSize, 2), totalsec, round(used_dbSize2, 2), round(free_dbSize2, 2), round(used_dbSize3, 2), round(free_dbSize3, 2)),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "rfrsh":
        await query.answer("Fetching MongoDb DataBase")
        buttons = [[
            InlineKeyboardButton('⟸ Bᴀᴄᴋ', callback_data='help'),
            InlineKeyboardButton('⟲ Rᴇғʀᴇsʜ', callback_data='rfrsh')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        total_users = await db.total_users_count()
        totl_chats = await db.total_chat_count()
        filesp = col.count_documents({})
        totalsec = sec_col.count_documents({})
        stats = vjdb.command('dbStats')
        used_dbSize = (stats['dataSize']/(1024*1024))+(stats['indexSize']/(1024*1024))
        free_dbSize = 512-used_dbSize
        stats2 = sec_db.command('dbStats')
        used_dbSize2 = (stats2['dataSize']/(1024*1024))+(stats2['indexSize']/(1024*1024))
        free_dbSize2 = 512-used_dbSize2
        stats3 = mydb.command('dbStats')
        used_dbSize3 = (stats3['dataSize']/(1024*1024))+(stats3['indexSize']/(1024*1024))
        free_dbSize3 = 512-used_dbSize3
        await query.message.edit_text(
            text=script.STATUS_TXT.format((int(filesp)+int(totalsec)), total_users, totl_chats, filesp, round(used_dbSize, 2), round(free_dbSize, 2), totalsec, round(used_dbSize2, 2), round(free_dbSize2, 2), round(used_dbSize3, 2), round(free_dbSize3, 2)),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
            
    elif query.data == "extra":
        buttons = [[
            InlineKeyboardButton('◀ Back', callback_data='admin')
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.EXTRAMOD_TXT.format(OWNER_LNK, CHNL_LNK),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    
        
    elif query.data == "shortlink_info":
        btn = [[
            InlineKeyboardButton("👇Select Your Language 👇", callback_data="laninfo")
        ],[
            InlineKeyboardButton("Tamil", callback_data="tamil_info"),
            InlineKeyboardButton("English", callback_data="english_info"),
            InlineKeyboardButton("Hindi", callback_data="hindi_info")
        ],[
            InlineKeyboardButton("Malayalam", callback_data="malayalam_info"),
            InlineKeyboardButton("Urdu", callback_data="urdu_info"),
            InlineKeyboardButton("Bangla", callback_data="bangladesh_info")
        ],[
            InlineKeyboardButton("Telugu", callback_data="telugu_info"),
            InlineKeyboardButton("Kannada", callback_data="kannada_info"),
            InlineKeyboardButton("Gujarati", callback_data="gujarati_info")
        ],[
            InlineKeyboardButton("◀ Back", callback_data="start")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.SHORTLINK_INFO),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "tele":
        btn = [[
            InlineKeyboardButton("◀ Back", callback_data="help"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="telegram.me/H21TG")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.TELE_TXT),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "ytdl":
        buttons = [[
            InlineKeyboardButton('◀ Back ', callback_data='help')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text="● ◌ ◌"
        )
        await query.message.edit_text(
            text="● ● ◌"
        )
        await query.message.edit_text(
            text="● ● ●"
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        await query.message.edit_text(
            text=script.YTDL_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )

    elif query.data == "disclaimer":
        btn = [[
            InlineKeyboardButton("◀ Back", callback_data="start"),
            InlineKeyboardButton("T&C", url="https://t.me/moovidex/19")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.DISCLAIMER_TXT),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "share":
        btn = [[
            InlineKeyboardButton("◀ Back", callback_data="help"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="telegram.me/H21TG")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.SHARE_TXT),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "song":
        btn = [[
            InlineKeyboardButton("◀ Back", callback_data="help"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="telegram.me/H21TG")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.SONG_TXT),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "json":
        buttons = [[
            InlineKeyboardButton('◀ Back ', callback_data='help')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text="● ◌ ◌"
        )
        await query.message.edit_text(
            text="● ● ◌"
        )
        await query.message.edit_text(
            text="● ● ●"
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        await query.message.edit_text(
            text=script.JSON_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "sticker":
        btn = [[
            InlineKeyboardButton("◀ Back", callback_data="help"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="telegram.me/H21TG")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.STICKER_TXT),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "tamil_info":
        btn = [[
            InlineKeyboardButton("◀ Back", callback_data="start"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="telegram.me/H21TG")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.TAMIL_INFO),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "english_info":
        btn = [[
            InlineKeyboardButton("◀ Back", callback_data="start"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="telegram.me/H21TG")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.ENGLISH_INFO),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "hindi_info":
        btn = [[
            InlineKeyboardButton("◀ Back", callback_data="start"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="telegram.me/H21TG")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.HINDI_INFO),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "telugu_info":
        btn = [[
            InlineKeyboardButton("◀ Back", callback_data="start"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="telegram.me/H21TG")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.TELUGU_INFO),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "malayalam_info":
        btn = [[
            InlineKeyboardButton("◀ Back", callback_data="start"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="telegram.me/H21TG")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.MALAYALAM_INFO),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "urdu_info":
        btn = [[
            InlineKeyboardButton("◀ Back", callback_data="start"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="telegram.me/H21TG")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.URDU_INFO),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "bangladesh_info":
        btn = [[
            InlineKeyboardButton("◀ Back", callback_data="start"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="telegram.me/H21TG")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.BANGLADESH_INFO),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "kannada_info":
        btn = [[
            InlineKeyboardButton("◀ Back", callback_data="start"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="telegram.me/H21TG")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.KANNADA_INFO),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "gujarati_info":
        btn = [[
            InlineKeyboardButton("◀ Back", callback_data="start"),
            InlineKeyboardButton("Cᴏɴᴛᴀᴄᴛ", url="telegram.me/H21TG")
        ]]
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(btn)
        await query.message.edit_text(
            text=(script.GUJARATI_INFO),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data.startswith("setgs"):
        ident, set_type, status, grp_id = query.data.split("#")
        grpid = await active_connection(str(query.from_user.id))

        if str(grp_id) != str(grpid):
            await query.message.edit("Yᴏᴜʀ Aᴄᴛɪᴠᴇ Cᴏɴɴᴇᴄᴛɪᴏɴ Hᴀs Bᴇᴇɴ Cʜᴀɴɢᴇᴅ. Gᴏ Tᴏ /connections ᴀɴᴅ ᴄʜᴀɴɢᴇ ʏᴏᴜʀ ᴀᴄᴛɪᴠᴇ ᴄᴏɴɴᴇᴄᴛɪᴏɴ.")
            return await query.answer(MSG_ALRT)

        if status == "True":
            await save_group_settings(grpid, set_type, False)
        else:
            settings = await get_settings(grpid)
            if set_type == "is_shortlink" and not settings['shortlink']:
                return await query.answer(text = "First Add Your Shortlink Url And Api By /shortlink Command, Then Turn Me On.", show_alert = True)
            await save_group_settings(grpid, set_type, True)

        settings = await get_settings(grpid)

        if settings is not None:
            buttons = [
                [
                    InlineKeyboardButton('Rᴇsᴜʟᴛ Pᴀɢᴇ',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}'),
                    InlineKeyboardButton('Bᴜᴛᴛᴏɴ' if settings["button"] else 'Tᴇxᴛ',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Pʀᴏᴛᴇᴄᴛ Cᴏɴᴛᴇɴᴛ',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Oɴ' if settings["file_secure"] else '❌ Oғғ',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Iᴍᴅʙ', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Oɴ' if settings["imdb"] else '❌ Oғғ',
                                         callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Sᴘᴇʟʟ Cʜᴇᴄᴋ',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Oɴ' if settings["spell_check"] else '❌ Oғғ',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Wᴇʟᴄᴏᴍᴇ Msɢ', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Oɴ' if settings["welcome"] else '❌ Oғғ',
                                         callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Aᴜᴛᴏ-Dᴇʟᴇᴛᴇ',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}'),
                    InlineKeyboardButton('5 Mɪɴs' if settings["auto_delete"] else '❌ Oғғ',
                                         callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Aᴜᴛᴏ-Fɪʟᴛᴇʀ',
                                         callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Oɴ' if settings["auto_ffilter"] else '❌ Oғғ',
                                         callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Mᴀx Bᴜᴛᴛᴏɴs',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}'),
                    InlineKeyboardButton('10' if settings["max_btn"] else f'{MAX_B_TN}',
                                         callback_data=f'setgs#max_btn#{settings["max_btn"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('SʜᴏʀᴛLɪɴᴋ',
                                         callback_data=f'setgs#is_shortlink#{settings["is_shortlink"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Oɴ' if settings["is_shortlink"] else '❌ Oғғ',
                                         callback_data=f'setgs#is_shortlink#{settings["is_shortlink"]}#{str(grp_id)}')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.message.edit_reply_markup(reply_markup)
    await query.answer(MSG_ALRT)



async def search_orchestrator(client, reply_msg, files, key, search, analysis):
    """
    God Function: Intelligently routes search results to the best view.
    """
    
    # 1. Language Picker (Multilingual Content)
    if len(analysis['languages']) > 1:
        btn = []
        for lang in analysis['languages']:
            btn.append([InlineKeyboardButton(f"🔊 {lang}", callback_data=f"smart_lang#{lang}#{key}")])
        btn.append([InlineKeyboardButton("📂 Show All Files", callback_data=f"smart_default#{key}")])
        
        try:
            await reply_msg.edit_text(
                f"**Found {len(files)} results for '{search}'**\n\nSELECT LANGUAGE:",
                reply_markup=InlineKeyboardMarkup(btn)
            )
        except Exception as e:
            logger.error(f"Orchestrator Error (Lang): {e}")
        return

    # 2. Season Picker (Series with Multiple Seasons)
    if analysis['is_series'] and len(analysis['seasons']) > 0:
        btn = []
        row = []
        for season in analysis['seasons']:
            row.append(InlineKeyboardButton(f"📺 {season}", callback_data=f"smart_season#{season}#{key}"))
            if len(row) == 3:
                btn.append(row)
                row = []
        if row:
            btn.append(row)
            
        btn.append([InlineKeyboardButton("📂 Show All Episodes", callback_data=f"smart_default#{key}")])
        
        try:
            await reply_msg.edit_text(
                f"**Found {len(analysis['seasons'])} Seasons for '{search}'**\n\nSELECT SEASON:",
                reply_markup=InlineKeyboardMarkup(btn)
            )
        except Exception as e:
            logger.error(f"Orchestrator Error (Season): {e}")
        return

    # 3. Quality Picker (Movies with variants, if many files)
    if not analysis['is_series'] and len(analysis['qualities']) > 1 and len(files) > 10:
        btn = []
        row = []
        for qual in analysis['qualities']:
            row.append(InlineKeyboardButton(f"{qual}", callback_data=f"smart_quality#{qual}#{key}"))
            if len(row) == 3:
                btn.append(row)
                row = []
        if row:
            btn.append(row)
        btn.append([InlineKeyboardButton("📂 Show All Files", callback_data=f"smart_default#{key}")])

        try:
            await reply_msg.edit_text( 
                f"**Found {len(files)} results.**\n\nSELECT QUALITY:",
                reply_markup=InlineKeyboardMarkup(btn) 
            )
        except Exception as e:
            logger.error(f"Orchestrator Error (Quality): {e}")
        return

    # 4. Standard List (Default)
    # Pass 'message' object (reply_msg) to show_smart_results
    await show_smart_results(client, reply_msg, files, key, f"{search}")


async def auto_filter(client, name, msg, reply_msg, ai_search, spoll=False):
    curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    if not spoll:
        message = msg
        text = message.caption or message.text or ""
        if len(text) < 50:
            search = name.lower()
            # Clean search query
            search = re.sub(r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|bro|bruh|broh|helo|that|find|dubbed|link|venum|iruka|pannunga|pannungga|anuppunga|anupunga|anuppungga|anupungga|film|undo|kitti|kitty|tharu|kittumo|kittum|movie|any(one)|with\ssubtitle(s)?)", "", search, flags=re.IGNORECASE)
            search = re.sub(r"\s+", " ", search).strip()
            search = search.replace("-", " ")
            search = search.replace(":", "")
            search = search.replace(":", "")
            search = search.replace(".", "")
            # Remove brackets and their content if desired, or just the brackets? User said "unwanted character". 
            # Usually removing generic special chars is safer.
            search = re.sub(r"[\[\]\(\)\{\}]", "", search)
            search = re.sub(r"[^\w\s]", "", search) # Keep only alphanumeric and whitespace
            
            # Fetch MORE results for analysis (up to 100)
            files, offset, total_results = await get_search_results(message.chat.id ,search, offset=0, max_results=100, filter=True)
            
            # Relevance Sorting
            files = sort_by_relevance(files, search)
                
            try:
                req_user_id = message.from_user.id if message.from_user else 0
                asyncio.create_task(stats_db.add_search_log(search, req_user_id, total_results, source='auto_filter'))
            except Exception as e:
                print(f"Error logging search: {e}")
                
            settings = await get_settings(message.chat.id)
            
            # Trigger Logic: Only check IMDb/Spell Check if NO files are found
            # Removed proactive "should_suggest" logic as per user request
            
            if not files:
                if settings["spell_check"]:
                    return await advantage_spell_chok(client, name, msg, reply_msg, ai_search)
                else:
                    return await reply_msg.edit_text(f"**⚠️ No File Found For Your Query - {name}**\n**Make Sure Spelling Is Correct.**")
    else:
        message = msg.message.reply_to_message  # msg will be callback query
        search, files, offset, total_results = spoll
        settings = await get_settings(message.chat.id)
        # await msg.message.delete() # Removed to prevent MESSAGE_ID_INVALID as orchestrator edits this message

    # --- Smart Filter Logic Start ---
    analysis = analyze_query_results(files)
    key = f"{message.chat.id}-{message.id}"
    FRESH[key] = search
    temp.GETALL[key] = files
    temp.SHORT[message.from_user.id] = message.chat.id
    
    await search_orchestrator(client, reply_msg, files, key, search, analysis)

async def handle_no_results(client, reply_msg, mv_rqst, reqstr):
    try:
        reqst_gle = mv_rqst.replace(" ", "+")
        button = [[
            InlineKeyboardButton("🔍 Search on Google", url=f"https://www.google.com/search?q={reqst_gle}")
        ]]

        # Always log the no-result info to LOG_CHANNEL
        log_text = f"🚫 <b>No results found</b>\n\n👤 User: {reqstr.mention} (`{reqstr.id}`)\n🔎 Query: <code>{mv_rqst}</code>"
        await client.send_message(chat_id=LOG_CHANNEL, text=log_text)

        # Show message to user
        if reply_msg and hasattr(reply_msg, 'edit_text'):
            k = await reply_msg.edit_text(
                text=script.I_CUDNT.format(mv_rqst),
                reply_markup=InlineKeyboardMarkup(button),
                disable_web_page_preview=True
            )
            await asyncio.sleep(30)
            await k.delete()

    except Exception as e:
        logger.exception("Error in handle_no_results: %s", e)



async def advantage_spell_chok(client, name, msg, reply_msg, ai_search):
    mv_id = msg.id
    mv_rqst = name
    reqstr1 = msg.from_user.id if msg.from_user else 0
    reqstr = await client.get_users(reqstr1)
    settings = await get_settings(msg.chat.id)

    msg_text = msg.text if isinstance(msg.text, str) else ""
    query = re.sub(
        r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|br((o|u)h?)*|^h(e|a)?(l)*(o)*|mal(ayalam)?|t(h)?amil|file|that|find|und(o)*|kit(t(i|y)?)?o(w)?|thar(u)?(o)*w?|kittum(o)*|aya(k)*(um(o)*)?|full\smovie|any(one)|with\ssubtitle(s)?)",
        "", msg_text,
        flags=re.IGNORECASE)
    query = query.strip()

    if not query:
        await handle_no_results(client, reply_msg, mv_rqst, reqstr)
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://imdb.iamidiotareyoutoo.com/search?q={query}") as res:
                data = await res.json()
        if not data.get("ok") or not data.get("description"):
            raise ValueError("No movie suggestions found.")
    except Exception as e:
        logger.exception("Spell suggestion API failed: %s", e)
        await handle_no_results(client, reply_msg, mv_rqst, reqstr)
        return

    suggestions = data["description"]
    movielist = [f"{m.get('#TITLE', '')} {m.get('#YEAR', '')}" for m in suggestions[:5]]
    SPELL_CHECK[mv_id] = movielist

    # Auto spell check shortcut
    if AI_SPELL_CHECK and ai_search:
        vj_search_new = False
        try:
            if reply_msg and hasattr(reply_msg, 'edit_text'):
                await reply_msg.edit_text("<b>🕵️ Trying to guess the movie you meant...</b>")
        except Exception as e:
            logger.exception("Failed to edit spell-check message: %s", e)

        techvj = suggestions[0].get("#TITLE", '')
        try:
            mv_rqst = mv_rqst.capitalize()
        except Exception:
            pass
        if mv_rqst and techvj:
            from difflib import SequenceMatcher
            similarity = SequenceMatcher(None, mv_rqst.lower(), techvj.lower()).ratio()
            if similarity > 0.6:  # Threshold for auto-search
                await auto_filter(client, techvj, msg, reply_msg, vj_search_new)
                return

        await handle_no_results(client, reply_msg, mv_rqst, reqstr)
        return

    # Inline keyboard for spell suggestions
    btn = [
        [
            InlineKeyboardButton(
                text=title.strip(),
                callback_data=f"spol#{reqstr1}#{k}",
            )
        ]
        for k, title in enumerate(movielist)
    ]
    btn.append([InlineKeyboardButton(text="Close", callback_data=f"spol#{reqstr1}#close_spellcheck")])

    try:
        if reply_msg and hasattr(reply_msg, 'edit_text'):
            spell_check_del = await reply_msg.edit_text(
                text="<b>Please select the movie / series</b>",
                reply_markup=InlineKeyboardMarkup(btn)
            )

            if settings.get('auto_delete'):
                await asyncio.sleep(600)
                await spell_check_del.delete()
        else:
            logger.warning("reply_msg is invalid or None.")
    except KeyError:
        grpid = await active_connection(str(msg.from_user.id))
        await save_group_settings(grpid, 'auto_delete', True)
        settings = await get_settings(msg.chat.id)
        if settings.get('auto_delete'):
            await asyncio.sleep(600)
            try:
                if spell_check_del:
                    await spell_check_del.delete()
            except Exception as e:
                logger.exception("Failed to delete spell check message: %s", e)


async def manual_filters(client, message, text=False):
    settings = await get_settings(message.chat.id)
    group_id = message.chat.id
    name = text or message.text
    reply_id = message.reply_to_message.id if message.reply_to_message else message.id
    keywords = await get_filters(group_id)
    for keyword in reversed(sorted(keywords, key=len)):
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, name, flags=re.IGNORECASE):
            reply_text, btn, alert, fileid = await find_filter(group_id, keyword)

            if reply_text:
                reply_text = reply_text.replace("\\n", "\n").replace("\\t", "\t")

            if btn is not None:
                try:
                    if fileid == "None":
                        if btn == "[]":
                            joelkb = await client.send_message(
                                group_id, 
                                reply_text, 
                                disable_web_page_preview=True,
                                protect_content=True if settings["file_secure"] else False,
                                reply_to_message_id=reply_id
                            )
                            try:
                                if settings['auto_ffilter']:
                                    ai_search = True
                                    reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                    await auto_filter(client, message.text, message, reply_msg, ai_search)
                                    try:
                                        if settings['auto_delete']:
                                            await joelkb.delete()
                                    except KeyError:
                                        grpid = await active_connection(str(message.from_user.id))
                                        await save_group_settings(grpid, 'auto_delete', True)
                                        settings = await get_settings(message.chat.id)
                                        if settings['auto_delete']:
                                            await joelkb.delete()
                                else:
                                    try:
                                        if settings['auto_delete']:
                                            await asyncio.sleep(600)
                                            await joelkb.delete()
                                    except KeyError:
                                        grpid = await active_connection(str(message.from_user.id))
                                        await save_group_settings(grpid, 'auto_delete', True)
                                        settings = await get_settings(message.chat.id)
                                        if settings['auto_delete']:
                                            await asyncio.sleep(600)
                                            await joelkb.delete()
                            except KeyError:
                                grpid = await active_connection(str(message.from_user.id))
                                await save_group_settings(grpid, 'auto_ffilter', True)
                                settings = await get_settings(message.chat.id)
                                if settings['auto_ffilter']:
                                    ai_search = True
                                    reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                    await auto_filter(client, message.text, message, reply_msg, ai_search)

                        else:
                            button = eval(btn)
                            joelkb = await client.send_message(
                                group_id,
                                reply_text,
                                disable_web_page_preview=True,
                                reply_markup=InlineKeyboardMarkup(button),
                                protect_content=True if settings["file_secure"] else False,
                                reply_to_message_id=reply_id
                            )
                            try:
                                if settings['auto_ffilter']:
                                    ai_search = True
                                    reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                    await auto_filter(client, message.text, message, reply_msg, ai_search)
                                    try:
                                        if settings['auto_delete']:
                                            await joelkb.delete()
                                    except KeyError:
                                        grpid = await active_connection(str(message.from_user.id))
                                        await save_group_settings(grpid, 'auto_delete', True)
                                        settings = await get_settings(message.chat.id)
                                        if settings['auto_delete']:
                                            await joelkb.delete()
                                else:
                                    try:
                                        if settings['auto_delete']:
                                            await asyncio.sleep(600)
                                            await joelkb.delete()
                                    except KeyError:
                                        grpid = await active_connection(str(message.from_user.id))
                                        await save_group_settings(grpid, 'auto_delete', True)
                                        settings = await get_settings(message.chat.id)
                                        if settings['auto_delete']:
                                            await asyncio.sleep(600)
                                            await joelkb.delete()
                            except KeyError:
                                grpid = await active_connection(str(message.from_user.id))
                                await save_group_settings(grpid, 'auto_ffilter', True)
                                settings = await get_settings(message.chat.id)
                                if settings['auto_ffilter']:
                                    ai_search = True
                                    reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                    await auto_filter(client, message.text, message, reply_msg, ai_search)
                    elif btn == "[]":
                        joelkb = await client.send_cached_media(
                            group_id,
                            fileid,
                            caption=reply_text or "",
                            protect_content=True if settings["file_secure"] else False,
                            reply_to_message_id=reply_id
                        )
                        try:
                            if settings['auto_ffilter']:
                                ai_search = True
                                reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                await auto_filter(client, message.text, message, reply_msg, ai_search)
                                try:
                                    if settings['auto_delete']:
                                        await joelkb.delete()
                                except KeyError:
                                    grpid = await active_connection(str(message.from_user.id))
                                    await save_group_settings(grpid, 'auto_delete', True)
                                    settings = await get_settings(message.chat.id)
                                    if settings['auto_delete']:
                                        await joelkb.delete()
                            else:
                                try:
                                    if settings['auto_delete']:
                                        await asyncio.sleep(600)
                                        await joelkb.delete()
                                except KeyError:
                                    grpid = await active_connection(str(message.from_user.id))
                                    await save_group_settings(grpid, 'auto_delete', True)
                                    settings = await get_settings(message.chat.id)
                                    if settings['auto_delete']:
                                        await asyncio.sleep(600)
                                        await joelkb.delete()
                        except KeyError:
                            grpid = await active_connection(str(message.from_user.id))
                            await save_group_settings(grpid, 'auto_ffilter', True)
                            settings = await get_settings(message.chat.id)
                            if settings['auto_ffilter']:
                                ai_search = True
                                reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                await auto_filter(client, message.text, message, reply_msg, ai_search)
                    else:
                        button = eval(btn)
                        joelkb = await message.reply_cached_media(
                            fileid,
                            caption=reply_text or "",
                            reply_markup=InlineKeyboardMarkup(button),
                            reply_to_message_id=reply_id
                        )
                        try:
                            if settings['auto_ffilter']:
                                ai_search = True
                                reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                await auto_filter(client, message.text, message, reply_msg, ai_search)
                                try:
                                    if settings['auto_delete']:
                                        await joelkb.delete()
                                except KeyError:
                                    grpid = await active_connection(str(message.from_user.id))
                                    await save_group_settings(grpid, 'auto_delete', True)
                                    settings = await get_settings(message.chat.id)
                                    if settings['auto_delete']:
                                        await joelkb.delete()
                            else:
                                try:
                                    if settings['auto_delete']:
                                        await asyncio.sleep(600)
                                        await joelkb.delete()
                                except KeyError:
                                    grpid = await active_connection(str(message.from_user.id))
                                    await save_group_settings(grpid, 'auto_delete', True)
                                    settings = await get_settings(message.chat.id)
                                    if settings['auto_delete']:
                                        await asyncio.sleep(600)
                                        await joelkb.delete()
                        except KeyError:
                            grpid = await active_connection(str(message.from_user.id))
                            await save_group_settings(grpid, 'auto_ffilter', True)
                            settings = await get_settings(message.chat.id)
                            if settings['auto_ffilter']:
                                ai_search = True
                                reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                await auto_filter(client, message.text, message, reply_msg, ai_search)

                except Exception as e:
                    logger.exception(e)
                break
    else:
        return False

async def global_filters(client, message, text=False):
    settings = await get_settings(message.chat.id)
    group_id = message.chat.id
    name = text or message.text
    reply_id = message.reply_to_message.id if message.reply_to_message else message.id
    keywords = await get_gfilters('gfilters')
    for keyword in reversed(sorted(keywords, key=len)):
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, name, flags=re.IGNORECASE):
            reply_text, btn, alert, fileid = await find_gfilter('gfilters', keyword)

            if reply_text:
                reply_text = reply_text.replace("\\n", "\n").replace("\\t", "\t")

            if btn is not None:
                try:
                    if fileid == "None":
                        if btn == "[]":
                            joelkb = await client.send_message(
                                group_id, 
                                reply_text, 
                                disable_web_page_preview=True,
                                reply_to_message_id=reply_id
                            )
                            manual = await manual_filters(client, message)
                            if manual == False:
                                settings = await get_settings(message.chat.id)
                                try:
                                    if settings['auto_ffilter']:
                                        ai_search = True
                                        reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                        await auto_filter(client, message.text, message, reply_msg, ai_search)
                                        try:
                                            if settings['auto_delete']:
                                                await joelkb.delete()
                                        except KeyError:
                                            grpid = await active_connection(str(message.from_user.id))
                                            await save_group_settings(grpid, 'auto_delete', True)
                                            settings = await get_settings(message.chat.id)
                                            if settings['auto_delete']:
                                                await joelkb.delete()
                                    else:
                                        try:
                                            if settings['auto_delete']:
                                                await asyncio.sleep(600)
                                                await joelkb.delete()
                                        except KeyError:
                                            grpid = await active_connection(str(message.from_user.id))
                                            await save_group_settings(grpid, 'auto_delete', True)
                                            settings = await get_settings(message.chat.id)
                                            if settings['auto_delete']:
                                                await asyncio.sleep(600)
                                                await joelkb.delete()
                                except KeyError:
                                    grpid = await active_connection(str(message.from_user.id))
                                    await save_group_settings(grpid, 'auto_ffilter', True)
                                    settings = await get_settings(message.chat.id)
                                    if settings['auto_ffilter']:
                                        ai_search = True
                                        reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                        await auto_filter(client, message.text, message, reply_msg, ai_search) 
                            else:
                                try:
                                    if settings['auto_delete']:
                                        await joelkb.delete()
                                except KeyError:
                                    grpid = await active_connection(str(message.from_user.id))
                                    await save_group_settings(grpid, 'auto_delete', True)
                                    settings = await get_settings(message.chat.id)
                                    if settings['auto_delete']:
                                        await joelkb.delete()
                            
                        else:
                            button = eval(btn)
                            joelkb = await client.send_message(
                                group_id,
                                reply_text,
                                disable_web_page_preview=True,
                                reply_markup=InlineKeyboardMarkup(button),
                                reply_to_message_id=reply_id
                            )
                            manual = await manual_filters(client, message)
                            if manual == False:
                                settings = await get_settings(message.chat.id)
                                try:
                                    if settings['auto_ffilter']:
                                        ai_search = True
                                        reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                        await auto_filter(client, message.text, message, reply_msg, ai_search)
                                        try:
                                            if settings['auto_delete']:
                                                await joelkb.delete()
                                        except KeyError:
                                            grpid = await active_connection(str(message.from_user.id))
                                            await save_group_settings(grpid, 'auto_delete', True)
                                            settings = await get_settings(message.chat.id)
                                            if settings['auto_delete']:
                                                await joelkb.delete()
                                    else:
                                        try:
                                            if settings['auto_delete']:
                                                await asyncio.sleep(600)
                                                await joelkb.delete()
                                        except KeyError:
                                            grpid = await active_connection(str(message.from_user.id))
                                            await save_group_settings(grpid, 'auto_delete', True)
                                            settings = await get_settings(message.chat.id)
                                            if settings['auto_delete']:
                                                await asyncio.sleep(600)
                                                await joelkb.delete()
                                except KeyError:
                                    grpid = await active_connection(str(message.from_user.id))
                                    await save_group_settings(grpid, 'auto_ffilter', True)
                                    settings = await get_settings(message.chat.id)
                                    if settings['auto_ffilter']:
                                        ai_search = True
                                        reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                        await auto_filter(client, message.text, message, reply_msg, ai_search)
                            else:
                                try:
                                    if settings['auto_delete']:
                                        await joelkb.delete()
                                except KeyError:
                                    grpid = await active_connection(str(message.from_user.id))
                                    await save_group_settings(grpid, 'auto_delete', True)
                                    settings = await get_settings(message.chat.id)
                                    if settings['auto_delete']:
                                        await joelkb.delete()

                    elif btn == "[]":
                        joelkb = await client.send_cached_media(
                            group_id,
                            fileid,
                            caption=reply_text or "",
                            reply_to_message_id=reply_id
                        )
                        manual = await manual_filters(client, message)
                        if manual == False:
                            settings = await get_settings(message.chat.id)
                            try:
                                if settings['auto_ffilter']:
                                    ai_search = True
                                    reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                    await auto_filter(client, message.text, message, reply_msg, ai_search)
                                    try:
                                        if settings['auto_delete']:
                                            await joelkb.delete()
                                    except KeyError:
                                        grpid = await active_connection(str(message.from_user.id))
                                        await save_group_settings(grpid, 'auto_delete', True)
                                        settings = await get_settings(message.chat.id)
                                        if settings['auto_delete']:
                                            await joelkb.delete()
                                else:
                                    try:
                                        if settings['auto_delete']:
                                            await asyncio.sleep(600)
                                            await joelkb.delete()
                                    except KeyError:
                                        grpid = await active_connection(str(message.from_user.id))
                                        await save_group_settings(grpid, 'auto_delete', True)
                                        settings = await get_settings(message.chat.id)
                                        if settings['auto_delete']:
                                            await asyncio.sleep(600)
                                            await joelkb.delete()
                            except KeyError:
                                grpid = await active_connection(str(message.from_user.id))
                                await save_group_settings(grpid, 'auto_ffilter', True)
                                settings = await get_settings(message.chat.id)
                                if settings['auto_ffilter']:
                                    ai_search = True
                                    reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                    await auto_filter(client, message.text, message, reply_msg, ai_search) 
                        else:
                            try:
                                if settings['auto_delete']:
                                    await joelkb.delete()
                            except KeyError:
                                grpid = await active_connection(str(message.from_user.id))
                                await save_group_settings(grpid, 'auto_delete', True)
                                settings = await get_settings(message.chat.id)
                                if settings['auto_delete']:
                                    await joelkb.delete()

                    else:
                        button = eval(btn)
                        joelkb = await message.reply_cached_media(
                            fileid,
                            caption=reply_text or "",
                            reply_markup=InlineKeyboardMarkup(button),
                            reply_to_message_id=reply_id
                        )
                        manual = await manual_filters(client, message)
                        if manual == False:
                            settings = await get_settings(message.chat.id)
                            try:
                                if settings['auto_ffilter']:
                                    ai_search = True
                                    reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                    await auto_filter(client, message.text, message, reply_msg, ai_search)
                                    try:
                                        if settings['auto_delete']:
                                            await joelkb.delete()
                                    except KeyError:
                                        grpid = await active_connection(str(message.from_user.id))
                                        await save_group_settings(grpid, 'auto_delete', True)
                                        settings = await get_settings(message.chat.id)
                                        if settings['auto_delete']:
                                            await joelkb.delete()
                                else:
                                    try:
                                        if settings['auto_delete']:
                                            await asyncio.sleep(600)
                                            await joelkb.delete()
                                    except KeyError:
                                        grpid = await active_connection(str(message.from_user.id))
                                        await save_group_settings(grpid, 'auto_delete', True)
                                        settings = await get_settings(message.chat.id)
                                        if settings['auto_delete']:
                                            await asyncio.sleep(600)
                                            await joelkb.delete()
                            except KeyError:
                                grpid = await active_connection(str(message.from_user.id))
                                await save_group_settings(grpid, 'auto_ffilter', True)
                                settings = await get_settings(message.chat.id)
                                if settings['auto_ffilter']:
                                    ai_search = True
                                    reply_msg = await message.reply_text(f"<b><i>Searching For {message.text} 🔍</i></b>")
                                    await auto_filter(client, message.text, message, reply_msg, ai_search)
                        else:
                            try:
                                if settings['auto_delete']:
                                    await joelkb.delete()
                            except KeyError:
                                grpid = await active_connection(str(message.from_user.id))
                                await save_group_settings(grpid, 'auto_delete', True)
                                settings = await get_settings(message.chat.id)
                                if settings['auto_delete']:
                                    await joelkb.delete()

                                
                except Exception as e:
                    logger.exception(e)
                break
    else:
        return False
