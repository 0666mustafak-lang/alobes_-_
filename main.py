import os, random, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ConversationHandler,
    MessageHandler, ContextTypes, filters
)
from instagrapi import Client
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import nest_asyncio

nest_asyncio.apply()

GULF_HASHTAGS = [
    "حلوين","ورعان","داعمين المواهب","الامارات","الكويت","الرياض",
    "جدة","قطر","الدوحة","سوالب","ورع"
]

def get_random_gulf_hashtag():
    return "#" + random.choice(GULF_HASHTAGS)

def load_instagram_clients():
    clients = []
    accounts = []
    for i in range(1, 21):
        session = os.getenv(f"INSTAGRAM_SESSION_{i}")
        if session:
            cl = Client()
            try:
                cl.login_by_sessionid(session.split(":")[-1].strip())
                if cl.account_id:
                    accounts.append({"index": i, "username": cl.account_info().username})
                    clients.append(cl)
            except Exception as e:
                accounts.append({"index": i, "username": f"ACCOUNT_{i}", "error": str(e)})
    return clients, accounts

DELAY_SECOND_DEFAULT = 6
(
    FETCH_ACTION, WAIT_LINK, WAIT_COMMENT, WAIT_IG_USER, WAIT_IG_PASS,
    SEL_SESSION_TYPE, WAIT_TG_PHONE, WAIT_TG_CODE, WAIT_TG_PASS
) = range(9)

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    clients, accounts = load_instagram_clients()
    context.bot_data["clients"], context.bot_data["accounts"] = clients, accounts
    active = [a for a in accounts if not a.get("error")]
    inactive = [a for a in accounts if a.get("error")]
    msg = f"🟢 الحسابات الفعّالة: {len(active)}\n🔴 حسابات لا تعمل: {len(inactive)}\n———\n"
    for acc in accounts:
        symbol = "🟢" if not acc.get("error") else "🔴"
        msg += f"{symbol} {acc['username']}\n"
    keyboard = [
        [InlineKeyboardButton("لايك + إكسبلور 🚀", callback_data='like_explore')],
        [InlineKeyboardButton("تعليق ✍️", callback_data='comment')],
        [InlineKeyboardButton("🗝 استخراج جلسة (انستجرام/تليجرام)", callback_data='extract_session')],
    ]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    await update.message.reply_text(
        "حدد التأخير (بالثواني) بين كل إجراء لكل حساب (مثلاً: 6):"
    )
    return FETCH_ACTION

async def set_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        delay = int(update.message.text)
        context.user_data["delay"] = abs(delay)
        await update.message.reply_text("تم تعيين التأخير. اختر العملية من الأزرار 👆")
    except Exception:
        await update.message.reply_text("رجاءً أرسل رقم فقط (عدد ثواني).")

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "like_explore":
        context.user_data["action"] = "like_explore"
        await query.edit_message_text("أرسل رابط منشور إنستجرام:")
        return WAIT_LINK
    elif query.data == "comment":
        context.user_data["action"] = "comment"
        await query.edit_message_text("أرسل رابط منشور إنستجرام:")
        return WAIT_LINK
    elif query.data == "extract_session":
        keyboard = [
            [InlineKeyboardButton("انستجرام", callback_data="extr_ig")],
            [InlineKeyboardButton("تيليجرام", callback_data="extr_tg")]
        ]
        await query.edit_message_text("اختر نوع الجلسة:", reply_markup=InlineKeyboardMarkup(keyboard))
        return SEL_SESSION_TYPE
    else:
        await query.edit_message_text("خيار غير مفهوم 🤔")
        return ConversationHandler.END

async def session_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "extr_ig":
        await query.edit_message_text("أدخل اسم المستخدم في انستجرام:")
        return WAIT_IG_USER
    elif query.data == "extr_tg":
        await query.edit_message_text("أدخل رقم هاتفك على تيليجرام (مع رمز الدولة):")
        return WAIT_TG_PHONE
    else:
        await query.edit_message_text("خيار غير مفهوم.")
        return ConversationHandler.END

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    context.user_data["post_url"] = url
    if context.user_data.get("action") == "comment":
        await update.message.reply_text("اكتب نص التعليق:")
        return WAIT_COMMENT
    else:
        await execute_actions(update, context)
        return ConversationHandler.END

async def handle_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["comment_text"] = update.message.text.strip()
    await execute_actions(update, context)
    return ConversationHandler.END

async def execute_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.get("action")
    url = context.user_data.get("post_url")
    delay = context.user_data.get("delay", DELAY_SECOND_DEFAULT)
    clients = context.bot_data.get("clients", [])
    success, failed = 0, 0
    post_pk = None
    if "instagram.com" in url:
        try:
            post_code = url.rstrip("/").split("/")[-1]
            post_pk = clients[0].media_pk_from_code(post_code)
        except Exception as e:
            await update.message.reply_text(f"❗ رابط غير صالح أو خطأ داخلي: {e}")
            return
    else:
        await update.message.reply_text("❗ الرابط ليس إنستجرام.")
        return

    msg = f"بدء التنفيذ على {len(clients)} حسابات...\n"
    await update.message.reply_text(msg)

    for idx, cl in enumerate(clients):
        try:
            username = cl.account_info().username
            if action == "like_explore":
                cl.media_like(post_pk)
                cl.media_save(post_pk)
                try:
                    following = cl.user_following(cl.user_id)
                    if following:
                        target = random.choice(list(following.keys()))
                        cl.direct_send(text="🔗", user_ids=[target], media_pk=post_pk)
                except: pass
                await update.message.reply_text(
                    f"✅ حساب {username}: تم اللايك + حفظ + مشاركة"
                )
            elif action == "comment":
                core_text = context.user_data.get("comment_text", "")
                comment = f"{core_text} {get_random_gulf_hashtag()}"
                cl.media_comment(post_pk, comment)
                await update.message.reply_text(
                    f"✅ حساب {username}: تم إضافة تعليق:\n{comment}"
                )
            await asyncio.sleep(delay)
            success += 1
        except Exception as e:
            failed += 1
            await update.message.reply_text(f"❌ حساب {idx+1} فشل: {e}")
    await update.message.reply_text(
        f"انتهى التنفيذ.\n💚 تمت بنجاح: {success}\n🛑 فشل: {failed}"
    )

# ---- استخراج sessionid Instagram ----
async def ig_get_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["extract_ig_username"] = update.message.text.strip()
    await update.message.reply_text("أدخل كلمة السر:")
    return WAIT_IG_PASS

async def ig_get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = context.user_data["extract_ig_username"]
    password = update.message.text.strip()
    cl = Client()
    try:
        cl.login(username, password)
        sessionid = cl.get_settings().get("sessionid") or cl.cookie_jar.get("sessionid")
        await update.message.reply_text(
            f"✅ هذا هو الـ sessionid الخاص بك، انسخه كله بين الأقواس:\n\n"
            f"<code>sessionid:{sessionid}</code>",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ في الدخول: {str(e)}")
    return ConversationHandler.END

# ---- استخراج StringSession Telegram ----
async def tg_get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tg_phone"] = update.message.text.strip()
    if not (API_ID and API_HASH):
        await update.message.reply_text("🔴 رجاءً أضِف API_ID وAPI_HASH كمتغيرات بيئة!")
        return ConversationHandler.END
    await update.message.reply_text("سيتم إرسال كود التحقق على تيليجرام. أدخل الكود (مع أو بدون -):")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, get_tg_session, context.user_data["tg_phone"])
    if not result[0]:
        await update.message.reply_text("❌ حدث خطأ أثناء محاولة تسجيل الدخول، تأكد من الرقم وصحة البيانات.")
    else:
        await update.message.reply_text(
            f"<b>StringSession الخاص بك، انسخه كاملاً بين الأقواس:</b>\n\n<code>{result[1]}</code>",
            parse_mode="HTML"
        )
    return ConversationHandler.END

def get_tg_session(phone):
    # sync code: user يدخل الكود بالبروامبت المباشر cli (أسهل وأسرع)
    try:
        with TelegramClient(StringSession(), int(API_ID), API_HASH) as client:
            client.start(phone=phone)
            return True, client.session.save()
    except Exception as e:
        return False, f"{e}"

def main():
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            FETCH_ACTION: [
                CallbackQueryHandler(menu_callback),
                MessageHandler(filters.Regex(r"^\d+$"), set_delay),
            ],
            WAIT_LINK: [
                MessageHandler(filters.Regex(r"^https?://instagram.com"), handle_link)
            ],
            WAIT_COMMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_comment)
            ],
            SEL_SESSION_TYPE: [
                CallbackQueryHandler(session_type_callback),
            ],
            WAIT_IG_USER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ig_get_username)
            ],
            WAIT_IG_PASS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ig_get_password)
            ],
            WAIT_TG_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, tg_get_phone)
            ],
        },
        fallbacks=[],
        allow_reentry=True
    )
    app.add_handler(conv)
    app.run_polling()

if __name__ == "__main__":
    main()
