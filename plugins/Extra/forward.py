import re
import logging
from pyrogram import Client, filters

# API Credentials
API_ID = 8281168  # Replace with your API ID
API_HASH = "445ff67ec34858448ac184c7479ce917"  # Replace with your API Hash

# Initialize Pyrogram Client (user session file method)
app = Client("my_session", api_id=API_ID, api_hash=API_HASH)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Source and Destination Channels
SOURCE_CHANNELS = [-1002570431865]  # Replace with actual private channel IDs
DESTINATION_CHANNEL = -1002540224499  # Replace with your target channel ID

# Function to clean text (replace URLs and usernames)
def clean_text(text):
    if text:
        text = re.sub(r"https?://\S+", "[LINK REMOVED]", text)  # Replace URLs
        text = re.sub(r"@[\w]+", "[USERNAME REMOVED]", text)  # Replace usernames
    return text

@app.on_message(filters.chat(SOURCE_CHANNELS) & (filters.document | filters.video))
async def forward_filtered(client, message):
    logging.info(f"Received message from {message.chat.id}")

    caption = clean_text(message.caption) if message.caption else None

    try:
        await message.copy(DESTINATION_CHANNEL, caption=caption)
        logging.info(f"Forwarded message to {DESTINATION_CHANNEL}")
    except Exception as e:
        logging.error(f"Failed to forward message: {e}")

# Start the Client
app.run()
