# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import os
import traceback
import speech_recognition as sr
from pydub import AudioSegment
from googletrans import Translator
from pyrogram import Client, filters
from pyrogram.types import Message


def transcribe_and_translate(audio_path: str) -> str:
    recognizer = sr.Recognizer()

    with sr.AudioFile(audio_path) as source:
        try:
            audio_data = recognizer.record(source)
            # Recognize speech (auto language detection)
            raw_text = recognizer.recognize_google(audio_data)
            
            # Translate to English if needed
            translator = Translator()
            translation = translator.translate(raw_text, dest="en")

            # Return translated text
            return translation.text

        except sr.UnknownValueError:
            return "🤖 Sorry, I couldn't understand your voice clearly."
        except sr.RequestError as e:
            return f"⚠️ Google Speech API error:\n{e}"
        except Exception as e:
            return f"❌ Unexpected error during transcription:\n{str(e)}"


@Client.on_message(filters.voice)
async def voice_to_text_handler(bot: Client, message: Message):
    status = await message.reply_text("🎙 Downloading and processing your voice message...")

    try:
        # Download Telegram .ogg voice message
        ogg_path = await bot.download_media(message.voice)
        if not ogg_path.endswith(".ogg"):
            raise ValueError("Unsupported file format. Only .ogg voice messages are supported.")

        wav_path = ogg_path.replace(".ogg", ".wav")

        # Convert .ogg to .wav using pydub (requires ffmpeg)
        sound = AudioSegment.from_ogg(ogg_path)
        sound.export(wav_path, format="wav")

        # Transcribe and translate
        result = transcribe_and_translate(wav_path)

        # Reply with recognized and translated text
        await message.reply_text(f"🗣 Recognized Text (in English):\n\n`{result}`", quote=True)
        await status.delete()

    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        await status.edit_text("❌ An error occurred:\n" + str(e))

    finally:
        # Clean up temporary files
        for file_path in [locals().get("ogg_path"), locals().get("wav_path")]:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
