# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import os
import io
import traceback
from pyrogram import Client, filters
from pyrogram.types import Message
from pydub import AudioSegment
from google.cloud import speech

# Set this in your environment or directly in code (not secure for public)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "glowing-arcadia-355406-4a2ab23f2d4a.json"

def transcribe_with_google(wav_path: str, language_code="hi-IN") -> str:
    client = speech.SpeechClient()

    with io.open(wav_path, "rb") as audio_file:
        content = audio_file.read()

    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code=language_code,
        enable_automatic_punctuation=True,
        model="latest_long"
    )

    response = client.recognize(config=config, audio=audio)

    result_text = ""
    for result in response.results:
        result_text += result.alternatives[0].transcript + " "

    return result_text.strip() or "🤖 Sorry, I couldn't understand your voice."


@Client.on_message(filters.voice)
async def voice_to_text_handler(bot: Client, message: Message):
    status = await message.reply_text("🎙 Processing your voice message...")

    try:
        ogg_path = await bot.download_media(message.voice)
        wav_path = ogg_path.replace(".ogg", ".wav")

        # Convert .ogg to .wav
        sound = AudioSegment.from_ogg(ogg_path).set_channels(1).set_frame_rate(16000)
        sound.export(wav_path, format="wav")

        # Set language here (you can make it dynamic)
        result = transcribe_with_google(wav_path, language_code="hi-IN")

        await message.reply_text(f"🗣 Recognized Text:\n\n`{result}`", quote=True)
        await status.delete()

    except Exception as e:
        traceback.print_exc()
        await status.edit_text(f"❌ Error occurred:\n{e}")

    finally:
        for path in [locals().get("ogg_path"), locals().get("wav_path")]:
            if path and os.path.exists(path):
                os.remove(path)
