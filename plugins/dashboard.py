import logging
import jinja2
import datetime
import psutil
import time
import sys
import platform
from aiohttp import web
from info import ADMIN_USERNAME, ADMIN_PASSWORD
from database.users_chats_db import db
from database.stats_db import stats_db
from database.config_db import mdb
from database.ia_filterdb import get_search_results, col, sec_col
from database.requests_db import requests_db
from TechVJ.bot import TechVJBot
from utils import get_size
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import REQST_CHANNEL
import asyncio
import re

routes = web.RouteTableDef()

# Jinja2 environment setup
template_loader = jinja2.FileSystemLoader(searchpath="./TechVJ/template/dashboard/")
template_env = jinja2.Environment(loader=template_loader)

def render_template(name, **kwargs):
    template = template_env.get_template(name)
    return template.render(**kwargs)

def check_auth(request):
    auth_cookie = request.cookies.get('admin_auth')
    return auth_cookie == "true"

@routes.get("/admin/login")
async def login_page(request):
    return web.Response(text=render_template("login.html"), content_type='text/html')

@routes.post("/admin/login")
async def login_handler(request):
    data = await request.post()
    username = data.get('username')
    password = data.get('password')
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        response = web.HTTPFound('/admin')
        response.set_cookie('admin_auth', 'true', max_age=3600*24)
        return response
    else:
        return web.Response(text=render_template("login.html", error="Invalid credentials"), content_type='text/html')

@routes.get("/admin/logout")
async def logout_handler(request):
    response = web.HTTPFound('/admin/login')
    response.del_cookie('admin_auth')
    return response

@routes.get("/admin")
async def dashboard_home(request):
    try:
        if not check_auth(request):
            return web.HTTPFound('/admin/login')
        
        total_users = await db.total_users_count()
        users_today = await db.get_users_joined_today_count()
        total_chats = await db.total_chat_count()
        total_searches = await stats_db.get_total_searches()
        
        # Bot status (online/uptime would require tracking start time, assuming bot is online if this works)
        # We can get uptime from a global variable if we stored it, or just show "Online"
        
        success_ratio = await stats_db.get_global_success_ratio()
        today_ratio = await stats_db.get_today_success_ratio()
        weekly_ratio = await stats_db.get_weekly_success_ratio()
        fulfillment_ratio = await stats_db.get_average_user_fulfillment()
        
        # New Stats for Chart and Box
        no_result_ratio = await stats_db.get_no_result_ratio()
        no_result_data = await stats_db.get_no_results_per_day(days=7)
        
        # Database Stats
        db_stats = await stats_db.get_database_stats()
        
        # Prepare Chart Data
        # Fill in missing days for last 7 days for a complete graph
        chart_labels = []
        chart_data = []
        
        # Map data by date
        data_map = {item['_id']: item['count'] for item in no_result_data}
        
        for i in range(6, -1, -1):
            d = datetime.date.today() - datetime.timedelta(days=i)
            date_str = d.strftime("%Y-%m-%d")
            chart_labels.append(date_str)
            chart_data.append(data_map.get(date_str, 0))

        return web.Response(text=render_template("index.html", 
                                                 total_users=total_users,
                                                 users_today=users_today,
                                                 total_chats=total_chats,
                                                 total_searches=total_searches,
                                                 success_ratio=success_ratio,
                                                 today_ratio=today_ratio,
                                                 weekly_ratio=weekly_ratio,
                                                 fulfillment_ratio=fulfillment_ratio,
                                                 db_stats=db_stats,
                                                 no_result_ratio=no_result_ratio,
                                                 no_result_chart_labels=chart_labels,
                                                 no_result_chart_data=chart_data,
                                                 status="Online"), content_type='text/html')
    except Exception as e:
        import traceback
        return web.Response(text=f"Error: {e}\n\n{traceback.format_exc()}", status=500)

@routes.get("/admin/users")
async def users_page(request):
    if not check_auth(request):
        return web.HTTPFound('/admin/login')
    
    try:
        page = int(request.query.get('page', 1))
    except ValueError:
        page = 1
    
    search_query = request.query.get('search')
    limit = 50
    
    if search_query:
        users_list = await db.search_users(search_query)
        total_users = len(users_list)
        total_pages = 1
    else:
        total_users = await db.total_users_count()
        total_pages = (total_users + limit - 1) // limit
        users_list = await db.get_all_users_paginated(page, limit)
    
    return web.Response(text=render_template("users.html", 
                                             users=users_list,
                                             page=page,
                                             total_pages=total_pages,
                                             search_query=search_query), content_type='text/html')

@routes.get("/admin/groups")
async def groups_page(request):
    if not check_auth(request):
        return web.HTTPFound('/admin/login')
    
    try:
        page = int(request.query.get('page', 1))
    except ValueError:
        page = 1
        
    limit = 20
    total_chats_count = await db.total_chat_count()
    total_pages = (total_chats_count + limit - 1) // limit
    
    chats_list = await db.get_all_chats_paginated(page, limit)
    
    return web.Response(text=render_template("groups.html", 
                                             chats=chats_list,
                                             page=page,
                                             total_pages=total_pages), content_type='text/html')

@routes.get("/admin/searches")
async def searches_page(request):
    if not check_auth(request):
        return web.HTTPFound('/admin/login')
    
    top_searches = await stats_db.get_top_searches()
    no_result_searches = await stats_db.get_no_result_stats() 
    top_users = await stats_db.get_top_active_users()
    recent_searches = await stats_db.get_recent_all_searches(limit=100)
    
    return web.Response(text=render_template("searches.html", 
                                             top_searches=top_searches,
                                             no_result_searches=no_result_searches,
                                             top_users=top_users,
                                             recent_searches=recent_searches), content_type='text/html')

@routes.get("/admin/pm_searches")
async def pm_searches_page(request):
    if not check_auth(request):
        return web.HTTPFound('/admin/login')
    
    try:
        page = int(request.query.get('page', 1))
    except ValueError:
        page = 1
        
    limit = 50
    pm_searches = await stats_db.get_recent_pm_searches(page=page, limit=limit)
    total_count = await stats_db.get_total_pm_searches_count()
    total_pages = (total_count + limit - 1) // limit
    
    return web.Response(text=render_template("pm_searches.html", 
                                             pm_searches=pm_searches,
                                             page=page,
                                             total_pages=total_pages), content_type='text/html')

@routes.post("/admin/clear_pm_searches")
async def clear_pm_searches(request):
    if not check_auth(request):
         return web.HTTPFound('/admin/login')
    
    await stats_db.clear_pm_search_logs()
    return web.HTTPFound('/admin/pm_searches')

# --- NEW FEATURES ---

# Broadcast
async def run_broadcast(target, text, pin):
    total = 0
    success = 0
    failed = 0
    
    if target == 'users':
        users = await db.get_all_users()
        async for user in users:
            try:
                msg = await TechVJBot.send_message(chat_id=int(user['id']), text=text)
                if pin:
                    try: await msg.pin()
                    except: pass
                success += 1
            except Exception as e:
                failed += 1
            total += 1
            # Rate limiting / yielding
            if total % 50 == 0: await asyncio.sleep(0.5)
    else:
        groups = await db.get_all_chats()
        async for group in groups:
            try:
                msg = await TechVJBot.send_message(chat_id=int(group['id']), text=text)
                if pin:
                    try: await msg.pin()
                    except: pass
                success += 1
            except:
                failed += 1
            total += 1
            if total % 50 == 0: await asyncio.sleep(0.5)
            
    logging.info(f"Broadcast Finished. Total: {total}, Success: {success}, Failed: {failed}")

@routes.get("/admin/broadcast")
async def broadcast_page(request):
    if not check_auth(request): return web.HTTPFound('/admin/login')
    return web.Response(text=render_template("broadcast.html"), content_type='text/html')

@routes.post("/admin/broadcast/send")
async def broadcast_send_handler(request):
    if not check_auth(request): return web.HTTPFound('/admin/login')
    data = await request.post()
    message_text = data.get('message')
    target = data.get('target') 
    pin = data.get('pin') == 'true'
    
    asyncio.create_task(run_broadcast(target, message_text, pin))
    
    return web.Response(text=render_template("broadcast.html", success="Broadcast started in background! This may take a while depending on user count."), content_type='text/html')

# Premium
@routes.get("/admin/premium")
async def premium_page(request):
    if not check_auth(request): return web.HTTPFound('/admin/login')
    user_id = request.query.get('user_id')
    user_data = None
    is_premium = False
    expiry_time = None
    message = request.query.get('message')
    error = None
    
    total_premium = await db.all_premium_users()
    
    if user_id:
        try:
            user_id = int(user_id)
            user_data = await db.get_user(user_id)
            if user_data:
                is_premium = await db.has_premium_access(user_id)
                expiry_time = user_data.get('expiry_time')
            else:
                error = "User not found in database."
        except ValueError:
            error = "Invalid User ID"
            
    return web.Response(text=render_template("premium.html", user_data=user_data, is_premium=is_premium, expiry_time=expiry_time, searched_id=user_id or "", error=error, message=message, total_premium=total_premium), content_type='text/html')

@routes.post("/admin/premium/add")
async def premium_add_handler(request):
    if not check_auth(request): return web.HTTPFound('/admin/login')
    data = await request.post()
    user_id = int(data.get('user_id'))
    duration = data.get('duration')
    
    seconds = 0
    if duration == '1_day': seconds = 86400
    elif duration == '1_week': seconds = 86400 * 7
    elif duration == '1_month': seconds = 86400 * 30
    elif duration == '3_months': seconds = 86400 * 90
    elif duration == '6_months': seconds = 86400 * 180
    elif duration == '1_year': seconds = 86400 * 365
    elif duration == 'lifetime': seconds = 86400 * 365 * 100
    
    new_expiry = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
    await db.update_user({'id': user_id, 'expiry_time': new_expiry})
    
    return web.HTTPFound(f'/admin/premium?user_id={user_id}&message=Premium Added!')

@routes.post("/admin/premium/remove")
async def premium_remove_handler(request):
    if not check_auth(request): return web.HTTPFound('/admin/login')
    data = await request.post()
    user_id = int(data.get('user_id'))
    await db.update_user({'id': user_id, 'expiry_time': None})
    return web.HTTPFound(f'/admin/premium?user_id={user_id}&message=Premium Revoked!')

# Files
@routes.get("/admin/files")
async def files_page(request):
    if not check_auth(request): return web.HTTPFound('/admin/login')
    query = request.query.get('query')
    files = []
    total_count = 0
    message = request.query.get('message')
    
    if query:
        results, _, total_count = await get_search_results(0, query, max_results=50) 
        for f in results:
            f['file_size_human'] = get_size(f['file_size'])
            files.append(f)
            
    return web.Response(text=render_template("files.html", files=files, query=query or "", total_count=total_count, message=message), content_type='text/html')

@routes.post("/admin/files/delete")
async def files_delete_handler(request):
    if not check_auth(request): return web.HTTPFound('/admin/login')
    data = await request.post()
    file_id = data.get('file_id')
    query = data.get('return_query')
    
    if file_id:
        try:
            col.delete_one({'file_id': file_id})
            sec_col.delete_one({'file_id': file_id})
        except Exception:
            pass
            
    return web.HTTPFound(f'/admin/files?query={query}&message=File Deleted')

# Settings
@routes.get("/admin/settings")
async def settings_page(request):
    if not check_auth(request): return web.HTTPFound('/admin/login')
    config = {}
    config['maintenance_mode'] = await mdb.get_configuration_value('maintenance_mode')
    config['auto_accept'] = await mdb.get_configuration_value('auto_accept')
    config['private_filter'] = await mdb.get_configuration_value('private_filter')
    config['group_filter'] = await mdb.get_configuration_value('group_filter')
    config['forcesub'] = await mdb.get_configuration_value('forcesub')
    config['spoll_check'] = await mdb.get_configuration_value('spoll_check')
    
    return web.Response(text=render_template("settings.html", config=config), content_type='text/html')

@routes.post("/admin/settings/update")
async def settings_update_handler(request):
    if not check_auth(request): return web.HTTPFound('/admin/login')
    data = await request.post()
    
    keys = ['maintenance_mode', 'auto_accept', 'private_filter', 'group_filter', 'forcesub', 'spoll_check']
    for key in keys:
        val = data.get(key) == 'on'
        await mdb.update_configuration(key, val)
        
    return web.HTTPFound('/admin/settings')

# PM User
@routes.get("/admin/pm_user")
async def pm_user_page(request):
    if not check_auth(request): return web.HTTPFound('/admin/login')
    return web.Response(text=render_template("pm_user.html"), content_type='text/html')

@routes.post("/admin/pm_user/send")
async def pm_user_send_handler(request):
    if not check_auth(request): return web.HTTPFound('/admin/login')
    data = await request.post()
    user_id = data.get('user_id')
    message = data.get('message')
    
    try:
        await TechVJBot.send_message(chat_id=int(user_id), text=message)
        success = f"Message sent successfully to {user_id}!"
        return web.Response(text=render_template("pm_user.html", success=success), content_type='text/html')
    except Exception as e:
        error = f"Failed to send: {str(e)}"
        return web.Response(text=render_template("pm_user.html", error=error), content_type='text/html')

@routes.get("/admin/requests")
async def requests_page(request):
    if not check_auth(request): return web.HTTPFound('/admin/login')
    
    try:
        page = int(request.query.get('page', 1))
    except ValueError:
        page = 1
        
    status_filter = request.query.get('status')
    if status_filter == 'all': status_filter = None
    
    limit = 20
    requests_list = await requests_db.get_all_requests(page=page, limit=limit, status=status_filter)
    total_count = await requests_db.get_total_requests_count(status=status_filter)
    total_pages = (total_count + limit - 1) // limit
    
    message = request.query.get('message')
    
    return web.Response(text=render_template("requests.html", 
                                             requests=requests_list,
                                             page=page,
                                             total_pages=total_pages,
                                             status_filter=status_filter or 'all',
                                             message=message), content_type='text/html')

@routes.post("/admin/requests/action")
async def requests_action_handler(request):
    if not check_auth(request): return web.HTTPFound('/admin/login')
    data = await request.post()
    
    request_id = data.get('request_id')
    action = data.get('action')
    notify = data.get('notify') == 'on'
    message_text = data.get('message_text')
    search_link = data.get('search_link')
    
    req = await requests_db.get_request(request_id)
    if not req:
         return web.HTTPFound('/admin/requests?message=Request Not Found')
    
    if action == 'delete':
        await requests_db.delete_request(request_id)
        return web.HTTPFound('/admin/requests?message=Request Deleted')
        
    status_map = {
        'uploaded': 'fulfilled',
        'available': 'fulfilled',
        'unavailable': 'rejected'
    }
    
    new_status = status_map.get(action)
    if new_status:
        await requests_db.update_request_status(request_id, new_status)

    msg_result = f"Request Marked as {action.capitalize()}."

    # --- 1. Sync Channel Message ---
    # Attempt to edit the original message in the Request Channel to reflect new status
    if req.get('message_id') and REQST_CHANNEL:
        try:
            # Reconstruct message with new status
            original_content = req.get('content')
            user_mention = f"<a href='tg://user?id={req['user_id']}'>{req['user_name']}</a>"
            
            updated_text = f"""
<b>♻️ Request Status Update</b>
━━━━━━━━━━━━━━━━━━
<b>👤 User:</b> {user_mention}
<b>🆔 ID:</b> <code>{req['user_id']}</code>

<b>🎞️ Title:</b>
<blockquote expandable>{original_content}</blockquote>

<b>🔰 Status:</b> #{action.capitalize()}
<b>📅 Date:</b> {req['request_date'].strftime("%d %B %Y")}
━━━━━━━━━━━━━━━━━━
"""
            # Define Button for Channel Message
            action_btn = []
            if action == 'uploaded':
                action_btn = [[InlineKeyboardButton("✅ Uᴘʟᴏᴀᴅᴇᴅ ✅", callback_data=f"upalert#{req['user_id']}")]]
            elif action == 'available':
                action_btn = [[InlineKeyboardButton("✅ Aᴠᴀɪʟᴀʙʟᴇ ✅", callback_data=f"upalert#{req['user_id']}")]]
            elif action == 'unavailable':
                action_btn = [[InlineKeyboardButton("⚠️ Uɴᴀᴠᴀɪʟᴀʙʟᴇ ⚠️", callback_data=f"unalert#{req['user_id']}")]]
            
            reply_markup_obj = InlineKeyboardMarkup(action_btn) if action_btn else None

            await TechVJBot.edit_message_text(
                chat_id=REQST_CHANNEL,
                message_id=req['message_id'],
                text=updated_text,
                disable_web_page_preview=True,
                reply_markup=reply_markup_obj
            )
        except Exception as e:
            msg_result += f" (Channel Sync Failed: {e})"

    # --- 2. Notify User ---
    if notify:
        try:
            view_btn_url = "https://t.me/moovidexrobot" # Fallback
            if req.get('message_id') and REQST_CHANNEL:
                 try:
                     # Attempt to construct deep link to the message
                     # Assumes REQST_CHANNEL is a private channel ID (starting with -100)
                     # Format: https://t.me/c/{id_without_100}/{msg_id}
                     chat_id_str = str(REQST_CHANNEL)
                     if chat_id_str.startswith("-100"):
                         chat_id_clean = chat_id_str[4:]
                         view_url = f"https://t.me/c/{chat_id_clean}/{req['message_id']}"
                         btn.append([InlineKeyboardButton("👀 View Status", url=view_url)])
                     elif not chat_id_str.startswith("-"):
                         # Probably public username or non-100 ID (unlikely for channel)
                         pass 
                 except:
                     pass

            btn = []
            txt = ""
            
            if action in ['uploaded', 'available']:
                emoji = "✅" if action == 'uploaded' else "📂"
                title = "Request Uploaded!" if action == 'uploaded' else "Request Already Available!"
                
                txt = f"<b>{emoji} {title}</b>\n\n<b>🎬 {req.get('content')}</b>\n\n"
                if message_text:
                    txt += f"{message_text}\n\n"
                txt += "<i>Click below to get it!</i>"

                if search_link:
                    btn.append([InlineKeyboardButton("🔍 Search Here", url=search_link)])
                
                if req.get('message_id') and REQST_CHANNEL:
                     try:
                         chat_id_str = str(REQST_CHANNEL)
                         if chat_id_str.startswith("-100"):
                             chat_id_clean = chat_id_str[4:]
                             view_url = f"https://t.me/c/{chat_id_clean}/{req['message_id']}"
                             btn.append([InlineKeyboardButton("👀 View Status", url=view_url)])
                     except:
                         pass
                
            elif action == 'unavailable':
                txt = f"<b>❌ Request Unavailable</b>\n\n<b>🎬 {req.get('content')}</b>\n\n"
                if message_text:
                    txt += f"<b>Reason:</b> {message_text}\n\n"
                
                if req.get('message_id') and REQST_CHANNEL:
                     try:
                         chat_id_str = str(REQST_CHANNEL)
                         if chat_id_str.startswith("-100"):
                             chat_id_clean = chat_id_str[4:]
                             view_url = f"https://t.me/c/{chat_id_clean}/{req['message_id']}"
                             btn.append([InlineKeyboardButton("👀 View Request", url=view_url)])
                     except:
                         pass
            
            if btn:
                markup = InlineKeyboardMarkup(btn)
                await TechVJBot.send_message(chat_id=int(req['user_id']), text=txt, reply_markup=markup)
            else:
                 await TechVJBot.send_message(chat_id=int(req['user_id']), text=txt)

            msg_result += " User notified."
        except Exception as e:
            msg_result += f" Failed to notify: {e}"

    return web.HTTPFound(f'/admin/requests?message={msg_result}')
