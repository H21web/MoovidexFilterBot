# plugins/Extra/voice2text.py

import os
import traceback
import requests
from pydub import AudioSegment
from pyrogram import Client, filters
from pyrogram.types import Message

# ─── CONFIG ────────────────────────────────────────────────────────────────────
DEEPGRAM_API_KEY = "6758ed3d0a4fbe81db0f3f58134cbe08d83cd985"  # ← replace with your key
# Endpoint with auto language detection, punctuation, numerals
DEEPGRAM_URL = (
    "https://api.deepgram.com/v1/listen"
    "?punctuate=true"
    "&numerals=true"
    "&model=general"
    "&detect_language=true"
)
# ────────────────────────────────────────────────────────────────────────────────

def transcribe_with_deepgram(audio_path: str) -> str:
    wav_path = None
    try:
        # 1) Convert OGG → WAV (16 kHz mono PCM)
        audio = AudioSegment.from_file(audio_path)
        wav_path = audio_path.replace(".ogg", "_dg.wav")
        audio.set_frame_rate(16000).set_channels(1).export(wav_path, format="wav")

        # 2) Read bytes and send to Deepgram
        with open(wav_path, "rb") as f:
            audio_bytes = f.read()

        headers = {
            "Authorization": f"Token {DEEPGRAM_API_KEY}",
            "Content-Type": "application/octet-stream"
        }
        resp = requests.post(DEEPGRAM_URL, headers=headers, data=audio_bytes)
        if resp.status_code != 200:
            return f"❌ Deepgram error {resp.status_code}:\n{resp.text}"

        data = resp.json()

        # 3) Extract transcript & detected language
        # Deepgram returns results.channels[0].alternatives[0]
        ch = data.get("results", {}).get("channels", [{}])[0]
        alt = ch.get("alternatives", [{}])[0]
        transcript = alt.get("transcript", "").strip()
        lang = data.get("metadata", {}).get("detected_language", "unknown")

        if not transcript:
            return "🤖 Sorry, I couldn't transcribe the audio."

        return f"🌐 Detected Language: `{lang}`\n\n📝 Transcription:\n{transcript}"

    except Exception as e:
        return f"❌ Unexpected error:\n{e}"

    finally:
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)

@Client.on_message(filters.voice)
async def voice_to_text_handler(bot: Client, message: Message):
    status = await message.reply_text("🎙 Downloading and transcribing…")
    ogg_path = None

    try:
        ogg_path = await bot.download_media(message.voice)
        result = transcribe_with_deepgram(ogg_path)
        await message.reply_text(result, quote=True)
        await status.delete()
    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        await status.edit_text("❌ Error:\n" + str(e))
    finally:
        if ogg_path and os.path.exists(ogg_path):
            os.remove(ogg_path)
