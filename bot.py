# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

# Clone Code Credit : YT - @Tech_VJ / TG - @VJ_Bots / GitHub - @VJBots

import asyncio
import logging
import logging.config
from pathlib import Path

import pytz

# Get logging configurations (resolved from this file, not the CWD)
logging.config.fileConfig(Path(__file__).resolve().parent / 'logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)

from pyrogram import filters, idle, StopPropagation
from pyrogram.errors import (
    ChannelPrivate,
    ChatAdminRequired,
    ChatWriteForbidden,
    PeerIdInvalid,
)
from pyrogram.handlers import MessageHandler

from database.users_chats_db import db
from database.ia_filterdb import ensure_indexes
from info import *
from utils import temp, close_http_session
from Script import script
from datetime import date, datetime
from aiohttp import web
from plugins import web_server


from TechVJ.bot import TechVJBot
from TechVJ.util.keepalive import ping_server
from TechVJ.bot.clients import initialize_clients
from TechVJ.util.conversation import install as install_conversation, match_listener

# Native ask()/listen() support (pyromod was never installed; see
# TechVJ/util/conversation.py). Registered at the earliest handler group so a
# pending conversation captures the reply before other handlers see it.
_conversation_deliver = install_conversation()


async def _conversation_router(client, message):
    if await _conversation_deliver(message):
        raise StopPropagation


TechVJBot.add_handler(
    MessageHandler(
        _conversation_router,
        filters.create(lambda _, __, m: match_listener(m) is not None),
    ),
    group=-1000,
)


async def start():
    print('\n')
    print('Initalizing Your Bot')
    await TechVJBot.start()
    me = await TechVJBot.get_me()
    try:
        await ensure_indexes()
    except Exception as e:
        logging.warning("Index setup skipped: %s", e)
    await initialize_clients()
    if ON_HEROKU:
        asyncio.create_task(ping_server())
    b_users, b_chats = await db.get_banned()
    temp.BANNED_USERS = b_users
    temp.BANNED_CHATS = b_chats
    temp.BOT = TechVJBot
    temp.ME = me.id
    temp.U_NAME = me.username
    temp.B_NAME = me.first_name
    logging.info(script.LOGO)
    tz = pytz.timezone('Asia/Kolkata')
    today = date.today()
    now = datetime.now(tz)
    time = now.strftime("%H:%M:%S %p")
    try:
        await TechVJBot.send_message(chat_id=LOG_CHANNEL, text=script.RESTART_TXT.format(today, time))
    except (PeerIdInvalid, ChannelPrivate, ChatWriteForbidden) as e:
        logging.error("Could not send restart notice to LOG_CHANNEL %s: %s. "
                      "Make the bot an admin in the log channel with full rights.", LOG_CHANNEL, e)
    for ch in CHANNELS:
        try:
            k = await TechVJBot.send_message(chat_id=ch, text="**Bot Restarted**")
            await k.delete()
        except (PeerIdInvalid, ChannelPrivate, ChatAdminRequired, ChatWriteForbidden) as e:
            logging.error("Could not post restart notice in file channel %s: %s. "
                          "Make the bot an admin there with full rights.", ch, e)
    if AUTH_CHANNEL is not None:
        try:
            k = await TechVJBot.send_message(chat_id=AUTH_CHANNEL, text="**Bot Restarted**")
            await k.delete()
        except (PeerIdInvalid, ChannelPrivate, ChatAdminRequired, ChatWriteForbidden) as e:
            logging.error("Could not post restart notice in AUTH_CHANNEL %s: %s. "
                          "Make the bot an admin there with full rights.", AUTH_CHANNEL, e)

    app = web.AppRunner(await web_server())
    await app.setup()
    bind_address = "0.0.0.0"
    await web.TCPSite(app, bind_address, PORT).start()
    try:
        await idle()
    finally:
        await close_http_session()


if __name__ == '__main__':
    try:
        asyncio.run(start())
    except KeyboardInterrupt:
        logging.info('Service Stopped Bye 👋')
