import asyncio
import random
import logging
import io
from datetime import datetime
from google import genai
from google.genai import types
from aiogram import Bot, Dispatcher, types as tg_types, F
from aiogram.types import Message, ContentType
from aiogram.utils.chat_action import ChatActionSender
from aiogram.filters import Command

# --- НАСТРОЙКИ ---
TG_TOKEN = "8676041970:AAHPOMxD96-VsEvXWr-HB5tY_iWEbbEp0nE"
NEW_API_KEY = "sk-REl1PPrPA0NMfYUvwFajyA"
BOT_USERNAME = "@Jirosik_bot"

# ID администраторов (добавь свой Telegram user_id)
ADMIN_IDS = {1821268346}  # <-- замени на свой реальный Telegram ID

client = genai.Client(
    api_key=NEW_API_KEY,
    http_options=types.HttpOptions(base_url='https://api.artemox.com')
)

MODEL_ID = "gemini-2.0-flash-lite"
NAMES_LIST = ["жиросик", "жиробас", "жирный"]
TEXT_REPLY_CHANCE = 0.05
PHOTO_REPLY_CHANCE = 0.1
MAX_MEMORY = 15

# {chat_id: [...messages]}, {chat_id: {user_id: username}}, {chat_id: chat_title}
chat_memories = {}
active_users_by_chat = {}
known_chats = {}  # chat_id -> {"title": str, "type": str, "joined": datetime}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TG_TOKEN)
dp = Dispatcher()

# --- СИСТЕМНЫЕ ИНСТРУКЦИИ ---
BASE_PROMPT = (
    "ты жиросик, дерзкий чел. пиши мелкими буквами, без точек. "
    "отвечай коротко. если к тебе обращаются по имени, можешь подстебать. "
    "не будь занудой, общайся как в обычном чате."
)

LORE = (
    "твоя инфа: ты создатель игры 'укради русский мем' в roblox, "
    "ведешь свой тг канал. знаешь родомитса и редгая. НЕ упоминай это просто так."
)

# --- МОЗГИ ---

async def ask_gemini_text(user_name: str, user_text: str, context: list):
    short_term = "\n".join(context[-MAX_MEMORY:])
    full_prompt = (
        f"ИНСТРУКЦИЯ: {BASE_PROMPT}\n"
        f"ТВОЙ ЛОР: {LORE}\n"
        f"Контекст чата:\n{short_term}\n\n"
        f"Сейчас тебе пишет {user_name}: {user_text}\n"
        f"Ответь ему дерзко и коротко."
    )
    try:
        response = await asyncio.to_thread(
            client.models.generate_content, model=MODEL_ID, contents=full_prompt
        )
        return response.text.strip().lower().replace(".", "")
    except Exception as e:
        logging.error(f"ошибка API: {e}")
        return "ошибка при подключении к серверу"


async def ask_gemini_vision(image_data: io.BytesIO, user_name: str, caption: str):
    vision_prompt = (
        f"ты жиросик, поясни {user_name} за эту пикчу дерзко и коротко. "
        f"пиши мелкими буквами без точек. подпись юзера: {caption if caption else 'пусто'}"
    )
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=MODEL_ID,
            contents=[
                vision_prompt,
                types.Part.from_bytes(data=image_data.getvalue(), mime_type="image/jpeg")
            ]
        )
        return response.text.strip().lower().replace(".", "")
    except Exception:
        return "чё это за мазня"


# --- ХЕЛПЕР: проверка на администратора ---
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# --- ХЕНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: Message):
    welcome_text = (
        "привет, я жиросик. добавь меня в чат и дай админку, "
        "буду имбово общаться с вами и наводить веселуху)) XDDD"
    )
    builder = tg_types.InlineKeyboardMarkup(inline_keyboard=[[
        tg_types.InlineKeyboardButton(
            text="➕ Добавить Жиросика в чат",
            url=f"https://t.me/{BOT_USERNAME.replace('@', '')}?startgroup=true"
        )
    ]])
    await message.answer(welcome_text, reply_markup=builder)


# --- ADMIN: список чатов ---
@dp.message(Command("chats"))
async def cmd_chats(message: Message):
    if message.chat.type != "private":
        return
    if not is_admin(message.from_user.id):
        await message.answer("нет доступа")
        return

    if not known_chats:
        await message.answer("жиросик ещё ни в каких чатах не состоит")
        return

    lines = [f"📋 чаты жиросика ({len(known_chats)}):\n"]
    for chat_id, info in known_chats.items():
        title = info.get("title", "без названия")
        chat_type = info.get("type", "?")
        joined = info.get("joined", "?")
        users_count = len(active_users_by_chat.get(chat_id, {}))
        lines.append(
            f"• {title} [{chat_type}]\n"
            f"  id: <code>{chat_id}</code>\n"
            f"  активных юзеров: {users_count}\n"
            f"  добавлен: {joined}"
        )

    await message.answer("\n\n".join(lines), parse_mode="HTML")


# --- ADMIN: рассылка ---
@dp.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if message.chat.type != "private":
        return
    if not is_admin(message.from_user.id):
        await message.answer("нет доступа")
        return

    # Текст после команды
    text = message.text.removeprefix("/broadcast").strip()
    if not text:
        await message.answer(
            "использование: /broadcast текст сообщения\n\n"
            "или ответь на сообщение командой /broadcast чтобы переслать его"
        )
        return

    if not known_chats:
        await message.answer("нет чатов для рассылки")
        return

    success = 0
    failed = 0
    for chat_id in list(known_chats.keys()):
        try:
            await bot.send_message(chat_id, text)
            success += 1
            await asyncio.sleep(0.05)  # небольшая задержка чтобы не флудить
        except Exception as e:
            logging.warning(f"не смог отправить в {chat_id}: {e}")
            failed += 1

    await message.answer(
        f"✅ рассылка завершена\n"
        f"отправлено: {success}\n"
        f"ошибок: {failed}"
    )


# --- ADMIN: переслать сообщение как рассылку ---
@dp.message(Command("broadcast"), F.reply_to_message)
async def cmd_broadcast_reply(message: Message):
    if message.chat.type != "private":
        return
    if not is_admin(message.from_user.id):
        await message.answer("нет доступа")
        return

    if not known_chats:
        await message.answer("нет чатов для рассылки")
        return

    success = 0
    failed = 0
    for chat_id in list(known_chats.keys()):
        try:
            await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=message.chat.id,
                message_id=message.reply_to_message.message_id
            )
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logging.warning(f"не смог переслать в {chat_id}: {e}")
            failed += 1

    await message.answer(
        f"✅ рассылка завершена\n"
        f"отправлено: {success}\n"
        f"ошибок: {failed}"
    )


# --- ОТСЛЕЖИВАНИЕ: бот добавлен/удалён из чата ---
@dp.my_chat_member()
async def on_my_chat_member(event: tg_types.ChatMemberUpdated):
    chat = event.chat
    new_status = event.new_chat_member.status

    if new_status in ("member", "administrator"):
        # Бота добавили в чат
        known_chats[chat.id] = {
            "title": chat.title or chat.username or str(chat.id),
            "type": chat.type,
            "joined": datetime.now().strftime("%d.%m.%Y %H:%M")
        }
        logging.info(f"добавлен в чат: {chat.title} ({chat.id})")

    elif new_status in ("left", "kicked", "banned"):
        # Бота удалили или кикнули
        known_chats.pop(chat.id, None)
        chat_memories.pop(chat.id, None)
        active_users_by_chat.pop(chat.id, None)
        logging.info(f"удалён из чата: {chat.title} ({chat.id})")


# --- ХЕНДЛЕР: фото ---
@dp.message(F.photo)
async def handle_photo(message: Message):
    # Регистрируем чат если ещё не знаем о нём
    _register_chat(message)

    user_name = message.from_user.first_name
    if random.random() < PHOTO_REPLY_CHANCE:
        async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
            photo = message.photo[-1]
            file_in_memory = io.BytesIO()
            await bot.download(photo, destination=file_in_memory)
            file_in_memory.seek(0)

            reply = await ask_gemini_vision(file_in_memory, user_name, message.caption)
            if reply:
                await message.reply(reply)


# --- ХЕНДЛЕР: текст ---
@dp.message(F.text)
async def handle_text(message: Message):
    if message.text.startswith("/"):
        return

    # Регистрируем чат если ещё не знаем о нём
    _register_chat(message)

    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name

    if chat_id not in active_users_by_chat:
        active_users_by_chat[chat_id] = {}
    if chat_id not in chat_memories:
        chat_memories[chat_id] = []

    active_users_by_chat[chat_id][user_id] = user_name

    text_lower = message.text.lower()
    is_named = any(name in text_lower for name in NAMES_LIST)

    # --- ЛОГИКА "КТО [ЧТО-ТО]" ---
    if "кто" in text_lower and (is_named or message.chat.type == "private" or random.random() < 0.3):
        phrase = text_lower
        for name in NAMES_LIST:
            phrase = phrase.replace(name, "")
        phrase = phrase.replace("кто", "").strip().replace("?", "")

        current_chat_users = active_users_by_chat[chat_id]
        if phrase and current_chat_users:
            random_user = random.choice(list(current_chat_users.values()))
            await message.reply(f"кажись {random_user} {phrase}")
            return

    chat_memories[chat_id].append(f"{user_name}: {message.text}")
    if len(chat_memories[chat_id]) > MAX_MEMORY:
        chat_memories[chat_id].pop(0)

    # Реакции
    trigger_words = {"база": "🔥", "кринж": "🤮", "пон": "👍", "жиза": "💯"}
    for word, emo in trigger_words.items():
        if word in text_lower:
            try:
                await message.react([tg_types.ReactionTypeEmoji(emoji=emo)])
            except Exception:
                pass
            break

    is_pinged = BOT_USERNAME.lower() in text_lower or (
        message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    )

    if is_pinged or is_named or random.random() < TEXT_REPLY_CHANCE:
        async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
            await asyncio.sleep(random.uniform(0.2, 0.5))
            reply = await ask_gemini_text(user_name, message.text, chat_memories[chat_id])
            if reply:
                await message.reply(reply)


# --- ХЕЛПЕР: регистрация чата при первом сообщении ---
def _register_chat(message: Message):
    chat = message.chat
    if chat.id not in known_chats and chat.type != "private":
        known_chats[chat.id] = {
            "title": chat.title or chat.username or str(chat.id),
            "type": chat.type,
            "joined": datetime.now().strftime("%d.%m.%Y %H:%M")
        }


# --- СТАРТ ---
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("--- Жиросик запущен ---")
    print(f"Admins: {ADMIN_IDS}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Жиросик ушел спать")
