# Diagnostic: log every raw MTProto update to prove/disprove update delivery.
# Temporary file - remove after diagnosis.
import logging

from pyrogram import Client


@Client.on_raw_update()
async def diag_raw_update(client, update, users, chats):
    logging.info("DIAG RAW UPDATE: %s", type(update).__name__)
