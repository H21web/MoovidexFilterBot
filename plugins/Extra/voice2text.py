# plugins/Extra/voice2text.py

import os
import wave
import json
import traceback
from vosk import Model, KaldiRecognizer
from pydub import AudioSegment
from pyrogram import Client, filters
from pyrogram.types import Message

# Load English Vosk model
model_path = "vosk-model-small-en-us-0.15"
if not os.path.exists(model_path):
    raise RuntimeError("❌ English model not found! Please unzip it to: vosk-model-small-en-us-0.15")

model = Model(model_path)

def transcribe_with_vosk(wav_path: str) -> str:
    with wave.open(wav_path, "rb") as wf:
        rec = KaldiRecognizer(model, wf.getframerate())
        rec.SetWords(True)
        results = []

        while True:
            data = wf.readframes(4000)
            if not data:
                break
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                results.append(result.get("text", ""))

        final_result = json.loads(rec.FinalResult())
        results.append(final_result.get("text", ""))

    return " ".join(results).strip() or "🤖 Sorry, I couldn't recognize any speech."

@Client.on_message(filters.voice)
async def voice_to_text_handler(bot: Client, message: Message):
    status = await message.reply_text("🎙 Downloading and transcribing your voice...")

    ogg_path = await bot.download_media(message.voice)
    wav_path = ogg_path.replace(".ogg", ".wav")

    try:
        # Convert OGG to WAV (mono, 16kHz)
        audio = AudioSegment.from_ogg(ogg_path)
        audio.set_frame_rate(16000).set_channels(1).export(wav_path, format="wav")

        # Transcribe using Vosk
        transcript = transcribe_with_vosk(wav_path)

        await message.reply_text(f"🗣 English Text:\n\n`{transcript}`", quote=True)
        await status.delete()

    except Exception as e:
        traceback.print_exc()
        await status.edit_text(f"❌ Error occurred:\n{str(e)}")
    finally:
        for path in (ogg_path, wav_path):
            if path and os.path.exists(path):
                os.remove(path)
