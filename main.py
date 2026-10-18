import os
import logging
import re
from threading import Thread
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(level=logging.INFO)

# --- Flask Server for Render Port Binding ---
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Bot is running live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

# --- Telegram Bot Configurations ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

bot = telebot.TeleBot(BOT_TOKEN)

groups_db = set()
trigger_buttons = {}

def is_group_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
    except Exception:
        return False

# ==========================================
# 1. COMMAND HANDLERS (सबसे ऊपर रखे गए हैं)
# ==========================================

@bot.message_handler(commands=['start'])
def start_command(message):
    if message.chat.type != 'private':
        return
    bot.reply_to(message, "👋 Welcome! Bot is active and running.")

@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    if message.from_user.id != OWNER_ID:
        return

    reply_msg = message.reply_to_message
    broadcast_text = message.text.replace('/broadcast', '').strip()

    if not reply_msg and not broadcast_text:
        bot.reply_to(message, "⚠️ Format: `/broadcast [message]`", parse_mode="Markdown")
        return

    success = 0
    failed = 0
    for group_id in list(groups_db):
        try:
            if reply_msg:
                bot.copy_message(chat_id=group_id, from_chat_id=reply_msg.chat.id, message_id=reply_msg.message_id)
            else:
                bot.send_message(chat_id=group_id, text=broadcast_text, parse_mode="Markdown")
            success += 1
        except Exception:
            failed += 1

    bot.reply_to(message, f"📢 Broadcast Complete!\n✅ Success: {success}\n❌ Failed: {failed}")

@bot.message_handler(commands=['groups'])
def groups_list_command(message):
    if message.from_user.id != OWNER_ID:
        return

    if not groups_db:
        bot.reply_to(message, "❌ Bot kisi bhi group me active nahi hai.")
        return

    response = "📋 **Groups List:**\n\n"
    count = 1
    for group_id in list(groups_db):
        try:
            chat = bot.get_chat(group_id)
            title = chat.title
            invite_link = chat.invite_link or "Link unavailable"
            response += f"{count}. **{title}**\n🆔 ID: `{group_id}`\n🔗 Link: {invite_link}\n\n"
            count += 1
        except Exception:
            response += f"{count}. **Group ID:** `{group_id}`\n\n"
            count += 1

    bot.reply_to(message, response, parse_mode="Markdown", disable_web_page_preview=True)

@bot.message_handler(commands=['button'])
def add_button_command(message):
    groups_db.add(message.chat.id)
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "⚠️ Ye command sirf group me chalegi!")
        return

    if not is_group_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "⚠️ Ye command sirf group admin use kar sakte hain!")
        return

    content = message.text.replace('/button', '', 1).strip()
    if not content:
        bot.reply_to(
            message,
            "⚠️ **Format Example:**\n\n"
            "`/button dm JOIN NOW 📌 [1. ENJOY ❤️](buttonurl:https://t.me/link1)`",
            parse_mode="Markdown"
        )
        return

    parts = content.split(maxsplit=1)
    word = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    button_pattern = r'\[(.*?)\]\(buttonurl:(.*?)\)'
    raw_buttons = re.findall(button_pattern, rest)
    clean_text = re.sub(button_pattern, '', rest).strip()

    if not raw_buttons:
        bot.reply_to(message, "❌ Button format galat hai! Use karein: `[Name](buttonurl:Link)`", parse_mode="Markdown")
        return

    chat_id = message.chat.id
    if chat_id not in trigger_buttons:
        trigger_buttons[chat_id] = {}

    trigger_buttons[chat_id][word] = {
        "text": clean_text,
        "buttons": raw_buttons
    }

    bot.reply_to(message, f"✅ **Set Ho Gaya!**\n\nAb jab bhi koi group me `{word}` likhega, ye message aur buttons reply ho jayenge.", parse_mode="Markdown")

@bot.message_handler(commands=['buttons'])
def list_buttons_command(message):
    groups_db.add(message.chat.id)
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "⚠️ Ye command sirf group me chalegi!")
        return

    chat_id = message.chat.id
    chat_triggers = trigger_buttons.get(chat_id, {})

    if not chat_triggers:
        bot.reply_to(message, "❌ Is group me koi button/trigger set nahi hai.")
        return

    text = "📋 **Active Triggers:**\n\n"
    for i, (word, data) in enumerate(chat_triggers.items(), 1):
        btn_count = len(data["buttons"])
        text += f"{i}. **Word:** `{word}` ({btn_count} buttons)\n"

    bot.reply_to(message, text, parse_mode="Markdown")

# ==========================================
# 2. GENERAL GROUP MESSAGE HANDLER (सबसे नीचे)
# ==========================================

@bot.message_handler(func=lambda message: message.chat.type in ['group', 'supergroup'] and message.text and not message.text.startswith('/'))
def process_group_triggers(message):
    chat_id = message.chat.id
    groups_db.add(chat_id)
    
    text_lower = message.text.strip().lower()
    chat_triggers = trigger_buttons.get(chat_id, {})

    if text_lower in chat_triggers:
        data = chat_triggers[text_lower]
        reply_text = data["text"]
        buttons = data["buttons"]

        markup = InlineKeyboardMarkup()
        for btn_name, btn_url in buttons:
            markup.add(InlineKeyboardButton(text=btn_name, url=btn_url))

        try:
            bot.reply_to(message, reply_text, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Error sending button reply: {e}")

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    
    print("🤖 Bot Started Successfully with Fixed Handlers!")
    bot.infinity_polling()
