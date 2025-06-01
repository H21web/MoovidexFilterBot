from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove, Message
import httpx

API_URL = "https://www.binged.com/wp-json/binged-api/v1/whats-streaming"
platform_data = {}

@Client.on_message(filters.regex(r"^🎬 What's Streaming$"))
async def handle_whats_streaming(client, message: Message):
    async with httpx.AsyncClient() as session:
        r = await session.get(API_URL)
        if r.status_code != 200:
            return await message.reply("⚠️ Failed to fetch data.")

        json_data = r.json()
        platform_data.clear()

        keyboard = []
        for pid, platform in json_data.items():
            title = platform.get("title")
            if title:
                keyboard.append([title])
                platform_data[title] = [m["title"] for m in platform.get("movies", [])]

        await message.reply(
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True),
            text=None  # No reply message
        )


@Client.on_message(filters.text)
async def handle_selection(client, message: Message):
    if message.text.startswith("/"):
        return  # Ignore commands

    text = message.text.strip()

    # Platform selected
    if text in platform_data:
        movie_titles = platform_data[text]
        if not movie_titles:
            return
        movie_buttons = [[title] for title in movie_titles]
        return await message.reply(
            reply_markup=ReplyKeyboardMarkup(movie_buttons, resize_keyboard=True, one_time_keyboard=True),
            text=None
        )

    # Movie selected
    for movie_list in platform_data.values():
        if text in movie_list:
            return await message.reply(text, reply_markup=ReplyKeyboardRemove())

    await message.reply("❌ Please use the provided keyboard.")
