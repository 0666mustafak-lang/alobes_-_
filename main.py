import os
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PasswordHashInvalid
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# إعدادات من ريلواي (تأكد من إضافتها في قسم Variables)
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# التحقق من وجود المتغيرات
if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("يجب إضافة API_ID و API_HASH و BOT_TOKEN في متغيرات بيئة ريلواي!")

bot = Client("bot_session", api_id=int(API_ID), api_hash=API_HASH, bot_token=BOT_TOKEN)

# مخزن مؤقت لبيانات الجلسات
user_data = {}

@bot.on_message(filters.command("start") & filters.private)
async def start(client, message):
    user_id = message.from_user.id
    # إنهاء أي جلسة قديمة لنفس المستخدم
    if user_id in user_data and "user_client" in user_data[user_id]:
        try:
            await user_data[user_id]["user_client"].log_out()
        except:
            pass
    
    user_data[user_id] = {"step": "phone"}
    await message.reply("📟 **مرحباً بك في بوت التنظيف الشامل**\n\nأرسل الآن رقم هاتف الحساب:\nمثال: `+9647xxxxxxx`")

@bot.on_message(filters.private & filters.text & ~filters.command("start"))
async def handle_logic(client, message: Message):
    user_id = message.from_user.id
    text = message.text.strip()

    if user_id not in user_data:
        return

    step = user_data[user_id].get("step")

    # 1. مرحلة رقم الهاتف
    if step == "phone":
        temp_client = Client(f"user_{user_id}", api_id=int(API_ID), api_hash=API_HASH)
        await temp_client.connect()
        try:
            code_hash = await temp_client.send_code(text.replace(" ", ""))
            user_data[user_id].update({
                "phone": text,
                "code_hash": code_hash.phone_code_hash,
                "user_client": temp_client,
                "step": "code"
            })
            await message.reply("🔐 **أرسل كود التحقق الآن:**")
        except Exception as e:
            await message.reply(f"❌ خطأ: {e}")

    # 2. مرحلة الكود
    elif step == "code":
        temp_client = user_data[user_id]["user_client"]
        try:
            await temp_client.sign_in(user_data[user_id]["phone"], user_data[user_id]["code_hash"], text)
            await show_admin_chats(client, message, temp_client)
        except SessionPasswordNeeded:
            user_data[user_id]["step"] = "2fa"
            await message.reply("🔐 **الحساب محمي بكلمة سر (2FA)، أرسلها الآن:**")
        except Exception as e:
            await message.reply(f"❌ خطأ في الكود: {e}")

    # 3. مرحلة كلمة السر (اختياري)
    elif step == "2fa":
        temp_client = user_data[user_id]["user_client"]
        try:
            await temp_client.check_password(text)
            await show_admin_chats(client, message, temp_client)
        except Exception:
            await message.reply("❌ كلمة السر خاطئة، حاول مجدداً:")

# دالة عرض القنوات والمجموعات التي يشرف عليها الحساب
async def show_admin_chats(bot_client, message, user_client):
    user_id = message.from_user.id
    buttons = []
    load_msg = await message.reply("🔍 **جاري فحص المجموعات التي تشرف عليها...**")

    async for dialog in user_client.get_dialogs(limit=50):
        if dialog.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP, enums.ChatType.CHANNEL]:
            try:
                member = await user_client.get_chat_member(dialog.chat.id, "me")
                if member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                    buttons.append([InlineKeyboardButton(f"🧹 {dialog.chat.title}", callback_data=f"clean_{dialog.chat.id}")])
            except:
                continue

    if buttons:
        await load_msg.edit("✅ **تم العثور على المجموعات.**\nاختر الواحدة التي تريد تنظيفها:", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await load_msg.edit("❌ لم أجد مجموعات أنت مشرف فيها بصلاحيات الحظر.")
        await user_client.log_out()

# مرحلة التنفيذ عند الضغط على الزر
@bot.on_callback_query(filters.regex("^clean_"))
async def start_cleaning(client: Client, callback_query: CallbackQuery):
    chat_id = int(callback_query.data.split("_")[1])
    user_id = callback_query.from_user.id
    
    if user_id not in user_data:
        return await callback_query.answer("⚠️ انتهت الجلسة، ابدأ من جديد.", show_alert=True)
        
    temp_client = user_data[user_id]["user_client"]
    await callback_query.answer("🚀 بدأ التنظيف الشامل...")

    status_msg = await callback_query.edit_message_text(
        "🔄 **جاري بدء العمل...**\n"
        "🧹 المرحلة الأولى: تنظيف رسائل الخدمة (انضمام/مغادرة)..."
    )

    try:
        # 1. تنظيف رسائل الخدمة (آخر 500 رسالة)
        s_count = 0
        async for message in temp_client.get_chat_history(chat_id, limit=500):
            if message.service:
                try:
                    await message.delete()
                    s_count += 1
                except: continue

        # 2. طرد الأعضاء مع تحديث الرسالة
        b_count = 0
        async for member in temp_client.get_chat_members(chat_id):
            if member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                try:
                    await temp_client.ban_chat_member(chat_id, member.user.id)
                    b_count += 1
                    
                    if b_count % 5 == 0:  # تحديث كل 5 عمليات
                        await status_msg.edit(
                            f"📊 **تقرير مباشر للعملية:**\n\n"
                            f"👤 الأعضاء المطرودين: `{b_count}`\n"
                            f"🗑 رسائل الخدمة المحذوفة: `{s_count}`\n"
                            f"🛡 **المحتوى (الصور/الفيديو) في أمان.**\n"
                            f"⏳ تأخير: 2 ثانية لتجنب الحظر..."
                        )
                    await asyncio.sleep(2)
                except Exception: continue
        
        await status_msg.edit(
            f"✅ **اكتمل التنظيف بنجاح!**\n\n"
            f"👤 إجمالي المطرودين: `{b_count}`\n"
            f"🗑 إجمالي رسائل الخدمة: `{s_count}`\n"
            f"👋 تم تسجيل الخروج من الحساب."
        )
    
    except Exception as e:
        await status_msg.edit(f"❌ حدث خطأ: {e}")

    # تسجيل الخروج النهائي
    try: await temp_client.log_out()
    except: pass
    if user_id in user_data: del user_data[user_id]

print("✅ Bot is running...")
bot.run()
