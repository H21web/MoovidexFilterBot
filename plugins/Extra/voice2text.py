# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import os
import traceback
import difflib
import speech_recognition as sr
from pydub import AudioSegment
from googletrans import Translator
from googlesearch import search
from pyrogram import Client, filters
from pyrogram.types import Message

# ---------- Function to search Google ----------
def search_google_for_movie(query: str, num_results: int = 5) -> str:
    try:
        results = list(search(query, num_results=num_results, lang="en"))
        if not results:
            return "❌ No relevant result found."

        # Try to fuzzy match domain/title
        titles = [url.split("//")[-1].split("/")[0].replace("www.", "") for url in results]
        best = difflib.get_close_matches(query.lower(), titles, n=1, cutoff=0.3)

        if best:
            best_index = titles.index(best[0])
            return f"🎬 Best Match Found:\n{results[best_index]}"
        else:
            return f"🔗 Top Google Result:\n{results[0]}"

    except Exception as e:
        return f"⚠️ Google search failed: {e}"


# ---------- Function to transcribe and translate ----------
def transcribe_and_translate(audio_path: str) -> str:
    recognizer = sr.Recognizer()

    with sr.AudioFile(audio_path) as source:
        try:
            audio_data = recognizer.record(source)
            raw_text = recognizer.recognize_google(audio_data)

            translator = Translator()
            translation = translator.translate(raw_text, dest="en")
            return translation.text

        except sr.UnknownValueError:
            return "🤖 Sorry, I couldn't understand your voice clearly."
        except sr.RequestError as e:
            return f"⚠️ Google Speech API error:\n{e}"
        except Exception as e:
            return f"❌ Unexpected error during transcription:\n{str(e)}"


# ---------- Pyrogram Voice Handler ----------
@Client.on_message(filters.voice)
async def voice_to_text_handler(bot: Client, message: Message):
    status = await message.reply_text("🎙 Downloading and processing your voice message...")

    ogg_path = wav_path = None
    try:
        # Download .ogg voice message
        ogg_path = await bot.download_media(message.voice)
        if not ogg_path.endswith(".ogg"):
            raise ValueError("Unsupported file format. Only .ogg voice messages are supported.")

        # Convert to .wav using pydub
        wav_path = ogg_path.replace(".ogg", ".wav")
        sound = AudioSegment.from_ogg(ogg_path)
        sound.export(wav_path, format="wav")

        # Transcribe and translate
        transcription = transcribe_and_translate(wav_path)

        # Google search for matching movie/series
        search_result = search_google_for_movie(transcription)

        # Send result
        await message.reply_text(
            f"🗣 Recognized Text:\n`{transcription}`\n\n🔍 Google Search Result:\n{search_result}",
            quote=True
        )
        await status.delete()

    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        await status.edit_text("❌ An error occurred:\n" + str(e))

    finally:
        # Clean up temp files
        for path in [ogg_path, wav_path]:
            if path and os.path.exists(path):
                os.remove(path)
