import os
import logging
from threading import Thread
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.background import BackgroundScheduler

logging.basicConfig(level=logging.INFO)

# --- Flask Server for Render Port Binding ---
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Bot is running live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

# --- Telegram Bot Setup ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

bot = telebot.TeleBot(BOT_TOKEN)
scheduler = BackgroundScheduler()
scheduler.start()

user_wizard = {}
scheduled_jobs = {}

@bot.message_handler(commands=['start'])
def start_command(message):
    if message.chat.type != 'private':
        return
    
    user_id = message.from_user.id
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("➕ Create Scheduled Post", callback_data="create_post"))
    markup.add(InlineKeyboardButton("📋 My Active Posts", callback_data="view_posts"))
    
    if user_id == OWNER_ID:
        markup.add(InlineKeyboardButton("👑 Owner Panel", callback_data="owner_panel"))
        
    bot.send_message(
        message.chat.id,
        "👋 **Welcome to Group Auto-Poster Bot!**\n\n"
        "Aap is bot ki madad se apne group me scheduled posts set kar sakte hain.",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    if call.data == "create_post":
        user_wizard[user_id] = {"step": "waiting_for_message"}
        bot.edit_message_text(
            "📷 **Step 1:** Apne message ka text bhejiye (Agar image ke sath bhejna hai toh image + caption ek sath bhejiye).",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
    
    elif call.data == "view_posts":
        jobs = scheduled_jobs.get(user_id, [])
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Back", callback_data="back_home"))
        
        if not jobs:
            bot.edit_message_text(
                "❌ Aapka koi bhi scheduled post active nahi hai.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
        else:
            text = "📋 **Aapke Active Scheduled Posts:**\n\n"
            for i, job in enumerate(jobs):
                text += f"{i+1}. Interval: har {job['interval']} minutes me\n"
            bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            
    elif call.data == "owner_panel":
        if user_id != OWNER_ID:
            bot.answer_callback_query(call.id, "⚠️ Yeh sirf bot owner ke liye hai!", show_alert=True)
            return
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Back", callback_data="back_home"))
        total_users_posts = sum(len(v) for v in scheduled_jobs.values())
        bot.edit_message_text(
            f"👑 **Owner Control Panel**\n\n• Total Active Scheduled Jobs: {total_users_posts}\n• Bot Status: Running ✅",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
    elif call.data == "back_home":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("➕ Create Scheduled Post", callback_data="create_post"))
        markup.add(InlineKeyboardButton("📋 My Active Posts", callback_data="view_posts"))
        if user_id == OWNER_ID:
            markup.add(InlineKeyboardButton("👑 Owner Panel", callback_data="owner_panel"))
        bot.edit_message_text(
            "👋 **Main Menu:**",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )

@bot.message_handler(func=lambda message: message.chat.type == 'private', content_types=['text', 'photo'])
def wizard_handler(message):
    user_id = message.from_user.id
    if user_id not in user_wizard:
        return
    
    state = user_wizard[user_id].get("step")
    
    if state == "waiting_for_message":
        user_wizard[user_id]["media_message"] = message
        user_wizard[user_id]["step"] = "waiting_for_buttons"
        bot.reply_to(
            message,
            "🔘 **Step 2:** Ab buttons bhejiye is format me:\n\n`Button Name - https://t.me/...`\n`Button 2 - https://example.com`\n\n(Har button ko nayi line me likhein. Agar button nahi chahiye toh `skip` likhein)",
            parse_mode="Markdown"
        )
        
    elif state == "waiting_for_buttons":
        btn_text = message.text
        markup = InlineKeyboardMarkup()
        
        if btn_text and btn_text.lower() != "skip":
            lines = btn_text.split("\n")
            for line in lines:
                if "-" in line:
                    parts = line.split("-")
                    b_name = parts[0].strip()
                    b_url = parts[1].strip()
                    markup.add(InlineKeyboardButton(b_name, url=b_url))
                    
        user_wizard[user_id]["reply_markup"] = markup if len(markup.keyboard) > 0 else None
        user_wizard[user_id]["step"] = "waiting_for_chat"
        bot.reply_to(message, "📢 **Step 3:** Us Group ka **Username** (jaise `@mygroup`) ya **Group Chat ID** bhejiye jahan message bhejna hai.", parse_mode="Markdown")
        
    elif state == "waiting_for_chat":
        user_wizard[user_id]["chat_id"] = message.text.strip()
        user_wizard[user_id]["step"] = "waiting_for_time"
        bot.reply_to(message, "⏱️ **Step 4:** Time interval set karein (Minutes me, jaise: `30`)", parse_mode="Markdown")
        
    elif state == "waiting_for_time":
        try:
            interval = int(message.text.strip())
        except ValueError:
            bot.reply_to(message, "❌ Kripya valid number dalein (jaise: 15, 30, 60).")
            return
            
        data = user_wizard[user_id]
        chat_id = data["chat_id"]
        media_msg = data["media_message"]
        reply_markup = data["reply_markup"]
        
        def send_scheduled_msg():
            try:
                if media_msg.photo:
                    photo_id = media_msg.photo[-1].file_id
                    bot.send_photo(chat_id, photo_id, caption=media_msg.caption or "", reply_markup=reply_markup)
                else:
                    bot.send_message(chat_id, media_msg.text or "", reply_markup=reply_markup)
            except Exception as e:
                logging.error(f"Error: {e}")

        job = scheduler.add_job(send_scheduled_msg, "interval", minutes=interval)
        
        if user_id not in scheduled_jobs:
            scheduled_jobs[user_id] = []
        scheduled_jobs[user_id].append({"job_id": job.id, "interval": interval})
        
        del user_wizard[user_id]
        bot.reply_to(message, f"✅ **Success!** Har {interval} minutes me message target group par auto-send hoga!", parse_mode="Markdown")

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    
    print("🤖 Bot Started Successfully with Telebot!")
    bot.infinity_polling()
