import re
import logging
from pyrogram import Client, filters
from pyrogram.session import StringSession

# Add your StringSession here (generate using Pyrogram)
STRING_SESSION = "1BVtsOIoBu4X-B021hLB4we-WRkOtYT5VJlHOpp8P6AKXHt5Jdoo2VGurK65sa_iGe5Hnl_idFdc8xLtkLUhnx74iI8NSuxb98OHIEXul3ikz1BNHm3CNiIXKftpxd_cia-fyFA4VZpNFIU8-S2gdtQnCTwcZQpgSbBcCE1evohvQHS3XcHumam1nGVki4Xr2LZhP98oyXJVbw8dfucZZ4XWT9NltQbfOd9Mvyn3qO-3lSpP-gm-bQayaGhD-RhThsCGxOgObbg5Xy0zu-x9EXWJ-DTcoGid0feaRtqryrRi2_Evr_D2qAPH1SE2GstPSxGPbIi4TBspn_1ot9V6A450vgdt6tsU="  # Replace with your session string
API_ID = 8281168  # Replace with your API ID
API_HASH = "445ff67ec34858448ac184c7479ce917"  # Replace with your API Hash

# Initialize Pyrogram Client using User Session
app = Client(StringSession(STRING_SESSION), api_id=API_ID, api_hash=API_HASH)

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
