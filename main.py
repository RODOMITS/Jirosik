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

# --- НАСТРОЙКИ ---
TG_TOKEN = "8676041970:AAHPOMxD96-VsEvXWr-HB5tY_iWEbbEp0nE"
NEW_API_KEY = "sk-REl1PPrPA0NMfYUvwFajyA"
BOT_USERNAME = "@Jirosik_bot" 

client = genai.Client(
    api_key=NEW_API_KEY,
    http_options=types.HttpOptions(base_url='https://api.artemox.com')
)

MODEL_ID = "gemini-2.0-flash-lite"
NAMES_LIST = ["жиросик", "жиробас", "жирный"] 
TEXT_REPLY_CHANCE = 0.05
PHOTO_REPLY_CHANCE = 0.1
MAX_MEMORY = 15

# ИСПРАВЛЕНО: Теперь это словари {chat_id: данные}
chat_memories = {}  
active_users_by_chat = {} 

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
        return "чё-то сервак приуныл"

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

# --- ХЕНДЛЕРЫ ---

@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    welcome_text = (
        "привет, я жиросик. добавь меня в чат и дай админку, "
        "буду имбово общаться с вами и наводить веселуху)) XDDD"
    )
    
    builder = tg_types.InlineKeyboardMarkup(inline_keyboard=[
        [
            tg_types.InlineKeyboardButton(
                text="➕ Добавить Жиросика в чат", 
                url=f"https://t.me/{BOT_USERNAME.replace('@', '')}?startgroup=true"
            )
        ]
    ])
    
    await message.answer(welcome_text, reply_markup=builder)

@dp.message(F.photo)
async def handle_photo(message: Message):
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

@dp.message(F.text)
async def handle_text(message: Message):
    if message.text.startswith("/"): return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    
    # ИСПРАВЛЕНО: Инициализируем данные для конкретного чата
    if chat_id not in active_users_by_chat:
        active_users_by_chat[chat_id] = {}
    if chat_id not in chat_memories:
        chat_memories[chat_id] = []

    # Запоминаем юзера ТОЛЬКО в этом чате
    active_users_by_chat[chat_id][user_id] = user_name

    text_lower = message.text.lower()
    is_named = any(name in text_lower for name in NAMES_LIST)

    # --- ЛОГИКА "КТО [ЧТО-ТО]" ---
    if "кто" in text_lower and (is_named or message.chat.type == "private" or random.random() < 0.3):
        phrase = text_lower
        for name in NAMES_LIST:
            phrase = phrase.replace(name, "")
        phrase = phrase.replace("кто", "").strip().replace("?", "")

        # Берем рандомного юзера ТОЛЬКО из этого чата
        current_chat_users = active_users_by_chat[chat_id]
        if phrase and current_chat_users:
            random_user = random.choice(list(current_chat_users.values()))
            await message.reply(f"кажись {random_user} {phrase}")
            return

    # Запоминаем в память ТОЛЬКО этого чата
    chat_memories[chat_id].append(f"{user_name}: {message.text}")
    if len(chat_memories[chat_id]) > MAX_MEMORY:
        chat_memories[chat_id].pop(0)

    # Реакции
    trigger_words = {"база": "🔥", "кринж": "🤮", "пон": "👍", "жиза": "💯"}
    for word, emo in trigger_words.items():
        if word in text_lower:
            await message.react([tg_types.ReactionTypeEmoji(emoji=emo)])
            break

    # Условия ответа
    is_pinged = BOT_USERNAME.lower() in text_lower or (message.reply_to_message and message.reply_to_message.from_user.id == bot.id)
    
    if is_pinged or is_named or random.random() < TEXT_REPLY_CHANCE:
        async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
            await asyncio.sleep(random.uniform(0.2, 0.5))
            # Отправляем в Gemini контекст ТОЛЬКО этого чата
            reply = await ask_gemini_text(user_name, message.text, chat_memories[chat_id])
            if reply:
                await message.reply(reply)

# --- СТАРТ ---
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("--- Жиросик (PRO Edition) запущен и разделяет чаты ---")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Жиросик ушел спать")
