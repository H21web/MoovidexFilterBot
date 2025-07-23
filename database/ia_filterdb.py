# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import re, base64
from struct import pack
from pyrogram.file_id import FileId
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from info import FILE_DB_URI, SEC_FILE_DB_URI, DATABASE_NAME, COLLECTION_NAME, MULTIPLE_DATABASE, USE_CAPTION_FILTER

# DB Connections
client = MongoClient(FILE_DB_URI)
db = client[DATABASE_NAME]
col = db[COLLECTION_NAME]

sec_client = MongoClient(SEC_FILE_DB_URI)
sec_db = sec_client[DATABASE_NAME]
sec_col = sec_db[COLLECTION_NAME]

def clean_file_name(file_name):
    file_name = re.sub(r"[_\-\.\+]", " ", str(file_name))
    for char in ['[', ']', '(', ')', '{', '}']:
        file_name = file_name.replace(char, '')
    return ' '.join(
        filter(
            lambda x: not x.startswith(('@', 'http', 'www.', 't.me')),
            file_name.split()
        )
    )

def encode_file_id(s: bytes) -> str:
    r, n = b"", 0
    for i in s + bytes([22, 4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0
            r += bytes([i])
    return base64.urlsafe_b64encode(r).decode().rstrip("=")

def unpack_new_file_id(new_file_id):
    decoded = FileId.decode(new_file_id)
    return encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )

def is_file_already_saved(file_id, file_name, file_size=None):
    filter_id = {'file_id': file_id}
    filter_name_size = {'file_name': file_name, 'file_size': file_size} if file_size else None
    for collection in [col, sec_col] if MULTIPLE_DATABASE else [col]:
        if collection.find_one(filter_id) or (filter_name_size and collection.find_one(filter_name_size)):
            return True
    return False

async def save_file(media):
    file_id = unpack_new_file_id(media.file_id)
    file_name = clean_file_name(media.file_name)
    file = {
        'file_id': file_id,
        'file_name': file_name,
        'file_size': media.file_size,
        'caption': media.caption.html if media.caption else None
    }

    if is_file_already_saved(file_id, file_name, media.file_size):
        return False, 0

    try:
        col.insert_one(file)
        print(f"{file_name} saved.")
        return True, 1
    except DuplicateKeyError:
        return False, 0
    except:
        if MULTIPLE_DATABASE:
            try:
                sec_col.insert_one(file)
                print(f"{file_name} saved in backup DB.")
                return True, 1
            except DuplicateKeyError:
                return False, 0
        else:
            print("DB full. Enable MULTIPLE_DATABASE.")
            return False, 0

async def get_search_results(chat_id, query, file_type=None, max_results=10, offset=0, filter=False):
    query = query.strip()
    if not query:
        raw_pattern = "."
    elif ' ' not in query:
        raw_pattern = rf"(\b|[.\-+_]){re.escape(query)}(\b|[.\-+_])"
    else:
        raw_pattern = re.sub(r'\s+', r'.*[\s.\-+_]', re.escape(query))

    try:
        regex = re.compile(raw_pattern, re.IGNORECASE)
    except re.error:
        regex = re.compile(re.escape(query), re.IGNORECASE)

    base_filter = {'file_name': regex}
    if USE_CAPTION_FILTER:
        search_filter = {'$or': [base_filter, {'caption': regex}]}
    else:
        search_filter = base_filter

    cursor_primary = col.find(search_filter).sort('$natural', -1).skip(offset).limit(max_results)
    files = list(cursor_primary)

    if MULTIPLE_DATABASE:
        cursor_secondary = sec_col.find(search_filter).sort('$natural', -1).skip(offset).limit(max_results)
        files += list(cursor_secondary)

    total_primary = col.count_documents(search_filter)
    total_secondary = sec_col.count_documents(search_filter) if MULTIPLE_DATABASE else 0
    total_results = total_primary + total_secondary

    next_offset = "" if (offset + max_results) >= total_results else (offset + max_results)

    return files, next_offset, total_results

async def get_bad_files(query):
    query = query.strip()
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = rf'(\b|[.+-_]){re.escape(query)}(\b|[.+-_])'
    else:
        raw_pattern = re.sub(r'\s+', r'.*[s.+-_]', re.escape(query))

    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except re.error:
        return [], 0

    filter_criteria = {'file_name': regex}
    if USE_CAPTION_FILTER:
        filter_criteria = {'$or': [filter_criteria, {'caption': regex}]}

    collections = [col, sec_col] if MULTIPLE_DATABASE else [col]
    files = []
    total = 0
    for collection in collections:
        found = list(collection.find(filter_criteria))
        files.extend(found)
        total += len(found)

    return files, total

async def get_file_details(query):
    return col.find_one({'file_id': query}) or sec_col.find_one({'file_id': query})
