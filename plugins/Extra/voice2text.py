# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import os
import traceback
import speech_recognition as sr
from pydub import AudioSegment
from pyrogram import Client, filters
from pyrogram.types import Message
from imdb import Cinemagoer
from googlesearch import search
import re

# IMDbPY client
ia = Cinemagoer()

# --- Step 1: Transcribe 10s audio ---
def transcribe_audio(audio_path: str) -> str:
    r = sr.Recognizer()
    with sr.AudioFile(audio_path) as source:
        try:
            audio = r.record(source, duration=10)  # limit to 10s
            return r.recognize_google(audio)
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            raise RuntimeError(f"Google API error: {e}")

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
    status = await message.reply_text("🎙 Transcribing your voice...")

    try:
        voice_file = await bot.download_media(message.voice)
        if not voice_file.endswith(".ogg"):
            raise ValueError("Only .ogg format supported.")

        wav_file = voice_file.replace(".ogg", ".wav")
        sound = AudioSegment.from_ogg(voice_file)
        sound[:10000].export(wav_file, format="wav")

        # Transcribe
        text = transcribe_audio(wav_file)
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
        await status.delete()

    except Exception as e:
        await status.edit_text("❌ Error:\n" + str(e))
        print(traceback.format_exc())

    finally:
        for f in [locals().get('voice_file'), locals().get('wav_file')]:
            if f and os.path.exists(f):
                os.remove(f)
