# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import os
import traceback
import whisper
from pydub import AudioSegment
from googletrans import Translator
from pyrogram import Client, filters
from pyrogram.types import Message


def transcribe_and_translate(audio_path: str) -> str:
    try:
        # Load Whisper model (you can use 'base', 'small', 'medium', or 'large')
        model = whisper.load_model("base")

        # Transcribe the audio (Whisper handles language detection)
        result = model.transcribe(audio_path)

        raw_text = result["text"]

        # Translate to English
        translator = Translator()
        translation = translator.translate(raw_text, dest="en")

        return translation.text

    except Exception as e:
        return f"❌ Whisper error:\n{str(e)}"


@Client.on_message(filters.voice)
async def voice_to_text_handler(bot: Client, message: Message):
    status = await message.reply_text("🎙 Downloading and processing your voice message...")

    try:
        ogg_path = await bot.download_media(message.voice)
        if not ogg_path.endswith(".ogg"):
            raise ValueError("Unsupported file format. Only .ogg voice messages are supported.")

        wav_path = ogg_path.replace(".ogg", ".wav")

        # Convert OGG to WAV
        sound = AudioSegment.from_ogg(ogg_path)
        sound.export(wav_path, format="wav")

        # Transcribe and translate using Whisper
        result = transcribe_and_translate(wav_path)

        await message.reply_text(f"🗣 Recognized Text (in English):\n\n`{result}`", quote=True)
        await status.delete()

    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        await status.edit_text("❌ An error occurred:\n" + str(e))

    finally:
        for file_path in [locals().get("ogg_path"), locals().get("wav_path")]:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
