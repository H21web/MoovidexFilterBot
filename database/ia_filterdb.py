
# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import re, base64, logging
from struct import pack
from pyrogram.file_id import FileId
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from info import FILE_DB_URI, SEC_FILE_DB_URI, DATABASE_NAME, COLLECTION_NAME, MULTIPLE_DATABASE, USE_CAPTION_FILTER, MAX_B_TN

logger = logging.getLogger(__name__)

# Async DB Client
client = AsyncIOMotorClient(FILE_DB_URI)
db = client[DATABASE_NAME]
col = db[COLLECTION_NAME]

if MULTIPLE_DATABASE:
    sec_client = AsyncIOMotorClient(SEC_FILE_DB_URI)
    sec_db = sec_client[DATABASE_NAME]
    sec_col = sec_db[COLLECTION_NAME]
else:
    sec_col = None

async def save_file(media):
    """Save file in the database."""
    
    file_id = unpack_new_file_id(media.file_id)
    file_name = clean_file_name(media.file_name)
    
    file = {
        'file_id': file_id,
        'file_name': file_name,
        'file_size': media.file_size,
        'caption': media.caption.html if media.caption else None
    }

    if await is_file_already_saved(file_id, file_name):
        return False, 0

    try:
        await col.insert_one(file)
        # Hook for Instant Update
        try:
             from plugins.Extra.today import check_and_post_if_needed
             import asyncio
             asyncio.create_task(check_and_post_if_needed(file_name))
        except Exception: 
            pass
        return True, 1
    except DuplicateKeyError:
        return False, 0
    except Exception as e:
        if MULTIPLE_DATABASE and sec_col:
            try:
                await sec_col.insert_one(file)
                try:
                     from plugins.Extra.today import check_and_post_if_needed
                     import asyncio
                     asyncio.create_task(check_and_post_if_needed(file_name))
                except Exception:
                    pass
                return True, 1
            except DuplicateKeyError:
                return False, 0
            except Exception as e:
                logger.error(f"Error saving to secondary DB: {e}")
                return False, 0
        else:
            logger.error(f"Database Full Error: {e}")
            return False, 0

def clean_file_name(file_name):
    """Clean and format the file name."""
    file_name = re.sub(r"(_|\-|\.|\+)", " ", str(file_name)) 
    unwanted_chars = ['[', ']', '(', ')', '{', '}']
    
    for char in unwanted_chars:
        file_name = file_name.replace(char, '')
        
    return ' '.join(filter(lambda x: not x.startswith('@') and not x.startswith('http') and not x.startswith('www.') and not x.startswith('t.me'), file_name.split()))

async def is_file_already_saved(file_id, file_name):
    """Check if the file is already saved in either collection."""
    found1 = {'file_name': file_name}
    found = {'file_id': file_id}

    if await col.find_one(found1) or await col.find_one(found):
        return True
    
    if MULTIPLE_DATABASE and sec_col:
        if await sec_col.find_one(found1) or await sec_col.find_one(found):
            return True
            
    return False

async def get_search_results(chat_id, query, file_type=None, max_results=10, offset=0, filter=False):
    """For given query return (results, next_offset)"""
    
    query = query.strip()
    
    if not query:
        filter_criteria = {}
    elif ' ' not in query:
        regex = {'$regex': query, '$options': 'i'}
        filter_criteria = {'$or': [{'file_name': regex}, {'caption': regex}]}
    else:
        # Optimized Logic: Use simple space split
        words = query.split()
        regex_list = []
        for word in words:
            # Escape to prevent regex errors
            pattern = re.escape(word)
            word_regex = {'$regex': pattern, '$options': 'i'}
            regex_list.append({'$or': [{'file_name': word_regex}, {'caption': word_regex}]})
        
        filter_criteria = {'$and': regex_list}

    projection = {'file_id': 1, 'file_name': 1, 'file_size': 1, 'caption': 1, '_id': 0}

    files = []
    cursor1 = col.find(filter_criteria, projection).sort('$natural', -1).skip(offset).limit(max_results)
    async for file in cursor1:
        files.append(file)
        
    if MULTIPLE_DATABASE and sec_col:
        # If we haven't filled max_results, check secondary
        if len(files) < max_results:
             # Adjust limit based on what we already have
             remaining_limit = max_results - len(files)
             # Note: Offset handling across two DBs is tricky. 
             # For simplicity/speed in this context, we just query secondary with same simple logic
             # Proper pagination across 2 DBs requires counting or complex logic.
             # Current logic: Append secondary results
             cursor2 = sec_col.find(filter_criteria, projection).sort('$natural', -1).skip(offset).limit(remaining_limit)
             async for file in cursor2:
                 files.append(file)
                 
    # Optimized Count: Use estimated_document_count if no filter (fast), else count_documents
    if not filter_criteria:
        total_results = await col.estimated_document_count()
        if MULTIPLE_DATABASE and sec_col:
            total_results += await sec_col.estimated_document_count()
    else:
        total_results = await col.count_documents(filter_criteria)
        if MULTIPLE_DATABASE and sec_col:
            total_results += await sec_col.count_documents(filter_criteria)

    next_offset = "" if (offset + max_results) >= total_results else (offset + max_results)

    return files, next_offset, total_results

async def get_bad_files(query, file_type=None, use_filter=False):
    query = query.strip()
    # Logic preserved but made async
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = rf'(\b|[.+-_]){query}(\b|[.+-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[s.+-_]')
        
    regex = {'$regex': raw_pattern, '$options': 'i'}
    filter_criteria = {'file_name': regex}
    
    if USE_CAPTION_FILTER:
        filter_criteria = {'$or': [filter_criteria, {'caption': regex}]}

    files = []
    async for file in col.find(filter_criteria):
        files.append(file)
        
    total_results = len(files)
    
    if MULTIPLE_DATABASE and sec_col:
         async for file in sec_col.find(filter_criteria):
             files.append(file)
         total_results = len(files)

    return files, total_results

async def get_file_details(query):
    file = await col.find_one({'file_id': query})
    if not file and MULTIPLE_DATABASE and sec_col:
        file = await sec_col.find_one({'file_id': query})
    return file

def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0
    for i in s + bytes([22]) + bytes([4]):
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
    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )
    return file_id
    
