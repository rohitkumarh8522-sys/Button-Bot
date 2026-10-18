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

# Storage Databases (In-Memory)
groups_db = set()  # Set of chat IDs where bot is added
trigger_buttons = {} # {chat_id: {word: {"text": str, "buttons": [(name, url)]}}}

def is_group_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
    except Exception:
        return False

# Track groups when bot receives messages
@bot.message_handler(func=lambda message: message.chat.type in ['group', 'supergroup'])
def track_and_process_groups(message):
    chat_id = message.chat.id
    groups_db.add(chat_id)
    
    # Check if message contains trigger word
    text = message.text or message.caption
    if not text or text.startswith('/'):
        return

    text_lower = text.strip().lower()
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

# --- BOT OWNER COMMANDS ---

@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    if message.from_user.id != OWNER_ID:
        return

    # Check if replying to a message or has text
    reply_msg = message.reply_to_message
    broadcast_text = message.text.replace('/broadcast', '').strip()

    if not reply_msg and not broadcast_text:
        bot.reply_to(message, "⚠️ **उपयोग:** `/broadcast [मैसेज]` या किसी मैसेज/फोटो को रिप्लाई करके `/broadcast` लिखें।", parse_mode="Markdown")
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

    bot.reply_to(message, f"📢 **ब्रोडकास्ट समाप्त!**\n\n✅ सफल: {success} ग्रुप्स\n❌ असफल: {failed} ग्रुप्स")

@bot.message_handler(commands=['groups'])
def groups_list_command(message):
    if message.from_user.id != OWNER_ID:
        return

    if not groups_db:
        bot.reply_to(message, "❌ बोट अभी किसी भी ग्रुप में नहीं जुड़ा है।")
        return

    response = "📋 **बोट जिन ग्रुप्स में एक्टिव है:**\n\n"
    count = 1

    for group_id in list(groups_db):
        try:
            chat = bot.get_chat(group_id)
            title = chat.title
            invite_link = chat.invite_link or "लिंक उपलब्ध नहीं है"
            response += f"{count}. **{title}**\n🆔 ID: `{group_id}`\n🔗 Link: {invite_link}\n\n"
            count += 1
        except Exception:
            response += f"{count}. **Group ID:** `{group_id}` (जानकारी लोड नहीं हो सकी)\n\n"
            count += 1

    bot.reply_to(message, response, parse_mode="Markdown", disable_web_page_preview=True)

# --- GROUP ADMIN COMMANDS ---

@bot.message_handler(commands=['button'])
def add_button_command(message):
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "⚠️ यह कमांड सिर्फ ग्रुप के अंदर काम करेगी!")
        return

    if not is_group_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "⚠️ यह कमांड सिर्फ ग्रुप एडमिन ही यूज़ कर सकते हैं!")
        return

    content = message.text.replace('/button', '', 1).strip()
    if not content:
        bot.reply_to(
            message,
            "⚠️ **फॉर्मेट सही नहीं है!**\n\n"
            "**उदाहरण:**\n"
            "`/button dm 𝐉𝐎𝐈𝐍 𝐍𝐎𝐖 📌 [1. 𝗜𝗻𝗝𝗢𝗬 ❤️](buttonurl:https://t.me/link1) [2. 𝗖𝗢𝗨𝗣𝗟𝗘 🌽](buttonurl:https://t.me/link2)`",
            parse_mode="Markdown"
        )
        return

    parts = content.split(maxsplit=1)
    word = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    # Extract buttons using pattern (buttonurl:link)
    button_pattern = r'\[(.*?)\]\(buttonurl:(.*?)\)'
    raw_buttons = re.findall(button_pattern, rest)

    # Remove button markup from response text
    clean_text = re.sub(button_pattern, '', rest).strip()

    if not raw_buttons:
        bot.reply_to(message, "❌ बटन फॉर्मेट गलत है! बटन के लिए `[नाम](buttonurl:लिंक)` का यूज़ करें।")
        return

    chat_id = message.chat.id
    if chat_id not in trigger_buttons:
        trigger_buttons[chat_id] = {}

    trigger_buttons[chat_id][word] = {
        "text": clean_text,
        "buttons": raw_buttons
    }

    bot.reply_to(message, f"✅ **सफलतापूर्वक सेट हो गया!**\n\nअब जब भी कोई ग्रुप में `{word}` लिखेगा, तो यह मैसेज और बटन्स ऑटो-रिप्लाई हो जाएंगे।", parse_mode="Markdown")

@bot.message_handler(commands=['buttons'])
def list_buttons_command(message):
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "⚠️ यह कमांड सिर्फ ग्रुप के अंदर काम करेगी!")
        return

    chat_id = message.chat.id
    chat_triggers = trigger_buttons.get(chat_id, {})

    if not chat_triggers:
        bot.reply_to(message, "❌ इस ग्रुप में अभी कोई ट्रिगर वर्ड या बटन सेट नहीं है।")
        return

    text = "📋 **इस ग्रुप के एक्टिव ट्रिगर वर्ड्स:**\n\n"
    for i, (word, data) in enumerate(chat_triggers.items(), 1):
        btn_count = len(data["buttons"])
        text += f"{i}. **वर्ड:** `{word}` ({btn_count} बटन्स शामिल हैं)\n"

    bot.reply_to(message, text, parse_mode="Markdown")

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    
    print("🤖 Custom Trigger Bot Started Successfully!")
    bot.infinity_polling() ka 
