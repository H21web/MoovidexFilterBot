import os
import traceback
import requests
import aiohttp
import asyncio
import random
from datetime import datetime
from collections import defaultdict
from pyrogram import Client, filters
from pyrogram.types import Message
from pydub import AudioSegment
from utils import get_poster
from info import ADMINS, LOG_CHANNEL, DEEPGRAM_API_KEYS
from plugins.pm_filter import boovo
from utils import get_settings

VOICE_LIMIT = 10
VOICE_DURATION_LIMIT = 5  # seconds
VOICE_DELETE_DELAY = 300  # seconds (5 minutes)
daily_usage = defaultdict(lambda: defaultdict(int))


def transcribe_with_deepgram(audio_path: str) -> str:
    keys = random.sample(DEEPGRAM_API_KEYS, len(DEEPGRAM_API_KEYS))
    for api_key in keys:
        try:
            with open(audio_path, "rb") as audio_file:
                response = requests.post(
                    "https://api.deepgram.com/v1/listen?model=whisper-large",
                    headers={
                        "Authorization": f"Token {api_key}",
                        "Content-Type": "audio/wav"
                    },
                    data=audio_file,
                    timeout=15
                )
            if response.status_code == 200:
                result = response.json()
                return result.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "")
            else:
                print(f"API error: {response.status_code} {response.text}")
        except Exception as e:
            print(f"Deepgram API error with key {api_key[:6]}: {e}")
    return ""


def convert_ogg_to_wav(input_path: str, output_path: str):
    sound = AudioSegment.from_ogg(input_path)
    sound.export(output_path, format="wav")


async def find_movie_with_api(query: str) -> str:
    api_url = f"https://imdblinkz.s1mallufiles.workers.dev/?q={query}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=10) as response:
                if response.status != 200:
                    print(f"API Error {response.status}")
                    return "unknown movie"
                data = await response.json()
                results = data.get("results", [])
                if not results:
                    return "unknown movie"
                imdb_id = results[0].get("id")
                if not imdb_id:
                    return "unknown movie"
                movie_data = await get_poster(imdb_id, id=True)
                return movie_data.get("title", "unknown movie") if movie_data else "unknown movie"
    except Exception as e:
        print(f"API Exception: {e}")
        return "unknown movie"


@Client.on_message(filters.voice)
async def handle_voice(bot: Client, message: Message):
    user = message.from_user
    if not user:
        await message.reply_text("❌ Cannot identify sender of this voice message.")
        return

    user_id = user.id
    today_str = datetime.utcnow().strftime('%Y-%m-%d')

    if message.voice.duration > VOICE_DURATION_LIMIT:
        await message.reply_text(f"⚠️ Voice too long. Limit is {VOICE_DURATION_LIMIT} seconds.")
        return

    if user_id not in ADMINS:
        if daily_usage[user_id][today_str] >= VOICE_LIMIT:
            await message.reply_text("🚫 You've reached your daily voice search limit.")
            return
        daily_usage[user_id][today_str] += 1

    status = await message.reply_text("🎙 Transcribing your voice...")

    voice_file = None
    wav_file = None

    try:
        voice_file = await bot.download_media(message.voice)
        if not voice_file.endswith(".ogg"):
            await status.edit_text("❌ Only .ogg voice messages are supported.")
            return

        wav_file = voice_file.replace(".ogg", ".wav")

        await asyncio.to_thread(convert_ogg_to_wav, voice_file, wav_file)
        text = await asyncio.to_thread(transcribe_with_deepgram, wav_file)

        if not text.strip():
            await status.edit_text("🤖 Could not understand speech. Please try again.")
            await log_unrecognized(bot, user, voice_file)
            return

        await status.edit_text("🔍 Searching for the movie...")
        title = await find_movie_with_api(text)

        if title.lower().strip() == "unknown movie":
            await status.edit_text("❌ Movie not found.")
            return

        await status.delete()
        await boovo(bot, title, message)
        await log_success(bot, user, title, text, voice_file)

        settings = await get_settings(message.chat.id)
        if settings.get("auto_delete"):
            asyncio.create_task(delayed_delete(message, VOICE_DELETE_DELAY))

    except Exception as e:
        print(f"Handler error: {e}")
        await status.edit_text("❌ An unexpected error occurred.")
        await log_error(bot, user, e)

    finally:
        for f in [voice_file, wav_file]:
            if f and os.path.exists(f):
                try:
                    os.remove(f)
                except Exception as cleanup_error:
                    print("Cleanup error:", cleanup_error)


async def delayed_delete(msg: Message, delay: int):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception as delete_error:
        print("Failed to delete message:", delete_error)


async def log_unrecognized(bot: Client, user, voice_file):
    try:
        user_display = f"@{user.username}" if user.username else f"{user.first_name} {user.last_name or ''}".strip()
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        text = (
            f"🛑 *No Transcript Found*\n\n"
            f"*User:* {user_display} (`{user.id}`)\n"
            f"*Time:* `{timestamp}`"
        )
        await bot.send_voice(chat_id=LOG_CHANNEL, voice=voice_file, caption=text)
    except Exception as e:
        print(f"Log unrecognized error: {e}")


async def log_success(bot: Client, user, title: str, text: str, voice_file: str):
    try:
        user_display = f"@{user.username}" if user.username else f"{user.first_name} {user.last_name or ''}".strip()
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        caption = (
            f"🎬 Title: {title}\n"
            f"🗣 Transcript: {text}\n\n"
            f"👤 User: {user_display}\n"
            f"🆔 ID: {user.id}\n"
            f"🕒 Time: {timestamp}"
        )
        await bot.send_voice(chat_id=LOG_CHANNEL, voice=voice_file, caption=caption)
    except Exception as e:
        print(f"Log success error: {e}")


async def log_error(bot: Client, user, exception):
    try:
        trace = traceback.format_exc()
        user_display = f"@{user.username}" if user.username else f"{user.first_name} {user.last_name or ''}".strip()
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        text = (
            f"⚠️ *Error Occurred*\n\n"
            f"*User:* {user_display} (`{user.id}`)\n"
            f"*Time:* `{timestamp}`\n"
            f"*Error:* ```{str(exception)}```\n\n"
            f"```{trace}```"
        )
        await bot.send_message(chat_id=LOG_CHANNEL, text=text)
    except Exception as e:
        print(f"Final logging error: {e}")
