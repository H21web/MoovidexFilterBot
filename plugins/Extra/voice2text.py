import os
import traceback
import requests
from pydub import AudioSegment
from pyrogram import Client, filters
from pyrogram.types import Message
from imdb import Cinemagoer
from googlesearch import search
import re
from datetime import datetime
from collections import defaultdict
from info import ADMINS  
from plugins.pm_filter import boovo

# IMDbPY client
ia = Cinemagoer()
DEEPGRAM_API_KEY = "d745106d263708f978a6428537300505be9589bb"

# Limit non-admin users to 10 voice messages per day
VOICE_LIMIT = 10
VOICE_DURATION_LIMIT = 10  # in seconds
daily_usage = defaultdict(lambda: defaultdict(int))  # user_id -> date_str -> count


def transcribe_with_deepgram(audio_path: str) -> str:
    with open(audio_path, "rb") as audio_file:
        response = requests.post(
            "https://api.deepgram.com/v1/listen?model=whisper-large",
            headers={
                "Authorization": f"Token {DEEPGRAM_API_KEY}",
                "Content-Type": "audio/wav"
            },
            data=audio_file
        )
    if response.status_code == 200:
        try:
            result = response.json()
            return result.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "")
        except Exception:
            return ""
    else:
        raise RuntimeError(f"Deepgram API error: {response.status_code} {response.text}")


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
        # Check duration limit
        if message.voice.duration > VOICE_DURATION_LIMIT:
            await message.reply_text(f"⚠️ Please send a voice message shorter than {VOICE_DURATION_LIMIT} seconds.")
            return

        # Enforce daily limit for non-admins
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

        # Transcribe audio
        text = transcribe_with_deepgram(wav_file)
        if not text:
            await status.edit_text("🤖 Could not recognize any speech.")
            return

        # Delete the "Please wait..." message after transcription
        if status:
            await status.delete()

        # Detect movie
        title = find_movie_with_imdb(text)
        if not title:
            title = find_movie_with_google(text)

        if title.lower().strip() == "unknown movie":
            await message.reply_text("❌ Movie not found.")
            return

        # Call boovo with the title
        await boovo(bot, title, message)

    except Exception as e:
        err_msg = f"❌ Error:\n{str(e)}"
        try:
            if status:
                await status.edit_text(err_msg[:4000])
            else:
                await message.reply_text(err_msg[:4000])
        except:
            pass
        print(traceback.format_exc())

    finally:
        for f in [voice_file, wav_file]:
            if f and os.path.exists(f):
                try:
                    os.remove(f)
                except Exception as cleanup_error:
                    print("Cleanup error:", cleanup_error)
