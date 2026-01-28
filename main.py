import os
import asyncio  # <--- أضف هذا السطر
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

app = Client("deleter_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

TRIGGER_WORD = "مسح"
finished_chats = set()

@app.on_message(filters.command([TRIGGER_WORD], prefixes='') & filters.group)
async def delete_all_members(client: Client, message: Message):
    chat_id = message.chat.id
    if chat_id in finished_chats:
        await message.reply("تم تنفيذ المهمة بالفعل. أزلني أو انقلني لمجموعة جديدة.")
        return

    # حذف جميع الأعضاء (عدا المشرفين وصاحب البوت)
    async for member in app.get_chat_members(chat_id):
        if member.status not in [
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
        ]:
            try:
                await app.kick_chat_member(chat_id, member.user.id)
                await asyncio.sleep(2)  # <--- أضف هذا التأخير بعد كل عملية طرد
            except Exception as e:
                pass

    # حذف كل رسائل الانضمام
    async for msg in app.get_chat_history(chat_id, limit=1000):
        if (
            msg.new_chat_members
            or msg.left_chat_member
            or msg.text == ""
        ):
            try:
                await app.delete_messages(chat_id, msg.id)
            except Exception:
                pass

    await message.reply("تم حذف كل الأعضاء ورسائل الانضمام. يمكنك الآن إزالة البوت أو استخدامه في جروب آخر.")
    finished_chats.add(chat_id)

app.run()
