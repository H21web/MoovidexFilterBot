
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
    sec_db = None
    sec_col = None

async def ensure_indexes():
    """Create helper indexes if missing. Non-unique on purpose: deployed data
    is not guaranteed duplicate-free, so a unique index could fail and block
    startup. Safe to call repeatedly (create_index is idempotent)."""
    targets = [("primary", col)]
    if MULTIPLE_DATABASE and sec_col is not None:
        targets.append(("secondary", sec_col))
    for label, collection in targets:
        try:
            await collection.create_index("file_id", name="file_id_1")
            logger.info(f"Ensured file_id index on {label} file collection")
        except Exception as e:
            logger.warning(f"Could not ensure index on {label} file collection: {e}")

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
        if MULTIPLE_DATABASE and sec_col is not None:
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
    
    if MULTIPLE_DATABASE and sec_col is not None:
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

    # Count first: correct cross-DB pagination needs the primary match count so
    # the secondary query can skip the right number of documents.
    if not filter_criteria:
        primary_total = await col.estimated_document_count()
    else:
        primary_total = await col.count_documents(filter_criteria)

    files = []
    if not MULTIPLE_DATABASE or sec_col is None:
        total_results = primary_total
        cursor1 = col.find(filter_criteria, projection).sort('$natural', -1).skip(offset).limit(max_results)
        async for file in cursor1:
            files.append(file)
    else:
        if not filter_criteria:
            secondary_total = await sec_col.estimated_document_count()
        else:
            secondary_total = await sec_col.count_documents(filter_criteria)
        total_results = primary_total + secondary_total

        if offset < primary_total:
            # Page starts in the primary DB; fill the rest from secondary.
            cursor1 = col.find(filter_criteria, projection).sort('$natural', -1).skip(offset).limit(max_results)
            async for file in cursor1:
                files.append(file)
            remaining = max_results - len(files)
            if remaining > 0:
                cursor2 = sec_col.find(filter_criteria, projection).sort('$natural', -1).skip(0).limit(remaining)
                async for file in cursor2:
                    files.append(file)
        else:
            # Page lies entirely in the secondary DB.
            cursor2 = sec_col.find(filter_criteria, projection).sort('$natural', -1).skip(offset - primary_total).limit(max_results)
            async for file in cursor2:
                files.append(file)

    next_offset = "" if (offset + max_results) >= total_results else (offset + max_results)

    return files, next_offset, total_results

def bad_files_filter(query):
    """Build the file_name/caption filter for admin mass-delete. The query is
    regex-escaped: raw user input used to crash this with `re.error` (or match
    far more than intended) when it contained regex metacharacters."""
    query = query.strip()
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = rf'(\b|[.+-_]){re.escape(query)}(\b|[.+-_])'
    else:
        raw_pattern = r'.*[s.+-_]'.join(re.escape(word) for word in query.split())

    regex = {'$regex': raw_pattern, '$options': 'i'}
    filter_criteria = {'file_name': regex}

    if USE_CAPTION_FILTER:
        filter_criteria = {'$or': [filter_criteria, {'caption': regex}]}
    return filter_criteria


async def get_bad_files(query, file_type=None, use_filter=False):
    filter_criteria = bad_files_filter(query)
    # Only the fields the delete flows need; full docs (with captions) used to
    # be loaded for every match.
    projection = {'file_id': 1, 'file_name': 1, '_id': 0}

    files = []
    async for file in col.find(filter_criteria, projection):
        files.append(file)

    if MULTIPLE_DATABASE and sec_col is not None:
        async for file in sec_col.find(filter_criteria, projection):
            files.append(file)

    return files, len(files)


async def count_bad_files(query):
    """Match count for `get_bad_files` without loading any documents."""
    filter_criteria = bad_files_filter(query)
    total = await col.count_documents(filter_criteria)
    if MULTIPLE_DATABASE and sec_col is not None:
        total += await sec_col.count_documents(filter_criteria)
    return total

async def get_file_details(query):
    file = await col.find_one({'file_id': query})
    if not file and MULTIPLE_DATABASE and sec_col is not None:
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
    
