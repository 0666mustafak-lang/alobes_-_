import os, json, random, asyncio, time
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from instagrapi import Client
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# الإعدادات الأساسية من ريلواي
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# الهاشتاقات الثابتة للتمويه (تمت إعادتها بالكامل كما طلبت)
GULF_TAGS = ["#الرياض", "#الطائف", "#جدة", "#القصيم", "#ورعان", "#حلوين", "#داعمين_المواهب", "#السعودية", "#الكويت", "#الإمارات"]

# مراحل الحوار (States)
TG_PHONE, TG_CODE, TG_PASS, IG_USER, IG_PASS, IG_2FA, RUN_URL, RUN_COMMENT = range(8)

# --- محرك العمليات (انستقرام) ---
def run_insta_tasks(url, my_comment):
    all_sessions = {k: v for k, v in os.environ.items() if k.startswith('ACC')}
    if not all_sessions:
        return "⚠️ لم يتم العثور على حسابات (ACC) في ريلواي."

    active_accounts = []
    results = []

    # الخطوة 1: فحص الحسابات قبل التنفيذ
    for name, s_json in all_sessions.items():
        try:
            cl = Client()
            cl.set_settings(json.loads(s_json))
            active_accounts.append((name, cl))
        except:
            results.append(f"❌ {name}: الجلسة منتهية")

    if not active_accounts:
        return "❌ كل الحسابات المضافة متعطلة حالياً."

    # الخطوة 2: التنفيذ على الحسابات الشغالة
    status_msg = f"🔍 فحص: {len(active_accounts)} حساب جاهز.\n"
    
    for name, cl in active_accounts:
        try:
            media_id = cl.media_id(cl.media_pk_from_url(url))
            cl.media_like(media_id)  # لايك
            cl.media_save(media_id)  # حفظ
            
            final_text = f"{my_comment} {random.choice(GULF_TAGS)}"
            cl.media_comment(media_id, final_text) # تعليقك + هاشتاق عشوائي
            
            results.append(f"✅ {name}: تم التفاعل")
            time.sleep(random.randint(20, 40)) # فاصل أمان
        except Exception as e:
            results.append(f"⚠️ {name}: خطأ ({str(e)[:15]})")

    return status_msg + "\n".join(results)

# --- واجهة البوت ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🔹 سيشن تليجرام", callback_data='t'), 
            InlineKeyboardButton("🔸 سيشن انستا", callback_data='i')],
          [InlineKeyboardButton("🚀 تشغيل المهام", callback_data='r')]]
    await update.message.reply_text("مرحباً بك في لوحة تحكم ريلواي 24 ساعة.\nاختر القسم المطلوب:", reply_markup=InlineKeyboardMarkup(kb))

# --- قسم تليجرام ---
async def tg_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("📱 أرسل رقم التليجرام (+964...):")
    return TG_PHONE

async def tg_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p'] = update.message.text
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    context.user_data['cl'] = client
    try:
        sent = await client.send_code_request(context.user_data['p'])
        context.user_data['h'] = sent.phone_code_hash
        await update.message.reply_text("🔢 أرسل الكود:")
        return TG_CODE
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")
        return ConversationHandler.END

async def tg_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client = context.user_data['cl']
    try:
        await client.sign_in(context.user_data['p'], update.message.text, phone_code_hash=context.user_data['h'])
        await update.message.reply_text(f"✅ سيشن تليجرام (انسخه):\n\n`{client.session.save()}`", parse_mode='Markdown')
        await client.disconnect()
        return ConversationHandler.END
    except SessionPasswordNeededError:
        await update.message.reply_text("🔐 الحساب محمي، أرسل كلمة السر (Cloud Password):")
        return TG_PASS

async def tg_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client = context.user_data['cl']
    try:
        await client.sign_in(password=update.message.text)
        await update.message.reply_text(f"✅ سيشن تليجرام:\n\n`{client.session.save()}`", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في كلمة السر: {e}")
    await client.disconnect()
    return ConversationHandler.END

# --- قسم انستا ---
async def ig_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("👤 أرسل يوزر انستقرام:")
    return IG_USER

async def ig_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ig_u'] = update.message.text
    await update.message.reply_text("🔑 أرسل كلمة السر:")
    return IG_PASS

async def ig_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ig_p'] = update.message.text
    await update.message.reply_text("🛡️ أرسل كود الأمان/2FA أو 'تخطى':")
    return IG_2FA

async def ig_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cl = Client()
    code = update.message.text
    try:
        if code == "تخطى": 
            cl.login(context.user_data['ig_u'], context.user_data['ig_p'])
        else: 
            cl.login(context.user_data['ig_u'], context.user_data['ig_p'], verification_code=code)
        await update.message.reply_text(f"✅ سيشن انستا (انسخه):\n\n`{json.dumps(cl.get_settings())}`", parse_mode='Markdown')
    except Exception as e: 
        await update.message.reply_text(f"❌ فشل: {e}")
    return ConversationHandler.END

# --- قسم المهام ---
async def run_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("🔗 أرسل رابط المنشور:")
    return RUN_URL

async def get_run_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['url'] = update.message.text
    await update.message.reply_text("✍️ أرسل نص التعليق الذي تريده:")
    return RUN_COMMENT

async def get_run_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ جاري فحص الحسابات والبدء...")
    # تشغيل في Thread منفصل لعدم تجميد البوت
    report = await asyncio.to_thread(run_insta_tasks, context.user_data['url'], update.message.text)
    await msg.edit_text(f"📊 تقرير العمليات:\n{report}")
    return ConversationHandler.END

# --- التشغيل ---
def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN is missing!")
        return

    app = Application.builder().token(BOT_TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(tg_start, pattern='t'), 
            CallbackQueryHandler(ig_start, pattern='i'),
            CallbackQueryHandler(run_start, pattern='r')
        ],
        states={
            TG_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, tg_phone)],
            TG_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, tg_code)],
            TG_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, tg_pass)],
            IG_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ig_user)],
            IG_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ig_pass)],
            IG_2FA: [MessageHandler(filters.TEXT & ~filters.COMMAND, ig_2fa)],
            RUN_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_run_url)],
            RUN_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_run_comment)]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv)
    
    print("🚀 البوت يعمل الآن...")
    app.run_polling()

if __name__ == '__main__':
    main()
