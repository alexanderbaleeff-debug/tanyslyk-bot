import asyncio
import logging
import os
import random
import re
import json
from pathlib import Path
from typing import Dict, Any, List

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove
)

BOT_TOKEN = "9273627807:AAEmDJd8IgTLcsSZQ1l0RCZbrMsyMo4pVS4"

users: Dict[int, Dict[str, Any]] = {}
likes: Dict[int, set] = {}
matches: Dict[int, set] = {}
current_profile: Dict[int, int] = {}  # кто сейчас смотрит кого

DATA_FILE = Path("users.json")

def load_data():
    global users, likes, matches
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text())
            users = {int(k): v for k, v in data.get("users", {}).items()}
            likes = {int(k): set(v) for k, v in data.get("likes", {}).items()}
            matches = {int(k): set(v) for k, v in data.get("matches", {}).items()}
        except Exception as e:
            print("Load error:", e)

def save_data():
    try:
        data = {
            "users": {str(k): v for k, v in users.items()},
            "likes": {str(k): list(v) for k, v in likes.items()},
            "matches": {str(k): list(v) for k, v in matches.items()},
        }
        DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        print("Save error:", e)

CITY_MAP = {
    "ashgabat": "aşgabat", "ашхабад": "aşgabat",
    "dashoguz": "daşoguz", "дашогуз": "daşoguz",
    "turkmenabat": "türkmenabat", "туркменабат": "türkmenabat",
    "mary": "mary", "мары": "mary",
    "balkanabat": "balkanabat", "балканабат": "balkanabat",
    "turkmenbashi": "türkmenbaşy", "туркменбаши": "türkmenbaşy",
}

def normalize_city(city: str) -> str:
    c = re.sub(r"[^\w\s]", "", city.lower().strip())
    return CITY_MAP.get(c, c)

class Form(StatesGroup):
    lang = State()
    gender = State()
    name = State()
    age = State()
    city = State()
    looking = State()
    about = State()
    photo = State()

def reply_menu(lang: str = "ru"):
    if lang == "ru":
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🚀 Смотреть анкеты")],
                [KeyboardButton(text="1"), KeyboardButton(text="2"), KeyboardButton(text="3"), KeyboardButton(text="4")],
            ],
            resize_keyboard=True,
            one_time_keyboard=False
        )
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Anketalary gör")],
            [KeyboardButton(text="1"), KeyboardButton(text="2"), KeyboardButton(text="3"), KeyboardButton(text="4")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

def reaction_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(text="❤️⭐"),
            KeyboardButton(text="❤️"),
            KeyboardButton(text="✉️"),
            KeyboardButton(text="👎"),
            KeyboardButton(text="💤"),
        ]],
        resize_keyboard=True
    )

def show_menu_text(lang: str = "ru") -> str:
    if lang == "ru":
        return (
            "1. Смотреть анкеты.\n"
            "2. Моя анкета.\n"
            "3. Я больше не хочу никого искать.\n"
            "***\n"
            "4. Активируй Premium — будь в топе ⭐."
        )
    return (
        "1. Anketalary gör.\n"
        "2. Meniň anketam.\n"
        "3. Men indi hiç kimi gözlemeýärin.\n"
        "***\n"
        "4. Premium işjeňleşdir — ýokarda bol ⭐."
    )

router = Router()

@router.message(CommandStart())
@router.message(Command("menu"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    if user_id in users:
        lang = users[user_id].get("lang", "ru")
        await message.answer(show_menu_text(lang), reply_markup=reply_menu(lang))
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇹🇲 Türkmençe", callback_data="lang_tm")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
    ])
    await message.answer("Dil saýla / Выбери язык:", reply_markup=kb)
    await state.set_state(Form.lang)

@router.callback_query(Form.lang, F.data.startswith("lang_"))
async def set_lang(callback: CallbackQuery, state: FSMContext):
    lang = "ru" if callback.data == "lang_ru" else "tm"
    await state.update_data(lang=lang)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Парень / Oglan", callback_data="g_male")],
        [InlineKeyboardButton(text="👩 Девушка / Gyz", callback_data="g_female")],
    ])
    await callback.message.edit_text("Выбери пол / Jynsyňy saýla:", reply_markup=kb)
    await state.set_state(Form.gender)
    await callback.answer()

@router.callback_query(Form.gender, F.data.startswith("g_"))
async def process_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.split("_")[1]
    await state.update_data(gender=gender)
    data = await state.get_data()
    text = "Как тебя зовут?" if data["lang"] == "ru" else "Adyň näme?"
    await callback.message.edit_text(text)
    await state.set_state(Form.name)
    await callback.answer()

@router.message(Form.name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()[:32]
    if len(name) < 2:
        await message.answer("Слишком коротко")
        return
    await state.update_data(name=name)
    data = await state.get_data()
    text = "Сколько тебе лет? (18-60)" if data["lang"] == "ru" else "Näçe ýaşyň? (18-60)"
    await message.answer(text)
    await state.set_state(Form.age)

@router.message(Form.age)
async def process_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Напиши число")
        return
    age = int(message.text)
    if not 18 <= age <= 60:
        await message.answer("От 18 до 60")
        return
    await state.update_data(age=age)
    data = await state.get_data()
    text = "Из какого города?" if data["lang"] == "ru" else "Haýsy şäherden?"
    await message.answer(text)
    await state.set_state(Form.city)

@router.message(Form.city)
async def process_city(message: Message, state: FSMContext):
    city = message.text.strip()[:40]
    await state.update_data(city=city, city_norm=normalize_city(city))
    data = await state.get_data()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Парней", callback_data="l_male")],
        [InlineKeyboardButton(text="👩 Девушек", callback_data="l_female")],
        [InlineKeyboardButton(text="💑 Любой", callback_data="l_any")],
    ])
    text = "Кого ищешь?" if data["lang"] == "ru" else "Kimi gözleýärsiň?"
    await message.answer(text, reply_markup=kb)
    await state.set_state(Form.looking)

@router.callback_query(Form.looking, F.data.startswith("l_"))
async def process_looking(callback: CallbackQuery, state: FSMContext):
    looking = callback.data.split("_")[1]
    await state.update_data(looking=looking)
    data = await state.get_data()
    text = "Расскажи о себе коротко:" if data["lang"] == "ru" else "Özüň barada gysgaça ýaz:"
    await callback.message.edit_text(text)
    await state.set_state(Form.about)
    await callback.answer()

@router.message(Form.about)
async def process_about(message: Message, state: FSMContext):
    about = message.text.strip()[:350]
    await state.update_data(about=about, photos=[])
    data = await state.get_data()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Готово", callback_data="photos_done")]
    ])
    text = "Отправь 1-3 фото. После последнего нажми «Готово»." if data["lang"] == "ru" else "1-3 surat iber. Soň «Taýýar» bas."
    await message.answer(text, reply_markup=kb)
    await state.set_state(Form.photo)

@router.message(Form.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    if len(photos) >= 3:
        await message.answer("Максимум 3 фото")
        return
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(f"Фото {len(photos)}/3 добавлено")

@router.callback_query(Form.photo, F.data == "photos_done")
async def photos_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    if not photos:
        await callback.answer("Нужно хотя бы одно фото", show_alert=True)
        return

    user_id = callback.from_user.id
    users[user_id] = {
        "id": user_id,
        "name": data["name"],
        "age": data["age"],
        "gender": data["gender"],
        "city": data["city"],
        "city_norm": data.get("city_norm", normalize_city(data["city"])),
        "looking": data["looking"],
        "about": data["about"],
        "photos": photos,
        "lang": data["lang"],
        "premium": False,
    }
    likes.setdefault(user_id, set())
    matches.setdefault(user_id, set())
    save_data()

    await state.clear()
    lang = data["lang"]
    await callback.message.answer("✅ Анкета готова!", reply_markup=reply_menu(lang))
    await callback.message.answer(show_menu_text(lang))
    await callback.answer()

@router.message(Command("browse"))
async def cmd_browse(message: Message):
    await browse_start(message)

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    await show_my_profile(message)

@router.message(Command("premium"))
async def cmd_premium(message: Message):
    await premium(message)
    user_id = message.from_user.id
    if user_id not in users:
        await message.answer("Сначала создай анкету через /start")
        return
    await show_next_profile(message)

async def show_next_profile(message: Message):
    me = users.get(message.from_user.id)
    if not me:
        return
    candidates = []
    for uid, p in users.items():
        if uid == me["id"]:
            continue
        if me["looking"] != "any" and p["gender"] != me["looking"]:
            continue
        if me["id"] in likes.get(uid, set()):
            continue
        candidates.append(p)
    if not candidates:
        lang = me.get("lang", "ru")
        text = "Пока новых анкет нет 😔" if lang == "ru" else "Häzirlikçe täze anketa ýok 😔"
        await message.answer(text, reply_markup=reply_menu(lang))
        return
    profile = random.choice(candidates)
    current_profile[message.from_user.id] = profile["id"]
    caption = f"<b>{profile['name']}, {profile['age']}</b>\n📍 {profile['city']}\n\n{profile['about']}"
    await message.answer_photo(profile["photos"][0], caption=caption, parse_mode="HTML", reply_markup=reaction_keyboard())

@router.message(F.text.in_({"❤️", "❤️⭐"}))
async def do_like(message: Message):
    my_id = message.from_user.id
    target_id = current_profile.get(my_id)
    if not target_id or target_id not in users:
        await message.answer("Сначала открой анкету")
        return
    likes.setdefault(my_id, set()).add(target_id)
    save_data()
    me = users[my_id]
    try:
        await message.bot.send_message(
            target_id,
            f"❤️ Тебя лайкнул: {me['name']}, {me['age']} ({me['city']})"
        )
    except Exception:
        pass
    if my_id in likes.get(target_id, set()):
        await message.answer("🔥 Взаимный лайк!")
    else:
        await message.answer("Лайк отправлен ❤️")
    await show_next_profile(message)

@router.message(F.text == "👎")
async def do_dislike(message: Message):
    await show_next_profile(message)

@router.message(F.text == "💤")
async def do_sleep(message: Message):
    me = users.get(message.from_user.id, {})
    lang = me.get("lang", "ru")
    text = "Подождём пока кто-то увидит твою анкету" if lang == "ru" else "Kimdir seniň anketany görýänçä garaşaly"
    await message.answer(text, reply_markup=reply_menu(lang))

@router.message(F.text == "2")
async def show_my_profile(message: Message):
    user = users.get(message.from_user.id)
    if not user:
        await message.answer("Анкета не найдена")
        return
    caption = f"<b>{user['name']}, {user['age']}</b>\n📍 {user['city']}\n\n{user['about']}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить анкету", callback_data="edit_profile")],
        [InlineKeyboardButton(text="🗑 Удалить анкету", callback_data="delete_profile")],
    ])
    await message.answer_photo(user["photos"][0], caption=caption, parse_mode="HTML", reply_markup=kb)

@router.message(F.text == "3")
async def delete_me(message: Message):
    user_id = message.from_user.id
    users.pop(user_id, None)
    likes.pop(user_id, None)
    matches.pop(user_id, None)
    save_data()
    await message.answer("Анкета удалена. Напиши /start чтобы создать заново.", reply_markup=ReplyKeyboardRemove())

@router.message(F.text == "4")
async def premium(message: Message):
    await message.answer_invoice(
        title="Premium",
        description="Безлимитные лайки и приоритет",
        payload="premium",
        currency="XTR",
        prices=[LabeledPrice(label="Premium", amount=49)],
    )

@router.callback_query(F.data == "edit_profile")
async def edit_profile(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Заполним анкету заново. Выбери язык:")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇹🇲 Türkmençe", callback_data="lang_tm")],
    ])
    await callback.message.answer("Dil saýla / Выбери язык:", reply_markup=kb)
    await state.set_state(Form.lang)
    await callback.answer()

@router.callback_query(F.data == "delete_profile")
async def delete_profile_cb(callback: CallbackQuery):
    user_id = callback.from_user.id
    users.pop(user_id, None)
    likes.pop(user_id, None)
    matches.pop(user_id, None)
    save_data()
    await callback.message.answer("Анкета удалена. /start — создать заново.", reply_markup=ReplyKeyboardRemove())
    await callback.answer()

@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment(message: Message):
    user_id = message.from_user.id
    if user_id in users:
        users[user_id]["premium"] = True
        save_data()
    lang = users.get(user_id, {}).get("lang", "ru")
    await message.answer("⭐ Premium активирован!", reply_markup=reply_menu(lang))

async def main():
    load_data()
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    try:
        if os.getenv("RENDER_EXTERNAL_URL"):
            WEBHOOK_PATH = "/webhook"
            WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL") + WEBHOOK_PATH
            await bot.set_webhook(WEBHOOK_URL)
            from aiohttp import web
            from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
            app = web.Application()
            SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
            setup_application(app, dp, bot=bot)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
            await site.start()
            print("Webhook started")
            await asyncio.Event().wait()
        else:
            await bot.delete_webhook(drop_pending_updates=True)
            print("Polling...")
            await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
