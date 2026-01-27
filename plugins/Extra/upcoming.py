import re
import asyncio
import aiohttp
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from utils import temp
from info import *
from plugins.Extra.binged import HEADERS, clean_text, get_tmdb_details, search_tmdb_advanced, format_search_title
from database.users_chats_db import db
from plugins.Extra.image_gen import generate_status_image

# ... imports ...

# Callback for Notify
@Client.on_callback_query(filters.regex(r"^notify_(.+)_(.+)$"))
async def notify_callback(client, cq):
    data = cq.data.split("_")
    # data format: notify_{safe_title}_{r_date}
    # safe_title could contain underscores, so we join standard parts
    # But wait, split("_") will split the title too if it has underscores.
    # We should split by `notify_` prefix first or use regex groups.
    # The regex r"^notify_(.+)_(.+)$" groups are lazy or greedy?
    # standard regex greedy: group 1 will eat up to the last underscore.
    
    match = re.match(r"^notify_(.+)_(.+)$", cq.data)
    if not match:
         return await cq.answer("Invalid data", show_alert=True)
         
    safe_title = match.group(1)
    date_str = match.group(2)
    user_id = cq.from_user.id
    
    # Check if already subscribed
    current_alerts = await db.get_movie_alerts(safe_title)
    if user_id in current_alerts:
        return await cq.answer("You are already subscribed to this movie! 🔔", show_alert=True)
        
    await db.add_movie_alert(user_id, safe_title)
    await cq.answer(f"✅ Notification Set! You'll be notified when {safe_title.replace('_', ' ')} releases.", show_alert=True)

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
    
    # Date Range: Tomorrow to +40 days
    tomorrow = datetime.now() + timedelta(days=1)
    future = tomorrow + timedelta(days=40)
    
    from_date = tomorrow.strftime("%Y-%m-%d")
    to_date = future.strftime("%Y-%m-%d")
    
    # user specified limit=10, but we probably want more coverage for 40 days.
    # Let's request 50 items to be safe.
    base_url = f"https://api2.ottplay.com/api/v4.7/web/new-release?limit=50&from_date={from_date}&to_date={to_date}&content_type=all&language=&provider="
    
    try:
        data = await fetch_url(base_url)
        # Parse based on User provided structure (v4.7/web/new-release)
        if data and 'result' in data:
            return data['result']
        if data and 'data' in data:
            return data['data']
    except Exception as e:
        print(f"Upcoming Fetch Error: {e}")
            
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


from plugins.Extra.binged import ADMIN_IDS

# ... existing imports ...

# Callback for Upcoming details
@Client.on_callback_query(filters.regex(r"^upcoming_detail_(.+)$"))
async def upcoming_detail(client, cq):
    user_id = cq.from_user.id
    movie_id = cq.data.split("_")[-1]
    
    # Re-fetch to find the object
    movies = await fetch_ottplay_upcoming()
    movie = next((m for m in movies if str(m.get("_id")) == movie_id), None)
    
    if not movie:
         return await cq.answer("Movie details not found (might be out of cached range).", show_alert=True)

    # --- Processing Logic ---
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
    if not api_date and movie.get("where_to_watch"):
        wht = movie.get("where_to_watch")[0]
        api_date = wht.get("available_from")
        
    r_date = "N/A"
    if api_date:
        try: r_date = datetime.fromisoformat(api_date.replace("Z", "+00:00")).strftime("%d-%m-%Y")
        except: r_date = api_date
    
    certs = [c.get("certification") for c in movie.get("certifications", [])]
    cert_str = "/".join(certs) if certs else "N/A"
    posters = movie.get("posters", [])
    ottplay_poster = posters[0] if posters else None
    
    tmdb_backdrop, tmdb_poster, tmdb_rating, tmdb_plot, tmdb_id = None, None, None, None, None
    cast_str = "N/A"
    trailer_url = None
    
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
            
            videos = tmdb_details.get("videos", [])
            if videos:
                 video_url = videos[0].get("url")
                 if video_url:
                     trailer_url = f"https://www.youtube.com/watch?v={video_url}"
            
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
    
    # Save Data for Post/Edit
    if not hasattr(temp, "OTTPLAY_RESULTS"): temp.OTTPLAY_RESULTS = {}
    if user_id not in temp.OTTPLAY_RESULTS: temp.OTTPLAY_RESULTS[user_id] = {}
    
    current_data = {
        "title": title, "year": year, "type_str": type_str, "lang_tag": lang_tag,
        "genre_str": genre_str, "provider_str": provider_str, "cert_str": cert_str,
        "rating": rating, "r_date": r_date, "cast_str": cast_str, "plot": plot,
        "backdrop_url": backdrop_url, "poster_url": poster_url, "provider_logos": provider_logos,
        "safe_title": safe_title, "movie_id": movie_id,
        "trailer_url": trailer_url, "tmdb_id": tmdb_id,
        "is_upcoming": True
    }
    temp.OTTPLAY_RESULTS[user_id][movie_id] = current_data

    final_image_io = None
    if backdrop_url and poster_url:
        await cq.answer("Generating image...", cache_time=0)
        final_image_io = await generate_status_image(backdrop_url, poster_url, provider_logos, title, year, rating, genre_str, plot)
    
    buttons = [[InlineKeyboardButton(f"🔔 Notify Me", callback_data=f"notify_{safe_title}_{r_date}")]] 
    
    # Admin Buttons
    if user_id in ADMIN_IDS:
         buttons.append([
             InlineKeyboardButton("✏️ Edit & Post", callback_data=f"upcoming_edit_post_{movie_id}"),
             InlineKeyboardButton("📣 Post Default", callback_data=f"upcoming_post_{movie_id}")
         ])
         
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_message")])
    
    if final_image_io:
        await cq.message.reply_photo(photo=final_image_io, caption=msg, reply_markup=InlineKeyboardMarkup(buttons))
    elif backdrop_url:
        await cq.message.reply_photo(photo=backdrop_url, caption=msg, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await cq.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
    await cq.answer()


async def process_upcoming_data(movie, user_id):
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
    if not api_date and movie.get("where_to_watch"):
        wht = movie.get("where_to_watch")[0]
        api_date = wht.get("available_from")
    
    if api_date:
        try: r_date = datetime.fromisoformat(api_date.replace("Z", "+00:00")).strftime("%d-%m-%Y")
        except: r_date = api_date
    else: r_date = "N/A"

    certs = [c.get("certification") for c in movie.get("certifications", [])]
    cert_str = "/".join(certs) if certs else "N/A"
    posters = movie.get("posters", [])
    ottplay_poster = posters[0] if posters else None
    
    tmdb_backdrop, tmdb_poster, tmdb_rating, tmdb_plot, tmdb_id = None, None, None, None, None
    cast_str = "N/A"
    trailer_url = None
    
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
            videos = tmdb_details.get("videos", [])
            if videos and videos[0].get("url"):
                 trailer_url = f"https://www.youtube.com/watch?v={videos[0].get('url')}"

    rating = tmdb_rating if tmdb_rating else (str(movie.get("ottplay_rating")) + "/10" if movie.get("ottplay_rating") else "N/A")
    plot = tmdb_plot if tmdb_plot else "No description available."
    safe_title = format_search_title(title, year)
    lang_tag = f"#{lang.replace(' ', '')}"
    
    # Cache
    movie_id = str(movie.get("_id"))
    if not hasattr(temp, "OTTPLAY_RESULTS"): temp.OTTPLAY_RESULTS = {}
    if user_id not in temp.OTTPLAY_RESULTS: temp.OTTPLAY_RESULTS[user_id] = {}
    
    temp.OTTPLAY_RESULTS[user_id][movie_id] = {
        "title": title, "year": year, "type_str": type_str, "lang_tag": lang_tag,
        "genre_str": genre_str, "provider_str": provider_str, "cert_str": cert_str,
        "rating": rating, "r_date": r_date, "cast_str": cast_str, "plot": plot,
        "backdrop_url": tmdb_backdrop if tmdb_backdrop else ottplay_poster,
        "poster_url": ottplay_poster if ottplay_poster else tmdb_poster,
        "provider_logos": provider_logos,
        "safe_title": safe_title, "movie_id": movie_id,
        "trailer_url": trailer_url, "tmdb_id": tmdb_id,
        "is_upcoming": True
    }
    return temp.OTTPLAY_RESULTS[user_id][movie_id]

@Client.on_callback_query(filters.regex(r"^upcoming_post_(.+)$"))
async def upcoming_post(client, cq):
    movie_id = cq.data.split("_")[-1]
    user_id = cq.from_user.id
    
    if user_id not in ADMIN_IDS:
        return await cq.answer("🚫 Authorized for Admins only!", show_alert=True)
        
    data = temp.OTTPLAY_RESULTS.get(user_id, {}).get(movie_id)
    if not data:
         await cq.answer("♻️ Session expired. Refetching...", cache_time=0)
         movies = await fetch_ottplay_upcoming()
         movie = next((m for m in movies if str(m.get("_id")) == movie_id), None)
         if movie:
             data = await process_upcoming_data(movie, user_id)
         else:
             return await cq.answer("Movie data expired/not found.", show_alert=True)
    
    await cq.answer("Posting...", cache_time=0)
    
    # Reconstruct message (Upcoming Style)
    msg = f"🔜 **{data['title']}** · {data['year']} · `{data['type_str']}`\n\n"
    msg += f"**>🉑 {data['lang_tag']}\n"
    msg += f">🎭 {data['genre_str']}\n"
    msg += f">🚀 **Releasing On:** {data['provider_str']}\n"
    msg += f">📅 **Date:** {data['r_date']}\n"
    msg += f">®️ {data['cert_str']} · ⭐ {data['rating']}\n"
    msg += f">👥 {data['cast_str']}\n"
    msg += f">\n"
    msg += f">__Plot:__\n"
    msg += f">{data['plot']}**\n"
    msg += f" **@MooviDex** "
    
    backdrop_url = data['backdrop_url']
    poster_url = data['poster_url']
    
    final_image_io = None
    if backdrop_url and poster_url:
        try:
             final_image_io = await generate_status_image(
                backdrop_url, poster_url, data['provider_logos'],
                data['title'], data['year'], data['rating'], data['genre_str'], data['plot']
             )
        except Exception as e:
            print(f"Post Image Gen Error: {e}")

    buttons = []
    # Notify Button for Channel
    buttons.append([
        InlineKeyboardButton(f"🔔 Notify Me", callback_data=f"notify_{data['safe_title']}_{data['r_date']}")
    ])
    
    row = []
    if data['trailer_url']:
        row.append(InlineKeyboardButton("🎬 Trailer", url=data['trailer_url']))
    if data['tmdb_id']:
        media_type = "movie" if data['type_str'] == "Movie" else "tv"
        row.append(InlineKeyboardButton("More like this", url=f"https://t.me/{temp.U_NAME}?start=more_like_{data['tmdb_id']}_{media_type}"))
    if row:
        buttons.append(row)
        
    try:
        UPDATE_CHANNEL_ID = -1001680629032
        if final_image_io:
            final_image_io.seek(0)
            await client.send_photo(
                chat_id=UPDATE_CHANNEL_ID,
                photo=final_image_io,
                caption=msg,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        elif backdrop_url:
            await client.send_photo(
                chat_id=UPDATE_CHANNEL_ID,
                photo=backdrop_url,
                caption=msg,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
             await client.send_message(
                chat_id=UPDATE_CHANNEL_ID,
                text=msg,
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=True
            )
        await cq.answer("✅ Posted successfully!", show_alert=True)
    except Exception as e:
        await cq.answer(f"Error: {e}", show_alert=True)

@Client.on_callback_query(filters.regex(r"^upcoming_edit_post_(.+)$"))
async def upcoming_edit_post(client, cq):
    movie_id = cq.data.split("_")[-1]
    user_id = cq.from_user.id
    
    if user_id not in ADMIN_IDS:
        return await cq.answer("🚫 Authorized for Admins only!", show_alert=True)

    data = temp.OTTPLAY_RESULTS.get(user_id, {}).get(movie_id)
    if not data:
         # Try Re-fetch
         movies = await fetch_ottplay_upcoming()
         movie = next((m for m in movies if str(m.get("_id")) == movie_id), None)
         if movie:
             data = await process_upcoming_data(movie, user_id)
         else:
             return await cq.answer("❌ Error: Movie data not found.", show_alert=True)
        
    temp.EDITING_POST[user_id] = {"movie_id": movie_id, "source": "ottplay"}
    await cq.message.reply_text("✏️ Send the **new search keyword** or **full URL** to use in the search button.", quote=True)
    await cq.answer()