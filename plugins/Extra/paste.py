# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import os
import re
import json
import aiohttp
from pyrogram import Client, filters

#Headers
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.104 Safari/537.36",
    "content-type": "application/json",
}

#Pastebins
async def p_paste(message, extension=None):
    siteurl = "https://pasty.lus.pm/api/v1/pastes"
    data = {"content": message}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url=siteurl, data=json.dumps(data), headers=headers) as response:
                if response.status == 201: # 201 Created typically, or check ok
                     resp_json = await response.json()
                     purl = (
                        f"https://pasty.lus.pm/{resp_json['id']}.{extension}"
                        if extension
                        else f"https://pasty.lus.pm/{resp_json['id']}.txt"
                     )
                     return {
                        "url": purl,
                        "raw": f"https://pasty.lus.pm/{resp_json['id']}/raw",
                        "bin": "Pasty",
                     }
    except Exception as e:
        return {"error": str(e)}
    return {"error": "Unable to reach pasty.lus.pm"}



@Client.on_message(filters.command(["tgpaste", "pasty", "paste"]))
async def pasty(client, message):
    pablo = await message.reply_text("`Please wait...`")
    if ' ' in message.text:
        message_s = message.text.split(" ", 1)[1]
    elif message.reply_to_message:
        message_s = message.reply_to_message.text
    else:
        await pablo.edit("sorry no in put. please repy to a text or /paste with text")
        return
    if not message_s:
        if not message.reply_to_message:
            await pablo.edit("`Only text and documents are supported.`")
            return
        if not message.reply_to_message.text:
            file = await message.reply_to_message.download()
            try:
                with open(file, "r") as f:
                    m_list = f.read()
            finally:
                os.remove(file)
            message_s = m_list
        else:
            message_s = message.reply_to_message.text

    ext = "py"
    x = await p_paste(message_s, ext)
    if "error" in x:
        await pablo.edit(f"Failed to paste: {x['error']}")
        return
    p_link = x["url"]
    p_raw = x["raw"]

    pasted = f"**Successfully Paste to Pasty**\n\n**Link:** • [Click here]({p_link})\n\n**Raw Link:** • [Click here]({p_raw})"
    await pablo.edit(pasted, disable_web_page_preview=True)
