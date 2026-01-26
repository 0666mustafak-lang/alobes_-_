import os
from telebot import TeleBot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from instagrapi import Client
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

# --- متغيرات البيئة ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
API_ID = int(os.environ.get("TG_API_ID", "0"))      # API_ID لتلقرام
API_HASH = os.environ.get("TG_API_HASH", "")        # API_HASH لتلقرام

bot = TeleBot(TELEGRAM_TOKEN)

user_states = {}
user_data = {}

# --- /start ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("سيشن إنستجرام"), KeyboardButton("سيشن تلغرام"))
    bot.send_message(message.chat.id, "👋 أهلاً، اختر نوع السيشن الذي تريد استخراجه:", reply_markup=markup)
    user_states[message.chat.id] = "choose_mode"

# --- خيار المستخدم ---
@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'choose_mode')
def choose_mode(message):
    if "إنستجرام" in message.text:
        user_states[message.chat.id] = 'ig_username'
        bot.send_message(message.chat.id, "🟦 أرسل البريد الإلكتروني أو اسم المستخدم لحسابك:")
    elif "تلغرام" in message.text:
        user_states[message.chat.id] = 'tg_phone'
        bot.send_message(message.chat.id, "📱 أرسل رقمك بهيئة دولية (مثال: +9647xxxxxxx):")
    else:
        bot.send_message(message.chat.id, "يرجى اختيار خيار صحيح.")

# --- إنستجرام: اسم المستخدم ---
@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'ig_username')
def handle_ig_username(message):
    user_data[message.chat.id] = {'username': message.text.strip()}
    user_states[message.chat.id] = 'ig_password'
    bot.send_message(message.chat.id, "🔑 أرسل كلمة المرور:")

# --- إنستجرام: كلمة السر ---
@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'ig_password')
def handle_ig_password(message):
    password = message.text.strip()
    username = user_data[message.chat.id]['username']
    bot.send_message(message.chat.id, "⏳ جاري تسجيل الدخول ...")
    try:
        cl = Client()
        cl.login(username, password)
        sessionid = cl.sessionid
        bot.send_message(message.chat.id, f"✅ السيشن (sessionid):\n\n`{sessionid}`", parse_mode="Markdown")
        bot.send_message(
            message.chat.id,
            f"📋 استخدمه بمتغير البيئة بهذا الشكل:\nIG_SESSION_{username.upper()}",
        )
    except Exception as ex:
        bot.send_message(message.chat.id, f"❌ حدث خطأ عند تسجيل الدخول!\n\n{str(ex)}")
    # إعادة لضبط الحالة للاستخراج من جديد
    user_states[message.chat.id] = "choose_mode"
    user_data.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "🔄 لاستخراج سيشن جديد، اختر النوع:")

# --- تلغرام: رقم الهاتف ---
@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'tg_phone')
def handle_tg_phone(message):
    phone = message.text.strip()
    user_data[message.chat.id] = {'tg_phone': phone}
    user_states[message.chat.id] = 'tg_code'
    bot.send_message(message.chat.id, "🔐 أرسل رمز التحقق (الكود):")
    # إنشاء عميل/جلسة جديدة للمستخدم
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    client.connect()
    user_data[message.chat.id]['tg_client'] = client
    try:
        client.send_code_request(phone)
    except Exception as ex:
        user_states[message.chat.id] = "choose_mode"
        bot.send_message(message.chat.id, f"❌ خطأ أثناء إرسال الرمز:\n{str(ex)}")
        return

# --- تلغرام: كود التحقق ---
@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'tg_code')
def handle_tg_code(message):
    code = message.text.strip()
    data = user_data[message.chat.id]
    client = data['tg_client']
    phone = data['tg_phone']
    try:
        client.sign_in(phone=phone, code=code)
        session_text = client.session.save()
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📋 انسخ السيشن", callback_data="copy_session"))
        bot.send_message(
            message.chat.id,
            f"✅ سيشن التلغرام:\n\n`{session_text}`",
            parse_mode="Markdown",
            reply_markup=markup
        )
    except SessionPasswordNeededError:
        user_states[message.chat.id] = "tg_pass"
        bot.send_message(message.chat.id, "🔒 الحساب مفعل عليه 2FA\nأرسل كلمة السر:")
        return
    except Exception as ex:
        bot.send_message(message.chat.id, f"❌ خطأ أثناء تسجيل الدخول:\n{str(ex)}")
    # إعادة لضبط الحالة
    user_states[message.chat.id] = "choose_mode"
    user_data.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "🔄 لاستخراج سيشن جديد، اختر النوع:")

# --- تلغرام: كلمة المرور للحسابات 2FA ---
@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'tg_pass')
def handle_tg_pass(message):
    password = message.text.strip()
    data = user_data[message.chat.id]
    client = data['tg_client']
    try:
        client.sign_in(password=password)
        session_text = client.session.save()
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📋 انسخ السيشن", callback_data="copy_session"))
        bot.send_message(
            message.chat.id,
            f"✅ سيشن التلغرام:\n\n`{session_text}`",
            parse_mode="Markdown",
            reply_markup=markup
        )
    except Exception as ex:
        bot.send_message(message.chat.id, f"❌ كلمة المرور غير صحيحة\n{str(ex)}")
    # إعادة لضبط الحالة
    user_states[message.chat.id] = "choose_mode"
    user_data.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "🔄 لاستخراج سيشن جديد، اختر النوع:")

# --- زر "انسخ السيشن" ---
@bot.callback_query_handler(func=lambda c: c.data == "copy_session")
def copy_session_handler(call):
    bot.answer_callback_query(call.id, "تم النسخ! (انسخه يدوياً إذا لم يظهر زر النسخ)", show_alert=True)
    # لا شيء إضافي لأن تيليجرام نفسه يعرض زر النسخ للصندوق البرمجي

print("Bot started ...")
bot.polling()
