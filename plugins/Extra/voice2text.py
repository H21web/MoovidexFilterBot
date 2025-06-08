import os, traceback
import speech_recognition as sr
from pydub import AudioSegment
from pyrogram import Client, filters
from pyrogram.types import Message
from googlesearch import search
import re

def transcribe_audio(audio_path: str) -> str:
    r = sr.Recognizer()
    with sr.AudioFile(audio_path) as src:
        audio = r.record(src, duration=10)  # 10-second limit
        try:
            return r.recognize_google(audio)
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            raise RuntimeError(f"Google API error: {e}")

def extract_movie_title(query: str) -> str:
    # Search Google for "<query> movie"
    for url in search(f"{query} movie", num_results=3, pause=2):
        # Optionally filter to known movie sites
        if "imdb.com/title" in url:
            # Extract the IMDb movie title from URL
            title = url.rstrip("/").split("/")[-1]  # e.g., tt0133093
            # Fallback: use query itself
            return re.sub(r'\W+', ' ', query).strip()
    # If no IMDb link found, return cleaned query
    return re.sub(r'\W+', ' ', query).strip()

@Client.on_message(filters.voice)
async def on_voice(bot: Client, message: Message):
    status = await message.reply_text("🎙️ Processing your voice message...")
    try:
        ogg = await bot.download_media(message.voice)
        if not ogg.endswith(".ogg"):
            raise ValueError("Only .ogg voice messages supported")

        wav = ogg.replace(".ogg", ".wav")
        audio = AudioSegment.from_ogg(ogg)
        audio[:10000].export(wav, format="wav")  # 10 sec

        text = transcribe_audio(wav)
        if not text:
            reply = "🤖 Couldn't recognize speech."
        else:
            title = extract_movie_title(text)
            reply = f"🎥 Detected movie: *{title}*"

        await message.reply_text(reply, quote=True)
        await status.delete()

    except Exception as e:
        await status.edit_text("❌ Error:\n" + str(e))
        print(traceback.format_exc())

    finally:
        for f in [locals().get('ogg'), locals().get('wav')]:
            if f and os.path.exists(f):
                os.remove(f)
