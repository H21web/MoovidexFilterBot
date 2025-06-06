# file: upcoming.py

import requests
from datetime import datetime
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from info import O_DB_URI

# MongoDB setup
client_mongo = MongoClient(O_DB_URI)
db = client_mongo["telegram_bot"]
reminders_col = db["reminders"]

# Function to fetch upcoming movies
def fetch_upcoming_movies():
    url = "https://www.binged.com/wp-json/binged-api/v1/movies?mode=streaming-soon"
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://www.binged.com/'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        try:
            data = response.json()
            # Try multiple keys
            for key in ['data', 'movies', 'results']:
                if key in data:
                    return data[key]
            # fallback: if data itself is list
            if isinstance(data, list):
                return data
            return []
        except ValueError:
            return []
    return []

    
@Client.on_message(filters.command("upcoming"))
async def send_upcoming_movies(client, message):
    movies_data = fetch_upcoming_movies()

    if not movies_data:
        await message.reply_text("🚫 No upcoming movies found.")
        return

    all_movies_details = "\U0001F4FA <b>Upcoming Movies</b>:\n\n"
    for movie in movies_data:
        movie_id = str(movie.get('id'))
        title = movie.get('title', 'No title')
        streaming_date = movie.get('streaming-date', 'Unknown')
        language = ', '.join(movie.get('languages', ['Unknown']))
        platform = ', '.join(p.get('name', 'Unknown') for p in movie.get('platforms', []))
        movie_type = movie.get('type', 'Unknown')

        movie_block = (
            f"<b>{title}</b> ({language})\n"
            f"\U0001F3AC Type: <i>{movie_type}</i>\n"
            f"\U0001F4C5 Release: <u>{streaming_date}</u>\n"
            f"\U0001F4FA Platform: {platform}\n"
            f"<a href=\"https://t.me/{{client.me.username}}?start=remind_{movie_id}\">\U0001F514 Remind Me</a>\n\n"
        )
        all_movies_details += movie_block

    await message.reply_text(all_movies_details, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

@Client.on_message(filters.regex(r"^/start remind_(\d+)$"))
async def remind_command(client, message):
    movie_id = message.matches[0].group(1)
    user_id = message.from_user.id

    movie = next((m for m in fetch_upcoming_movies() if str(m.get('id')) == movie_id), None)
    if not movie:
        await message.reply_text("⚠️ Movie not found or already released.")
        return

    existing = reminders_col.find_one({"user_id": user_id, "movie_id": movie_id})
    if existing:
        await message.reply_text("✅ You're already set to be reminded.")
        return

    reminders_col.insert_one({
        "user_id": user_id,
        "movie_id": movie_id,
        "title": movie.get("title"),
        "remind_date": movie.get("streaming-date"),
        "platform": ', '.join(p.get('name') for p in movie.get('platforms', [])),
        "notified": False
    })
    await message.reply_text("🔔 Reminder set! You'll be alerted on release day.")

@Client.on_message(filters.command("myreminders"))
async def my_reminders(client, message):
    user_id = message.from_user.id
    reminders = list(reminders_col.find({"user_id": user_id, "notified": False}))

    if not reminders:
        await message.reply_text("📭 You have no active reminders.")
        return

    text = "<b>🔔 Your Active Reminders:</b>\n\n"
    buttons = []
    for r in reminders:
        text += f"• <b>{r['title']}</b> on <i>{r['remind_date']}</i> ({r['platform']})\n"
        buttons.append([
            InlineKeyboardButton(f"❌ Remove {r['title'][:15]}", callback_data=f"remove_{str(r['_id'])}")
        ])

    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

@Client.on_callback_query(filters.regex(r"^remove_(.*)"))
async def remove_reminder(client, callback_query):
    from bson import ObjectId
    reminder_id = callback_query.matches[0].group(1)
    result = reminders_col.delete_one({"_id": ObjectId(reminder_id)})

    if result.deleted_count:
        await callback_query.answer("🗑️ Reminder removed.", show_alert=False)
        await callback_query.message.delete()
    else:
        await callback_query.answer("⚠️ Failed to remove reminder.", show_alert=True)

# Daily checker job
async def check_and_notify(app):
    today = datetime.today().strftime('%Y-%m-%d')
    for reminder in reminders_col.find({"remind_date": today, "notified": False}):
        try:
            await app.send_message(
                reminder["user_id"],
                f"🎬 <b>{reminder['title']}</b> is out today on <b>{reminder['platform']}</b>!",
                parse_mode=ParseMode.HTML
            )
            reminders_col.delete_one({"_id": reminder["_id"]})
        except Exception:
            continue

# Scheduler setup
def setup_scheduler(app):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: app.loop.create_task(check_and_notify(app)), 'interval', hours=24)
    scheduler.start()
