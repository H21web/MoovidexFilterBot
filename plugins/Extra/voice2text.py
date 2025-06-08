# plugins/Extra/voice2text.py

import os
import time
import traceback
import requests
from pydub import AudioSegment
from pyrogram import Client, filters
from pyrogram.types import Message

ASSEMBLYAI_API_KEY = "e8540603a6294a14acadf2e6a4a16787"  # Replace this with your real AssemblyAI API key

def transcribe_with_assemblyai(audio_path: str) -> str:
    wav_path = None
    try:
        # Convert OGG to WAV (16kHz, mono)
        audio = AudioSegment.from_file(audio_path)
        wav_path = audio_path.replace(".ogg", "_converted.wav")
        audio.set_frame_rate(16000).set_channels(1).export(wav_path, format="wav")

        # Upload to AssemblyAI
        with open(wav_path, "rb") as f:
            upload_res = requests.post(
                "https://api.assemblyai.com/v2/upload",
                headers={"authorization": ASSEMBLYAI_API_KEY},
                files={"file": f}
            )

        if upload_res.status_code != 200:
            return f"❌ Upload failed:\n{upload_res.text}"
        
        audio_url = upload_res.json().get("upload_url")
        if not audio_url:
            return "❌ Could not get upload URL from AssemblyAI."

        # Request transcription
        transcribe_res = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            headers={"authorization": ASSEMBLYAI_API_KEY, "content-type": "application/json"},
            json={
                "audio_url": audio_url,
                "auto_detect": True,
                "language_detection": True
            }
        )

        if transcribe_res.status_code != 200:
            return f"❌ Transcription request failed:\n{transcribe_res.text}"
        
        transcript_id = transcribe_res.json().get("id")
        if not transcript_id:
            return "❌ Couldn't retrieve transcript ID."

        # Poll for completion
        status_url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
        while True:
            status_res = requests.get(status_url, headers={"authorization": ASSEMBLYAI_API_KEY})
            status_json = status_res.json()

            if status_json["status"] == "completed":
                text = status_json.get("text", "")
                lang = status_json.get("language_code", "unknown")
                return f"🌐 Detected Language: `{lang}`\n\n📝 Transcription:\n{text}"
            elif status_json["status"] == "error":
                return f"❌ Transcription error: {status_json.get('error', 'Unknown error')}"
            
            time.sleep(3)  # Avoid spamming API

    except Exception as e:
        return f"❌ Unexpected error:\n{str(e)}"
    finally:
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)

@Client.on_message(filters.voice)
async def voice_to_text_handler(bot: Client, message: Message):
    status = await message.reply_text("🎙 Downloading and transcribing your voice message...")

    try:
        ogg_path = await bot.download_media(message.voice)
        result = transcribe_with_assemblyai(ogg_path)
        await message.reply_text(result, quote=True)
        await status.delete()
    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        await status.edit_text("❌ Error:\n" + str(e))
    finally:
        if ogg_path and os.path.exists(ogg_path):
            os.remove(ogg_path)
