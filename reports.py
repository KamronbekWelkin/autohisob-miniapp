def format_period_report(period: dict, totals: dict, closed: bool = False) -> str:
    start = period["start_date"]
    end = period["end_date"]
    opening = int(period.get("opening_stock_cost") or 0)
    closing = period.get("closing_stock_cost", None)

    cash = int(totals.get("cash", 0))
    card = int(totals.get("card", 0))
    sales = cash + card
    purchases = int(totals.get("purchases", 0))
    expenses = int(totals.get("expenses", 0))

    # Agar davr yopilmagan bo'lsa va yakuniy ombor yo'q bo'lsa
    if (not closed) and (closing is None):
        return (
            f"📊 *Joriy 15 kunlik hisobot*\n"
            f"📅 Davr: *{start} → {end}*\n\n"
            f"💰 Savdo: *{sales:,} so‘m*\n"
            f"├ Naqd: {cash:,} so‘m\n"
            f"└ Karta: {card:,} so‘m\n\n"
            f"📦 Kirim (tannarx): *{purchases:,} so‘m*\n"
            f"🧾 Chiqim: *{expenses:,} so‘m*\n\n"
            f"🧮 Ombor (tannarx):\n"
            f"├ Boshlang‘ich: {opening:,} so‘m\n"
            f"└ Yakuniy: kiritilmagan\n\n"
            f"✅ Yakuniy ombor tannarxi kiritilgach foyda avtomatik hisoblanadi."
        )

    closing = int(closing or 0)
    cogs = opening + purchases - closing
    gross = sales - cogs
    net = gross - expenses

    return (
        f"📊 *15 kunlik yakuniy hisobot*\n"
        f"📅 Davr: *{start} → {end}*\n\n"
        f"💰 Savdo: *{sales:,} so‘m*\n"
        f"├ Naqd: {cash:,} so‘m\n"
        f"└ Karta: {card:,} so‘m\n\n"
        f"📦 Kirim (tannarx): *{purchases:,} so‘m*\n"
        f"🧾 Chiqim: *{expenses:,} so‘m*\n\n"
        f"🧮 Ombor (tannarx):\n"
        f"├ Boshlang‘ich: {opening:,} so‘m\n"
        f"└ Yakuniy: {closing:,} so‘m\n\n"
        f"📉 COGS (sotilgan tovar tannarxi): *{cogs:,} so‘m*\n"
        f"📈 Gross foyda: *{gross:,} so‘m*\n"
        f"✅ Sof foyda/zarar: *{net:,} so‘m*"
    )
