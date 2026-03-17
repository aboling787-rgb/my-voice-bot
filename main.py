import os
import logging
import asyncio
import threading
import random
import requests
import io
import edge_tts
from flask import Flask
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)

# --- الإعدادات ---
TOKEN = "TOKEN"  # ضع التوكن الخاص بك
VOICE_LIST = {
    "ar-sa-hamed": ("ar-SA-HamedNeural", "🔊 سعودي رجالي فخم"),
    "ar-sa-zariyah": ("ar-SA-ZariyahNeural", "🔊 سعودي نسائي واضح"),
    "ar-eg-salma": ("ar-EG-SalmaNeural", "🔊 مصري نسائي"),
    "ar-eg-shakir": ("ar-EG-ShakirNeural", "🔊 مصري رجالي"),
    "en-us-jenny": ("en-US-JennyNeural", "🔊 انجليزي نسائي واقعي"),
    "en-us-guy": ("en-US-GuyNeural", "🔊 انجليزي رجالي طبيعي"),
}
DEFAULT_VOICE_KEY = "ar-sa-hamed"
SUPPORT_CHAT = "https://t.me/your_support_chat"  # ضع رابط الدعم الفني هنا

CHOOSING, TYPING_TEXT, TYPING_IMAGE_PROMPT, CHOOSING_VOICE = range(4)

# --- سيرفر وهمي للإبقاء على الحياة في Render ---
app = Flask('')
@app.route('/')
def home():
    return "Bot is Running!"

def run_flask():
    app.run(host='0.0.0.0', port=os.getenv("PORT", 8080))

def keep_alive():
    threading.Thread(target=run_flask).start()

# حفظ الصوت المختار لكل مستخدم (مؤقت في الذاكرة - يمكن تطويره بقاعدة بيانات)
user_voice_pref = {}

# --- رسائل ثابتة ---
WELCOME_TEXT = (
    "🌟 أهلاً بك في *بوت الذكاء الصوتي والصوري المتكامل*!\n\n"
    "يسعدني تقديم هذه الميزات الاحترافية:\n"
    "1️⃣ تحويل النص العربي أو الإنجليزي إلى صوت طبيعي بأنواع متعددة.\n"
    "2️⃣ توليد صور احترافية من الوصف.\n"
    "3️⃣ اختيار الصوت المفضل.\n"
    "4️⃣ دعم فني مباشر.\n"
    "5️⃣ قائمة أوامر سهلة وسريعة.\n\n"
    "اختر من الأسفل للبدء 👇"
)

ABOUT_TEXT = (
    "🤖 *عن البوت:*\n"
    "- بوت متكامل لتحويل النصوص إلى صوت واقعي بعدة لهجات.\n"
    "- يدعم إنشاء صور بالذكاء الاصطناعي.\n"
    "- يمكنك التواصل مع الدعم الفني لأي استفسار.\n"
    "- الإصدار: 2.0\n"
    "- المطور: @YourUsername"
)

HELP_TEXT = (
    "*كيفية الاستخدام:*\n"
    "1. اضغط على زر (تحويل نص إلى صوت) واكتب النص ثم اختر الصوت المناسب.\n"
    "2. اضغط على زر (توليد صورة) وأرسل وصف الصورة (يفضل باللغة الإنجليزية).\n"
    "3. يمكنك تغيير الصوت المختار من زر (تغيير الصوت).\n"
    "4. استخدم زر (الدعم الفني) للتواصل في حال وجود مشكلة."
)

# --- Bot Main Menu ---
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎙️ تحويل نص إلى صوت", callback_data='tts')],
        [InlineKeyboardButton("🎨 توليد صورة احترافية", callback_data='img')],
        [InlineKeyboardButton("🔄 تغيير الصوت", callback_data='change_voice')],
        [InlineKeyboardButton("ℹ️ معلومات عن البوت", callback_data='about')],
        [InlineKeyboardButton("❓ تعليمات الاستخدام", callback_data='help')],
        [InlineKeyboardButton("🆘 الدعم الفني", url=SUPPORT_CHAT)]
    ])

def voice_menu_keyboard(selected=None):
    rows = []
    for k, (v, desc) in VOICE_LIST.items():
        mark = "✅ " if k==selected else ""
        rows.append([InlineKeyboardButton(f"{mark}{desc}", callback_data=f"setvoice_{k}")])
    rows.append([InlineKeyboardButton("⬅️ عودة", callback_data='back_to_menu')])
    return InlineKeyboardMarkup(rows)

# --- الوظائف ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # إعداد قائمة الأوامر للبوت لتسهيل استخدامها (تظهر في قائمة تيليجرام)
    await context.bot.set_my_commands([
        BotCommand("start", "ابدأ واكتشف ميزات البوت"),
        BotCommand("help", "شرح كيفية استخدام البوت"),
        BotCommand("about", "معلومات عن البوت"),
        BotCommand("voice", "تغيير الصوت"),
        BotCommand("img", "توليد صورة")
    ])
    # ضبط متغير صوت المستخدم
    user_id = update.effective_user.id if update.effective_user else None
    if user_id and user_id not in user_voice_pref:
        user_voice_pref[user_id] = DEFAULT_VOICE_KEY
    # رسالة رئيسية
    if update.message:
        await update.message.reply_text(WELCOME_TEXT, reply_markup=main_menu_keyboard(), parse_mode='Markdown')
    else:
        await update.callback_query.message.edit_text(WELCOME_TEXT, reply_markup=main_menu_keyboard(), parse_mode='Markdown')
    return CHOOSING

async def tts_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.edit_text(
        "✍️ *أرسل النص الذي تريد تحويله لصوت...*\n"
        "_يمكنك استخدام العربية أو الإنجليزية._",
        parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ عودة", callback_data='back_to_menu')],
        ])
    )
    return TYPING_TEXT

async def img_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.edit_text(
        "🖼️ *أرسل وصف الصورة التي تريد إنشاءها:*\n"
        "_يفضل إرسال الوصف بالإنجليزية للحصول على جودة عالية._",
        parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ عودة", callback_data='back_to_menu')],
        ])
    )
    return TYPING_IMAGE_PROMPT

async def show_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.edit_text(
        ABOUT_TEXT,
        parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ عودة للقائمة", callback_data='back_to_menu')],
        ])
    )

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.edit_text(
        HELP_TEXT,
        parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ عودة للقائمة", callback_data='back_to_menu')],
        ])
    )

async def change_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    user_id = update.effective_user.id
    voice_key = user_voice_pref.get(user_id, DEFAULT_VOICE_KEY)
    await update.callback_query.message.edit_text(
        "🎤 *اختر الصوت المفضل لك:*\n"
        "_يمكنك تعديل الصوت في أي وقت._",
        parse_mode='Markdown', reply_markup=voice_menu_keyboard(voice_key)
    )
    return CHOOSING_VOICE

async def set_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    key = update.callback_query.data.replace("setvoice_", "")
    if key in VOICE_LIST:
        user_voice_pref[user_id] = key
        desc = VOICE_LIST[key][1]
        await update.callback_query.answer(f"تم اختيار: {desc}")
        await update.callback_query.message.edit_text(
            f"✅ *تم اختيار الصوت:* {desc}\n\n"
            "يمكنك الآن استخدام ميزة النص إلى صوت بهذا الصوت.",
            parse_mode='Markdown', reply_markup=main_menu_keyboard()
        )
        return CHOOSING
    else:
        await update.callback_query.answer("لم يتم العثور على هذا الصوت.")
        return CHOOSING_VOICE

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.edit_text(WELCOME_TEXT,
        reply_markup=main_menu_keyboard(),
        parse_mode='Markdown'
    )
    return CHOOSING

async def handle_tts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    voice_key = user_voice_pref.get(user_id, DEFAULT_VOICE_KEY)
    voice, voicename = VOICE_LIST[voice_key]
    msg = await update.message.reply_text("⏳ جاري توليد الصوت...")
    file_path = f"voice_{user_id}.mp3"
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(file_path)
        with open(file_path, 'rb') as audio:
            await update.message.reply_audio(
                audio=audio,
                caption=f"🎧 صوت ({voicename})\n\n✅ حولت نصك بنجاح!",
                reply_markup=InlineKeyboardMarkup([
                   [InlineKeyboardButton("⬅️ عودة للقائمة", callback_data='back_to_menu')]
                ])
            )
        os.remove(file_path)
    except Exception as e:
        await update.message.reply_text(
            f"❌ حدث خطأ أثناء تحويل النص إلى صوت:\n`{e}`",
            parse_mode='Markdown'
        )
    finally:
        await msg.delete()
    return CHOOSING

async def handle_img(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text
    msg = await update.message.reply_text("🎨 جاري رسم الصورة... الرجاء الانتظار.")
    try:
        seed = random.randint(1, 999999)
        url = (
            f"https://pollinations.ai/p/{requests.utils.quote(prompt)}"
            f"?width=1024&height=1024&seed={seed}&model=flux&nologo=true"
        )
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            await update.message.reply_photo(
                photo=io.BytesIO(response.content),
                caption=f"✨ نتيجة الوصف: {prompt}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ عودة للقائمة", callback_data='back_to_menu')]
                ])
            )
        else:
            await update.message.reply_text("❌ لم تتمكن خدمة توليد ال��ور من الاستجابة، حاول لاحقاً.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ خطأ في الاتصال:\n`{e}`", parse_mode='Markdown')
    finally:
        await msg.delete()
    return CHOOSING

# --- main ---
def main():
    keep_alive()
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("help", lambda u,c: start(u,c)),
            CommandHandler("about", lambda u,c: start(u,c)),
            CommandHandler("voice", change_voice),
            CommandHandler("img", img_request),
        ],
        states={
            CHOOSING: [
                CallbackQueryHandler(tts_request, pattern='^tts$'),
                CallbackQueryHandler(img_request, pattern='^img$'),
                CallbackQueryHandler(change_voice, pattern='^change_voice$'),
                CallbackQueryHandler(show_about, pattern='^about$'),
                CallbackQueryHandler(show_help, pattern='^help$'),
                CallbackQueryHandler(back_to_menu, pattern='^back_to_menu$'),
            ],
            TYPING_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_tts),
                CallbackQueryHandler(back_to_menu, pattern='^back_to_menu$'),
            ],
            TYPING_IMAGE_PROMPT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_img),
                CallbackQueryHandler(back_to_menu, pattern='^back_to_menu$'),
            ],
            CHOOSING_VOICE: [
                CallbackQueryHandler(set_voice, pattern='^setvoice_'),
                CallbackQueryHandler(back_to_menu, pattern='^back_to_menu$'),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(filters.COMMAND, start),
        ]
    )

    application.add_handler(conv_handler)
    print("🚀 البوت الاحترافي الآن يعمل على Render ...")
    application.run_polling()

if __name__ == "__main__":
    main()
