import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# API Credentials (Apni API details yahan dalein)
API_ID = int(os.environ.get("API_ID", "123456"))
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
OWNER_ID = int(os.environ.get("OWNER_ID", "123456789"))  # Aapki Telegram User ID

app = Client("my_filter_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# In-memory Databases (Production ke liye MongoDB/SQLite use kar sakte hain)
filters_db = {}     # {chat_id: {filter_name: {"text": str, "buttons": list}}}
welcome_db = {}     # {chat_id: {"status": bool, "text": str}}

# Helper Function: Extract buttons from text syntax [Text](buttonurl:link)
def parse_text_and_buttons(text: str):
    import re
    buttons = []
    # Pattern to match [Button Text](buttonurl:https://example.com)
    pattern = r"\[(.*?)\]\(buttonurl:(.*?)\)"
    matches = re.findall(pattern, text)
    
    clean_text = re.sub(pattern, "", text).strip()
    
    keyboard = []
    for btn_text, btn_url in matches:
        keyboard.append([InlineKeyboardButton(text=btn_text.strip(), url=btn_url.strip())])
        
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    return clean_text, reply_markup

# ==========================================
# 1. FILTER MANAGEMENT COMMANDS
# ==========================================

# Filter Add Command (/filter name response)
@app.on_message(filters.command("filter") & filters.group)
async def add_filter(client: Client, message: Message):
    if len(message.command) < 2 and not message.reply_to_message:
        await message.reply_text("❌ Usage: `/filter [filter_name] [reply text or button link]`")
        return

    filter_name = message.command[1].lower()
    
    if message.reply_to_message:
        reply_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    else:
        reply_text = message.text.split(None, 2)[2] if len(message.command) > 2 else ""

    if not reply_text:
        await message.reply_text("❌ Response text nahi mila!")
        return

    chat_id = message.chat.id
    chat_title = message.chat.title

    if chat_id not in filters_db:
        filters_db[chat_id] = {}

    filters_db[chat_id][filter_name] = reply_text

    # Formatting requested response message
    response_msg = (
        f"Saved 1 filters in {chat_title} :\n"
        f"-{filter_name}"
    )
    await message.reply_text(response_msg)

# Stop Single Filter (/stopbutton filter_name)
@app.on_message(filters.command("stopbutton") & filters.group)
async def stop_single_filter(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: `/stopbutton [filter_name]`")
        return

    filter_name = message.command[1].lower()
    chat_id = message.chat.id

    if chat_id in filters_db and filter_name in filters_db[chat_id]:
        del filters_db[chat_id][filter_name]
        await message.reply_text(f"✅ Filter `-{filter_name}` ko successfully delete kar diya gaya hai.")
    else:
        await message.reply_text(f"❌ `{filter_name}` naam ka koi filter nahi mila.")

# Stop All Filters (/stopallbutton)
@app.on_message(filters.command("stopallbutton") & filters.group)
async def stop_all_filters(client: Client, message: Message):
    chat_id = message.chat.id
    if chat_id in filters_db and filters_db[chat_id]:
        filters_db[chat_id].clear()
        await message.reply_text("🛑 Iss group ke saare buttons/filters successfully stop aur delete kar diye gaye hain.")
    else:
        await message.reply_text("❌ Iss group me koi active filters nahi hain.")

# View Active Filters (/filters)
@app.on_message(filters.command("filters") & filters.group)
async def list_filters(client: Client, message: Message):
    chat_id = message.chat.id
    if chat_id in filters_db and filters_db[chat_id]:
        filter_list = "\n".join([f"- {name}" for name in filters_db[chat_id].keys()])
        await message.reply_text(f"📋 **Active Filters in {message.chat.title}:**\n\n{filter_list}")
    else:
        await message.reply_text("❌ Iss group me abhi koi filters set nahi hain.")

# ==========================================
# 2. WELCOME MESSAGE SYSTEM
# ==========================================

# Set Welcome Message (/setwelcome text)
@app.on_message(filters.command("setwelcome") & filters.group)
async def set_welcome(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: `/setwelcome Welcome {user} to {group}!`")
        return

    welcome_text = message.text.split(None, 1)[1]
    chat_id = message.chat.id

    welcome_db[chat_id] = {"status": True, "text": welcome_text}
    await message.reply_text("✅ Welcome message successfully set aur ON kar diya gaya hai!")

# Turn Welcome ON (/welcome on)
@app.on_message(filters.command(["welcomeon", "welcome"]) & filters.group)
async def toggle_welcome(client: Client, message: Message):
    chat_id = message.chat.id
    cmd = message.text.split()
    
    if len(cmd) > 1 and cmd[1].lower() == "off":
        if chat_id in welcome_db:
            welcome_db[chat_id]["status"] = False
        await message.reply_text("🔴 Welcome message OFF kar diya gaya hai.")
    else:
        if chat_id not in welcome_db:
            welcome_db[chat_id] = {"status": True, "text": "Welcome {user} to {group}!"}
        else:
            welcome_db[chat_id]["status"] = True
        await message.reply_text("🟢 Welcome message ON kar diya gaya hai.")

# New Member Event Listener
@app.on_chat_member_updated()
async def welcome_new_member(client: Client, event):
    if event.new_chat_member and not event.old_chat_member:
        chat_id = event.chat.id
        user = event.new_chat_member.user
        
        if chat_id in welcome_db and welcome_db[chat_id]["status"]:
            raw_text = welcome_db[chat_id]["text"]
            formatted_text = raw_text.replace("{user}", user.mention).replace("{group}", event.chat.title)
            
            clean_text, reply_markup = parse_text_and_buttons(formatted_text)
            await client.send_message(chat_id, clean_text, reply_markup=reply_markup)

# ==========================================
# 3. OWNER COMMANDS (/groups)
# ==========================================

@app.on_message(filters.command("groups") & filters.user(OWNER_ID))
async def list_owner_groups(client: Client, message: Message):
    status_msg = await message.reply_text("🔄 Groups fetch kiye ja rahe hain...")
    
    group_text = "📊 **Bot Admin Groups List:**\n\n"
    count = 0

    async for dialog in client.get_dialogs():
        if dialog.chat.type.value in ["group", "supergroup"]:
            try:
                member = await client.get_chat_member(dialog.chat.id, "me")
                if member.status.value in ["administrator", "owner"]:
                    count += 1
                    chat_title = dialog.chat.title
                    
                    # Group Link Generate/Fetch
                    if dialog.chat.username:
                        link = f"https://t.me/{dialog.chat.username}"
                    else:
                        try:
                            link = await client.export_chat_invite_link(dialog.chat.id)
                        except Exception:
                            link = "No Link / Private"

                    group_text += f"{count}. **{chat_title}**\n🔗 [Group Link]({link})\n\n"
            except Exception:
                continue

    if count == 0:
        await status_msg.edit_text("❌ Bot kisi bhi group me Admin nahi hai.")
    else:
        group_text = f"Total Admin Groups: **{count}**\n\n" + group_text
        await status_msg.edit_text(group_text, disable_web_page_preview=True)

# ==========================================
# 4. FILTER TRIGGER LISTENER
# ==========================================

@app.on_message(filters.group & ~filters.bot)
async def trigger_filter(client: Client, message: Message):
    if not message.text:
        return

    chat_id = message.chat.id
    msg_text = message.text.lower()

    if chat_id in filters_db:
        for keyword, response in filters_db[chat_id].items():
            if keyword == msg_text or f" {keyword} " in f" {msg_text} ":
                clean_text, reply_markup = parse_text_and_buttons(response)
                await message.reply_text(clean_text, reply_markup=reply_markup)
                break

if __name__ == "__main__":
    app.run()
