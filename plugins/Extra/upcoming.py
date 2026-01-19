import re
import asyncio
import aiohttp
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import temp
from info import *
from plugins.Extra.binged import HEADERS, clean_text, get_tmdb_details, search_tmdb_advanced, format_search_title
from plugins.Extra.image_gen import generate_status_image

# Reusing fetch logic
async def fetch_url(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, timeout=10) as response:
                if response.status == 200:
                    return await response.json()
    except Exception as e:
        print(f"Request Error: {e}")
    return None

async def fetch_ottplay_upcoming():
    # New API endpoint provided by user
    url = "https://api2.ottplay.com/api/v4.5/web/ranking?module_name=hot_new&platform=web&section=widget_coming_soon_to_you&page=1&pin_it=true&template_name=upcoming_content"
    data = await fetch_url(url)
    if data and 'rank' in data:
        # The structure is data['rank'] -> list of items -> item['movie'] contains the details
        return [item.get('movie') for item in data['rank'] if item.get('movie')]
    return []

# /upcoming command
@Client.on_message(filters.command("upcoming"))
async def upcoming_movies_command(client, message):
    msg = await message.reply_text("⏳ Fetching upcoming releases...")
    
    movies_data = await fetch_ottplay_upcoming()

    if not movies_data:
        await msg.edit("🚫 No upcoming releases found.")
        return

    # Group by date for better UX? Or just list.
    # User asked for "like today logic", which is a list of buttons.
    
    buttons = []
    # Sort by date
    # Sort by date (use a helper to extract date safely)
    def get_sort_date(m):
        d = m.get('release_date')
        if not d and m.get('where_to_watch'):
            d = m.get('where_to_watch')[0].get('available_from')
        return d or '9999'

    movies_data.sort(key=get_sort_date)
    
    count = 0
    for movie in movies_data:
        if count >= 30: # Limit to avoid button limit issues
            break
            
        title = clean_text(movie.get('name', 'No title'))
        movie_id = str(movie.get("_id"))
        
        # Add date to button text
        r_date = movie.get('release_date')
        if not r_date and movie.get("where_to_watch"):
             r_date = movie.get("where_to_watch")[0].get("available_from")
             
        date_str = ""
        if r_date:
            try:
                d = datetime.fromisoformat(r_date.replace("Z", "+00:00"))
                date_str = f" ({d.strftime('%d %b')})"
            except:
                pass
        
        btn_text = f"{title}{date_str}"
        callback_data = f"upcoming_detail_{movie_id}"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])
        count += 1

    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
    reply_markup = InlineKeyboardMarkup(buttons)

    await msg.edit(f"🗓 **Upcoming Releases:**", reply_markup=reply_markup)


# Callback for Upcoming details
@Client.on_callback_query(filters.regex(r"^upcoming_detail_(.+)$"))
async def upcoming_detail(client, cq):
    movie_id = cq.data.split("_")[-1]
    
    # Re-fetch to find the object
    movies = await fetch_ottplay_upcoming()
    movie = next((m for m in movies if str(m.get("_id")) == movie_id), None)
    
    if not movie:
         return await cq.answer("Movie details not found (might be out of cached range).", show_alert=True)

    # --- Processing Logic (Similar to today.py) ---
    title = clean_text(movie.get("name", ""))
    year = movie.get("release_year")
    content_type = movie.get("content_type", "movie")
    media_type = "movie" if content_type == "movie" else "tv"
    type_str = "Movie" if media_type == "movie" else "Series"
    lang = movie.get("primary_language", {}).get("logo_text", "Unknown")
    genres = [g.get("name") for g in movie.get("genres", [])]
    genre_str = ", ".join(genres) if genres else "N/A"
    
    providers_data = movie.get("where_to_watch", [])
    provider_logos = []
    platform_links = []
    
    for p in providers_data:
        prov = p.get("provider", {})
        p_name = prov.get("name")
        logo = prov.get("logo_url") or prov.get("icon_url")
        if logo: provider_logos.append(logo)
        
        p_link = p.get("movie_url") or p.get("show_url")
        # Try direct link construct
        if not p_link and p_name and p.get("partner_title_id"):
            ptid = p.get("partner_title_id")
            if "netflix" in p_name.lower():
                p_link = f"https://www.netflix.com/title/{ptid}"
            elif "zee5" in p_name.lower():
                p_link = f"https://www.zee5.com/global/content/{ptid}"
            elif "sonyliv" in p_name.lower():
                p_link = f"https://www.sonyliv.com/shows/{ptid}"

        if p_link:
             if p_link.startswith("http"): pass
             elif p_link.startswith("www."): p_link = f"https://{p_link}"
             else: p_link = None
        
        if p_link: platform_links.append(f"[{p_name}]({p_link})")
        elif p_name: platform_links.append(p_name)
        
    provider_str = ", ".join(platform_links[:3]) if platform_links else "N/A"
    
    api_date = movie.get("release_date")
    # If API release_date is missing or invalid, check where_to_watch for available_from
    if not api_date and movie.get("where_to_watch"):
        wht = movie.get("where_to_watch")[0]
        api_date = wht.get("available_from")
        
    r_date = "N/A"
    if api_date:
        try: r_date = datetime.fromisoformat(api_date.replace("Z", "+00:00")).strftime("%d-%m-%Y")
        except: r_date = api_date
    
    # Try to find 'name' from provider if missing or just generic
    # (Existing provider logic remains below, this block was just date)

    certs = [c.get("certification") for c in movie.get("certifications", [])]
    cert_str = "/".join(certs) if certs else "N/A"
    posters = movie.get("posters", [])
    ottplay_poster = posters[0] if posters else None
    
    tmdb_backdrop, tmdb_poster, tmdb_rating, tmdb_plot, tmdb_id = None, None, None, None, None
    cast_str = "N/A"
    
    tmdb_results = search_tmdb_advanced(title, year=year, media_type=media_type)
    if tmdb_results:
        tmdb_id = tmdb_results[0].get("id")
        tmdb_details = get_tmdb_details(tmdb_id, media_type)
        if tmdb_details:
            tmdb_img = tmdb_details.get("image")
            if tmdb_img: tmdb_backdrop = tmdb_img
            t_orig = tmdb_details.get("original_data", {})
            p_path = t_orig.get("poster_path")
            if p_path: tmdb_poster = f"https://image.tmdb.org/t/p/original{p_path}"
            tmdb_rating = tmdb_details.get("rating")
            tmdb_plot = tmdb_details.get("plot")
            cast = tmdb_details.get("cast", [])
            cast_str = ", ".join(cast[:5]) if cast else "N/A"
            
    rating = tmdb_rating if tmdb_rating else (str(movie.get("ottplay_rating")) + "/10" if movie.get("ottplay_rating") else "N/A")
    plot = tmdb_plot if tmdb_plot else "No description available."
    safe_title = format_search_title(title, year)
    lang_tag = f"#{lang.replace(' ', '')}"
    
    msg = f"🔜 **{title}** · {year} · `{type_str}`\n\n"
    msg += f"**>🉑 {lang_tag}\n"
    msg += f">🎭 {genre_str} · 📺 {provider_str}\n"
    msg += f">®️ {cert_str} · ⭐ {rating}\n"
    msg += f">📅 {r_date}\n"
    msg += f">👥 {cast_str}\n"
    msg += f">\n"
    msg += f">__Plot:__\n"
    msg += f">{plot}**\n"
    msg += f" **@MooviDex** "
    
    backdrop_url = tmdb_backdrop if tmdb_backdrop else ottplay_poster
    poster_url = ottplay_poster if ottplay_poster else tmdb_poster
    
    final_image_io = None
    if backdrop_url and poster_url:
        await cq.answer("Generating image...", cache_time=0)
        final_image_io = await generate_status_image(backdrop_url, poster_url, provider_logos, title, year, rating, genre_str, plot)
    
    buttons = [[InlineKeyboardButton(f"🔔 Notify Me", callback_data=f"notify_{safe_title}_{r_date}")]] # Placeholder for notify
    # Search probably useless for upcoming, but maybe valid? 
    # buttons.append([InlineKeyboardButton(f"🔍 Search: {title}", url=f"https://t.me/{temp.U_NAME}?start=Search_{safe_title}")])
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
    
    if final_image_io:
        await cq.message.reply_photo(photo=final_image_io, caption=msg, reply_markup=InlineKeyboardMarkup(buttons))
    elif backdrop_url:
        await cq.message.reply_photo(photo=backdrop_url, caption=msg, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await cq.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
    await cq.answer()
