import os
import asyncio
import logging
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from db import (
    db_init,
    get_or_create_user,
    get_open_period,
    create_period,
    set_opening_stock,
    add_sale,
    add_expense,
    add_purchase,
    close_period,
    period_totals,
    get_reminder,
)
from keyboards import main_menu_kb
from states import StartState, SaleState, ExpenseState, PurchaseState, CloseState
from reports import format_period_report

logging.basicConfig(level=logging.INFO)

TZ = ZoneInfo("Asia/Tashkent")

def tg_today(dt) -> date:
    # Telegramdan keladigan datetime (UTC) -> Toshkent sanasi
    return dt.astimezone(TZ).date()

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ALLOWED_ID = os.getenv("ALLOWED_TELEGRAM_ID", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi. .env faylni tekshiring!")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

def is_allowed(user_id: int) -> bool:
    if not ALLOWED_ID:
        return True
    return str(user_id) == ALLOWED_ID


# -------------------- HANDLERS --------------------

@dp.message(CommandStart())
async def start(m: Message, state: FSMContext):
    if not is_allowed(m.from_user.id):
        return await m.answer("Kechirasiz, bu bot faqat egasi uchun.")

    await get_or_create_user(m.from_user.id)

    p = await get_open_period(m.from_user.id)
    if p:
        await m.answer("Bosh menyu:", reply_markup=main_menu_kb())
        return

    await m.answer(
        "Assalomu alaykum! 😊\n"
        "Boshlash uchun hozirgi ombordagi tovarning **boshlang‘ich tannarxini** kiriting (so‘m).\n"
        "Agar ombor bo‘sh bo‘lsa, 0 deb yozing.",
        parse_mode="Markdown",
    )
    await state.set_state(StartState.opening_stock)


@dp.message(StartState.opening_stock)
async def set_opening(m: Message, state: FSMContext):
    if not is_allowed(m.from_user.id):
        return

    try:
        opening = int(m.text.replace(" ", ""))
        if opening < 0:
            raise ValueError
    except:
        return await m.answer("Iltimos, musbat son kiriting. Masalan: 5000000 yoki 0")

    today = tg_today(m.date)
    end = today + timedelta(days=14)

    period_id = await create_period(m.from_user.id, today.isoformat(), end.isoformat())
    await set_opening_stock(period_id, opening)

    await state.clear()
    await m.answer(
        f"✅ Saqlandi.\n📅 Yangi 15 kunlik davr: **{today.isoformat()} → {end.isoformat()}**",
        parse_mode="Markdown",
    )
    await m.answer("Bosh menyu:", reply_markup=main_menu_kb())


# --- SAVDO ---
@dp.callback_query(F.data == "sale")
async def sale_start(c: CallbackQuery, state: FSMContext):
    if not is_allowed(c.from_user.id):
        await c.answer("Ruxsat yo‘q", show_alert=True)
        return
    await c.message.answer("💰 Savdo kiritish.\nBugungi naqd savdo (so‘m)?")
    await state.set_state(SaleState.cash)
    await c.answer()


@dp.message(SaleState.cash)
async def sale_cash(m: Message, state: FSMContext):
    if not is_allowed(m.from_user.id):
        return

    try:
        cash = int(m.text.replace(" ", ""))
        if cash < 0:
            raise ValueError
    except:
        return await m.answer("Son kiriting. Masalan: 1200000")

    await state.update_data(cash=cash)
    await m.answer("💳 Karta savdo (so‘m)?")
    await state.set_state(SaleState.card)


@dp.message(SaleState.card)
async def sale_card(m: Message, state: FSMContext):
    if not is_allowed(m.from_user.id):
        return

    try:
        card = int(m.text.replace(" ", ""))
        if card < 0:
            raise ValueError
    except:
        return await m.answer("Son kiriting. Masalan: 800000")

    data = await state.get_data()
    cash = data["cash"]

    p = await get_open_period(m.from_user.id)
    if not p:
        await state.clear()
        return await m.answer("Ochiq 15 kunlik davr topilmadi. /start bosing.")

    d = tg_today(m.date).isoformat()
    await add_sale(m.from_user.id, p["id"], d, cash, card)

    await state.clear()
    await m.answer(
        f"✅ Saqlandi.\nNaqd: {cash}\nKarta: {card}\nJami: {cash + card}",
        reply_markup=main_menu_kb(),
    )


# --- CHIQIM ---
@dp.callback_query(F.data == "expense")
async def expense_start(c: CallbackQuery, state: FSMContext):
    if not is_allowed(c.from_user.id):
        await c.answer("Ruxsat yo‘q", show_alert=True)
        return
    await c.message.answer("🧾 Chiqim summasi (so‘m)?")
    await state.set_state(ExpenseState.amount)
    await c.answer()


@dp.message(ExpenseState.amount)
async def expense_amount(m: Message, state: FSMContext):
    if not is_allowed(m.from_user.id):
        return

    try:
        amount = int(m.text.replace(" ", ""))
        if amount < 0:
            raise ValueError
    except:
        return await m.answer("Son kiriting. Masalan: 200000")

    await state.update_data(amount=amount)
    await m.answer("✍️ Sabab (ixtiyoriy). Yozmasangiz '-' deb yuboring.")
    await state.set_state(ExpenseState.note)


@dp.message(ExpenseState.note)
async def expense_note(m: Message, state: FSMContext):
    if not is_allowed(m.from_user.id):
        return

    data = await state.get_data()
    amount = data["amount"]
    note = m.text.strip()

    p = await get_open_period(m.from_user.id)
    if not p:
        await state.clear()
        return await m.answer("Ochiq 15 kunlik davr topilmadi. /start bosing.")

    d = tg_today(m.date).isoformat()
    await add_expense(m.from_user.id, p["id"], d, amount, note)

    await state.clear()
    await m.answer("✅ Chiqim saqlandi.", reply_markup=main_menu_kb())


# --- KIRIM ---
@dp.callback_query(F.data == "purchase")
async def purchase_start(c: CallbackQuery, state: FSMContext):
    if not is_allowed(c.from_user.id):
        await c.answer("Ruxsat yo‘q", show_alert=True)
        return
    await c.message.answer("➕ Kirim tannarxi (umumiy summa, so‘m)?")
    await state.set_state(PurchaseState.amount)
    await c.answer()


@dp.message(PurchaseState.amount)
async def purchase_amount(m: Message, state: FSMContext):
    if not is_allowed(m.from_user.id):
        return

    try:
        amount = int(m.text.replace(" ", ""))
        if amount < 0:
            raise ValueError
    except:
        return await m.answer("Son kiriting. Masalan: 3500000")

    await state.update_data(amount=amount)
    await m.answer("✍️ Izoh (ixtiyoriy). Yozmasangiz '-' deb yuboring.")
    await state.set_state(PurchaseState.note)


@dp.message(PurchaseState.note)
async def purchase_note(m: Message, state: FSMContext):
    if not is_allowed(m.from_user.id):
        return

    data = await state.get_data()
    amount = data["amount"]
    note = m.text.strip()

    p = await get_open_period(m.from_user.id)
    if not p:
        await state.clear()
        return await m.answer("Ochiq 15 kunlik davr topilmadi. /start bosing.")

    d = tg_today(m.date).isoformat()
    await add_purchase(m.from_user.id, p["id"], d, amount, note)

    await state.clear()
    await m.answer("✅ Kirim saqlandi.", reply_markup=main_menu_kb())


# --- HISOBOT ---
@dp.callback_query(F.data == "report")
async def report(c: CallbackQuery):
    if not is_allowed(c.from_user.id):
        await c.answer("Ruxsat yo‘q", show_alert=True)
        return

    p = await get_open_period(c.from_user.id)
    if not p:
        await c.message.answer("Ochiq davr yo‘q. /start bosing.")
        return await c.answer()

    totals = await period_totals(c.from_user.id, p["id"])
    text = format_period_report(p, totals, closed=False)
    await c.message.answer(text, parse_mode="Markdown")
    await c.answer()


# --- 15 KUNNI YOPISH ---
@dp.callback_query(F.data == "close")
async def close_start(c: CallbackQuery, state: FSMContext):
    if not is_allowed(c.from_user.id):
        await c.answer("Ruxsat yo‘q", show_alert=True)
        return

    await c.message.answer(
        "✅ 15 kunni yopish.\nOmborda qolgan tovarning **yakuniy tannarxini** kiriting (so‘m).",
        parse_mode="Markdown",
    )
    await state.set_state(CloseState.closing_stock)
    await c.answer()


@dp.message(CloseState.closing_stock)
async def close_finish(m: Message, state: FSMContext):
    if not is_allowed(m.from_user.id):
        return

    try:
        closing = int(m.text.replace(" ", ""))
        if closing < 0:
            raise ValueError
    except:
        return await m.answer("Son kiriting. Masalan: 7200000")

    p = await get_open_period(m.from_user.id)
    if not p:
        await state.clear()
        return await m.answer("Ochiq davr topilmadi. /start bosing.")

    await close_period(p["id"], closing)
    totals = await period_totals(m.from_user.id, p["id"])

    p_closed = {**p, "closing_stock_cost": closing, "is_closed": 1}
    text = format_period_report(p_closed, totals, closed=True)

    # yangi davr: oldingi end_date + 1 kundan
    end = datetime.fromisoformat(p["end_date"]).date()
    new_start = end + timedelta(days=1)
    new_end = new_start + timedelta(days=14)

    new_period_id = await create_period(m.from_user.id, new_start.isoformat(), new_end.isoformat())
    await set_opening_stock(new_period_id, closing)

    await state.clear()
    await m.answer(text, parse_mode="Markdown")
    await m.answer(
        f"📅 Yangi 15 kunlik davr ochildi: {new_start.isoformat()} → {new_end.isoformat()}",
        reply_markup=main_menu_kb(),
    )


# -------------------- REMINDER --------------------

async def send_daily_reminder():
    if not ALLOWED_ID:
        return

    rid = int(ALLOWED_ID)

    r = await get_reminder(rid)
    if r.get("enabled", 1) != 1:
        return

    today = datetime.now(tz=TZ).date()

    p = await get_open_period(rid)
    if not p:
        await bot.send_message(
            rid,
            "⏰ Eslatma: botda ochiq 15 kunlik davr yo‘q.\n/start bosing va boshlang‘ich tannarxni kiriting."
        )
        return

    end_date = datetime.fromisoformat(p["end_date"]).date()

    if today >= end_date:
        await bot.send_message(
            rid,
            f"📌 15 kunlik davr tugadi!\n"
            f"📅 Davr: {p['start_date']} → {p['end_date']}\n\n"
            f"✅ Iltimos, *15 kunni yopish* tugmasini bosib,\n"
            f"omborda qolgan tovarning yakuniy tannarxini kiriting.\n"
            f"Shundan keyin foyda/zarar avtomatik hisoblanadi.",
            parse_mode="Markdown",
        )
    else:
        await bot.send_message(
            rid,
            "⏰ Eslatma: bugungi savdo/chiqim/kirimni kiritdingizmi?\n"
            "✅ Menyudan: Savdo kiritish / Chiqim kiritish / Kirim kiritish"
        )


@dp.message(F.text == "/test_reminder")
async def test_reminder(m: Message):
    if not is_allowed(m.from_user.id):
        return
    await send_daily_reminder()
    await m.answer("✅ Test eslatma yuborildi.")


# -------------------- MAIN --------------------

async def main():
    print("BOT: start bo'ldi")
    await db_init()
    print("BOT: polling boshlandi")

    scheduler = AsyncIOScheduler(timezone=TZ)

    # 21:00 Toshkent bo'yicha
    if ALLOWED_ID:
        rid = int(ALLOWED_ID)
        r = await get_reminder(rid)
        if r.get("enabled", 1) == 1:
            scheduler.add_job(
                send_daily_reminder,
                CronTrigger(hour=21, minute=0, timezone=TZ),
                id="daily_reminder",
                replace_existing=True,
            )

    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
