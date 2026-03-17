import os
import logging
import asyncio
import threading
import random
import requests
import io
import edge_tts
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

# --- الإعدادات ---
TOKEN = "8695370562:AAGBkpBtxzY5BslA-L0CCA6tkZo-Bp-RtKw"
VOICE = "ar-SA-HamedNeural"  # صوت رجالي سعودي فخم

# حالات المحادثة
CHOOSING, TYPING_TEXT, TYPING_PROMPT = range(3)

# --- سيرفر وهمي لإبقاء البوت حياً على Render ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Running!"

def run_flask():
    app.run(host='0.0.0.0', port=os.getenv("PORT", default=8080))

def keep_alive():
    threading.Thread(target=run_flask).start()

# --- وظائف البوت ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎙️ تحويل نص إلى صوت", callback_data='tts')],
        [InlineKeyboardButton("🎨 توليد صورة احترافية", callback_data='img')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "🌟 **مرحباً بك في بوت الإبداع المتكامل!**\n\nاختر الخدمة التي تريدها من الأسفل:"
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return CHOOSING

async def tts_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.edit_text("✍️ أرسل النص العربي الذي تريد تحويله لصوت:")
    return TYPING_TEXT

async def img_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.edit_text("🖼️ أرسل وصف الصورة (يفضل بالإنجليزية لنتائج أفضل):")
    return TYPING_PROMPT

async def handle_tts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    file_path = f"voice_{update.message.chat_id}.mp3"
    msg = await update.message.reply_text("⏳ جاري توليد الصوت الفخم...")
    
    try:
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(file_path)
        with open(file_path, 'rb') as audio:
            await update.message.reply_audio(audio=audio, caption="✅ تم التحويل بنجاح")
        os.remove(file_path)
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")
    finally:
        await msg.delete()
    return await start(update, context)

async def handle_img(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text
    msg = await update.message.reply_text("🎨 جاري رسم لوحتك... يرجى الانتظار.")
    
    try:
        seed = random.randint(1, 999999)
        # الرابط المطور لضمان جودة Flux وتجاوز الكاش
        url = f"https://pollinations.ai/p/{requests.utils.quote(prompt)}?width=1024&height=1024&seed={seed}&model=flux&nologo=true"
        
        # تحميل الصورة للسيرفر أولاً لضمان عدم ظهور الشعار
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            await update.message.reply_photo(photo=io.BytesIO(response.content), caption=f"✨ نتيجة الوصف: {prompt}")
        else:
            await update.message.reply_text("❌ فشل المحرك في الاستجابة، حاول مجدداً.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ خطأ في الاتصال: {e}")
    finally:
        await msg.delete()
    return await start(update, context)

def main():
    keep_alive() # تشغيل السيرفر الوهمي
    
    application = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [
                CallbackQueryHandler(tts_request, pattern='^tts$'),
                CallbackQueryHandler(img_request, pattern='^img$')
            ],
            TYPING_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_tts)],
            TYPING_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_img)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    application.add_handler(conv_handler)
    print("🚀 البوت يعمل الآن على Render...")
    application.run_polling()

if __name__ == "__main__":
    main()
