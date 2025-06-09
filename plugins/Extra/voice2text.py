import os
import traceback
import requests
import asyncio
import random
from datetime import datetime
from collections import defaultdict
from pyrogram import Client, filters
from pyrogram.types import Message
from pydub import AudioSegment
from imdb import Cinemagoer
from googlesearch import search
import re

from info import ADMINS, LOG_CHANNEL, DEEPGRAM_API_KEYS  # DEEPGRAM_API_KEYS should be a list of your keys
from plugins.pm_filter import boovo

# IMDbPY client
ia = Cinemagoer()

VOICE_LIMIT = 10
VOICE_DURATION_LIMIT = 10  # seconds
VOICE_DELETE_DELAY = 300  # seconds (5 minutes)
daily_usage = defaultdict(lambda: defaultdict(int))  # user_id -> date_str -> count


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
                transcript = result.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "")
                if transcript:
                    return transcript
                else:
                    print(f"Deepgram key {api_key[:6]} returned empty transcript.")
            else:
                print(f"Deepgram key {api_key[:6]} API error: {response.status_code} {response.text}")
        except requests.Timeout:
            print(f"Deepgram key {api_key[:6]} timeout.")
        except Exception as e:
            print(f"Deepgram key {api_key[:6]} exception: {e}")
    return ""


def convert_ogg_to_wav(input_path: str, output_path: str):
    sound = AudioSegment.from_ogg(input_path)
    sound[:10000].export(output_path, format="wav")


def find_movie_with_imdb(query: str) -> str:
    try:
        results = ia.search_movie(query)
        if results:
            return results[0]['title']
    except Exception as e:
        print("IMDbPY error:", e)
    return ""


def find_movie_with_google(query: str) -> str:
    try:
        for url in search(f"{query} movie site:imdb.com", num_results=3):
            if "imdb.com/title" in url:
                return extract_title_from_url(url)
    except Exception as e:
        print("Google search error:", e)
    return re.sub(r'\W+', ' ', query).strip()


def extract_title_from_url(url: str) -> str:
    imdb_id = url.strip("/").split("/")[-1]
    if imdb_id.startswith("tt"):
        try:
            movie = ia.get_movie(imdb_id[2:])
            return movie.get('title', f"IMDb ID: {imdb_id}")
        except:
            return f"IMDb ID: {imdb_id}"
    return "Unknown movie"


@Client.on_message(filters.voice)
async def handle_voice(bot: Client, message: Message):
    user = message.from_user
    user_id = user.id
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    voice_file = None
    wav_file = None

    if message.voice.duration > VOICE_DURATION_LIMIT:
        await message.reply_text(f"⚠️ Voice message too long. Max {VOICE_DURATION_LIMIT} seconds.")
        return

    if user_id not in ADMINS:
        if daily_usage[user_id][today_str] >= VOICE_LIMIT:
            await message.reply_text("🚫 You've reached your daily voice search limit.")
            return
        daily_usage[user_id][today_str] += 1

    status = await message.reply_text("🎙 Please wait...")

    try:
        voice_file = await bot.download_media(message.voice)
        if not voice_file.endswith(".ogg"):
            await status.edit_text("❌ Only .ogg voice messages are supported.")
            return

        wav_file = voice_file.replace(".ogg", ".wav")

        await asyncio.to_thread(convert_ogg_to_wav, voice_file, wav_file)
        text = await asyncio.to_thread(transcribe_with_deepgram, wav_file)

        if not text:
            await status.edit_text("🤖 Could not recognize any speech or transcription timed out. Try Again")
            await log_unrecognized(bot, user, voice_file)
            return

        await status.delete()

        title = find_movie_with_imdb(text) or find_movie_with_google(text)

        if title.lower().strip() == "unknown movie":
            await message.reply_text("❌ Movie not found.")
            return

        await boovo(bot, title, message)
        await log_success(bot, user, title, text, voice_file)

        # 🔁 Delete user's original voice message after delay
        asyncio.create_task(delayed_delete(message, VOICE_DELETE_DELAY))

    except Exception as e:
        print("Voice handling error:", e)
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
        print("Failed to delete user's voice message:", delete_error)


# Logging helpers

async def log_unrecognized(bot: Client, user, voice_file):
    try:
        user_display = f"@{user.username}" if user.username else f"{user.first_name} {user.last_name or ''}".strip()
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        log_text = (
            f"🛑 *No Transcript Found*\n\n"
            f"*User:* {user_display} (`{user.id}`)\n"
            f"*Time:* `{timestamp}`\n"
            f"*Reason:* No recognizable speech or transcription timeout."
        )
        await bot.send_voice(chat_id=LOG_CHANNEL, voice=voice_file, caption=log_text)
    except Exception as log_error:
        print("Failed to log unrecognized voice:", log_error)


async def log_success(bot: Client, user, title: str, text: str, voice_file: str):
    try:
        user_display = f"@{user.username}" if user.username else f"{user.first_name} {user.last_name or ''}".strip()
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        caption_text = (
            f"🎬 Title: {title}\n"
            f"🗣 Transcript: {text}\n\n"
            f"👤 User: {user_display}\n"
            f"🆔 ID: {user.id}\n"
            f"🕒 Time: {timestamp}"
        )
        await bot.send_voice(chat_id=LOG_CHANNEL, voice=voice_file, caption=caption_text)
    except Exception as log_error:
        print("Logging success failed:", log_error)


async def log_error(bot: Client, user, exception):
    try:
        error_trace = traceback.format_exc()
        user_display = f"@{user.username}" if user.username else f"{user.first_name} {user.last_name or ''}".strip()
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        log_text = (
            f"⚠️ *Error Occurred*\n\n"
            f"*User:* {user_display} (`{user.id}`)\n"
            f"*Time:* `{timestamp}`\n"
            f"*Error:* ```{str(exception)}```\n\n"
            f"```{error_trace}```"
        )
        await bot.send_message(chat_id=LOG_CHANNEL, text=log_text)
    except Exception as log_log_error:
        print("Final error logging failed:", log_log_error)
