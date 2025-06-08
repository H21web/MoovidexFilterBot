# plugins/Extra/voice2text.py

import os
import traceback
import requests
from pydub import AudioSegment
from pyrogram import Client, filters
from pyrogram.types import Message

ASSEMBLYAI_API_KEY = "e8540603a6294a14acadf2e6a4a16787"  # Replace with your API key

def transcribe_with_assemblyai(audio_path: str) -> str:
    try:
        # Convert to WAV with correct format
        audio = AudioSegment.from_file(audio_path)
        wav_path = audio_path.replace(".ogg", "_converted.wav")
        audio.set_frame_rate(16000).set_channels(1).export(wav_path, format="wav")

        # Upload audio
        with open(wav_path, "rb") as f:
            headers = {"authorization": ASSEMBLYAI_API_KEY}
            upload_response = requests.post("https://api.assemblyai.com/v2/upload", headers=headers, files={"file": f})
            audio_url = upload_response.json()["upload_url"]

        # Start transcription
        json_payload = {
            "audio_url": audio_url,
            "auto_detect": True,
            "language_detection": True,
        }
        response = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            json=json_payload,
            headers={"authorization": ASSEMBLYAI_API_KEY}
        )
        transcript_id = response.json()["id"]

        # Poll for completion
        status_url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
        while True:
            status_check = requests.get(status_url, headers={"authorization": ASSEMBLYAI_API_KEY}).json()
            if status_check["status"] == "completed":
                return f"🌐 Detected Language: `{status_check.get('language_code', 'unknown')}`\n\n📝 Transcription:\n{status_check['text']}"
            elif status_check["status"] == "error":
                return f"❌ Error: {status_check['error']}"
        
    except Exception as e:
        return f"❌ AssemblyAI error:\n{str(e)}"
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)

@Client.on_message(filters.voice)
async def voice_to_text_handler(bot: Client, message: Message):
    status = await message.reply_text("🎙 Uploading and transcribing...")

    try:
        ogg_path = await bot.download_media(message.voice)
        result = transcribe_with_assemblyai(ogg_path)

        await message.reply_text(result, quote=True)
        await status.delete()

    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        await status.edit_text("❌ An error occurred:\n" + str(e))

    finally:
        if ogg_path and os.path.exists(ogg_path):
            os.remove(ogg_path)
