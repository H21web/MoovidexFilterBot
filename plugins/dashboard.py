import logging
import jinja2
import datetime
from aiohttp import web
from info import ADMIN_USERNAME, ADMIN_PASSWORD
from database.users_chats_db import db
from database.stats_db import stats_db
from TechVJ.bot import TechVJBot

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
    if not check_auth(request):
        return web.HTTPFound('/admin/login')
    
    total_users = await db.total_users_count()
    users_today = await db.get_users_joined_today_count()
    total_chats = await db.total_chat_count()
    total_searches = await stats_db.get_total_searches()
    
    # Bot status (online/uptime would require tracking start time, assuming bot is online if this works)
    # We can get uptime from a global variable if we stored it, or just show "Online"
    
    success_ratio = await stats_db.get_global_success_ratio()
    fulfillment_ratio = await stats_db.get_average_user_fulfillment()

    return web.Response(text=render_template("index.html", 
                                             total_users=total_users,
                                             users_today=users_today,
                                             total_chats=total_chats,
                                             total_searches=total_searches,
                                             success_ratio=success_ratio,
                                             fulfillment_ratio=fulfillment_ratio,
                                             status="Online"), content_type='text/html')

@routes.get("/admin/users")
async def users_page(request):
    if not check_auth(request):
        return web.HTTPFound('/admin/login')
    
    try:
        page = int(request.query.get('page', 1))
    except ValueError:
        page = 1
        
    limit = 50
    total_users = await db.total_users_count()
    total_pages = (total_users + limit - 1) // limit
    
    users_list = await db.get_all_users_paginated(page, limit)
    
    return web.Response(text=render_template("users.html", 
                                             users=users_list,
                                             page=page,
                                             total_pages=total_pages), content_type='text/html')

@routes.get("/admin/groups")
async def groups_page(request):
    if not check_auth(request):
        return web.HTTPFound('/admin/login')
    
    chats = await db.get_all_chats()
    chats_list = await chats.to_list(length=100)
    
    return web.Response(text=render_template("groups.html", chats=chats_list), content_type='text/html')

@routes.get("/admin/searches")
async def searches_page(request):
    if not check_auth(request):
        return web.HTTPFound('/admin/login')
    
    top_searches = await stats_db.get_top_searches()
    no_result_searches = await stats_db.get_no_result_stats() 
    top_users = await stats_db.get_top_active_users()
    
    return web.Response(text=render_template("searches.html", 
                                             top_searches=top_searches,
                                             no_result_searches=no_result_searches,
                                             top_users=top_users), content_type='text/html')

@routes.get("/admin/pm_searches")
async def pm_searches_page(request):
    if not check_auth(request):
        return web.HTTPFound('/admin/login')
    
    pm_searches = await stats_db.get_recent_pm_searches()
    
    return web.Response(text=render_template("pm_searches.html", pm_searches=pm_searches), content_type='text/html')

@routes.post("/admin/clear_pm_searches")
async def clear_pm_searches(request):
    if not check_auth(request):
         return web.HTTPFound('/admin/login')
    
    await stats_db.clear_pm_search_logs()
    return web.HTTPFound('/admin/pm_searches')
