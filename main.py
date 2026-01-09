import asyncio
import os
import re
from telethon import TelegramClient, events, Button
from telethon.errors import SessionPasswordNeededError

# ========== CONFIG ==========
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

AUTH_CODES = {"25864mnb00", "20002000"}
AUTH_FILE = "authorized.txt"

# ========== AUTH STORAGE ==========
def load_authorized():
    if os.path.exists(AUTH_FILE):
        with open(AUTH_FILE, "r") as f:
            return set(map(int, f.read().splitlines()))
    return set()

def save_authorized(uid):
    with open(AUTH_FILE, "a") as f:
        f.write(f"{uid}\n")

AUTHORIZED_USERS = load_authorized()

# ========== BOT ==========
bot = TelegramClient("bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)
state = {}

def clean_caption(txt):
    return re.sub(r'@\w+|https?://\S+', '', txt or '')

# ================= START =================
@bot.on(events.NewMessage(pattern="/start"))
async def start(event):
    uid = event.sender_id

    if uid not in AUTHORIZED_USERS:
        state[uid] = {"step": "auth"}
        await event.respond("🔐 أرسل رمز الدخول")
        return

    state[uid] = {
        "step": "phone",
        "phone": None,
        "phone_code_hash": None,
        "tmp": None,
        "client": None,
        "mode": None,
        "send_mode": None,
        "delay": 10,
        "running": False,
        "sent": 0,
        "total": 0,
        "status": None,
        "link": None
    }
    await event.respond("📱 أرسل رقم الهاتف مع المفتاح الدولي")

# ================= FLOW =================
@bot.on(events.NewMessage)
async def flow(event):
    uid = event.sender_id
    txt = (event.text or "").strip()

    if uid not in state:
        return

    s = state[uid]

    # ===== AUTH =====
    if s["step"] == "auth":
        if txt in AUTH_CODES:
            AUTHORIZED_USERS.add(uid)
            save_authorized(uid)
            await event.respond("✅ تم التحقق، ارسل /start")
            state.pop(uid, None)
        else:
            await event.respond("❌ رمز خطأ")
        return

    # ===== LOGIN =====
    if s["step"] == "phone":
        s["phone"] = txt
        c = TelegramClient(f"s_{uid}", API_ID, API_HASH)
        await c.connect()
        sent = await c.send_code_request(txt)
        s["phone_code_hash"] = sent.phone_code_hash
        s["tmp"] = c
        s["step"] = "code"
        await event.respond("🔑 أرسل كود التحقق")
        return

    if s["step"] == "code":
        try:
            await s["tmp"].sign_in(
                phone=s["phone"],
                code=txt,
                phone_code_hash=s["phone_code_hash"]
            )
        except SessionPasswordNeededError:
            s["step"] = "2fa"
            await event.respond("🔐 أرسل رمز 2FA")
            return

        s["client"] = s["tmp"]
        s["step"] = "mode"
        await choose_mode(event)
        return

    if s["step"] == "2fa":
        await s["tmp"].sign_in(password=txt)
        s["client"] = s["tmp"]
        s["step"] = "mode"
        await choose_mode(event)
        return

    if s["step"] == "delay":
        try:
            s["delay"] = int(txt)
        except:
            await event.respond("⚠️ أرسل رقم صحيح")
            return
        s["step"] = "link"
        await event.respond("🔗 أرسل رابط القناة أو الكروب")
        return

    if s["step"] == "link":
        s["link"] = txt
        s["running"] = True
        s["sent"] = 0
        s["status"] = await event.respond(
            "🚀 بدء العملية...",
            buttons=[[Button.inline("⏸️ إيقاف", b"stop")]]
        )
        asyncio.create_task(run(s))
        return

# ================= MENUS =================
async def choose_mode(event):
    await event.respond(
        "اختر العملية:",
        buttons=[
            [Button.inline("📤 نقل الفيديوهات", b"transfer")],
            [Button.inline("🕵️‍♂️ سرقة", b"steal")]
        ]
    )

async def choose_steal_mode(event):
    await event.respond(
        "اختر طريقة السرقة:",
        buttons=[
            [Button.inline("⚡ fast", b"fast")],
            [Button.inline("📦 all", b"all")],
            [Button.inline("🔓 protected", b"protected")]
        ]
    )

# ================= CALLBACK =================
@bot.on(events.CallbackQuery)
async def cb(event):
    await event.answer()
    uid = event.sender_id
    s = state.get(uid)
    if not s:
        return

    if event.data == b"stop":
        s["running"] = False
        await event.respond("⏹️ تم الإيقاف")
        return

    if event.data == b"transfer":
        s["mode"] = "transfer"
        s["step"] = "delay"
        await event.respond(f"⏱️ التأخير الحالي: {s['delay']} ثانية\nأرسل رقم جديد")
        return

    if event.data == b"steal":
        s["mode"] = "steal"
        await choose_steal_mode(event)
        return

    if event.data in (b"fast", b"all", b"protected"):
        s["send_mode"] = event.data.decode()
        s["step"] = "link"
        await event.respond("🔗 أرسل رابط القناة")
        return

# ================= RUN =================
async def run(s):
    c = s["client"]

    # ===== STEAL =====
    if s["mode"] == "steal":
        src = await c.get_entity(s["link"])
        dst = await c.get_entity("me")

        videos = [m async for m in c.iter_messages(src) if m.video]
        s["total"] = len(videos)

        batch = []
        for m in videos:
            if not s["running"]:
                break

            if s["send_mode"] == "protected":
                path = await c.download_media(m.video)
                batch.append(path)
            else:
                batch.append(m.video)

            if len(batch) == 10:
                await c.send_file(dst, batch)
                if s["send_mode"] == "protected":
                    for f in batch:
                        os.remove(f)
                s["sent"] += len(batch)
                batch.clear()

            await s["status"].edit(
                f"📊 التقدم\n🎞️ {s['sent']} / {s['total']}",
                buttons=[[Button.inline("⏸️ إيقاف", b"stop")]]
            )

    # ===== TRANSFER =====
    else:
        src = await c.get_entity("me")
        dst = await c.get_entity(s["link"])

        msgs = [m async for m in c.iter_messages(src) if m.video]
        s["total"] = len(msgs)

        for m in msgs:
            if not s["running"]:
                break

            await c.send_file(dst, m.video, caption=clean_caption(m.text))
            s["sent"] += 1

            await s["status"].edit(
                f"📊 التقدم\n🎞️ {s['sent']} / {s['total']}",
                buttons=[[Button.inline("⏸️ إيقاف", b"stop")]]
            )

            await asyncio.sleep(s["delay"])

bot.run_until_disconnected()
