# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import os
import traceback
import requests
import json
from pydub import AudioSegment
from pyrogram import Client, filters
from pyrogram.types import Message
from imdb import Cinemagoer
from googlesearch import search
import re

# IMDbPY client
ia = Cinemagoer()

# Your Deepgram API key
DEEPGRAM_API_KEY = "d745106d263708f978a6428537300505be9589bb"

# --- Step 1: Transcribe audio using Deepgram ---
def transcribe_with_deepgram(audio_path: str) -> str:
    with open(audio_path, "rb") as audio_file:
        response = requests.post(
            "https://api.deepgram.com/v1/listen?smart_format=true&language=en&model=whisper",
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

# --- Step 2: Try finding movie via IMDbPY ---
def find_movie_with_imdb(query: str) -> str:
    try:
        results = ia.search_movie(query)
        if results:
            return results[0]['title']
    except Exception as e:
        print("IMDbPY error:", e)
    return ""

# --- Step 3: Fallback - search Google and extract IMDb title ---
def find_movie_with_google(query: str) -> str:
    try:
        for url in search(f"{query} movie site:imdb.com", num_results=3):
            if "imdb.com/title" in url:
                return extract_title_from_url(url)
    except Exception as e:
        print("Google search error:", e)
    return re.sub(r'\W+', ' ', query).strip()

# Dummy title from IMDb URL (can be improved)
def extract_title_from_url(url: str) -> str:
    imdb_id = url.strip("/").split("/")[-1]
    if imdb_id.startswith("tt"):
        try:
            movie = ia.get_movie(imdb_id[2:])
            return movie.get('title', f"IMDb ID: {imdb_id}")
        except:
            return f"IMDb ID: {imdb_id}"
    return "Unknown movie"

# --- Step 4: Handle Voice ---
@Client.on_message(filters.voice)
async def handle_voice(bot: Client, message: Message):
    status = None
    voice_file = None
    wav_file = None

    try:
        status = await message.reply_text("🎙 Transcribing your voice...")

        voice_file = await bot.download_media(message.voice)
        if not voice_file.endswith(".ogg"):
            raise ValueError("Only .ogg format supported.")

        # Convert to WAV for Deepgram
        wav_file = voice_file.replace(".ogg", ".wav")
        sound = AudioSegment.from_ogg(voice_file)
        sound[:10000].export(wav_file, format="wav")

        # Transcribe using Deepgram
        text = transcribe_with_deepgram(wav_file)
        if not text:
            await status.edit_text("🤖 Could not recognize any speech.")
            return

        # Try IMDbPY first
        title = find_movie_with_imdb(text)
        if not title:
            title = find_movie_with_google(text)

        await message.reply_text(
            f"🗣 Transcribed:\n`{text}`\n\n🎬 Detected Movie: **{title}**", quote=True
        )

        if status:
            await status.delete()

    except Exception as e:
        error_message = f"❌ Error:\n{str(e)}"
        try:
            if status:
                await status.edit_text(error_message[:4000])
            else:
                await message.reply_text(error_message[:4000])
        except Exception as inner_e:
            print("Failed to send error message:", inner_e)
        print(traceback.format_exc())

    finally:
        for f in [voice_file, wav_file]:
            if f and os.path.exists(f):
                try:
                    os.remove(f)
                except Exception as cleanup_error:
                    print("File cleanup error:", cleanup_error)
