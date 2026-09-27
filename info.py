# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01


import re
from os import environ
from Script import script 

# Fixed: the old pattern `^.\d+$` matched any string containing digits
# (e.g. 'abc123'), misclassifying usernames as numeric ids.
id_pattern = re.compile(r'^-?\d+$')

_TRUE_VALUES = {'1', 'true', 'yes', 'y', 'on', 't'}


def _bool(name, default=False):
    """Parse an on/off env var. The old code used ``bool(environ.get(...))``,
    which treats the string "False" as True."""
    raw = environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in _TRUE_VALUES


def _int(name, default):
    """Parse an integer env var; fall back to ``default`` if invalid."""
    raw = environ.get(name)
    if raw in (None, ''):
        return default
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        print(f"[config] WARNING: {name}={raw!r} is not a valid integer; using default {default!r}.")
        return default


def _required(name):
    """Return a mandatory env var, or abort startup with a clear message."""
    value = (environ.get(name) or '').strip()
    if not value:
        raise SystemExit(
            f"[config] ERROR: required environment variable {name!r} is not set. "
            f"Set it before starting the bot."
        )
    return value


def _required_int(name):
    value = _required(name)
    try:
        return int(value)
    except ValueError:
        raise SystemExit(
            f"[config] ERROR: environment variable {name!r} must be an integer, got {value!r}."
        )


def _id_list(name, allow_names=False):
    """Parse a space-separated list of Telegram ids."""
    items = []
    for token in (environ.get(name, '') or '').split():
        token = token.strip()
        if not token:
            continue
        if id_pattern.search(token):
            items.append(int(token))
        elif allow_names:
            items.append(token)
        else:
            raise SystemExit(
                f"[config] ERROR: {name!r} contains an invalid Telegram id {token!r}. "
                f"Use space-separated numeric ids."
            )
    return items


def _optional_id(name):
    raw = (environ.get(name, '') or '').strip()
    if not raw:
        return None
    if not id_pattern.search(raw):
        raise SystemExit(
            f"[config] ERROR: {name!r} must be a numeric Telegram id, got {raw!r}."
        )
    return int(raw)

# Bot information
SESSION = environ.get('SESSION', 'TechVJBot')
MAINTENANCE_MODE = {
    "is_on": False,
    "reason": "No reason provided."
}
API_ID = _required_int('API_ID')
API_HASH = _required('API_HASH')
BOT_TOKEN = _required('BOT_TOKEN')
# No defaults: the old admin/admin default let anyone into the web dashboard.
ADMIN_USERNAME = _required('ADMIN_USERNAME')
ADMIN_PASSWORD = _required('ADMIN_PASSWORD')
# Server-side key; must come from the environment. (The previously
# hardcoded key was committed to git history and should be rotated.)
TMDB_API_KEY = environ.get('TMDB_API_KEY', '') # Default key or empty


# Keys must come from the environment (space- or comma-separated);
# no keys are bundled anymore.
DEEPGRAM_API_KEYS = [
    key for key in environ.get('DEEPGRAM_API_KEYS', '').replace(',', ' ').split()
    if key.strip()
]
# This Pictures Is For Start Message Picture, You Can Add Multiple By Giving One Space Between Each.
PICS = (environ.get('PICS', 'https://graph.org/file/ce1723991756e48c35aa1.jpg')).split()


# Admins & Users
ADMINS = _id_list('ADMINS', allow_names=True) # For Multiple Id Use One Space Between Each.
auth_users = _id_list('AUTH_USERS', allow_names=True)  # For Multiple Id Use One Space Between Each.
# Admins are always authorized, even when AUTH_USERS is unset/empty.
AUTH_USERS = list(dict.fromkeys(auth_users + ADMINS))

# This Channel Is For When User Start Your Bot Then Bot Send That User Name And Id In This Log Channel, Same For Group Also.
LOG_CHANNEL = _required_int('LOG_CHANNEL')

# This Is File Channel Where You Upload Your File Then Bot Automatically Save It In Database 
CHANNELS = _id_list('CHANNELS', allow_names=True)  # For Multiple Id Use One Space Between Each.

# auth_channel means force subscribe channel.
# if REQUEST_TO_JOIN_MODE is true then force subscribe work like request to join fsub, else if false then work like normal fsub.
REQUEST_TO_JOIN_MODE = _bool('REQUEST_TO_JOIN_MODE', False) # Set True Or False
TRY_AGAIN_BTN = _bool('TRY_AGAIN_BTN', False) # Set True Or False (This try again button is only for request to join fsub not for normal fsub)

# This Is Force Subscribe Channel, also known as Auth Channel 
AUTH_CHANNEL = _optional_id('AUTH_CHANNEL') # give your force subscribe channel id here else leave it blank

# This Channel Is For When User Request Any File Name With command or hashtag like - /request or #request
REQST_CHANNEL = _optional_id('REQST_CHANNEL')

# This Channel Is For Index Request 
INDEX_REQ_CHANNEL = _int('INDEX_REQ_CHANNEL', LOG_CHANNEL)

# This Is Your Bot Support Group Id , Here Bot Will Not Give File Because This Is Support Group.
SUPPORT_CHAT_ID = _optional_id('SUPPORT_CHAT_ID')

# This Channel Is For /batch command file store.
FILE_STORE_CHANNEL = _id_list('FILE_STORE_CHANNEL')  # For Multiple Id Use One Space Between Each.

# This Channel Is For Delete Index File, Forward Your File In This Channel Which You Want To Delete Then Bot Automatically Delete That File From Database.
DELETE_CHANNELS = _id_list('DELETE_CHANNELS', allow_names=True) or [0]  # For Multiple Id Use One Space Between Each.


# MongoDB information
DATABASE_URI = environ.get('DATABASE_URI', "")   # IF Multiple Database Is False Then Fill Only This Database Url.
DATABASE_NAME = environ.get('DATABASE_NAME', "techvjclonefilterbot")
COLLECTION_NAME = environ.get('COLLECTION_NAME', 'vjcollection')

MULTIPLE_DATABASE = _bool('MULTIPLE_DATABASE', False) # Set True or False

# If Multiple Database Is True Then Fill All Three Below Database Uri Else You Will Get Error.
O_DB_URI = environ.get('O_DB_URI', "")   # This Db Is For Other Data Store
F_DB_URI = environ.get('F_DB_URI', "")   # This Db Is For File Data Store
S_DB_URI = environ.get('S_DB_URI', "")   # This Db is for File Data Store When First Db Is Going To Be Full.


# Premium And Referal Settings
PREMIUM_AND_REFERAL_MODE = _bool('PREMIUM_AND_REFERAL_MODE', False) # Set Ture Or False

# If PREMIUM_AND_REFERAL_MODE is True Then Fill Below Variable, If Flase Then No Need To Fill.
REFERAL_COUNT = _int('REFERAL_COUNT', 1) # number of referal count
REFERAL_PREMEIUM_TIME = environ.get('REFERAL_PREMEIUM_TIME', '3months') # time in week, day, month.
PAYMENT_QR = environ.get('PAYMENT_QR', 'https://graph.org/file/2915157bfcbe94c56080c.jpg') # payment code picture url.
PAYMENT_UPI_ID = environ.get('PAYMENT_UPI_ID', 'hariskuttu21-1@okhdfcbank') # UPI ID shown in the payment text.
PAYMENT_TEXT = environ.get('PAYMENT_TEXT', '<b>- ᴀᴠᴀɪʟᴀʙʟᴇ ᴘʟᴀɴs - \n\n- 9ʀs - 1 ᴡᴇᴇᴋ\n-<strike>28ʀs</strike> 21ʀs - 1 ᴍᴏɴᴛʜs\n- 69ʀs - 3 ᴍᴏɴᴛʜs\n- 120ʀs - 6 ᴍᴏɴᴛʜs\n\n🎁 ᴘʀᴇᴍɪᴜᴍ ғᴇᴀᴛᴜʀᴇs 🎁\n\n○ ᴀʟʟ ᴀᴄᴄᴇss\n○ ɴᴏ ᴄʜᴀɴɴᴇʟ ᴊᴏɪɴ ɴᴇᴇᴅᴇᴅ\n○ ɴᴏ ɴᴇᴇᴅ ᴛᴏ ᴠᴇʀɪғʏ\n○ ɴᴏ ɴᴇᴇᴅ ᴛᴏ ᴏᴘᴇɴ ʟɪɴᴋ\n○ ᴅɪʀᴇᴄᴛ ғɪʟᴇs\n○ ᴀᴅ-ғʀᴇᴇ ᴇxᴘᴇʀɪᴇɴᴄᴇ\n○ ʜɪɢʜ-sᴘᴇᴇᴅ ᴅᴏᴡɴʟᴏᴀᴅ ʟɪɴᴋ\n○ ᴍᴜʟᴛɪ-ᴘʟᴀʏᴇʀ sᴛʀᴇᴀᴍɪɴɢ ʟɪɴᴋs\n○ ᴜɴʟɪᴍɪᴛᴇᴅ ᴍᴏᴠɪᴇs & sᴇʀɪᴇs\n○ ꜰᴜʟʟ ᴀᴅᴍɪɴ sᴜᴘᴘᴏʀᴛ\n○ ʀᴇǫᴜᴇsᴛ ᴡɪʟʟ ʙᴇ ᴄᴏᴍᴘʟᴇᴛᴇᴅ ɪɴ 1ʜ ɪꜰ ᴀᴠᴀɪʟᴀʙʟᴇ\n\n✨ 𝐔𝐏𝐈 𝐈𝐃 ➪ <code>' + PAYMENT_UPI_ID + '</code> \n\nᴄʟɪᴄᴋ ᴛᴏ ᴄʜᴇᴄᴋ ʏᴏᴜʀ ᴀᴄᴛɪᴠᴇ ᴘʟᴀɴ /myplan\n\n💢 ᴍᴜsᴛ sᴇɴᴅ sᴄʀᴇᴇɴsʜᴏᴛ ᴀғᴛᴇʀ ᴘᴀʏᴍᴇɴᴛ\n\n‼️ ᴀғᴛᴇʀ sᴇɴᴅɪɴɢ ᴀ sᴄʀᴇᴇɴsʜᴏᴛ ᴘʟᴇᴀsᴇ ɢɪᴠᴇ ᴜs sᴏᴍᴇ ᴛɪᴍᴇ ᴛᴏ ᴀᴅᴅ ʏᴏᴜ ɪɴ ᴛʜᴇ ᴘʀᴇᴍɪᴜᴍ</b>')





# Links
GRP_LNK = environ.get('GRP_LNK', 'https://t.me/moovidexsphere')
CHNL_LNK = environ.get('CHNL_LNK', 'https://t.me/moovidex')
SUPPORT_CHAT = environ.get('SUPPORT_CHAT', 'https://t.me/moovidexvangaurd') # Support Chat Link Without https:// or @
OWNER_LNK = environ.get('OWNER_LNK', 'https://t.me/h21tg')

# True Or False
AI_SPELL_CHECK = _bool('AI_SPELL_CHECK', True)
PM_SEARCH = _bool('PM_SEARCH', True)
BUTTON_MODE = _bool('BUTTON_MODE', True)
MAX_BTN = _bool('MAX_BTN', True)
IS_TUTORIAL = _bool('IS_TUTORIAL', False)
IMDB = _bool('IMDB', False)
AUTO_FFILTER = _bool('AUTO_FFILTER', True)
AUTO_DELETE = _bool('AUTO_DELETE', True)
LONG_IMDB_DESCRIPTION = _bool('LONG_IMDB_DESCRIPTION', False)
SPELL_CHECK_REPLY = _bool('SPELL_CHECK_REPLY', True)
MELCOW_NEW_USERS = _bool('MELCOW_NEW_USERS', True)
PROTECT_CONTENT = _bool('PROTECT_CONTENT', False)
PUBLIC_FILE_STORE = _bool('PUBLIC_FILE_STORE', True)
NO_RESULTS_MSG = _bool('NO_RESULTS_MSG', False)
USE_CAPTION_FILTER = _bool('USE_CAPTION_FILTER', True)


# Token Verification Info :
VERIFY = _bool('VERIFY', False)
VERIFY_SHORTLINK_URL = environ.get('VERIFY_SHORTLINK_URL', '')
VERIFY_SHORTLINK_API = environ.get('VERIFY_SHORTLINK_API', '')
VERIFY_TUTORIAL = environ.get('VERIFY_TUTORIAL', '')

# If You Fill Second Shortner Then Bot Attach Both First And Second Shortner And Use It For Verify.
VERIFY_SECOND_SHORTNER = _bool('VERIFY_SECOND_SHORTNER', False)
# if verify second shortner is True then fill below url and api
VERIFY_SND_SHORTLINK_URL = environ.get('VERIFY_SND_SHORTLINK_URL', '')
VERIFY_SND_SHORTLINK_API = environ.get('VERIFY_SND_SHORTLINK_API', '')


# Shortlink Info
SHORTLINK_MODE = _bool('SHORTLINK_MODE', False) # Set True Or False
SHORTLINK_URL = environ.get('SHORTLINK_URL', '')
SHORTLINK_API = environ.get('SHORTLINK_API', '')
TUTORIAL = environ.get('TUTORIAL', '') # How Open Shortner Link Video Link , Channel Link Where You Upload Your Video.


# Others
CACHE_TIME = _int('CACHE_TIME', 1800)
MAX_B_TN = _int('MAX_B_TN', 5)
PORT = _int('PORT', 8080)
MSG_ALRT = environ.get('MSG_ALRT', '⏳ MOOVIDEX ENTERTAINMENTS™')
CUSTOM_FILE_CAPTION = environ.get("CUSTOM_FILE_CAPTION", f"{script.CAPTION}")
BATCH_FILE_CAPTION = environ.get("BATCH_FILE_CAPTION", CUSTOM_FILE_CAPTION)
IMDB_TEMPLATE = environ.get("IMDB_TEMPLATE", f"{script.IMDB_TEMPLATE_TXT}")
MAX_LIST_ELM = environ.get("MAX_LIST_ELM", None)


# Choose Option Settings 
LANGUAGES = ["malayalam", "tamil", "english", "hindi", "telugu", "kannada", "bengali", "punjabi"]
SEASONS = ["season 1", "season 2", "season 3", "season 4", "season 5", "season 6", "season 7", "season 8", "season 9", "season 10"]
EPISODES = ["E01", "E02", "E03", "E04", "E05", "E06", "E07", "E08", "E09", "E10", "E11", "E12", "E13", "E14", "E15", "E16", "E17", "E18", "E19", "E20", "E21", "E22", "E23", "E24", "E25", "E26", "E27", "E28", "E29", "E30", "E31", "E32", "E33", "E34", "E35", "E36", "E37", "E38", "E39", "E40"]
QUALITIES = ["360p", "480p", "720p", "1080p", "1440p", "2160p"]
YEARS = ["1900", "1991", "1992", "1993", "1994", "1995", "1996", "1997", "1998", "1999", "2000", "2001", "2002", "2003", "2004", "2005", "2006", "2007", "2008", "2009", "2010", "2011", "2012", "2013", "2014", "2015", "2016", "2017", "2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025"]


                           # Don't Remove Credit @VJ_Botz
                           # Subscribe YouTube Channel For Amazing Bot @Tech_VJ
                           # Ask Doubt on telegram @KingVJ01


# Online Stream and Download
STREAM_MODE = _bool('STREAM_MODE', True) # Set True or False
#Stream file store
STREAM_FILES_CHANNEL = _int('STREAM_FILES_CHANNEL', LOG_CHANNEL)
# If Stream Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
MULTI_CLIENT = False
SLEEP_THRESHOLD = _int('SLEEP_THRESHOLD', 60)
PING_INTERVAL = _int('PING_INTERVAL', 1200)  # 20 minutes
if 'DYNO' in environ:
    ON_HEROKU = True
else:
    ON_HEROKU = False
URL = environ.get("URL", "https://testofvjfilter-1fa60b1b8498.herokuapp.com/")


# Rename Info : If True Then Bot Rename File Else Not
RENAME_MODE = _bool('RENAME_MODE', False) # Set True or False


# Auto Approve Info : If True Then Bot Approve New Upcoming Join Request Else Not
AUTO_APPROVE_MODE = _bool('AUTO_APPROVE_MODE', False) # Set True or False


# Start Command Reactions
REACTIONS = ["🤝", "😇", "🤗", "😍", "👍", "🎅", "😐", "🥰", "🤩", "😱", "🤣", "😘", "👏", "😛", "😈", "🎉", "⚡️", "🫡", "🤓", "😎", "🏆", "🔥", "🤭", "🌚", "🆒", "👻", "😁"] #don't add any emoji because tg not support all emoji reactions


if MULTIPLE_DATABASE is False:
    USER_DB_URI = DATABASE_URI
    OTHER_DB_URI = DATABASE_URI
    FILE_DB_URI = DATABASE_URI
    SEC_FILE_DB_URI = DATABASE_URI
else:
    USER_DB_URI = O_DB_URI    # This Db is for User Data Store
    OTHER_DB_URI = O_DB_URI       # This Db Is For Other Data Store
    FILE_DB_URI = F_DB_URI        # This Db Is For File Data Store
    SEC_FILE_DB_URI = S_DB_URI    # This Db is for File Data Store When First Db Is Going To Be Full.


# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01


