from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.constants import ChatAction
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import os
import asyncpg
import random
from dotenv import load_dotenv
from google import genai

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)

# Links
UPDATES_LINK = "https://t.me/WorkGlows"
SUPPORT_LINK = "https://t.me/TheCryptoElders"
ADD_BOT_LINK = "https://t.me/zaptalkbot?startgroup=true"

# Persona
CHARACTER = "Gojo Satoru"
SERIES = "Jujutsu Kaisen"
persona = f"""
Character: {CHARACTER}
Series: {SERIES}

Act like {CHARACTER} from {SERIES}. Be witty, sarcastic, flirty, or funny when needed.
Use slangs, memes, short forms like "u", "r", "gonna", "lol". Talk like a real person.
Never say you're an assistant. You can write code, answer deeply, or just roast someone.
Be engaging and act human. No assistant behavior.
"""
fallbacks = [
    "No idea bro.", "Hmm, say that again?", "Still learning... lol", 
    "That's above my pay grade.", "Brain's fried, try later."
]

# Inline Buttons
def get_main_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Updates", url=UPDATES_LINK),
         InlineKeyboardButton("Support", url=SUPPORT_LINK)],
        [InlineKeyboardButton("Add Me To Your Group", url=ADD_BOT_LINK)]
    ])

# Database Helpers
async def db_connect():
    return await asyncpg.connect(DATABASE_URL)

async def is_chat_enabled(chat_id):
    conn = await db_connect()
    res = await conn.fetchval("SELECT 1 FROM chatbot_status WHERE chat_id = $1", chat_id)
    await conn.close()
    return res is not None

async def enable_chat(chat_id):
    conn = await db_connect()
    await conn.execute("INSERT INTO chatbot_status(chat_id) VALUES($1) ON CONFLICT DO NOTHING", chat_id)
    await conn.close()

async def disable_chat(chat_id):
    conn = await db_connect()
    await conn.execute("DELETE FROM chatbot_status WHERE chat_id = $1", chat_id)
    await conn.close()

# Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    await update.message.reply_text(
        "Hey! I'm your AI companion based on Gojo Satoru. Add me to your group and reply to my messages to chat!",
        reply_markup=get_main_buttons()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    await update.message.reply_text(
        "Here’s what I can do:\n\n"
        "• Chat with you when you reply to my message.\n"
        "• Enable/Disable chat in group with /chatbot\n\n"
        "Admin-only in groups: `/chatbot enable|disable`",
        reply_markup=get_main_buttons()
    )

async def chatbot_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type == "private":
        await update.message.reply_text("Use this command in a group.")
        return

    member = await context.bot.get_chat_member(update.message.chat.id, update.effective_user.id)
    if not member.status in ["administrator", "creator"]:
        await update.message.reply_text("Only admins can control the chatbot.")
        return

    args = context.args
    if not args:
        await update.message.reply_text("Usage: /chatbot enable or /chatbot disable")
        return

    arg = args[0].lower()
    if arg in ["enable", "on", "yes"]:
        await enable_chat(update.effective_chat.id)
        await update.message.reply_text("Chatbot enabled.")
    elif arg in ["disable", "off", "no"]:
        await disable_chat(update.effective_chat.id)
        await update.message.reply_text("Chatbot disabled.")
    else:
        await update.message.reply_text("Invalid argument. Use enable/disable.")

# AI Chat Handler
async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return
    if update.message.reply_to_message.from_user.id != context.bot.id:
        return
    if not await is_chat_enabled(update.effective_chat.id):
        return

    text = update.message.text
    if not text:
        return

    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

    try:
        result = genai.GenerativeModel("gemini-1.5-flash").generate_content(f"{persona}\nUser: {text}")
        reply_text = result.text.strip() if result.text else None
    except Exception as e:
        print(f"Gemini Error: {e}")
        reply_text = None

    if not reply_text:
        await update.message.reply_text(random.choice(fallbacks))
    elif len(reply_text) > 4096:
        with open("response.txt", "w", encoding="utf-8") as f:
            f.write(reply_text)
        await update.message.reply_document("response.txt")
    else:
        await update.message.reply_text(reply_text)

# Main Setup
async def set_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Help and buttons"),
        BotCommand("chatbot", "Enable or disable chat")
    ])

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("chatbot", chatbot_toggle))
    app.add_handler(MessageHandler(filters.TEXT & filters.REPLY, handle_reply))

    app.post_init = lambda _: set_commands(app)
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
