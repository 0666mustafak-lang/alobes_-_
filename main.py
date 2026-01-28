import os
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PasswordHashInvalid
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# إعدادات من ريلواي
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Client("bot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_data = {}

@bot.on_message(filters.command("start") & filters.private)
async def start(client, message):
    user_id = message.from_user.id
    # تنظيف أي جلسة قديمة
    if user_id in user_data and "user_client" in user_data[user_id]:
        try: await user_data[user_id]["user_client"].log_out()
        except: pass
    
    user_data[user_id] = {"step": "phone"}
    await message.reply("مرحباً! أرسل الآن رقم هاتف الحساب:\n`+9647xxxxxxx`")

@bot.on_message(filters.private & filters.text & ~filters.command("start"))
async def handle_logic(client, message: Message):
    user_id = message.from_user.id
    text = message.text

    if user_id not in user_data: return
    step = user_data[user_id].get("step")

    # 1. رقم الهاتف
    if step == "phone":
        temp_client = Client(f"user_{user_id}", api_id=API_ID, api_hash=API_HASH)
        await temp_client.connect()
        try:
            code_hash = await temp_client.send_code(text.replace(" ", ""))
            user_data[user_id].update({"phone": text, "code_hash": code_hash.phone_code_hash, "user_client": temp_client, "step": "code"})
            await message.reply("🔐 أرسل كود التحقق الآن:")
        except Exception as e: await message.reply(f"❌ خطأ: {e}")

    # 2. الكود
    elif step == "code":
        temp_client = user_data[user_id]["user_client"]
        try:
            await temp_client.sign_in(user_data[user_id]["phone"], user_data[user_id]["code_hash"], text)
            await show_admin_chats(client, message, temp_client)
        except SessionPasswordNeeded:
            user_data[user_id]["step"] = "2fa"
            await message.reply("🔐 الحساب محمي بـ 2FA، أرسل كلمة السر:")
        except Exception as e: await message.reply(f"❌ خطأ: {e}")

    # 3. كلمة السر
    elif step == "2fa":
        temp_client = user_data[user_id]["user_client"]
        try:
            await temp_client.check_password(text)
            await show_admin_chats(client, message, temp_client)
        except Exception as e: await message.reply(f"❌ كلمة سر خاطئة.")

# دالة لجلب المجموعات التي يكون فيها الحساب مشرفاً
async def show_admin_chats(bot_client, message, user_client):
    user_id = message.from_user.id
    buttons = []
    msg = await message.reply("🔍 جاري فحص المجموعات التي تشرف عليها...")

    async for dialog in user_client.get_dialogs():
        if dialog.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP, enums.ChatType.CHANNEL]:
            member = await user_client.get_chat_member(dialog.chat.id, "me")
            if member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                buttons.append([InlineKeyboardButton(dialog.chat.title, callback_data=f"clean_{dialog.chat.id}")])

    if buttons:
        await msg.edit("✅ اختر المجموعة أو القناة التي تريد تنظيفها:", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await msg.edit("❌ لم أجد أي مجموعة أنت مشرف فيها.")
        await user_client.log_out()

@bot.on_callback_query(filters.regex("^clean_"))
async def start_cleaning(client: Client, callback_query: CallbackQuery):
    chat_id = int(callback_query.data.split("_")[1])
    user_id = callback_query.from_user.id
    temp_client = user_data[user_id]["user_client"]

    await callback_query.answer("بدء العملية...")
    await callback_query.edit_message_text(f"⏳ جاري حذف الأعضاء من المعرف: {chat_id}...\nسيتم الحذف كل 2 ثانية.")

    count = 0
    try:
        async for member in temp_client.get_chat_members(chat_id):
            if member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                try:
                    await temp_client.ban_chat_member(chat_id, member.user.id)
                    count += 1
                    await asyncio.sleep(2) # التأخير المطلوب
                except Exception: continue
        
        await client.send_message(user_id, f"🏁 تم الانتهاء! تم حذف {count} عضو.\nجاري تسجيل الخروج...")
    except Exception as e:
        await client.send_message(user_id, f"❌ حدث خطأ: {e}")

    await temp_client.log_out()
    if user_id in user_data: del user_data[user_id]

bot.run()
