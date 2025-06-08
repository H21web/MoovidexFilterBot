# plugins/Extra/voice2text.py

import os
import traceback
import whisper
from pydub import AudioSegment
from pyrogram import Client, filters
from pyrogram.types import Message

# Load the lightest Whisper model ("tiny")
whisper_model = whisper.load_model("tiny")

def transcribe_with_whisper(audio_path: str) -> str:
    try:
        # Convert to 16kHz mono WAV (required by Whisper)
        audio = AudioSegment.from_file(audio_path)
        wav_path = audio_path.replace(".ogg", "_whisper.wav")
        audio.set_frame_rate(16000).set_channels(1).export(wav_path, format="wav")

        # Transcribe with Whisper
        result = whisper_model.transcribe(wav_path)

        # Clean up temp file
        os.remove(wav_path)

        return f"🌐 Detected Language: `{result['language']}`\n\n📝 Transcription:\n{result['text']}"

    except Exception as e:
        return f"❌ Whisper error:\n{str(e)}"

@Client.on_message(filters.voice)
async def voice_to_text_handler(bot: Client, message: Message):
    status = await message.reply_text("🎙 Processing your voice message...")

    try:
        ogg_path = await bot.download_media(message.voice)
        result = transcribe_with_whisper(ogg_path)

        await message.reply_text(result, quote=True)
        await status.delete()

    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        await status.edit_text("❌ An error occurred:\n" + str(e))

    finally:
        if ogg_path and os.path.exists(ogg_path):
            os.remove(ogg_path)
