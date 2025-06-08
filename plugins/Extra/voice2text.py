# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import os
import traceback
import speech_recognition as sr
from pydub import AudioSegment
from pyrogram import Client, filters
from pyrogram.types import Message


def transcribe_audio(audio_path: str) -> str:
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_path) as source:
        try:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
            return text
        except sr.UnknownValueError:
            return "🤖 Sorry, I couldn't understand the voice."
        except sr.RequestError as e:
            return f"⚠️ Google Speech Recognition API error:\n{e}"
        except Exception as e:
            return f"❌ Unexpected error during transcription:\n{str(e)}"


@Client.on_message(filters.voice)
async def handle_voice_message(bot: Client, message: Message):
    status = await message.reply_text("🎙 Downloading and processing your voice message...")

    try:
        # Download .ogg voice file
        voice_file = await bot.download_media(message.voice)
        if not voice_file.endswith(".ogg"):
            raise ValueError("Unsupported file format. Only .ogg is supported.")

        wav_file = voice_file.replace(".ogg", ".wav")

        # Convert .ogg to .wav
        try:
            sound = AudioSegment.from_ogg(voice_file)
            sound.export(wav_file, format="wav")
        except Exception as e:
            raise RuntimeError("Failed to convert OGG to WAV. Ensure ffmpeg is installed.") from e

        # Transcribe
        result = transcribe_audio(wav_file)

        # Respond with the transcription
        await message.reply_text(f"🗣 Recognized Text:\n\n`{result}`", quote=True)
        await status.delete()

    except Exception as e:
        error_log = traceback.format_exc()
        print(error_log)
        await status.edit_text("❌ An error occurred:\n" + str(e))
    finally:
        # Clean up downloaded and converted files
        for file in [locals().get('voice_file'), locals().get('wav_file')]:
            if file and os.path.exists(file):
                os.remove(file)
