import os
from instagrapi import Client
import telebot

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TELEGRAM_TOKEN)

user_states = {}
user_data = {}

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_states[message.chat.id] = 'awaiting_username'
    bot.send_message(message.chat.id, "مرحباً 👋\nاكتب البريد أو اسم المستخدم لحسابك على إنستجرام:")

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'awaiting_username')
def ask_password(message):
    user_data[message.chat.id] = {'username': message.text.strip()}
    user_states[message.chat.id] = 'awaiting_password'
    bot.send_message(message.chat.id, "الآن ارسل كلمة السر (الرمز السري):")

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == 'awaiting_password')
def extract_session(message):
    password = message.text.strip()
    username = user_data[message.chat.id]['username']
    bot.send_message(message.chat.id, "⏳ جاري تسجيل الدخول واستخراج sessionid ...")
    try:
        cl = Client()
        cl.login(username, password)
        sessionid = cl.sessionid
        # إرسال السيشن في صندوق مخصص للنسخ بضغطة واحدة
        bot.send_message(message.chat.id, f"✅ سيشن الحساب بنجاح:\n\n`{sessionid}`", parse_mode='Markdown')
        bot.send_message(message.chat.id, f"📋 يمكنك وضعه كمتغير بيئة هكذا:\nIG_SESSION_{username.upper()}")
    except Exception as ex:
        bot.send_message(message.chat.id, "❌ حدث خطأ أثناء تسجيل الدخول!\nتأكد من البيانات وجرب مجدداً.")
    # إعادة ضبط الحالة لإتاحة استخراج جديد
    user_states[message.chat.id] = 'awaiting_username'
    user_data.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "🔄 لإستخراج سيشن لحساب آخر، أرسل البريد/يوزر الجديد:")

bot.polling()
