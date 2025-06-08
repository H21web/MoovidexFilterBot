# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import os
import traceback
import speech_recognition as sr
from pydub import AudioSegment
from pyrogram import Client, filters
from pyrogram.types import Message


# Languages to try in order (you can adjust priorities)
LANG_CODES = [
    "ml-IN",  # Malayalam
    "ta-IN",  # Tamil
    "hi-IN",  # Hindi
    "kn-IN",  # Kannada
    "te-IN",  # Telugu
    "en-IN",  # Indian English (fallback)
]


def transcribe_indian_languages(audio_path: str) -> str:
    recognizer = sr.Recognizer()

    with sr.AudioFile(audio_path) as source:
        audio_data = recognizer.record(source)

        for lang in LANG_CODES:
            try:
                # Try recognition with a specific language
                text = recognizer.recognize_google(audio_data, language=lang)
                return f"🗣 Detected Language: `{lang}`\n\n`{text}`"
            except sr.UnknownValueError:
                continue  # Try next language
            except sr.RequestError as e:
                return f"⚠️ Google Speech API error:\n{e}"
            except Exception as e:
                return f"❌ Error with language {lang}:\n{str(e)}"

        return "🤖 Sorry, I couldn't understand your voice clearly."


@Client.on_message(filters.voice)
async def handle_voice(bot: Client, message: Message):
    status = await message.reply_text("🎧 Processing your voice message...")

    try:
        ogg_path = await bot.download_media(message.voice)
        wav_path = ogg_path.replace(".ogg", ".wav")

        # Convert to WAV
        sound = AudioSegment.from_ogg(ogg_path)
        sound.export(wav_path, format="wav")

        # Transcribe using multiple Indian language profiles
        result = transcribe_indian_languages(wav_path)

        await message.reply_text(result, quote=True)
        await status.delete()

    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        await status.edit_text("❌ Error:\n" + str(e))

    finally:
        # Clean up
        for path in [locals().get("ogg_path"), locals().get("wav_path")]:
            if path and os.path.exists(path):
                os.remove(path)
