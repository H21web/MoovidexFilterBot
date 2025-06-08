# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import os
import traceback
import speech_recognition as sr
from pydub import AudioSegment
from pyrogram import Client, filters
from pyrogram.types import Message

# Set your target languages here
LANG_CODES = {
    "hi": "hi-IN",     # Hindi
    "ta": "ta-IN",     # Tamil
    "ml": "ml-IN",     # Malayalam
    "kn": "kn-IN",     # Kannada
    "te": "te-IN"      # Telugu
}


def transcribe_local_language(audio_path: str, lang_code: str) -> str:
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_path) as source:
        try:
            audio_data = recognizer.record(source)
            # Recognize with specific language
            return recognizer.recognize_google(audio_data, language=lang_code)
        except sr.UnknownValueError:
            return "🤖 Sorry, I couldn't understand your voice clearly."
        except sr.RequestError as e:
            return f"⚠️ Google Speech API error:\n{e}"
        except Exception as e:
            return f"❌ Error:\n{str(e)}"


@Client.on_message(filters.voice)
async def handle_voice(bot: Client, message: Message):
    status = await message.reply_text("🎙 Processing your voice message...")

    try:
        # Download the voice message
        ogg_path = await bot.download_media(message.voice)
        wav_path = ogg_path.replace(".ogg", ".wav")

        # Convert .ogg to .wav
        sound = AudioSegment.from_ogg(ogg_path)
        sound.export(wav_path, format="wav")

        # Select language: you can customize this per chat/user
        selected_lang = "ta"  # Change to "hi", "ml", "kn", "te" based on your audience
        lang_code = LANG_CODES.get(selected_lang, "en-IN")

        # Transcribe in specified language, output phonetic text in English
        result = transcribe_local_language(wav_path, lang_code)

        await message.reply_text(f"🗣 Spoken words (phonetic):\n\n`{result}`", quote=True)
        await status.delete()

    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        await status.edit_text("❌ Error:\n" + str(e))

    finally:
        for path in [ogg_path, wav_path]:
            if path and os.path.exists(path):
                os.remove(path)
