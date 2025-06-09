import os
import traceback
import requests
import asyncio
from pydub import AudioSegment
from pyrogram import Client, filters
from pyrogram.types import Message
from imdb import Cinemagoer
from googlesearch import search
import re
from datetime import datetime
from collections import defaultdict
from info import ADMINS, LOG_CHANNEL  # ✅ Ensure these are defined
from plugins.pm_filter import boovo

# IMDbPY client
ia = Cinemagoer()
ASSEMBLYAI_API_KEY = "e8540603a6294a14acadf2e6a4a16787"

# Limits
VOICE_LIMIT = 10
VOICE_DURATION_LIMIT = 10  # seconds
daily_usage = defaultdict(lambda: defaultdict(int))  # user_id -> date_str -> count

# AssemblyAI endpoints
UPLOAD_ENDPOINT = "https://api.assemblyai.com/v2/upload"
TRANSCRIPT_ENDPOINT = "https://api.assemblyai.com/v2/transcript"

HEADERS = {
    "authorization": ASSEMBLYAI_API_KEY,
    "content-type": "application/json"
}


async def upload_audio_assemblyai(audio_path: str) -> str:
    """Upload audio file to AssemblyAI and return upload URL."""
    with open(audio_path, "rb") as f:
        response = requests.post(UPLOAD_ENDPOINT, headers={"authorization": ASSEMBLYAI_API_KEY}, data=f)
    if response.status_code == 200:
        return response.json()['upload_url']
    else:
        raise RuntimeError(f"AssemblyAI upload failed: {response.status_code} {response.text}")


async def request_transcript(audio_url: str) -> str:
    """Request transcript and poll until completed."""
    json_data = {
        "audio_url": audio_url,
        "language_code": "en"
    }
    response = requests.post(TRANSCRIPT_ENDPOINT, headers=HEADERS, json=json_data)
    if response.status_code != 200:
        raise RuntimeError(f"AssemblyAI transcript request failed: {response.status_code} {response.text}")

    transcript_id = response.json()['id']
    polling_endpoint = f"{TRANSCRIPT_ENDPOINT}/{transcript_id}"

    # Poll for completion (timeout 60s max)
    for _ in range(30):
        poll_response = requests.get(polling_endpoint, headers=HEADERS)
        if poll_response.status_code != 200:
            raise RuntimeError(f"AssemblyAI polling failed: {poll_response.status_code} {poll_response.text}")

        status = poll_response.json()['status']
        if status == 'completed':
            return poll_response.json().get('text', '')
        elif status == 'error':
            raise RuntimeError(f"AssemblyAI transcription error: {poll_response.json().get('error', 'Unknown error')}")

        await asyncio.sleep(2)

    raise TimeoutError("AssemblyAI transcription timed out")


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
    status = None
    voice_file = None
    wav_file = None
    user_id = message.from_user.id
    today_str = datetime.utcnow().strftime('%Y-%m-%d')

    try:
        if message.voice.duration > VOICE_DURATION_LIMIT:
            await message.reply_text(f"⚠️ Please send a voice message shorter than {VOICE_DURATION_LIMIT} seconds.")
            return

        if user_id not in ADMINS:
            if daily_usage[user_id][today_str] >= VOICE_LIMIT:
                await message.reply_text("🚫 You've reached your daily voice search limit.")
                return
            daily_usage[user_id][today_str] += 1

        status = await message.reply_text("🎙 Please wait...")

        voice_file = await bot.download_media(message.voice)
        if not voice_file.endswith(".ogg"):
            raise ValueError("Only .ogg format supported.")

        wav_file = voice_file.replace(".ogg", ".wav")
        sound = AudioSegment.from_ogg(voice_file)
        sound[:10000].export(wav_file, format="wav")

        # Upload to AssemblyAI and get transcript
        audio_url = await upload_audio_assemblyai(wav_file)
        text = await request_transcript(audio_url)

        if not text:
            await status.edit_text("🤖 Could not recognize any speech.")

            user = message.from_user
            user_name = user.first_name
            if user.last_name:
                user_name += f" {user.last_name}"
            user_display = f"@{user.username}" if user.username else user_name
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

            log_text = (
                f"🛑 *No Transcript Found*\n\n"
                f"*User:* {user_display} (`{user.id}`)\n"
                f"*Time:* `{timestamp}`\n"
                f"*Reason:* No recognizable speech in the voice message."
            )

            try:
                await bot.send_voice(
                    chat_id=LOG_CHANNEL,
                    voice=voice_file,
                    caption=log_text
                )
            except Exception as log_error:
                print("Logging failed (no transcript):", log_error)

            return

        if status:
            await status.delete()

        title = find_movie_with_imdb(text)
        if not title:
            title = find_movie_with_google(text)

        if title.lower().strip() == "unknown movie":
            await message.reply_text("❌ Movie not found.")
            return

        await boovo(bot, title, message)

        user = message.from_user
        user_name = user.first_name
        if user.last_name:
            user_name += f" {user.last_name}"
        user_display = f"@{user.username}" if user.username else user_name
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        caption_text = (
            f"🎬 Title: {title}\n"
            f"🗣 Transcript: {text}\n\n"
            f"👤 User: {user_display}\n"
            f"🆔 ID: {user.id}\n"
            f"🕒 Time: {timestamp}"
        )

        await bot.send_voice(
            chat_id=LOG_CHANNEL,
            voice=voice_file,
            caption=caption_text
        )

    except Exception as e:
        try:
            if status:
                await status.edit_text("❌ An unexpected error occurred while processing your request.")
            else:
                await message.reply_text("❌ An unexpected error occurred while processing your request.")
        except:
            pass

        # Prepare and send error log
        error_trace = traceback.format_exc()
        user = message.from_user
        user_name = user.first_name
        if user.last_name:
            user_name += f" {user.last_name}"
        user_display = f"@{user.username}" if user.username else user_name
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        log_text = (
            f"⚠️ *Error Occurred*\n\n"
            f"*User:* {user_display} (`{user.id}`)\n"
            f"*Time:* `{timestamp}`\n"
            f"*Error:* ```{str(e)}```\n\n"
            f"```{error_trace}```"
        )

        try:
            await bot.send_message(chat_id=LOG_CHANNEL, text=log_text)
        except Exception as log_error:
            print("Logging failed:", log_error)
            print(error_trace)

    finally:
        for f in [voice_file, wav_file]:
            if f and os.path.exists(f):
                try:
                    os.remove(f)
                except Exception as cleanup_error:
                    print("Cleanup error:", cleanup_error)
