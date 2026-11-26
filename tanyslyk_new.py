import asyncio
import logging
import os
import random
import re
from typing import Dict, Any, List

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery
)

BOT_TOKEN = "9273627807:AAEmDJd8IgTLcsSZQ1l0RCZbrMsyMo4pVS4"

import json
from pathlib import Path

DATA_FILE = Path("users.json")

def load_data():
    global users, likes, matches
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text())
            users = {int(k): v for k, v in data.get("users", {}).items()}
            likes = {int(k): set(v) for k, v in data.get("likes", {}).items()}
            matches = {int(k): set(v) for k, v in data.get("matches", {}).items()}
        except Exception:
            pass

def save_data():
    data = {
        "users": {str(k): v for k, v in users.items()},
        "likes": {str(k): list(v) for k, v in likes.items()},
        "matches": {str(k): list(v) for k, v in matches.items()},
    }
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

# Нормализация городов (русский ↔ латиница)
CITY_MAP = {
    "ashgabat": "aşgabat", "ашхабад": "aşgabat", "ashabad": "aşgabat",
    "dashoguz": "daşoguz", "дашогуз": "daşoguz", "dashogus": "daşoguz",
    "turkmenabat": "türkmenabat", "туркменабат": "türkmenabat",
    "mary": "mary", "мары": "mary",
    "balkanabat": "balkanabat", "балканабат": "balkanabat",
    "turkmenbashi": "türkmenbaşy", "туркменбаши": "türkmenbaşy",
}

def normalize_city(city: str) -> str:
    c = city.lower().strip()
    c = re.sub(r"[^\w\s]", "", c)
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

TEXTS = {
    "tm": {
        "welcome": "Salam! 👋\n«Tanyşlyk» botuna hoş geldiňiz! ❤️\n\nBaşlamak üçin dil saýla:",
        "gender": "Jynsyňy saýla:",
        "name": "Adyň näme? Ýaz:",
        "age": "Näçe ýaşyň? (18-60)",
        "city": "Haýsy şäherden?",
        "looking": "Kimi gözleýärsiň?",
        "about": "Özüň barada gysgaça ýaz (2-3 setir):",
        "photo": "Suratlaryňy iber (1-3 sany) 📸\nSoňky suraty ibereniňden soň «Taýýar» bas.",
        "ready": "✅ Taýýar",
        "profile_ready": "✅ Anketa taýýar!",
        "menu": "Esasy menýu:",
        "no_profiles": "Häzirlikçe täze anketa ýok 😔",
        "my_profile": "Meniň anketam",
        "edit": "✏️ Anketany üýtget",
        "delete": "🗑 Anketany poz",
        "deleted": "Anketa pozuldy. /start basyp täzeden döredip bilersiň.",
        "browse": "🔥 Anketalary gör",
        "premium": "⭐ Premium",
    },
    "ru": {
        "welcome": "Привет! 👋\nДобро пожаловать в «Tanyşlyk»! ❤️\n\nВыбери язык:",
        "gender": "Выбери пол:",
        "name": "Как тебя зовут?",
        "age": "Сколько тебе лет? (18-60)",
        "city": "Из какого города?",
        "looking": "Кого ищешь?",
        "about": "Расскажи о себе коротко (2-3 строки):",
        "photo": "Отправь фото (1-3 штуки) 📸\nПосле последнего нажми «Готово».",
        "ready": "✅ Готово",
        "profile_ready": "✅ Анкета готова!",
        "menu": "Главное меню:",
        "no_profiles": "Пока новых анкет нет 😔",
        "my_profile": "Моя анкета",
        "edit": "✏️ Изменить анкету",
        "delete": "🗑 Удалить анкету",
        "deleted": "Анкета удалена. Напиши /start чтобы создать заново.",
        "browse": "🔥 Смотреть анкеты",
        "premium": "⭐ Premium",
    }
}

def get_text(lang: str, key: str) -> str:
    return TEXTS.get(lang, TEXTS["tm"]).get(key, key)

def reply_menu(lang: str = "tm"):
    if lang == "ru":
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🚀 Смотреть анкеты")],
                [KeyboardButton(text="1"), KeyboardButton(text="2"), KeyboardButton(text="3"), KeyboardButton(text="4")],
            ],
            resize_keyboard=True
        )
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Anketalary gör")],
            [KeyboardButton(text="1"), KeyboardButton(text="2"), KeyboardButton(text="3"), KeyboardButton(text="4")],
        ],
        resize_keyboard=True
    )

def reaction_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="❤️⭐"),
                KeyboardButton(text="❤️"),
                KeyboardButton(text="✉️"),
                KeyboardButton(text="👎"),
                KeyboardButton(text="💤"),
            ]
        ],
        resize_keyboard=True
    )

def profile_menu(lang: str = "tm"):
    t = TEXTS.get(lang, TEXTS["tm"])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["edit"], callback_data="edit_profile")],
        [InlineKeyboardButton(text=t["delete"], callback_data="delete_profile")],
        [InlineKeyboardButton(text="🏠 " + t["menu"], callback_data="menu")],
    ])

router = Router()

def show_main_menu(lang: str = "tm"):
    if lang == "ru":
        text = (
            "1. Смотреть анкеты.\n"
            "2. Моя анкета.\n"
            "3. Я больше не хочу никого искать.\n"
            "***\n"
            "4. Активируй Premium — будь в топе ⭐."
        )
    else:
        text = (
            "1. Anketalary gör.\n"
            "2. Meniň anketam.\n"
            "3. Men indi hiç kimi gözlemeýärin.\n"
            "***\n"
            "4. Premium işjeňleşdir — ýokarda bol ⭐."
        )
    return text

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    if user_id in users:
        lang = users[user_id].get("lang", "tm")
        await message.answer(show_main_menu(lang), reply_markup=reply_menu(lang))
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇹🇲 Türkmençe", callback_data="lang_tm")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
    ])
    await message.answer("Dil saýla / Выбери язык:", reply_markup=kb)
    await state.set_state(Form.lang)

@router.callback_query(Form.lang, F.data.startswith("lang_"))
async def set_lang(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    await state.update_data(lang=lang)
    t = get_text(lang, "gender")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Oglan / Парень", callback_data="g_male")],
        [InlineKeyboardButton(text="👩 Gyz / Девушка", callback_data="g_female")],
    ])
    await callback.message.edit_text(t, reply_markup=kb)
    await state.set_state(Form.gender)
    await callback.answer()

@router.callback_query(Form.gender, F.data.startswith("g_"))
async def process_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.split("_")[1]
    await state.update_data(gender=gender)
    data = await state.get_data()
    await callback.message.edit_text(get_text(data["lang"], "name"))
    await state.set_state(Form.name)
    await callback.answer()

@router.message(Form.name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()[:32]
    if len(name) < 2:
        await message.answer("Слишком коротко / Gysga")
        return
    await state.update_data(name=name)
    data = await state.get_data()
    await message.answer(get_text(data["lang"], "age"))
    await state.set_state(Form.age)

@router.message(Form.age)
async def process_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Только число / Diňe san")
        return
    age = int(message.text)
    if not 18 <= age <= 60:
        await message.answer("18-60")
        return
    await state.update_data(age=age)
    data = await state.get_data()
    await message.answer(get_text(data["lang"], "city"))
    await state.set_state(Form.city)

@router.message(Form.city)
async def process_city(message: Message, state: FSMContext):
    city_raw = message.text.strip()[:40]
    city_norm = normalize_city(city_raw)
    await state.update_data(city=city_raw, city_norm=city_norm)
    data = await state.get_data()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Oglanlary / Парней", callback_data="l_male")],
        [InlineKeyboardButton(text="👩 Gyzlary / Девушек", callback_data="l_female")],
        [InlineKeyboardButton(text="💑 Любой / Tapawudy ýok", callback_data="l_any")],
    ])
    await message.answer(get_text(data["lang"], "looking"), reply_markup=kb)
    await state.set_state(Form.looking)

@router.callback_query(Form.looking, F.data.startswith("l_"))
async def process_looking(callback: CallbackQuery, state: FSMContext):
    looking = callback.data.split("_")[1]
    await state.update_data(looking=looking)
    data = await state.get_data()
    await callback.message.edit_text(get_text(data["lang"], "about"))
    await state.set_state(Form.about)
    await callback.answer()

@router.message(Form.about)
async def process_about(message: Message, state: FSMContext):
    about = message.text.strip()[:350]
    await state.update_data(about=about, photos=[])
    data = await state.get_data()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(data["lang"], "ready"), callback_data="photos_done")]
    ])
    await message.answer(get_text(data["lang"], "photo"), reply_markup=kb)
    await state.set_state(Form.photo)

@router.message(Form.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos: List[str] = data.get("photos", [])
    if len(photos) >= 3:
        await message.answer("Максимум 3 фото / 3 surat")
        return
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(f"Фото {len(photos)}/3 добавлено. Ещё или «Готово».")

@router.callback_query(Form.photo, F.data == "photos_done")
async def photos_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    if not photos:
        await callback.answer("Отправь хотя бы одно фото", show_alert=True)
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
    caption = (
        f"{get_text(lang, 'profile_ready')}\n\n"
        f"<b>{data['name']}, {data['age']}</b>\n"
        f"📍 {data['city']}\n"
        f"{data['about']}"
    )
    await callback.message.answer_photo(photos[0], caption=caption, parse_mode="HTML", reply_markup=reply_menu(lang))
    await callback.answer()

@router.message(Form.photo)
async def wrong_photo(message: Message):
    await message.answer("Отправь фото / Surat iber")

@router.callback_query(F.data == "browse")
async def browse(callback: CallbackQuery):
    me = users.get(callback.from_user.id)
    if not me:
        await callback.answer("Сначала создай анкету", show_alert=True)
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
        lang = me.get("lang", "tm")
        await callback.message.answer(get_text(lang, "no_profiles"), reply_markup=reply_menu(lang))
        await callback.answer()
        return

    profile = random.choice(candidates)
    lang = me.get("lang", "tm")
    caption = (
        f"<b>{profile['name']}, {profile['age']}</b>\n"
        f"📍 {profile['city']}\n\n"
        f"{profile['about']}"
    )
    await callback.message.answer_photo(
        profile["photos"][0],
        caption=caption,
        parse_mode="HTML",
        reply_markup=reaction_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("like_"))
async def process_like(callback: CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    my_id = callback.from_user.id
    likes.setdefault(my_id, set()).add(target_id)
    save_data()

    me = users.get(my_id)
    if not me:
        await callback.answer()
        return

    # Уведомление тому, кого лайкнули
    try:
        target = users.get(target_id)
        if target:
            lang = target.get("lang", "tm")
            text = f"❤️ Seni like basdy: {me['name']}, {me['age']} ({me['city']})" if lang == "tm" else f"❤️ Тебя лайкнул: {me['name']}, {me['age']} ({me['city']})"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❤️ Like yzyna / Лайк в ответ", callback_data=f"like_{my_id}")],
                [InlineKeyboardButton(text="👀 Anketany gör / Посмотреть", callback_data=f"view_{my_id}")],
            ])
            await callback.bot.send_message(target_id, text, reply_markup=kb)
    except Exception:
        pass

    # Взаимный лайк
    if my_id in likes.get(target_id, set()):
        matches.setdefault(my_id, set()).add(target_id)
        matches.setdefault(target_id, set()).add(my_id)
        save_data()
        await callback.answer("Взаимный лайк! 🔥", show_alert=True)
        try:
            await callback.bot.send_message(
                target_id,
                f"🔥 Özara like! {me['name']} seni halady.\nНапиши ему/ей в личку или через бота."
            )
            await callback.message.answer(f"🔥 Взаимный лайк с {users[target_id]['name']}! Можешь написать.")
        except Exception:
            pass
    else:
        await callback.answer("Лайк отправлен ❤️")

    await browse(callback)

@router.callback_query(F.data == "who_liked")
async def who_liked(callback: CallbackQuery):
    my_id = callback.from_user.id
    me = users.get(my_id)
    if not me:
        await callback.answer("Сначала создай анкету", show_alert=True)
        return

    who = []
    for uid, liked_set in likes.items():
        if my_id in liked_set and uid != my_id:
            if uid in users:
                who.append(users[uid])

    lang = me.get("lang", "tm")
    if not who:
        text = "Häzirlikçe seni hiç kim like basmady 😔" if lang == "tm" else "Пока никто тебя не лайкнул 😔"
        await callback.message.answer(text, reply_markup=reply_menu(lang))
        await callback.answer()
        return

    for p in who[:10]:
        caption = f"<b>{p['name']}, {p['age']}</b>\n📍 {p['city']}\n\n{p['about']}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❤️ Like yzyna / Лайк в ответ", callback_data=f"like_{p['id']}")],
        ])
        await callback.message.answer_photo(p["photos"][0], caption=caption, parse_mode="HTML", reply_markup=kb)

    await callback.answer()

@router.message(F.text.in_({"🚀 Смотреть анкеты", "🚀 Anketalary gör", "1"}))
async def browse_text(message: Message):
    class FakeCallback:
        def __init__(self, msg):
            self.from_user = msg.from_user
            self.message = msg
            self.data = "browse"
            self.bot = msg.bot
        async def answer(self, *a, **k):
            pass
    await browse(FakeCallback(message))

@router.message(F.text == "2")
async def my_profile_text(message: Message):
    class FakeCallback:
        def __init__(self, msg):
            self.from_user = msg.from_user
            self.message = msg
            self.data = "my_profile"
            self.bot = msg.bot
        async def answer(self, *a, **k):
            pass
    await my_profile(FakeCallback(message))

@router.message(F.text.in_({"❤️", "❤️⭐"}))
async def like_reaction(message: Message):
    # упрощённо — лайк последнему показанному (нужно хранить current profile)
    await message.answer("Лайк отправлен ❤️", reply_markup=reaction_keyboard())

@router.message(F.text == "👎")
async def dislike_reaction(message: Message):
    class FakeCallback:
        def __init__(self, msg):
            self.from_user = msg.from_user
            self.message = msg
            self.data = "browse"
            self.bot = msg.bot
        async def answer(self, *a, **k):
            pass
    await browse(FakeCallback(message))

@router.message(F.text == "3")
async def stop_searching(message: Message):
    user_id = message.from_user.id
    lang = users.get(user_id, {}).get("lang", "tm")
    users.pop(user_id, None)
    likes.pop(user_id, None)
    matches.pop(user_id, None)
    save_data()
    text = "Anketa pozuldy. /start basyp täzeden döredip bilersiň." if lang == "tm" else "Анкета удалена. Напиши /start чтобы создать заново."
    await message.answer(text)

@router.callback_query(F.data == "my_profile")
async def my_profile(callback: CallbackQuery):
    user = users.get(callback.from_user.id)
    if not user:
        await callback.answer("Анкета не найдена", show_alert=True)
        return
    lang = user.get("lang", "tm")
    looking_map = {"male": "Парней / Oglanlary", "female": "Девушек / Gyzlary", "any": "Любой"}
    caption = (
        f"<b>{user['name']}, {user['age']}</b>\n"
        f"📍 {user['city']}\n"
        f"🔍 {looking_map.get(user['looking'], '—')}\n\n"
        f"{user['about']}\n\n"
        f"Фото: {len(user['photos'])}\n"
        f"Premium: {'✅' if user.get('premium') else '❌'}"
    )
    await callback.message.answer_photo(user["photos"][0], caption=caption, parse_mode="HTML", reply_markup=profile_menu(lang))
    await callback.answer()

@router.callback_query(F.data == "edit_profile")
async def edit_profile(callback: CallbackQuery, state: FSMContext):
    user = users.get(callback.from_user.id, {})
    lang = user.get("lang", "tm")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Oglan / Парень", callback_data="g_male")],
        [InlineKeyboardButton(text="👩 Gyz / Девушка", callback_data="g_female")],
    ])
    await callback.message.answer(get_text(lang, "gender"), reply_markup=kb)
    await state.update_data(lang=lang)
    await state.set_state(Form.gender)
    await callback.answer()

@router.callback_query(F.data == "delete_profile")
async def delete_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = users.get(user_id, {}).get("lang", "tm")
    users.pop(user_id, None)
    likes.pop(user_id, None)
    matches.pop(user_id, None)
    save_data()
    await callback.message.answer(get_text(lang, "deleted"))
    await callback.answer()

@router.callback_query(F.data == "premium")
async def buy_premium(callback: CallbackQuery):
    await callback.message.answer_invoice(
        title="Premium",
        description="Безлимитные лайки",
        payload="premium_7d",
        currency="XTR",
        prices=[LabeledPrice(label="Premium", amount=49)],
    )
    await callback.answer()

@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment(message: Message):
    user_id = message.from_user.id
    if user_id in users:
        users[user_id]["premium"] = True
    await message.answer("⭐ Premium активирован!", reply_markup=reply_menu(users[user_id].get("lang", "tm")))

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
