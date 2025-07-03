async def send_movies_page(client, chat_id, user_id, page):
    page_size = 20  # 2 columns = 10 rows per page
    titles = user_pages[user_id]["titles"]

    # Ensure latest title (first in list) is last button
    if titles:
        latest_title = titles[0]
        rest_titles = titles[1:]
        display_titles = rest_titles + [latest_title]
    else:
        display_titles = []

    start = page * page_size
    end = start + page_size
    current_titles = display_titles[start:end]

    keyboard = []
    row = []
    for title in current_titles:
        row.append(KeyboardButton(title))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(KeyboardButton("⬅️ Prev"))
    if end < len(display_titles):
        nav_buttons.append(KeyboardButton("➡️ Next"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([KeyboardButton("❌ Close")])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await client.send_message(chat_id, "🎬 **Latest Streaming Movies:**", reply_markup=reply_markup)
