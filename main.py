import asyncio
import os
import logging

# Event loop fix for Python 3.14 / Render environment before pyrogram import
try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from threading import Thread
from flask import Flask
from pyrogram import Client, filters, idle
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO)

# --- Flask Server for Render Web Service Port Binding ---
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Bot is running live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

# --- Telegram Bot Configurations ---
API_ID = int(os.environ.get("API_ID", "123456"))
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
OWNER_ID = int(os.environ.get("OWNER_ID", "123456789"))

app = Client(
    "group_scheduler_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

scheduler = AsyncIOScheduler()

user_wizard = {}
scheduled_jobs = {}

@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id
    keyboard = [
        [InlineKeyboardButton("➕ Create Scheduled Post", callback_data="create_post")],
        [InlineKeyboardButton("📋 My Active Posts", callback_data="view_posts")]
    ]
    
    if user_id == OWNER_ID:
        keyboard.append([InlineKeyboardButton("👑 Owner Panel", callback_data="owner_panel")])
        
    await message.reply_text(
        "👋 **Welcome to Group Auto-Poster Bot!**\n\n"
        "Aap is bot ki madad se apne group me scheduled posts set kar sakte hain.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@app.on_callback_query()
async def callback_handler(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    if data == "create_post":
        user_wizard[user_id] = {"step": "waiting_for_message"}
        await callback_query.message.edit_text(
            "📷 **Step 1:** Apne message ka text bhejiye (Agar image ke sath bhejna hai toh image + caption ek sath bhejiye)."
        )
    
    elif data == "view_posts":
        jobs = scheduled_jobs.get(user_id, [])
        if not jobs:
            await callback_query.message.edit_text(
                "❌ Aapka koi bhi scheduled post active nahi hai.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_home")]])
            )
        else:
            text = "📋 **Aapke Active Scheduled Posts:**\n\n"
            for i, job in enumerate(jobs):
                text += f"{i+1}. Interval: har {job['interval']} minutes me\n"
            await callback_query.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_home")]])
            )
            
    elif data == "owner_panel":
        if user_id != OWNER_ID:
            await callback_query.answer("⚠️ Yeh sirf bot owner ke liye hai!", show_alert=True)
            return
        
        total_users_posts = sum(len(v) for v in scheduled_jobs.values())
        await callback_query.message.edit_text(
            f"👑 **Owner Control Panel**\n\n"
            f"• Total Active Scheduled Jobs: {total_users_posts}\n"
            f"• Bot Status: Running ✅",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back_home")]
            ])
        )
        
    elif data == "back_home":
        keyboard = [
            [InlineKeyboardButton("➕ Create Scheduled Post", callback_data="create_post")],
            [InlineKeyboardButton("📋 My Active Posts", callback_data="view_posts")]
        ]
        if user_id == OWNER_ID:
            keyboard.append([InlineKeyboardButton("👑 Owner Panel", callback_data="owner_panel")])
        await callback_query.message.edit_text(
            "👋 **Main Menu:**",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

@app.on_message(filters.private & ~filters.command(["start"]))
async def wizard_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_wizard:
        return
    
    state = user_wizard[user_id].get("step")
    
    if state == "waiting_for_message":
        user_wizard[user_id]["media_message"] = message
        user_wizard[user_id]["step"] = "waiting_for_buttons"
        
        await message.reply_text(
            "🔘 **Step 2:** Ab buttons bhejiye is format me:\n\n"
            "`Button Name - https://t.me/...`\n"
            "`Button 2 - https://example.com`\n\n"
            "(Har button ko nayi line me likhein. Agar button nahi chahiye toh `skip` likhein)"
        )
        
    elif state == "waiting_for_buttons":
        btn_text = message.text
        keyboard_buttons = []
        
        if btn_text.lower() != "skip":
            lines = btn_text.split("\n")
            for line in lines:
                if "-" in line:
                    parts = line.split("-")
                    b_name = parts[0].strip()
                    b_url = parts[1].strip()
                    keyboard_buttons.append([InlineKeyboardButton(b_name, url=b_url)])
                    
        user_wizard[user_id]["reply_markup"] = InlineKeyboardMarkup(keyboard_buttons) if keyboard_buttons else None
        user_wizard[user_id]["step"] = "waiting_for_chat"
        
        await message.reply_text(
            "📢 **Step 3:** Us Group ka **Username** (jaise `@mygroup`) ya **Group Chat ID** bhejiye jahan message bhejna hai.\n\n"
            "*(Dhyan rahe: Bot us group me Admin hona chahiye!)*"
        )
        
    elif state == "waiting_for_chat":
        chat_id = message.text.strip()
        user_wizard[user_id]["chat_id"] = chat_id
        user_wizard[user_id]["step"] = "waiting_for_time"
        
        await message.reply_text(
            "⏱️ **Step 4:** Time interval set karein (Minutes me).\n"
            "Misal ke taur par: `30` likhein agar har 30 minute me message bhejna hai."
        )
        
    elif state == "waiting_for_time":
        try:
            interval = int(message.text.strip())
        except ValueError:
            await message.reply_text("❌ Kripya valid number dalein (jaise: 15, 30, 60). Dobara koshish karein.")
            return
            
        data = user_wizard[user_id]
        chat_id = data["chat_id"]
        media_msg = data["media_message"]
        reply_markup = data["reply_markup"]
        
        async def send_scheduled_msg():
            try:
                if media_msg.photo:
                    await client.send_photo(
                        chat_id=chat_id,
                        photo=media_msg.photo.file_id,
                        caption=media_msg.caption or "",
                        reply_markup=reply_markup
                    )
                else:
                    await client.send_message(
                        chat_id=chat_id,
                        text=media_msg.text or "",
                        reply_markup=reply_markup
                    )
            except Exception as e:
                logging.error(f"Error sending scheduled post: {e}")

        job = scheduler.add_job(send_scheduled_msg, "interval", minutes=interval)
        
        if user_id not in scheduled_jobs:
            scheduled_jobs[user_id] = []
        scheduled_jobs[user_id].append({"job_id": job.id, "interval": interval})
        
        del user_wizard[user_id]
        
        await message.reply_text(
            f"✅ **Success!** Aapka scheduled post successfully set ho gaya hai.\n"
            f"Har {interval} minutes me message target group par auto-send hoga!"
        )

async def main():
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    
    scheduler.start()
    await app.start()
    print("🤖 Bot Started Successfully!")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
