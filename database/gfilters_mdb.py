# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01


import motor.motor_asyncio
from info import OTHER_DB_URI, DATABASE_NAME
from pyrogram import enums
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

# Motor (async) client: the old synchronous PyMongo client blocked the event
# loop inside every `async def` here.
myclient = motor.motor_asyncio.AsyncIOMotorClient(OTHER_DB_URI)
mydb = myclient[DATABASE_NAME]



async def add_gfilter(gfilters, text, reply_text, btn, file, alert):
    mycol = mydb[str(gfilters)]
    # mycol.create_index([('text', 'text')])

    data = {
        'text': str(text),
        'reply': str(reply_text),
        'btn': str(btn),
        'file': str(file),
        'alert': str(alert)
    }

    try:
        await mycol.update_one({'text': str(text)}, {"$set": data}, upsert=True)
    except Exception:
        logger.exception('Some error occured!')


async def find_gfilter(gfilters, name):
    mycol = mydb[str(gfilters)]

    doc = await mycol.find_one({"text": name})
    if not doc:
        return None, None, None, None
    return doc.get('reply'), doc.get('btn'), doc.get('alert'), doc.get('file')


async def get_gfilters(gfilters):
    mycol = mydb[str(gfilters)]

    texts = []
    try:
        async for doc in mycol.find():
            texts.append(doc['text'])
    except Exception:
        logger.exception('get_gfilters failed')
    return texts


async def delete_gfilter(message, text, gfilters):
    mycol = mydb[str(gfilters)]

    myquery = {'text': text}
    query = await mycol.count_documents(myquery)
    if query == 1:
        await mycol.delete_one(myquery)
        await message.reply_text(
            f"'`{text}`'  deleted. I'll not respond to that gfilter anymore.",
            quote=True,
            parse_mode=enums.ParseMode.MARKDOWN
        )
    else:
        await message.reply_text("Couldn't find that gfilter!", quote=True)


async def del_allg(message, gfilters):
    if str(gfilters) not in await mydb.list_collection_names():
        await message.edit_text("Nothing to Remove !")
        return

    mycol = mydb[str(gfilters)]
    try:
        await mycol.drop()
        await message.edit_text(f"All gfilters has been removed !")
    except Exception:
        await message.edit_text("Couldn't remove all gfilters !")
        return


async def count_gfilters(gfilters):
    mycol = mydb[str(gfilters)]

    count = await mycol.count_documents({})
    return False if count == 0 else count


async def gfilter_stats():
    collections = await mydb.list_collection_names()

    if "CONNECTION" in collections:
        collections.remove("CONNECTION")

    totalcount = 0
    for collection in collections:
        mycol = mydb[collection]
        count = await mycol.count_documents({})
        totalcount += count

    totalcollections = len(collections)

    return totalcollections, totalcount
