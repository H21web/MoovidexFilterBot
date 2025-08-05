import logging
from info import API_ID, API_HASH, CLONE_MODE, LOG_CHANNEL
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, CallbackQuery
from database.users_chats_db import db
import re
import datetime
import asyncio
from Script import script

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('clone_bots.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Store bot start times for uptime calculation
bot_start_times = {}
active_bot_instances = {}  # Store active client instances

async def log_clone_bot_creation(client, bot_info, user_info, bot_token):
    """Log new clone bot creation details"""
    try:
        # Create detailed log message
        log_message = f"""
🤖 **New Clone Bot Created**

**📊 Bot Details:**
• **Bot Name:** `{bot_info.first_name or 'N/A'}`
• **Bot Username:** @{bot_info.username or 'N/A'}
• **Bot ID:** `{bot_info.id}`
• **Bot Token:** `{bot_token[:10]}...{bot_token[-10:]}`  # Partial token for security

**👤 Owner Details:**
• **Owner Name:** `{user_info.first_name or 'N/A'} {user_info.last_name or ''}`
• **Owner Username:** @{user_info.username or 'N/A'}
• **Owner ID:** `{user_info.id}`

**📅 Creation Details:**
• **Created At:** `{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}`
• **Status:** ✅ **Active**
• **Server:** `Clone Bot System`

**🔗 Bot Link:** https://t.me/{bot_info.username}

#CloneBot #NewBot #Created
"""

        # Log to file and console
        logger.info(f"New clone bot created - Bot ID: {bot_info.id}, Owner ID: {user_info.id}, Username: @{bot_info.username}")
        
        # Send to log channel if configured
        if LOG_CHANNEL:
            try:
                await client.send_message(
                    chat_id=LOG_CHANNEL,
                    text=log_message,
                    disable_web_page_preview=True
                )
                logger.info(f"Clone bot creation logged to channel: {LOG_CHANNEL}")
            except Exception as e:
                logger.error(f"Failed to send log to channel {LOG_CHANNEL}: {e}")
        
        # Store in database with additional metadata
        creation_log = {
            'bot_id': bot_info.id,
            'bot_username': bot_info.username,
            'bot_name': bot_info.first_name,
            'owner_id': user_info.id,
            'owner_username': user_info.username,
            'owner_name': f"{user_info.first_name or ''} {user_info.last_name or ''}".strip(),
            'created_at': datetime.datetime.now(),
            'status': 'active',
            'action': 'created'
        }
        
        # Add to database logs (you might need to add this collection)
        await db.log_clone_action(creation_log)
        
    except Exception as e:
        logger.error(f"Error logging clone bot creation: {e}")

async def log_clone_bot_deletion(client, clone_data, user_info):
    """Log clone bot deletion details"""
    try:
        log_message = f"""
🗑️ **Clone Bot Deleted**

**📊 Bot Details:**
• **Bot Name:** `{clone_data.get('bot_name', 'N/A')}`
• **Bot Username:** @{clone_data.get('bot_username', 'N/A')}
• **Bot ID:** `{clone_data.get('bot_id', 'N/A')}`

**👤 Owner Details:**
• **Owner Name:** `{user_info.first_name or 'N/A'} {user_info.last_name or ''}`
• **Owner Username:** @{user_info.username or 'N/A'}
• **Owner ID:** `{user_info.id}`

**📅 Deletion Details:**
• **Deleted At:** `{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}`
• **Status:** ❌ **Deleted**

#CloneBot #Deleted #Removed
"""

        # Log to file and console
        logger.info(f"Clone bot deleted - Bot ID: {clone_data.get('bot_id')}, Owner ID: {user_info.id}")
        
        # Send to log channel if configured
        if LOG_CHANNEL:
            try:
                await client.send_message(
                    chat_id=LOG_CHANNEL,
                    text=log_message,
                    disable_web_page_preview=True
                )
                logger.info(f"Clone bot deletion logged to channel: {LOG_CHANNEL}")
            except Exception as e:
                logger.error(f"Failed to send deletion log to channel {LOG_CHANNEL}: {e}")
        
        # Store deletion log in database
        deletion_log = {
            'bot_id': clone_data.get('bot_id'),
            'bot_username': clone_data.get('bot_username'),
            'bot_name': clone_data.get('bot_name'),
            'owner_id': user_info.id,
            'owner_username': user_info.username,
            'owner_name': f"{user_info.first_name or ''} {user_info.last_name or ''}".strip(),
            'deleted_at': datetime.datetime.now(),
            'status': 'deleted',
            'action': 'deleted'
        }
        
        await db.log_clone_action(deletion_log)
        
    except Exception as e:
        logger.error(f"Error logging clone bot deletion: {e}")
