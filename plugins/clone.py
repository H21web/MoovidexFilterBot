# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

# Clone Code Credit : YT - @Tech_VJ / TG - @VJ_Bots / GitHub - @VJBots

from info import API_ID, API_HASH, CLONE_MODE, LOG_CHANNEL
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, CallbackQuery
from database.users_chats_db import db
import re
import datetime
from Script import script

from pyrogram import Client, filters
import re

# Main clone menu with inline buttons
@Client.on_message(filters.command('clone'))
async def clone_menu(client, message):
    user_id = message.from_user.id
    
    if CLONE_MODE == False:
        return await message.reply("**🚫 Clone mode is currently disabled!**")
    
    # Check if user has premium access
    if not await db.has_premium_access(user_id):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 Get Premium", callback_data="get_premium")],
            [InlineKeyboardButton("🆓 Free Trial", callback_data="free_trial")]
        ])
        return await message.reply(
            "**🔒 Premium Feature Required!**\n\n"
            "Clone bot feature is available for premium users only.\n"
            "Get premium access to create your own bot clone!",
            reply_markup=keyboard
        )
    
    # Show clone dashboard
    await show_clone_dashboard(client, message, user_id)

async def show_clone_dashboard(client, message, user_id):
    clone_data = await db.get_clone(user_id)
    
    if clone_data:
        # Bot exists - show bot details and management options
        try:
            bot_token = clone_data['bot_token']
            vj = Client(f"{bot_token}", API_ID, API_HASH, bot_token=bot_token)
            await vj.start()
            bot_info = await vj.get_me()
            await vj.stop()
            
            # Format bot details
            bot_details = f"""
**🤖 Your Clone Bot Details:**

**📱 Bot Name:** `{bot_info.first_name}`
**👤 Username:** @{bot_info.username}
**🆔 Bot ID:** `{bot_info.id}`
**📊 Status:** ✅ Active
**📅 Created:** {datetime.datetime.now().strftime('%Y-%m-%d')}

**⚙️ Current Settings:**
• **🔗 Shortlink:** {clone_data.get('url', 'Not Set')}
• **🔑 API Key:** {'Set' if clone_data.get('api') else 'Not Set'}
• **📚 Tutorial:** {'Enabled' if clone_data.get('tutorial') else 'Disabled'}
• **📢 Channel:** {clone_data.get('update_channel_link', 'Not Set')}
            """
            
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⚙️ Bot Settings", callback_data=f"bot_settings_{user_id}"),
                    InlineKeyboardButton("📊 Statistics", callback_data=f"bot_stats_{user_id}")
                ],
                [
                    InlineKeyboardButton("🔗 Set Shortlink", callback_data=f"set_shortlink_{user_id}"),
                    InlineKeyboardButton("📚 Set Tutorial", callback_data=f"set_tutorial_{user_id}")
                ],
                [
                    InlineKeyboardButton("📢 Update Channel", callback_data=f"set_channel_{user_id}"),
                    InlineKeyboardButton("🔄 Restart Bot", callback_data=f"restart_bot_{user_id}")
                ],
                [
                    InlineKeyboardButton("🗑️ Delete Clone", callback_data=f"delete_clone_{user_id}"),
                    InlineKeyboardButton("❌ Close", callback_data="close_menu")
                ]
            ])
            
            await message.reply(bot_details, reply_markup=keyboard)
            
        except Exception as e:
            error_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑️ Delete Clone", callback_data=f"delete_clone_{user_id}")],
                [InlineKeyboardButton("❌ Close", callback_data="close_menu")]
            ])
            await message.reply(
                f"**⚠️ Bot Error Detected:**\n\n`{str(e)}`\n\n"
                "Your clone bot seems to have issues. You may need to delete and recreate it.",
                reply_markup=error_keyboard
            )
    else:
        # No bot exists - show creation options
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Create New Bot", callback_data=f"create_bot_{user_id}")],
            [InlineKeyboardButton("📖 How to Clone?", callback_data="clone_tutorial")],
            [InlineKeyboardButton("❌ Close", callback_data="close_menu")]
        ])
        
        await message.reply(
            "**🚀 Welcome to Clone Bot Dashboard!**\n\n"
            "You don't have any clone bot yet.\n"
            "Click the button below to create your first clone bot!",
            reply_markup=keyboard
        )

# Callback query handlers
@Client.on_callback_query()
async def handle_callbacks(client, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    # Create new bot
    if data.startswith("create_bot_"):
        await create_new_bot(client, callback_query)
    
    # Bot settings
    elif data.startswith("bot_settings_"):
        await show_bot_settings(client, callback_query)
    
    # Bot statistics
    elif data.startswith("bot_stats_"):
        await show_bot_statistics(client, callback_query)
    
    # Set shortlink
    elif data.startswith("set_shortlink_"):
        await set_shortlink_menu(client, callback_query)
    
    # Set tutorial
    elif data.startswith("set_tutorial_"):
        await set_tutorial_menu(client, callback_query)
    
    # Set channel
    elif data.startswith("set_channel_"):
        await set_channel_menu(client, callback_query)
    
    # Restart bot
    elif data.startswith("restart_bot_"):
        await restart_single_bot(client, callback_query)
    
    # Delete clone
    elif data.startswith("delete_clone_"):
        await delete_clone_confirmation(client, callback_query)
    
    # Confirm delete
    elif data.startswith("confirm_delete_"):
        await confirm_delete_clone(client, callback_query)
    
    # Clone tutorial
    elif data == "clone_tutorial":
        await show_clone_tutorial(client, callback_query)
    
    # Get premium
    elif data == "get_premium":
        await show_premium_info(client, callback_query)
    
    # Free trial
    elif data == "free_trial":
        await handle_free_trial(client, callback_query)
    
    # Close menu
    elif data == "close_menu":
        await callback_query.message.delete()

async def create_new_bot(client, callback_query):
    user_id = callback_query.from_user.id
    
    if await db.is_clone_exist(user_id):
        await callback_query.answer("You already have a clone bot!", show_alert=True)
        return
    
    await callback_query.message.edit_text(
        "<b>🤖 Creating New Clone Bot</b>\n\n"
        "<b>Follow these steps:</b>\n"
        "1) Send <code>/newbot</code> to @BotFather\n"
        "2) Give a name for your bot\n"
        "3) Give a unique username\n"
        "4) Forward the bot token message to me\n\n"
        "<b>⏱️ You have 5 minutes to complete this process</b>\n\n"
        "/cancel - Cancel this process"
    )
    
    try:
        techvj = await client.listen(callback_query.message.chat.id, timeout=300)
        
        if techvj.text and techvj.text.lower() == '/cancel':
            return await callback_query.message.edit_text('<b>❌ Process cancelled</b>')
        
        if techvj.forward_from and techvj.forward_from.id == 93372553:
            try:
                bot_token = re.findall(r"\b(\d+:[A-Za-z0-9_-]+)\b", techvj.text)[0]
            except:
                return await callback_query.message.edit_text('<b>❌ Invalid bot token format</b>')
        else:
            return await callback_query.message.edit_text('<b>❌ Message not forwarded from @BotFather</b>')
        
        await callback_query.message.edit_text("**🔄 Creating your bot... Please wait**")
        
        try:
            vj = Client(f"{bot_token}", API_ID, API_HASH, bot_token=bot_token, plugins={"root": "CloneTechVJ"})
            await vj.start()
            bot = await vj.get_me()
            await db.add_clone_bot(bot.id, user_id, bot_token)
            
            success_text = f"""
**✅ Bot Successfully Created!**

**🤖 Bot Details:**
**📱 Name:** `{bot.first_name}`
**👤 Username:** @{bot.username}
**🆔 Bot ID:** `{bot.id}`

**🎉 Your clone bot is ready to use!**

Use /clone command again to manage your bot settings.
            """
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Manage Bot", callback_data=f"bot_settings_{user_id}")],
                [InlineKeyboardButton("❌ Close", callback_data="close_menu")]
            ])
            
            await callback_query.message.edit_text(success_text, reply_markup=keyboard)
            
        except Exception as e:
            await callback_query.message.edit_text(
                f"**⚠️ Bot Creation Failed:**\n\n`{str(e)}`\n\n"
                "Please forward this message to @KingVJ01 for assistance."
            )
    
    except Exception as e:
        await callback_query.message.edit_text(
            f"**⏱️ Time expired or error occurred:**\n\n`{str(e)}`\n\n"
            "Please try again with /clone command."
        )

async def show_bot_settings(client, callback_query):
    user_id = int(callback_query.data.split('_')[2])
    clone_data = await db.get_clone(user_id)
    
    if not clone_data:
        await callback_query.answer("No clone bot found!", show_alert=True)
        return
    
    settings_text = f"""
**⚙️ Bot Settings Panel**

**Current Configuration:**
• **🔗 Shortlink URL:** {clone_data.get('url', '❌ Not Set')}
• **🔑 Shortlink API:** {'✅ Set' if clone_data.get('api') else '❌ Not Set'}
• **📚 Tutorial Link:** {clone_data.get('tutorial', '❌ Not Set')}
• **📢 Update Channel:** {clone_data.get('update_channel_link', '❌ Not Set')}

**Choose an option to modify:**
    """
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔗 Shortlink", callback_data=f"set_shortlink_{user_id}"),
            InlineKeyboardButton("📚 Tutorial", callback_data=f"set_tutorial_{user_id}")
        ],
        [
            InlineKeyboardButton("📢 Channel", callback_data=f"set_channel_{user_id}"),
            InlineKeyboardButton("🔄 Restart", callback_data=f"restart_bot_{user_id}")
        ],
        [InlineKeyboardButton("🔙 Back to Dashboard", callback_data=f"back_dashboard_{user_id}")],
        [InlineKeyboardButton("❌ Close", callback_data="close_menu")]
    ])
    
    await callback_query.message.edit_text(settings_text, reply_markup=keyboard)

async def show_bot_statistics(client, callback_query):
    user_id = int(callback_query.data.split('_')[2])
    clone_data = await db.get_clone(user_id)
    
    if not clone_data:
        await callback_query.answer("No clone bot found!", show_alert=True)
        return
    
    # Get bot statistics (you can expand this based on your needs)
    stats_text = f"""
**📊 Bot Statistics**

**Bot ID:** `{clone_data.get('bot_id', 'N/A')}`
**Owner ID:** `{clone_data.get('user_id', 'N/A')}`
**Status:** ✅ Active
**Created:** Today

**📈 Usage Stats:**
• **Total Users:** Coming Soon
• **Total Groups:** Coming Soon
• **Files Shared:** Coming Soon
• **Uptime:** Coming Soon

*Statistics feature is under development*
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Dashboard", callback_data=f"back_dashboard_{user_id}")],
        [InlineKeyboardButton("❌ Close", callback_data="close_menu")]
    ])
    
    await callback_query.message.edit_text(stats_text, reply_markup=keyboard)

async def delete_clone_confirmation(client, callback_query):
    user_id = int(callback_query.data.split('_')[2])
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_delete_{user_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"back_dashboard_{user_id}")
        ]
    ])
    
    await callback_query.message.edit_text(
        "**⚠️ Delete Clone Bot**\n\n"
        "Are you sure you want to delete your clone bot?\n"
        "This action cannot be undone!",
        reply_markup=keyboard
    )

async def confirm_delete_clone(client, callback_query):
    user_id = int(callback_query.data.split('_')[2])
    
    if await db.is_clone_exist(user_id):
        await db.delete_clone(user_id)
        await callback_query.message.edit_text(
            "**✅ Clone bot successfully deleted!**\n\n"
            "You can create a new clone bot anytime using /clone command."
        )
    else:
        await callback_query.message.edit_text("**❌ No clone bot found to delete!**")

async def show_clone_tutorial(client, callback_query):
    tutorial_text = """
**📖 How to Clone a Bot?**

**Step 1:** Get Premium Access
• Clone feature is available for premium users only

**Step 2:** Create Bot with BotFather
• Send `/newbot` to @BotFather
• Choose a name for your bot
• Choose a unique username ending with 'bot'

**Step 3:** Get Bot Token
• BotFather will send you a token
• Forward that message to this bot

**Step 4:** Customize Your Bot
• Set shortlink URL and API
• Add tutorial link
• Configure update channel

**Step 5:** Enjoy!
• Your clone bot is ready to use
• Manage it anytime with /clone command
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="back_main_menu")],
        [InlineKeyboardButton("❌ Close", callback_data="close_menu")]
    ])
    
    await callback_query.message.edit_text(tutorial_text, reply_markup=keyboard)

# Additional handlers for setting shortlink, tutorial, channel, etc.
async def set_shortlink_menu(client, callback_query):
    user_id = int(callback_query.data.split('_')[2])
    
    await callback_query.message.edit_text(
        "**🔗 Set Shortlink Configuration**\n\n"
        "Send your shortlink URL and API in this format:\n"
        "`URL API_KEY`\n\n"
        "Example: `https://short.link.com your_api_key`\n\n"
        "/cancel - Cancel this process"
    )
    
    # Add listen logic here for shortlink setup

async def restart_single_bot(client, callback_query):
    user_id = int(callback_query.data.split('_')[2])
    clone_data = await db.get_clone(user_id)
    
    if not clone_data:
        await callback_query.answer("No clone bot found!", show_alert=True)
        return
    
    await callback_query.message.edit_text("**🔄 Restarting your bot... Please wait**")
    
    try:
        bot_token = clone_data['bot_token']
        vj = Client(f"{bot_token}", API_ID, API_HASH, bot_token=bot_token, plugins={"root": "CloneTechVJ"})
        await vj.start()
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Dashboard", callback_data=f"back_dashboard_{user_id}")],
            [InlineKeyboardButton("❌ Close", callback_data="close_menu")]
        ])
        
        await callback_query.message.edit_text(
            "**✅ Bot successfully restarted!**\n\n"
            "Your clone bot is now online and ready to use.",
            reply_markup=keyboard
        )
        
    except Exception as e:
        await callback_query.message.edit_text(
            f"**❌ Failed to restart bot:**\n\n`{str(e)}`\n\n"
            "Please contact support if this issue persists."
        )

# Enhanced restart all bots function
async def restart_bots():
    """Restart all clone bots on server startup"""
    try:
        bots_cursor = await db.get_all_bots()
        bots = await bots_cursor.to_list(None)
        
        successful_restarts = 0
        failed_restarts = 0
        
        for bot in bots:
            bot_token = bot['bot_token']
            try:
                vj = Client(
                    f"{bot_token}", API_ID, API_HASH,
                    bot_token=bot_token,
                    plugins={"root": "CloneTechVJ"},
                )
                await vj.start()
                successful_restarts += 1
                print(f"✅ Successfully restarted bot: {bot.get('bot_id', 'Unknown')}")
            except Exception as e:
                failed_restarts += 1
                print(f"❌ Failed to restart bot {bot.get('bot_id', 'Unknown')}: {e}")
        
        print(f"🔄 Bot restart summary: {successful_restarts} successful, {failed_restarts} failed")
        
    except Exception as e:
        print(f"❌ Error in restart_bots function: {e}")

# Command to show all clone bots (admin only)
@Client.on_message(filters.command('allclones'))
async def show_all_clones(client, message):
    # Add admin check here
    user_id = message.from_user.id
    # if user_id not in ADMINS: return
    
    bots_cursor = await db.get_all_bots()
    bots = await bots_cursor.to_list(None)
    
    if not bots:
        return await message.reply("**No clone bots found in database.**")
    
    clone_list = "**🤖 All Clone Bots:**\n\n"
    
    for i, bot in enumerate(bots, 1):
        clone_list += f"{i}. **Bot ID:** `{bot.get('bot_id', 'N/A')}`\n"
        clone_list += f"   **Owner:** `{bot.get('user_id', 'N/A')}`\n"
        clone_list += f"   **Status:** {'✅ Active' if bot.get('bot_token') else '❌ Inactive'}\n\n"
    
    await message.reply(clone_list)
