import logging
import asyncio
import edge_tts
import os
import uuid
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# الإعدادات
TOKEN = "8695370562:AAGBkpBtxzY5BslA-L0CCA6tkZo-Bp-RtKw"
VOICE = "ar-EG-SalmaNeural"

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎙️ أرسل لي أي نص لتحويله لصوت احترافي...")

async def text_to_speech_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    # استخدام معرف فريد للملف لتجنب تداخل الطلبات
    file_path = f"voice_{uuid.uuid4().hex}.mp3"
    waiting_msg = await update.message.reply_text("⏳ جاري توليد الصوت...")

    try:
        # تنفيذ عملية التوليد
        communicate = edge_tts.Communicate(user_text, VOICE)
        await communicate.save(file_path)

        # التأكد من وجود الملف قبل الإرسال
        if os.path.exists(file_path):
            with open(file_path, 'rb') as audio:
                await update.message.reply_audio(audio=audio, caption="✅ تم التحويل")
            os.remove(file_path)
        else:
            raise Exception("File not created")

    except Exception as e:
        logging.error(f"TTS Error: {e}")
        await update.message.reply_text("❌ عذراً، يبدو أن السيرفر المجاني يمنع الاتصال بمحرك الصوت حالياً.")

    finally:
        await waiting_msg.delete()

def main():
    # بناء التطبيق
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_to_speech_handler))

    print("🎙️ البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()

