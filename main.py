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
TG_TOKEN = "8676041970:AAGAwzt04pKwPL7CNmxT7wJqo-9rn4_5CnE"
NEW_API_KEY = "sk-REl1PPrPA0NMfYUvwFajyA"
BOT_USERNAME = "@Jirosik_bot" 

client = genai.Client(
    api_key=NEW_API_KEY,
    http_options=types.HttpOptions(base_url='https://api.artemox.com')
)

MODEL_ID = "gemini-2.0-flash-lite"
NAMES_LIST = ["жиросик", "жиробас", "жирный"] # Добавляй сколько хочешь
TEXT_REPLY_CHANCE = 0.1
PHOTO_REPLY_CHANCE = 0.2
MAX_MEMORY = 15
chat_memory = []

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

@dp.message(F.photo)
async def handle_photo(message: Message):
    chat_name = message.chat.title or "Личка"
    user_name = message.from_user.first_name
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{chat_name}] {user_name} скинул фото. смотрю...")
    
    if random.random() < PHOTO_REPLY_CHANCE:
        async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
            photo = message.photo[-1]
            file_in_memory = io.BytesIO()
            await bot.download(photo, destination=file_in_memory)
            file_in_memory.seek(0)
            
            reply = await ask_gemini_vision(file_in_memory, user_name, message.caption)
            if reply:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [ОТВЕТ] {reply}")
                await message.reply(reply)

@dp.message(F.text)
async def handle_text(message: Message):
    if message.text.startswith("/"): return
    
    chat_name = message.chat.title or "Личка"
    user_name = message.from_user.first_name
    text_lower = message.text.lower()
    
    # 1. Информативный лог в консоль
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{chat_name}] {user_name}: {message.text[:50]}...")

    # Запоминаем в память
    chat_memory.append(f"{user_name}: {message.text}")
    if len(chat_memory) > MAX_MEMORY: chat_memory.pop(0)

    # 2. Умные реакции
    trigger_words = {"база": "🔥", "кринж": "🤮", "пон": "👍", "жиза": "💯"}
    for word, emo in trigger_words.items():
        if word in text_lower:
            await message.react([tg_types.ReactionTypeEmoji(emoji=emo)])
            break

    # 3. Условия ответа (Пинг, Имя или Рандом)
    is_pinged = BOT_USERNAME.lower() in text_lower or (message.reply_to_message and message.reply_to_message.from_user.id == bot.id)
    is_named = any(name in text_lower for name in NAMES_LIST)
    
    if is_pinged or is_named or random.random() < TEXT_REPLY_CHANCE:
        if is_pinged:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [ПИНГ] Отвечаю на упоминание...")
        
        async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
            await asyncio.sleep(random.uniform(0.2, 0.5))
            reply = await ask_gemini_text(user_name, message.text, chat_memory)
            if reply:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [ОТВЕТ] {reply}")
                await message.reply(reply)

# --- СТАРТ ---
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("--- Жиросик (PRO Edition) запущен и всё видит ---")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Жиросик ушел спать")
