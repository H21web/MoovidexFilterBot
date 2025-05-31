# Don't Remove Credit @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot @Tech_VJ
# Ask Doubt on telegram @KingVJ01

import logging
import re
import os
from info import CHNL_LNK  # Assuming this contains your channel link
from pyrogram import Client, filters
from pyrogram.types import Message

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration - Replace with your source and destination channels
# Format: {"source_channel_id": ["dest_channel_id1", "dest_channel_id2"]}
CHANNEL_MAPPING = {
    -1001234567890: [-1009876543210, -1001122334455],  # Example mapping
    # Add more channel mappings as needed
}

# Regex patterns for URL and username replacement
URL_PATTERN = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
USERNAME_PATTERN = re.compile(r'@(\w+)')

# Custom caption template - you can modify this
CAPTION_TEMPLATE = """{filename}
Size: {size}
{original_caption}

🔗 {channel_link}"""

@Client.on_message(filters.channel & filters.incoming)
async def forward_documents_and_videos(client: Client, message: Message):
    try:
        source_chat = message.chat.id
        
        # Check if this source channel is in our mapping
        if source_chat not in CHANNEL_MAPPING:
            logger.info(f"Ignoring message from unmapped channel: {source_chat}")
            return

        destination_chats = CHANNEL_MAPPING[source_chat]
        
        # Check if message has document or video
        if not (message.document or message.video):
            logger.info(f"Ignoring non-media message from channel {source_chat}")
            return

        # Prepare file info
        if message.document:
            file = message.document
            file_type = "Document"
        else:
            file = message.video
            file_type = "Video"

        file_name = file.file_name if hasattr(file, 'file_name') else f"{file_type}_{file.file_id}"
        file_size = human_readable_size(file.file_size)

        # Process caption
        original_caption = message.caption or ""
        
        # Replace URLs and usernames
        cleaned_caption = URL_PATTERN.sub("[LINK REMOVED]", original_caption)
        cleaned_caption = USERNAME_PATTERN.sub("[USERNAME REMOVED]", cleaned_caption)
        
        # Format new caption
        new_caption = CAPTION_TEMPLATE.format(
            filename=file_name,
            size=file_size,
            original_caption=cleaned_caption,
            channel_link=CHNL_LNK
        )

        # Forward to all destination channels
        for dest_chat in destination_chats:
            try:
                if message.document:
                    await message.document.copy(
                        chat_id=dest_chat,
                        caption=new_caption
                    )
                else:
                    await message.video.copy(
                        chat_id=dest_chat,
                        caption=new_caption
                    )
                logger.info(f"Successfully forwarded {file_type} from {source_chat} to {dest_chat}")
            except Exception as e:
                logger.error(f"Failed to forward to {dest_chat}: {str(e)}")

    except Exception as e:
        logger.error(f"Error in forward_documents_and_videos: {str(e)}")

def human_readable_size(size_bytes):
    """Convert file size to human-readable format"""
    if size_bytes is None:
        return "Unknown size"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"
