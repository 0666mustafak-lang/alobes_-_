import os
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PasswordHashInvalid
from pyrogram.types import Message

# قراءة البيانات من متغيرات البيئة (Variables) في ريلواي
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# تحويل API_ID إلى رقم وتأكيد وجود القيم
if not API_ID or not API_HASH or not BOT_TOKEN:
    raise ValueError("تأكد من إضافة API_ID و API_HASH و BOT_TOKEN في إعدادات Variables في ريلواي")

API_ID = int(API_ID)

bot = Client("bot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# مخزن مؤقت لبيانات الجلسات
user_data = {}

@bot.on_message(filters.command("start") & filters.private)
async def start(client, message):
    user_id = message.from_user.id
    # إنهاء الجلسة القديمة إن وجدت
    if user_id in user_data and "user_client" in user_data[user_id]:
        try:
            await user_data[user_id]["user_client"].log_out()
        except:
            pass
    
    user_data[user_id] = {"step": "phone"}
    await message.reply("مرحباً! أرسل الآن رقم الهاتف بصيغة: \n`+9647xxxxxxx`")

@bot.on_message(filters.private & filters.text & ~filters.command("start"))
async def handle_logic(client, message: Message):
    user_id = message.from_user.id
    text = message.text

    if user_id not in user_data:
        return

    step = user_data[user_id].get("step")

    # 1. إرسال رقم الهاتف
    if step == "phone":
        phone_number = text.replace(" ", "")
        temp_client = Client(f"user_{user_id}", api_id=API_ID, api_hash=API_HASH)
        await temp_client.connect()
        
        try:
            code_hash = await temp_client.send_code(phone_number)
            user_data[user_id].update({
                "phone": phone_number,
                "code_hash": code_hash.phone_code_hash,
                "user_client": temp_client,
                "step": "code"
            })
            await message.reply("🔐 أرسل كود التحقق الآن:")
        except Exception as e:
            await message.reply(f"❌ خطأ: {e}")

    # 2. إرسال الكود
    elif step == "code":
        temp_client = user_data[user_id]["user_client"]
        try:
            await temp_client.sign_in(
                user_data[user_id]["phone"], 
                user_data[user_id]["code_hash"], 
                text
            )
            user_data[user_id]["step"] = "link"
            await message.reply("✅ تم تسجيل الدخول بنجاح!\nأرسل الآن رابط القناة أو الكروب:")
        except SessionPasswordNeeded:
            user_data[user_id]["step"] = "2fa"
            await message.reply("🔐 الحساب محمي بكلمة سر (2FA)، أرسل كلمة السر:")
        except PhoneCodeInvalid:
            await message.reply("❌ الكود خاطئ، أرسل الكود الصحيح:")
        except Exception as e:
            await message.reply(f"❌ خطأ غير متوقع: {e}")

    # 3. إرسال كلمة السر (اختياري)
    elif step == "2fa":
        temp_client = user_data[user_id]["user_client"]
        try:
            await temp_client.check_password(text)
            user_data[user_id]["step"] = "link"
            await message.reply("✅ تم التحقق من كلمة السر. أرسل الآن رابط القناة أو الكروب:")
        except PasswordHashInvalid:
            await message.reply("❌ كلمة السر خاطئة، حاول مجدداً:")

    # 4. إرسال الرابط والتنفيذ
    elif step == "link":
        chat_link = text.replace("https://t.me/", "")
        temp_client = user_data[user_id]["user_client"]
        msg = await message.reply("⏳ جاري التحقق من الصلاحيات وبدء التنفيذ...")

        try:
            chat = await temp_client.get_chat(chat_link)
            
            # عداد للأعضاء المحذوفين
            count = 0
            async for member in temp_client.get_chat_members(chat.id):
                if member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                    try:
                        await temp_client.ban_chat_member(chat.id, member.user.id)
                        count += 1
                        # تأخير 2 ثانية كما طلبت
                        await asyncio.sleep(2)
                    except Exception:
                        continue
            
            await msg.edit(f"🏁 اكتملت العملية بنجاح.\nتم حذف {count} عضو.\nجاري تسجيل الخروج...")
            
        except Exception as e:
            await msg.edit(f"❌ حدث خطأ أثناء التنفيذ: {e}")
        
        # تسجيل الخروج النهائي وفصل الجلسة
        try:
            await temp_client.log_out()
        except:
            pass
        del user_data[user_id]
        await message.reply("👋 تم تسجيل الخروج بنجاح. البوت جاهز لحساب جديد.")

bot.run()
