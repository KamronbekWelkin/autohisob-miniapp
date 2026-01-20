from aiogram.utils.keyboard import InlineKeyboardBuilder

def main_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 Savdo kiritish", callback_data="sale")
    kb.button(text="🧾 Chiqim kiritish", callback_data="expense")
    kb.button(text="➕ Kirim kiritish (tovar)", callback_data="purchase")
    kb.button(text="📊 Hisobot", callback_data="report")
    kb.button(text="✅ 15 kunni yopish", callback_data="close")
    kb.adjust(1)
    return kb.as_markup()
