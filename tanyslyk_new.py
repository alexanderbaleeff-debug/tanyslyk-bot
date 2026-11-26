import asyncio
import logging
import os
import random
from typing import Dict, Any

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

# Хранилище (потом лучше заменить на SQLite)
users: Dict[int, Dict[str, Any]] = {}
likes: Dict[int, set] = {}
matches: Dict[int, set] = {}

class Form(StatesGroup):
    gender = State()
    name = State()
    age = State()
    city = State()
    looking = State()
    about = State()
    photo = State()

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Anketalary gör", callback_data="browse")],
        [InlineKeyboardButton(text="📝 Meniň anketam", callback_data="my_profile")],
        [InlineKeyboardButton(text="⭐ Premium", callback_data="premium")],
    ])

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    name = message.from_user.first_name or "dost"

    if user_id not in users:
        text = (
            "Salam! 👋\n"
            "«Tanyşlyk» botuna hoş geldiňiz! ❤️\n\n"
            "Bu ýerde sen:\n"
            "✨ Öz şäheriňden täze dostlary we bagtyňy tapyp bilersiň\n"
            "📸 Öz anketaňy döredip, suratlaryňy paýlaşyp bilersiň\n"
            "❤️ Halan adamlaryňa like basyp, tanyşyp bilersiň\n\n"
            "Başlamak üçin jynsyňy saýla:"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👨 Oglan", callback_data="g_male")],
            [InlineKeyboardButton(text="👩 Gyz", callback_data="g_female")],
        ])
        await message.answer(text, reply_markup=kb)
        await state.set_state(Form.gender)
    else:
        await message.answer(f"Hoş geldiňiz, {name}! 🔥", reply_markup=main_menu())

@router.callback_query(Form.gender, F.data.startswith("g_"))
async def process_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.split("_")[1]
    await state.update_data(gender=gender)
    await callback.message.edit_text("Adyň näme? Ýaz:")
    await state.set_state(Form.name)
    await callback.answer()

@router.message(Form.name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()[:32]
    if len(name) < 2:
        await message.answer("Ady gysga. Täzeden ýaz:")
        return
    await state.update_data(name=name)
    await message.answer("Näçe ýaşyň? (18-60)")
    await state.set_state(Form.age)

@router.message(Form.age)
async def process_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("San bilen ýaz:")
        return
    age = int(message.text)
    if not 18 <= age <= 60:
        await message.answer("18-den 60-a çenli bolmaly:")
        return
    await state.update_data(age=age)
    await message.answer("Haýsy şäherden?")
    await state.set_state(Form.city)

@router.message(Form.city)
async def process_city(message: Message, state: FSMContext):
    city = message.text.strip()[:40]
    await state.update_data(city=city)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Oglanlary", callback_data="l_male")],
        [InlineKeyboardButton(text="👩 Gyzlary", callback_data="l_female")],
        [InlineKeyboardButton(text="💑 Tapawudy ýok", callback_data="l_any")],
    ])
    await message.answer("Kimi gözleýärsiň?", reply_markup=kb)
    await state.set_state(Form.looking)

@router.callback_query(Form.looking, F.data.startswith("l_"))
async def process_looking(callback: CallbackQuery, state: FSMContext):
    looking = callback.data.split("_")[1]
    await state.update_data(looking=looking)
    await callback.message.edit_text("Özüň barada gysgaça ýaz (2-3 setir):")
    await state.set_state(Form.about)
    await callback.answer()

@router.message(Form.about)
async def process_about(message: Message, state: FSMContext):
    about = message.text.strip()[:350]
    await state.update_data(about=about)
    await message.answer("Iň gowy suratyňy iber 📸")
    await state.set_state(Form.photo)

@router.message(Form.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id

    users[user_id] = {
        "id": user_id,
        "name": data["name"],
        "age": data["age"],
        "gender": data["gender"],
        "city": data["city"],
        "looking": data["looking"],
        "about": data["about"],
        "photo": message.photo[-1].file_id,
        "premium": False,
    }
    likes.setdefault(user_id, set())
    matches.setdefault(user_id, set())

    await state.clear()
    caption = (
        f"✅ Anketa taýýar!\n\n"
        f"<b>{data['name']}, {data['age']}</b>\n"
        f"📍 {data['city']}\n"
        f"{data['about']}"
    )
    await message.answer_photo(
        message.photo[-1].file_id,
        caption=caption,
        parse_mode="HTML",
        reply_markup=main_menu()
    )

@router.message(Form.photo)
async def wrong_photo(message: Message):
    await message.answer("Surat iber, tekst däl.")

@router.callback_query(F.data == "browse")
async def browse(callback: CallbackQuery):
    me = users.get(callback.from_user.id)
    if not me:
        await callback.answer("Ilki anketa döret", show_alert=True)
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
        await callback.message.answer(
            "Häzirlikçe täze anketa ýok 😔\nSoňrak gel ýa-da dostlaryňy çagyr!",
            reply_markup=main_menu()
        )
        await callback.answer()
        return

    profile = random.choice(candidates)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ Like", callback_data=f"like_{profile['id']}"),
            InlineKeyboardButton(text="👎 Geç", callback_data="browse"),
        ],
        [InlineKeyboardButton(text="🏠 Menýu", callback_data="menu")]
    ])
    caption = (
        f"<b>{profile['name']}, {profile['age']}</b>\n"
        f"📍 {profile['city']}\n\n"
        f"{profile['about']}"
    )
    await callback.message.answer_photo(
        profile["photo"],
        caption=caption,
        parse_mode="HTML",
        reply_markup=kb
    )
    await callback.answer()

@router.callback_query(F.data.startswith("like_"))
async def process_like(callback: CallbackQuery):
    target_id = int(callback.data.split("_")[1])
    my_id = callback.from_user.id

    likes.setdefault(my_id, set()).add(target_id)

    if my_id in likes.get(target_id, set()):
        matches.setdefault(my_id, set()).add(target_id)
        matches.setdefault(target_id, set()).add(my_id)
        await callback.answer("Bu özara like! 🔥", show_alert=True)
        try:
            me = users.get(my_id)
            await callback.bot.send_message(
                target_id,
                f"🔥 Özara like! {me['name']} seni halady."
            )
        except Exception:
            pass
    else:
        await callback.answer("Like iberildi ❤️")

    await browse(callback)

@router.callback_query(F.data == "menu")
async def to_menu(callback: CallbackQuery):
    await callback.message.answer("Esasy menýu:", reply_markup=main_menu())
    await callback.answer()

@router.callback_query(F.data == "my_profile")
async def my_profile(callback: CallbackQuery):
    user = users.get(callback.from_user.id)
    if not user:
        await callback.answer("Anketa ýok", show_alert=True)
        return
    caption = (
        f"<b>{user['name']}, {user['age']}</b>\n"
        f"📍 {user['city']}\n"
        f"{user['about']}\n\n"
        f"Premium: {'✅' if user.get('premium') else '❌'}"
    )
    await callback.message.answer_photo(
        user["photo"],
        caption=caption,
        parse_mode="HTML",
        reply_markup=main_menu()
    )
    await callback.answer()

@router.callback_query(F.data == "premium")
async def buy_premium(callback: CallbackQuery):
    await callback.message.answer_invoice(
        title="Premium",
        description="Çäksiz like we köp görnüş",
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
    await message.answer("⭐ Premium işjeňleşdi!", reply_markup=main_menu())

async def main():
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
            print("Webhook started on port", os.getenv("PORT", 10000))
            await asyncio.Event().wait()
        else:
            await bot.delete_webhook(drop_pending_updates=True)
            print("Bot işledi (polling)...")
            await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
